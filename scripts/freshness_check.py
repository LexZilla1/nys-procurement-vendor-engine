#!/usr/bin/env python3
"""
Monthly golden-copy freshness check — NYS Procurement Vendor Engine.

Fetches all 22 STATUTE-CLASS sources (coordinates from
docs/API-REBUILD-PHASE1-CLASSIFICATION.md) from the NY Senate Open Legislation
API v3, diffs each against the current golden-copy STATE TEXT, and classifies
FULL-MATCH / FRAGMENT / DIVERGENT. It also cross-checks the four sunset statutes'
repeal metadata (API `repealed`/`repealedDate` and the in-text `* NB Repealed`
date) against our recorded sunset dates — mismatches are FLAGGED, never
auto-reconciled.

Boundaries (match the Phase-3 methodology):
  * Read-only w.r.t. golden-copy/: this script NEVER edits a source file. Its
    only output is a markdown report under docs/freshness/YYYY-MM-DD.md.
  * Key from env NYSLEG_API_KEY only — never logged, never written.
  * On any API error: stop and report; NO scraping fallback.
  * API text is reflowed to the golden one-line-per-subdivision style BEFORE
    diffing, or the cite() raw-substring comparison would spuriously diverge.

Drift = any DIVERGENT verdict OR any sunset mismatch. The workflow opens a
labeled PR on drift and commits the report only when everything is FULL-MATCH.

Offline test (no key, no network):
    python3 scripts/freshness_check.py --selftest
"""

import argparse
import datetime
import difflib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API_BASE = "https://legislation.nysenate.gov/api/3/laws"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_DIR = os.path.join(REPO_ROOT, "golden-copy", "sources")
REPORT_DIR = os.path.join(REPO_ROOT, "docs", "freshness")
sys.path.insert(0, REPO_ROOT)
from engine import freshness_state as fs  # noqa: E402  (needs REPO_ROOT on path)
# Sanctioned statute-capture registry (scripts/statute_capture.py). Sections
# captured through the manual capture workflow become "freshness-registered"
# here: any target whose golden file EXISTS on disk is merged into the monthly
# check. See load_registry_sources() for the existence guard.
REGISTRY_PATH = os.path.join(REPO_ROOT, "data", "config",
                             "statute_capture_registry.json")

# 22 statute-class coordinates (source file -> lawId/locationId).
STATUTE_SOURCES = {
    "source-exec-314-mwbe-cert-validity.md": ("EXC", "314"),
    "source-lab-220-i-public-work-registration.md": ("LAB", "220-I"),
    "source-stf-109-vendor-certificate.md": ("STF", "109"),
    "source-stf-112.md": ("STF", "112"),
    "source-stf-139-d-noncollusion.md": ("STF", "139-D"),
    "source-stf-139-h-international-boycott.md": ("STF", "139-H"),
    "source-stf-139-j.md": ("STF", "139-J"),
    "source-stf-139-k.md": ("STF", "139-K"),
    "source-stf-139-l-sexual-harassment.md": ("STF", "139-L"),
    "source-stf-139-m-gender-based-violence.md": ("STF", "139-M"),
    "source-stf-163.md": ("STF", "163"),
    "source-stf-179-d.md": ("STF", "179-D"),
    "source-stf-179-e.md": ("STF", "179-E"),
    "source-stf-179-f.md": ("STF", "179-F"),
    "source-stf-179-g.md": ("STF", "179-G"),
    "source-stf-179-p.md": ("STF", "179-P"),
    "source-stf-179-q.md": ("STF", "179-Q"),
    "source-stf-179-s.md": ("STF", "179-S"),
    "source-stf-179-t.md": ("STF", "179-T"),
    "source-stf-179-u.md": ("STF", "179-U"),
    "source-stf-179-v.md": ("STF", "179-V"),
    "source-wkc-57-workers-comp.md": ("WKC", "57"),
}

# stf-109 keeps OSC guidance + form layers in STATE TEXT; compare only its
# statute layer ("### A.") against the API. exc-314 stores the full single-version
# section (post the 2026-07-01 subd. 5 transition), so a normal full-text compare
# is correct.
LAYER_A_ONLY = {"source-stf-109-vendor-certificate.md"}

# Sunset records to defend (our golden dates). Mismatch => flag, never reconcile.
SUNSET_EXPECT = {
    "source-exec-314-mwbe-cert-validity.md": "2028-07-01",
    "source-stf-139-j.md": "2028-07-31",
    "source-stf-139-k.md": "2028-07-31",
    "source-stf-163.md": "2031-06-30",
}

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

MARK = re.compile(
    r'^\s*(\*+\s*)?(\d+(-[a-z])?\.\s|\([0-9a-z]+\)\s|[a-z]\.\s|[ivxlc]+\.\s|§|NB\b)', re.I)


def unescape_api_text(text):
    """Normalize the RAW Open Legislation API `text` field to plain text.

    CONFIRMED LIVE quirk (the bug behind the 22/22 false DIVERGENT): the API's
    JSON `text` value carries *literal* escape sequences — after json.loads the
    string still contains two-character `\\n` / `\\r\\n` / `\\t` runs (and NBSP),
    not real whitespace. The offline echo-back test never exercised this because
    it fed already-clean golden text back as the mock response, so reflow was a
    no-op. Convert those literal escapes to real whitespace BEFORE reflow, or the
    residual `\\n` characters survive normalization and every section diverges.

    Idempotent on already-clean text (golden captures contain no literal escapes),
    so it is safe to run on both live and injected inputs.
    """
    if not text:
        return text or ""
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    text = text.replace("\\t", " ")
    text = text.replace(" ", " ")   # non-breaking space -> normal space
    return text


def reflow(text):
    """Join hard-wrapped API lines into the golden one-line-per-subdivision
    style (words untouched); keep subdivision/annotation markers as line starts.
    Unescapes the raw API text first (see unescape_api_text)."""
    text = unescape_api_text(text)
    out, cur = [], ""
    for ln in text.replace("\r", "").split("\n"):
        s = ln.strip()
        if not s:
            if cur:
                out.append(cur)
                cur = ""
            continue
        if MARK.match(ln) or s.startswith(("*", "§")):
            if cur:
                out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip() if cur else s
    if cur:
        out.append(cur)
    return "\n".join(out)


def norm(s):
    """Whitespace-insensitive, annotation-star-insensitive comparison key.
    Defensively strips any residual literal escape runs too (belt-and-suspenders
    with unescape_api_text), so a stray `\\n` can never reach the comparison."""
    s = unescape_api_text(s)
    s = re.sub(r"[*]+", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def nb_repeal_iso(text):
    """Parse a `* NB Repealed <Month D, YYYY>` date from section text to ISO,
    or None if absent."""
    m = re.search(r"NB Repealed\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", text)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).lower())
    if not mon:
        return None
    return "%04d-%02d-%02d" % (int(m.group(3)), mon, int(m.group(2)))


def stored_state_text(fn, layer_a_only=False):
    raw = open(os.path.join(SOURCES_DIR, fn), encoding="utf-8").read()
    m = re.search(r"^##\s*STATE TEXT[^\n]*\n(.*?)(?=^##\s|\Z)", raw, re.M | re.S)
    body = m.group(1) if m else ""
    body = re.sub(r"\n?-{3,}\s*$", "", body).strip()
    if layer_a_only:
        am = re.search(r"^### A\.[^\n]*\n(.*?)(?=^### B\.)", body, re.M | re.S)
        if am:
            body = am.group(1).strip()
    return body


def classify(stored, live):
    ns, nl = norm(stored), norm(live)
    if not ns:
        return "EMPTY-STORED"
    if ns == nl:
        return "FULL-MATCH"
    if ns in nl:
        return "FRAGMENT"
    if difflib.SequenceMatcher(None, ns, nl).ratio() > 0.985:
        return "FULL-MATCH"
    return "DIVERGENT"


# --------------------------------------------------------------------------
# API fetcher (injectable for offline tests)
# --------------------------------------------------------------------------

def http_fetcher(key):
    def fetch(law_id, location_id):
        params = urllib.parse.urlencode({"key": key})
        url = "%s/%s/%s?%s" % (API_BASE, law_id, location_id, params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload.get("success", False):
            raise RuntimeError("API success=false for %s/%s: %s"
                               % (law_id, location_id, payload.get("message")))
        d = payload.get("result", {})
        return {"text": d.get("text") or "", "activeDate": d.get("activeDate"),
                "repealed": d.get("repealed"), "repealedDate": d.get("repealedDate")}
    return fetch


# --------------------------------------------------------------------------
# Core run
# --------------------------------------------------------------------------

def load_registry_sources(registry_path=None, sources_dir=None):
    """Merge sanctioned statute-capture targets into the freshness source map,
    but ONLY those whose golden file already exists on disk.

    This is the "freshness-registered" hook: a section captured via the manual
    statute-capture workflow joins the monthly check automatically once its
    golden file is merged. A target declared in the registry BEFORE its golden
    file exists (a pending capture) is skipped, so the registry can never break
    the live run. Returns {source_file: (lawId, locationId)}.
    """
    registry_path = registry_path or REGISTRY_PATH
    sources_dir = sources_dir or SOURCES_DIR
    try:
        with open(registry_path, encoding="utf-8") as fh:
            reg = json.load(fh)
    except (OSError, ValueError):
        return {}
    out = {}
    for coord, spec in (reg.get("targets") or {}).items():
        fn = (spec or {}).get("file")
        if not fn or "/" not in coord:
            continue
        if not os.path.exists(os.path.join(sources_dir, fn)):
            continue  # existence guard: pending capture, not yet golden
        law, loc = coord.split("/", 1)
        out[fn] = (law, loc)
    return out


def all_sources():
    """Base 22 statute-class sources plus any freshness-registered captures
    whose golden file exists (existence-guarded merge)."""
    return {**STATUTE_SOURCES, **load_registry_sources()}


def run(fetch, sources=None):
    sources = sources or STATUTE_SOURCES
    results = []
    for fn, (law, loc) in sorted(sources.items()):
        try:
            live = fetch(law, loc)
        except Exception as exc:  # API error => stop, no scraping fallback
            raise SystemExit("FATAL: API fetch failed for %s/%s: %s "
                             "(stopping; no fallback)." % (law, loc, exc))
        live_text = reflow(live.get("text", ""))
        stored = stored_state_text(fn, layer_a_only=(fn in LAYER_A_ONLY))
        verdict = classify(stored, live_text)
        row = {"file": fn, "law": law, "loc": loc, "verdict": verdict,
               "activeDate": live.get("activeDate"),
               "repealed": live.get("repealed"),
               "repealedDate": live.get("repealedDate"),
               "sunset_flags": []}
        # sunset cross-check. Bind every API field via .get() with a safe
        # default first — the Open Legislation API omits repealed/repealedDate
        # on some sections (confirmed live: a direct d["repealed"] KeyErrors).
        exp = SUNSET_EXPECT.get(fn)
        if exp is not None:
            nb = nb_repeal_iso(live_text)
            repealed = live.get("repealed")
            repealed_date = live.get("repealedDate")
            if repealed is True:
                row["sunset_flags"].append("API reports section ALREADY repealed")
            if repealed_date and repealed_date != exp:
                row["sunset_flags"].append(
                    "API repealedDate %s != record %s" % (repealed_date, exp))
            if nb and nb != exp:
                row["sunset_flags"].append(
                    "in-text NB Repealed %s != record %s" % (nb, exp))
            if nb is None and not repealed_date:
                row["sunset_flags"].append(
                    "no NB-repeal date found in live text (record expects %s)" % exp)
        results.append(row)
    return results


def has_drift(results):
    return any(r["verdict"] == "DIVERGENT" or r["sunset_flags"] for r in results)


def results_to_state(results, date_str):
    """Convert a run()'s per-source results into the engine freshness-state shape
    {source_file: {verdict, checked_date, detail}} that engine/freshness_state.py
    reads. Only the audited (statute-class) sources appear; every other golden
    source is absent -> citable, exactly today's behavior."""
    sources = {}
    for r in results:
        detail = "; ".join(r.get("sunset_flags") or []) or "live audit"
        sources[r["file"]] = {"verdict": r["verdict"], "checked_date": date_str,
                              "detail": detail}
    return {"generated": date_str,
            "note": "Live freshness run via scripts/freshness_check.py --write-state.",
            "sources": sources}


def _read_state_json(path):
    """Read an existing freshness-state JSON, or {} if absent/unreadable. Used
    only to compare the PREVIOUS committed state against a fresh run (offline)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def material_state_change(old, new):
    """True iff `new` is a MATERIAL change vs the previously-committed `old` state:
      * `old` is the checked-in SEED placeholder (the first real run always
        replaces it), OR
      * a source was added or removed, OR
      * a source's VERDICT CLASS changed (FULL-MATCH / FRAGMENT / EMPTY-STORED /
        UNREACHABLE / DIVERGENT).
    A run that changes ONLY non-verdict bytes (checked_date, detail text) is NOT
    material -> no PR, no noise. Verdict strings ARE the classes, so comparing the
    per-source `verdict` directly is the class comparison. This decides whether the
    Action opens a human-reviewed state-update PR; it never merges anything."""
    if "SEED" in (old.get("note") or ""):
        return True
    old_s, new_s = old.get("sources", {}), new.get("sources", {})
    if set(old_s) != set(new_s):
        return True
    for fn, rec in new_s.items():
        if rec.get("verdict") != old_s.get(fn, {}).get("verdict"):
            return True
    return False


def render_report(results, date_str):
    drift = has_drift(results)
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    flagged = [r for r in results if r["sunset_flags"]]
    L = []
    L.append("# Golden-Copy Freshness Check — %s" % date_str)
    L.append("")
    L.append("Automated monthly check of the 22 statute-class sources against the "
             "NY Senate Open Legislation API v3.")
    L.append("")
    L.append("**Result: %s**" % ("⚠️ DRIFT DETECTED" if drift else "✅ all FULL-MATCH, no drift"))
    L.append("")
    L.append("| verdict | count |")
    L.append("|---|---|")
    for k in ("FULL-MATCH", "FRAGMENT", "DIVERGENT", "EMPTY-STORED"):
        if counts.get(k):
            L.append("| %s | %d |" % (k, counts[k]))
    L.append("| sunset mismatches | %d |" % len(flagged))
    L.append("")
    L.append("## Per-source")
    L.append("")
    L.append("| source | law | verdict | API activeDate | repealed | sunset flags |")
    L.append("|---|---|---|---|---|---|")
    for r in results:
        L.append("| %s | %s/%s | %s | %s | %s | %s |" % (
            r["file"].replace("source-", "").replace(".md", ""), r["law"], r["loc"],
            r["verdict"], r["activeDate"], r["repealed"],
            "; ".join(r["sunset_flags"]) or "—"))
    if drift:
        L.append("")
        L.append("## Action required")
        L.append("")
        L.append("This report was opened as a **freshness-drift** PR. A human must "
                 "review each DIVERGENT source and sunset flag, then decide whether "
                 "to re-capture (Phase-3 rebuild) or update sunset records. **Nothing "
                 "here rewrites golden-copy files automatically.**")
        for r in results:
            if r["verdict"] == "DIVERGENT":
                L.append("- **DIVERGENT %s** (%s/%s): live text differs from stored "
                         "STATE TEXT — possible amendment. activeDate %s."
                         % (r["file"], r["law"], r["loc"], r["activeDate"]))
            for f in r["sunset_flags"]:
                L.append("- **SUNSET %s**: %s" % (r["file"], f))
    L.append("")
    L.append("_Generated by scripts/freshness_check.py. Read-only against "
             "golden-copy/; API text reflowed to golden style before diffing._")
    return "\n".join(L) + "\n"


def emit_output(drift, date_str, report_path, state_change=False):
    """Expose results to the GitHub Actions job via $GITHUB_OUTPUT."""
    gh = os.environ.get("GITHUB_OUTPUT")
    if not gh:
        return
    with open(gh, "a", encoding="utf-8") as fh:
        fh.write("drift=%s\n" % ("true" if drift else "false"))
        fh.write("date=%s\n" % date_str)
        fh.write("report=%s\n" % report_path)
        fh.write("state_change=%s\n" % ("true" if state_change else "false"))


# --------------------------------------------------------------------------
# Offline self-test (no key / no network): synthesizes API responses
# --------------------------------------------------------------------------

def _selftest():
    # Build a fake fetcher that returns the CURRENT golden text for two normal
    # sources (=> FULL-MATCH) and a deliberately mutated one + a bad sunset date
    # (=> DIVERGENT + sunset mismatch), proving both branches are detected.
    good = ["source-stf-179-g.md", "source-wkc-57-workers-comp.md"]
    drifted = "source-stf-139-l-sexual-harassment.md"
    sunset = "source-stf-163.md"
    subset = {f: STATUTE_SOURCES[f] for f in good + [drifted, sunset]}

    def golden_as_live(fn):
        # reverse of reflow isn't needed: the stored text is already golden-style;
        # the fetcher returns it as the "API text" so reflow is idempotent.
        return stored_state_text(fn, layer_a_only=(fn in LAYER_A_ONLY))

    def fake_fetch(law, loc):
        fn = next(f for f, c in subset.items() if c == (law, loc))
        text = golden_as_live(fn)
        rep = None
        if fn == drifted:
            # Simulate a substantive amendment: replace the first half of the
            # section with different wording so the stored text is neither a
            # subset nor a near-match of the live text (=> DIVERGENT).
            half = len(text) // 2
            text = ("1. AMENDED. This subdivision was materially rewritten by a "
                    "later session law and no longer matches the stored capture. "
                    + text[half:])
        if fn == sunset:
            # keep text but claim a different repealedDate than our record
            rep = "2099-01-01"
        return {"text": text, "activeDate": "2099-01-01",
                "repealed": False, "repealedDate": rep}

    results = run(fake_fetch, sources=subset)
    by = {r["file"]: r for r in results}
    assert by["source-stf-179-g.md"]["verdict"] == "FULL-MATCH", by["source-stf-179-g.md"]
    assert by["source-wkc-57-workers-comp.md"]["verdict"] == "FULL-MATCH"
    assert by[drifted]["verdict"] == "DIVERGENT", by[drifted]
    assert by[sunset]["sunset_flags"], "expected a sunset mismatch flag"
    assert has_drift(results) is True
    # And an all-clean run must report no drift:
    clean = run(lambda law, loc: {"text": golden_as_live(
        next(f for f, c in {**{g: STATUTE_SOURCES[g] for g in good}}.items() if c == (law, loc))),
        "activeDate": "2099-01-01", "repealed": False, "repealedDate": None},
        sources={g: STATUTE_SOURCES[g] for g in good})
    assert has_drift(clean) is False

    # Fixture: the API OMITS repealed/repealedDate/activeDate entirely on some
    # sections (confirmed live). A response missing those keys must not crash.
    # (a) a non-sunset section returning ONLY {"text": ...}:
    sparse = run(lambda law, loc: {"text": golden_as_live("source-stf-179-g.md")},
                 sources={"source-stf-179-g.md": ("STF", "179-G")})
    assert sparse[0]["verdict"] == "FULL-MATCH"
    assert sparse[0]["repealed"] is None and sparse[0]["repealedDate"] is None
    assert sparse[0]["activeDate"] is None and sparse[0]["sunset_flags"] == []
    # (b) a SUNSET section missing repealed/repealedDate but whose text carries
    # the NB-repeal line: cross-check still works off the in-text date, no crash,
    # no false flag (NB date matches the record):
    ss = run(lambda law, loc: {"text": golden_as_live("source-stf-163.md")},
             sources={"source-stf-163.md": ("STF", "163")})
    assert ss[0]["sunset_flags"] == [], ss[0]["sunset_flags"]
    # (c) a completely empty response {} (every field absent) must not crash:
    empty = run(lambda law, loc: {}, sources={"source-stf-179-g.md": ("STF", "179-G")})
    assert empty[0]["verdict"] in ("DIVERGENT", "EMPTY-STORED")
    # and rendering a report over the sparse rows must not crash either:
    render_report(sparse + ss + empty, "2026-07-04")

    # RAW-FORMAT FIXTURE (regression for the 22/22 false-DIVERGENT bug):
    # a captured-shape API response whose JSON `text` carries LITERAL escaped
    # newlines (two-char \n runs surviving json.loads), hard-wrapped with leading
    # spaces and NBSP — exactly the live format the echo-back never exercised. An
    # unchanged section MUST classify FULL-MATCH against its golden file.
    fixture_path = os.path.join(REPO_ROOT, "tests", "fixtures",
                                "openleg_raw_stf-179-g.json")
    with open(fixture_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    decoded = payload["result"]["text"]
    assert "\\n" in decoded and "\n" not in decoded, \
        "fixture must carry LITERAL escaped newlines (the live quirk)"
    raw_row = run(lambda law, loc: payload["result"],
                  sources={"source-stf-179-g.md": ("STF", "179-G")})
    assert raw_row[0]["verdict"] == "FULL-MATCH", \
        "raw escaped-newline response must diff FULL-MATCH after unescape+reflow"
    assert has_drift(raw_row) is False

    rep = render_report(results, "2026-07-04")
    assert "DRIFT DETECTED" in rep and "DIVERGENT" in rep

    # REGISTRY MERGE (existence guard): only registered targets whose golden
    # file exists are added; pending captures are skipped, and the merge never
    # shrinks or duplicates the base 22-source map.
    reg = load_registry_sources()
    for fn, coord in reg.items():
        assert os.path.exists(os.path.join(SOURCES_DIR, fn)), \
            "registry merged a non-existent golden file: %s" % fn
    merged = all_sources()
    assert set(STATUTE_SOURCES).issubset(set(merged)), \
        "registry merge dropped a base source"
    # A pending target (golden file absent) must be skipped:
    pending = load_registry_sources(
        sources_dir=os.path.join(REPO_ROOT, "does-not-exist"))
    assert pending == {}, "existence guard failed: %r" % pending

    print("SELF-TEST: ALL PASS")
    print("  FULL-MATCH x2, DIVERGENT detected, sunset mismatch detected,")
    print("  missing-field responses handled, RAW escaped-newline fixture => "
          "FULL-MATCH,")
    print("  clean run => no drift, report renders.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Monthly golden-copy freshness check")
    ap.add_argument("--selftest", action="store_true",
                    help="run offline against synthesized API responses (no key)")
    ap.add_argument("--date", help="override report date (YYYY-MM-DD)")
    ap.add_argument("--write-state", metavar="PATH",
                    help="after a live run, also write the engine freshness-state "
                         "JSON to PATH (e.g. data/config/freshness-state.json)")
    ap.add_argument("--seed-all-ok", metavar="PATH",
                    help="offline: write an all-OK (FULL-MATCH) seed state to PATH "
                         "and exit (no network, no key)")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if args.seed_all_ok:
        date_str = args.date or datetime.date.today().isoformat()
        fs.write_state(args.seed_all_ok, fs.seed_all_ok(date_str))
        print("seed-all-ok freshness state written: %s (%s)"
              % (args.seed_all_ok, date_str))
        return 0

    key = os.environ.get("NYSLEG_API_KEY")
    if not key:
        print("FATAL: NYSLEG_API_KEY not set (add it as a repo Actions secret).",
              file=sys.stderr)
        return 2

    date_str = args.date or datetime.date.today().isoformat()
    results = run(http_fetcher(key), sources=all_sources())
    report = render_report(results, date_str)
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = os.path.join("docs", "freshness", "%s.md" % date_str)
    with open(os.path.join(REPO_ROOT, path), "w", encoding="utf-8") as fh:
        fh.write(report)
    drift = has_drift(results)

    # Freshness live-fire: write the runtime state and decide whether the change
    # is MATERIAL (a verdict-class transition / source add-remove / first seed
    # replacement). Only a material change should open a human-reviewed
    # state-update PR; a date/detail-only diff is a silent no-op.
    state_change = False
    if args.write_state:
        new_state = results_to_state(results, date_str)
        old_state = _read_state_json(args.write_state)
        state_change = material_state_change(old_state, new_state)
        fs.write_state(args.write_state, new_state)
        print("freshness-state written: %s (material_change=%s)"
              % (args.write_state, state_change))

    emit_output(drift, date_str, path, state_change)
    print("freshness check %s: drift=%s state_change=%s report=%s"
          % (date_str, drift, state_change, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
