#!/usr/bin/env python3
"""
Phase 2, Step 2 — NYS Procurement Vendor: Freshness Checker.

For every verbatim `source-*.md` file in golden-copy/sources/, this tool:
  1. Extracts the rule's recorded capture date (the `Date` header label) and its
     canonical `Link` URL.
  2. Re-fetches the URL and reads the source's CURRENT revision / effective /
     last-modified date and a verbatim "load-bearing" probe taken from the
     stored body.
  3. Classifies each rule as:
        OK          — still reachable, key passage intact, no newer revision.
        DRIFTED     — the live source carries a newer revision date, OR the
                      load-bearing passage we captured is no longer present.
        UNREACHABLE — the URL could not be fetched (network/policy/HTTP error).
  4. Emits a per-rule human-readable report AND a machine-readable JSON summary.
     Exit 0 if every rule is OK, 1 if any rule is DRIFTED or UNREACHABLE.

Watch-list (hard-coded elevated priority, per PHASE2-BUILD-SPEC §3 Step 2):
  * §179 cluster — active legislation S7001 / A11179 / S4877 affecting
    prompt-contracting / prompt-payment.
  * Repeal dates — §139-j / §139-k expire 2028-07-31; §163 expires 2031-06-30.

Run (live fetch):                python3 freshness_checker.py
Offline against local snapshots: python3 freshness_checker.py --snapshot DIR
Prove the drift logic offline:   python3 freshness_checker.py --selftest

The fetch layer is the only seam that needs the network. It is normalised the
same way the Phase 1 diff harness normalised formatting noise (curly vs.
straight quotes, en/em dashes, non-breaking spaces, collapsed whitespace,
markdown emphasis / rules / heading symbols) so that cosmetic rendering
differences are never mistaken for a content change.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

TODAY = datetime.date(2026, 6, 29)  # spec-fixed "as of" date for this build run.

# ---------------------------------------------------------------------------
# Watch-list (elevated priority) — PHASE2-BUILD-SPEC §3, Step 2
# ---------------------------------------------------------------------------

# §179 cluster: active bills to watch for amendments to the prompt-contracting /
# prompt-payment statutes. Any source file whose name matches one of these
# patterns is flagged elevated and annotated with the bills to watch.
WATCH_179_BILLS = ["S7001", "A11179", "S4877"]
WATCH_179_FILE_RE = re.compile(r"source-stf-179-")

# Sunset / authorization-expiry watch (unifies scheduled repeals AND program
# sunsets into one axis). A verbatim-correct rule can still be legally DEAD once
# its authorizing program lapses, so this is tracked SEPARATELY from text
# freshness. A source file may declare it inline via the optional fields
# `sunset_watch: true` + `authorization_expires: YYYY-MM-DD` (plus optional
# `authorizing_vehicle:` and `sunset_date_verified:`); the seed below covers
# statutes whose files carry no such fields (the scheduled repeals).
SUNSET_APPROACHING_DAYS = 180
SUNSET_SEED = {
    # filename fragment -> (authorization_expires, primary_verified, kind)
    "source-stf-139-j": (datetime.date(2028, 7, 31), True, "scheduled repeal"),
    "source-stf-139-k": (datetime.date(2028, 7, 31), True, "scheduled repeal"),
    "source-stf-163":   (datetime.date(2031, 6, 30), True, "scheduled repeal"),
}

SUNSET_WATCH_RE = re.compile(r"sunset_watch:\s*true", re.IGNORECASE)
AUTH_EXPIRES_RE = re.compile(r"authorization_expires:\s*(\d{4})-(\d{2})-(\d{2})")
AUTH_VEHICLE_RE = re.compile(r"authorizing_vehicle:\s*(.+)")
SUNSET_VERIFIED_RE = re.compile(r"sunset_date_verified:\s*(\w+)")


def read_sunset(record):
    """Return (expires_date, primary_verified, kind) for a source under sunset
    watch, or None. Inline `sunset_watch: true` + `authorization_expires:` in the
    file take precedence; otherwise the SUNSET_SEED table (scheduled repeals)."""
    raw = record.get("raw", "")
    if SUNSET_WATCH_RE.search(raw):
        m = AUTH_EXPIRES_RE.search(raw)
        if m:
            exp = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            vm = SUNSET_VERIFIED_RE.search(raw)
            verified = bool(vm) and vm.group(1).lower() in ("confirmed", "verified", "yes", "true")
            km = AUTH_VEHICLE_RE.search(raw)
            kind = km.group(1).strip() if km else "program authorization"
            return (exp, verified, kind)
    for frag, seed in SUNSET_SEED.items():
        if record["file"].startswith(frag):
            return seed
    return None


def classify_sunset(expires):
    """OK (>=180 days out) / APPROACHING (<180 days) / LAPSED (past)."""
    days = (expires - TODAY).days
    if days < 0:
        return ("LAPSED", days)
    if days < SUNSET_APPROACHING_DAYS:
        return ("APPROACHING", days)
    return ("OK", days)

# ---------------------------------------------------------------------------
# Header parsing (mirrors parse_golden_copy.py, incl. multi-line label values)
# ---------------------------------------------------------------------------

H_STATE_TEXT = "## STATE TEXT (verbatim)"
H_CITATIONS = "## CITATIONS"
H_AGENCY_GUIDANCE = "## AGENCY GUIDANCE"
LABEL_RE = re.compile(r"^- \*\*(?P<label>[^:*]+):\*\*\s?(?P<value>.*)$")


def find_golden_copy_root():
    """Locate the dir holding sources/, the INDEX and the verification report.

    Fails closed (returns None) when the golden copy is not next to this script:
    the drift checker must NEVER examine a different golden copy than the engine
    cites from — a fallback there could write freshness verdicts about the wrong
    files with no error. The former /mnt/project fallback was removed for that
    reason (#63 removed the analogous fallback from the runtime GoldenCopy path).
    This is the freshness-live-fire GATE (PR A)."""
    base = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(os.path.join(base, "golden-copy", "sources")):
        return os.path.join(base, "golden-copy")
    return None


def extract_record(path):
    """Pull Name, Date, Link and the verbatim STATE TEXT body from one file."""
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    idx_state = idx_citations = idx_agency = None
    for i, line in enumerate(lines):
        if idx_state is None and line.startswith(H_STATE_TEXT):
            idx_state = i
        elif idx_citations is None and line.startswith(H_CITATIONS):
            idx_citations = i
        elif idx_agency is None and line.startswith(H_AGENCY_GUIDANCE):
            idx_agency = i

    header_end = idx_state if idx_state is not None else len(lines)
    fields = {}
    i = 0
    while i < header_end:
        m = LABEL_RE.match(lines[i])
        if not m:
            i += 1
            continue
        label = m.group("label").strip()
        parts = [m.group("value").strip()]
        j = i + 1
        while j < header_end:
            nxt = lines[j]
            if nxt.strip() == "" or not (nxt.startswith(" ") or nxt.startswith("\t")):
                break
            parts.append(nxt.strip())
            j += 1
        key = "Link" if label.startswith("Link") else label
        fields.setdefault(key, "\n".join(p for p in parts if p).strip())
        i = j

    body = ""
    if idx_state is not None:
        body_end = idx_citations if idx_citations is not None else len(lines)
        if idx_agency is not None and idx_state < idx_agency < body_end:
            body_end = idx_agency
        body = "\n".join(lines[idx_state + 1:body_end]).strip()

    return {
        "file": os.path.basename(path),
        "name": fields.get("Name", ""),
        "date_raw": fields.get("Date", ""),
        "link": fields.get("Link", ""),
        "body": body,
        "raw": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# Date extraction
# ---------------------------------------------------------------------------

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}

# Revision keywords that mark the rule's OWN effective/revision date (as opposed
# to incidental "page last modified" metadata, which we explicitly skip).
REV_KEYWORDS = r"(?:REV\.?|Rev\.?|Revised|revision|as of|version|effective)"
SKIP_KEYWORDS = re.compile(r"last modified|page modified", re.IGNORECASE)

ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
MDY_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")     # MM/DD/YYYY or MM/DD/YY
MY_RE = re.compile(r"(\d{1,2})/(\d{2,4})")                # MM/YYYY or M/YY
MONTH_YEAR_RE = re.compile(r"([A-Za-z]+)\s+(\d{4})")      # "June 2023"
# "June 2023 version" — an explicit version label that names the rule's own
# edition; it outranks incidental MM/DD/YYYY dates elsewhere in the string.
MONTH_YEAR_VERSION_RE = re.compile(r"([A-Za-z]+)\s+(\d{4})\s+version", re.IGNORECASE)


def _norm_year(y):
    y = int(y)
    return y + 2000 if y < 100 else y


def _safe_date(y, m, d):
    try:
        return datetime.date(y, m, d)
    except ValueError:
        return None


def parse_rule_date(text):
    """Extract the rule's own revision/effective date from a free-text string.

    Returns (date, precision, matched_text) where precision is 'day' | 'month' |
    'year', or (None, None, None) if no rule date can be identified. We prefer a
    date adjacent to a revision keyword and never pick a "last modified" date.
    """
    if not text:
        return (None, None, None)

    # Remove parentheticals that talk about page-modified metadata so their
    # dates can't be mistaken for the rule's revision date.
    cleaned = re.sub(r"\([^)]*(?:last modified|page modified)[^)]*\)", " ", text,
                     flags=re.IGNORECASE)

    # 1) ISO date (statutes: "Current revision as of 2026-06-19").
    m = ISO_RE.search(cleaned)
    if m:
        dt = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if dt:
            return (dt, "day", m.group(0))

    # 1b) Explicit "Month YYYY version" label (Appendix A) — the rule's own
    #     edition, preferred over an incidental effective-for-new-contracts date.
    m = MONTH_YEAR_VERSION_RE.search(cleaned)
    if m and m.group(1).lower() in MONTHS:
        dt = _safe_date(int(m.group(2)), MONTHS[m.group(1).lower()], 1)
        if dt:
            return (dt, "month", m.group(0))

    # 2) A keyword-anchored MM/DD/YYYY (GFO "REV. 03/10/2020").
    kw_mdy = re.compile(REV_KEYWORDS + r"[^0-9]{0,12}" + MDY_RE.pattern)
    m = kw_mdy.search(cleaned)
    if m:
        dt = _safe_date(_norm_year(m.group(3)), int(m.group(1)), int(m.group(2)))
        if dt:
            return (dt, "day", m.group(0))

    # 3) Any MM/DD/YYYY anywhere (still not a "last modified" one — those were
    #    stripped above).
    m = MDY_RE.search(cleaned)
    if m:
        dt = _safe_date(_norm_year(m.group(3)), int(m.group(1)), int(m.group(2)))
        if dt:
            return (dt, "day", m.group(0))

    # 4) Keyword-anchored MM/YYYY (forms: "Rev. 03/2022", "Rev. 1/17").
    kw_my = re.compile(REV_KEYWORDS + r"[^0-9]{0,12}" + MY_RE.pattern)
    m = kw_my.search(cleaned)
    if m:
        dt = _safe_date(_norm_year(m.group(2)), int(m.group(1)), 1)
        if dt:
            return (dt, "month", m.group(0))

    # 5) Bare MM/YYYY (form stamp "03/2022").
    m = MY_RE.search(cleaned)
    if m:
        dt = _safe_date(_norm_year(m.group(2)), int(m.group(1)), 1)
        if dt:
            return (dt, "month", m.group(0))

    # 6) "Month YYYY" (Appendix A: "June 2023 version").
    m = MONTH_YEAR_RE.search(cleaned)
    if m and m.group(1).lower() in MONTHS:
        dt = _safe_date(int(m.group(2)), MONTHS[m.group(1).lower()], 1)
        if dt:
            return (dt, "month", m.group(0))

    return (None, None, None)


def extract_current_date(content):
    """Best-effort extraction of the live source's current revision date.

    Scans fetched page text for revision-keyword-anchored dates and ISO dates,
    skipping lines that are clearly "last modified" metadata. Returns the most
    recent plausible rule date found, or None.
    """
    if not content:
        return None
    candidates = []
    for line in content.split("\n"):
        if SKIP_KEYWORDS.search(line):
            continue
        dt, _, _ = parse_rule_date(line)
        if dt:
            candidates.append(dt)
    # Also a whole-text ISO sweep (statute pages render the revision as ISO).
    for m in ISO_RE.finditer(content):
        dt = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if dt:
            candidates.append(dt)
    return max(candidates) if candidates else None


# ---------------------------------------------------------------------------
# Normalisation + load-bearing probe (the diffcheck.py seed behaviour)
# ---------------------------------------------------------------------------

def normalize(text):
    """Collapse formatting noise so cosmetic rendering diffs don't read as drift."""
    if not text:
        return ""
    repl = {
        "‘": "'", "’": "'", "“": '"', "”": '"',
        "–": "-", "—": "-", "−": "-", " ": " ",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    text = re.sub(r"\*\*|__|[*_`]", "", text)   # markdown emphasis
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)  # heading marks
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)     # horizontal rules
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def load_bearing_probe(body):
    """Pick a stable verbatim slice of the stored body to test for presence.

    Uses the longest run of contiguous "wordy" text near the top of the body
    (skipping the leading blockquote note and headings), capped at ~120 chars.
    Returns the normalised probe, or "" if the body is too thin to probe.
    """
    norm = normalize(body)
    if len(norm) < 40:
        return norm
    # Take a window from ~5% in (past any leading marker) for a representative,
    # load-bearing slice rather than boilerplate at the very start.
    start = min(len(norm) // 20, 200)
    return norm[start:start + 120]


# ---------------------------------------------------------------------------
# Fetch layer (live HTTP via the env proxy + CA bundle, or local snapshots)
# ---------------------------------------------------------------------------

def _ssl_context():
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        p = os.environ.get(var)
        if p and os.path.isfile(p):
            return ssl.create_default_context(cafile=p)
    for p in ("/root/.ccr/ca-bundle.crt",):
        if os.path.isfile(p):
            return ssl.create_default_context(cafile=p)
    return ssl.create_default_context()


def _snapshot_path(snapshot_dir, url):
    slug = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return os.path.join(snapshot_dir, slug + ".html")


def fetch(url, snapshot_dir=None, timeout=25):
    """Fetch a URL's current content.

    Returns (ok: bool, content_or_error: str). When snapshot_dir is given, reads
    a local file keyed by a hash of the URL instead of going to the network —
    used for offline runs and tests.
    """
    if not url:
        return (False, "no link recorded in source file")

    if snapshot_dir is not None:
        path = _snapshot_path(snapshot_dir, url)
        if not os.path.isfile(path):
            return (False, "no snapshot for url ({})".format(os.path.basename(path)))
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return (True, fh.read())

    # Live fetch. urllib honours http_proxy / https_proxy from the environment.
    req = urllib.request.Request(url, headers={
        "User-Agent": "NYSProcurementVendor-FreshnessChecker/1.0 (+integrity-check)",
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read()
        # PDFs aren't decodable as text; we still record reachability and skip
        # body-level date extraction for them.
        try:
            return (True, raw.decode("utf-8", errors="replace"))
        except Exception:
            return (True, "")
    except urllib.error.HTTPError as exc:
        return (False, "HTTP {} {}".format(exc.code, exc.reason))
    except urllib.error.URLError as exc:
        return (False, "URL error: {}".format(exc.reason))
    except Exception as exc:  # timeouts, proxy CONNECT failures, TLS, etc.
        return (False, "{}: {}".format(type(exc).__name__, exc))


# ---------------------------------------------------------------------------
# Freshness assessment for one rule
# ---------------------------------------------------------------------------

def assess(record, snapshot_dir=None):
    """Return a freshness result dict for one source record."""
    cap_date, cap_prec, cap_match = parse_rule_date(record["date_raw"])

    # Watch-list annotations (independent of fetch outcome).
    watch = []
    if WATCH_179_FILE_RE.search(record["file"]):
        watch.append("§179 cluster — watch bills " + ", ".join(WATCH_179_BILLS))

    # Sunset / authorization axis (separate from text freshness).
    sunset = read_sunset(record)
    sunset_status = sunset_days = None
    if sunset:
        s_expires, s_verified, s_kind = sunset
        sunset_status, sunset_days = classify_sunset(s_expires)
        watch.append("authorization sunset {} — {} ({}, {} days out){}".format(
            s_expires.isoformat(), sunset_status, s_kind, sunset_days,
            "" if s_verified else " — DATE PENDING PRIMARY VERIFICATION"))

    result = {
        "file": record["file"],
        "name": record["name"],
        "link": record["link"],
        "captured_date": cap_date.isoformat() if cap_date else None,
        "captured_date_raw": record["date_raw"],
        "captured_precision": cap_prec,
        "current_date": None,
        "status": None,
        "reason": "",
        "elevated": bool(watch),
        "watch": watch,
        # Sunset axis — LAPSED quarantines the rule from "green" regardless of text status.
        "sunset_status": sunset_status,
        "authorization_expires": sunset[0].isoformat() if sunset else None,
        "sunset_days": sunset_days,
        "sunset_verified": sunset[1] if sunset else None,
        "sunset_kind": sunset[2] if sunset else None,
        "quarantined": sunset_status == "LAPSED",
    }

    ok, content = fetch(record["link"], snapshot_dir=snapshot_dir)
    if not ok:
        result["status"] = "UNREACHABLE"
        result["reason"] = "could not fetch source: {}".format(content)
        return result

    cur_date = extract_current_date(content)
    result["current_date"] = cur_date.isoformat() if cur_date else None

    # Content drift: the verbatim passage we captured is no longer present.
    probe = load_bearing_probe(record["body"])
    norm_content = normalize(content)
    probe_present = bool(probe) and probe in norm_content
    # We only trust an "absent" verdict when the page actually returned text we
    # could normalise; an empty body (e.g. a PDF) can't disprove the passage.
    if probe and norm_content and not probe_present:
        result["status"] = "DRIFTED"
        result["reason"] = "load-bearing passage not found in current source (content drift)"
        return result

    # Date drift: the live source advertises a newer revision than we captured.
    if cap_date and cur_date and cur_date > cap_date:
        result["status"] = "DRIFTED"
        result["reason"] = "source revision {} is newer than captured {}".format(
            cur_date.isoformat(), cap_date.isoformat())
        return result

    result["status"] = "OK"
    if cap_date and cur_date:
        result["reason"] = "current revision {} not newer than captured {}".format(
            cur_date.isoformat(), cap_date.isoformat())
    elif probe_present:
        result["reason"] = "reachable; load-bearing passage intact"
    else:
        result["reason"] = "reachable; no newer revision detected"
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

STATUS_ORDER = {"DRIFTED": 0, "UNREACHABLE": 1, "OK": 2}


def print_report(results):
    print("=" * 78)
    print("NYS Procurement Vendor — Freshness Checker")
    print("Run date (as-of): {}".format(TODAY.isoformat()))
    print("=" * 78)

    # Watch-list summary up top so elevated rules are never buried.
    elevated = [r for r in results if r["elevated"]]
    print("\nWATCH-LIST (elevated priority): {} rule(s)".format(len(elevated)))
    for r in elevated:
        print("  * {:<44} [{}]".format(r["file"], r["status"]))
        for w in r["watch"]:
            print("      - {}".format(w))

    print("\nPER-RULE FRESHNESS")
    print("-" * 78)
    ordered = sorted(results, key=lambda r: (STATUS_ORDER.get(r["status"], 9), r["file"]))
    for r in ordered:
        flag = "*" if r["elevated"] else " "
        cap = r["captured_date"] or r["captured_date_raw"][:24] or "—"
        cur = r["current_date"] or "—"
        print("{} [{:<11}] {}".format(flag, r["status"], r["file"]))
        print("       name     : {}".format(r["name"][:90]))
        print("       captured : {}   current: {}".format(cap, cur))
        print("       detail   : {}".format(r["reason"]))
        if r.get("sunset_status"):
            print("       sunset   : {} — authorization expires {} ({} days){}{}".format(
                r["sunset_status"], r["authorization_expires"], r["sunset_days"],
                "" if r.get("sunset_verified") else " [date pending verification]",
                "  ⛔ QUARANTINED" if r.get("quarantined") else ""))

    print("-" * 78)
    counts = {"OK": 0, "DRIFTED": 0, "UNREACHABLE": 0}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    sunset_counts = {"OK": 0, "APPROACHING": 0, "LAPSED": 0}
    for r in results:
        if r.get("sunset_status"):
            sunset_counts[r["sunset_status"]] = sunset_counts.get(r["sunset_status"], 0) + 1
    print("Totals: {} rule(s) | text: OK={} DRIFTED={} UNREACHABLE={}".format(
        len(results), counts["OK"], counts["DRIFTED"], counts["UNREACHABLE"]))
    print("        sunset watch: OK={} APPROACHING={} LAPSED={}".format(
        sunset_counts["OK"], sunset_counts["APPROACHING"], sunset_counts["LAPSED"]))

    # A LAPSED authorization quarantines the rule from "green" regardless of text status.
    all_ok = (counts["DRIFTED"] == 0 and counts["UNREACHABLE"] == 0
              and sunset_counts["LAPSED"] == 0)
    print("=" * 78)
    if all_ok:
        print("RESULT: ALL FRESH — every rule OK (text current, no lapsed authorizations).")
    else:
        print("RESULT: ATTENTION NEEDED — {} drifted, {} unreachable, {} LAPSED "
              "(authorization expired → quarantined). These rules must not be presented "
              "as authoritative until re-verified per the methodology manual.".format(
                  counts["DRIFTED"], counts["UNREACHABLE"], sunset_counts["LAPSED"]))
    print("=" * 78)
    counts["LAPSED_sunset"] = sunset_counts["LAPSED"]
    counts["APPROACHING_sunset"] = sunset_counts["APPROACHING"]
    return all_ok, counts


def emit_json(results, counts, all_ok):
    summary = {
        "tool": "freshness_checker",
        "as_of": TODAY.isoformat(),
        "status": "ALL_FRESH" if all_ok else "ATTENTION_NEEDED",
        "totals": {"rules": len(results), **counts},
        "watch_list": {
            "s179_bills": WATCH_179_BILLS,
            "sunset_seed": {frag: {"authorization_expires": exp.isoformat(),
                                   "primary_verified": ver, "kind": kind}
                            for frag, (exp, ver, kind) in SUNSET_SEED.items()},
            "sunset_approaching_days": SUNSET_APPROACHING_DAYS,
        },
        "rules": [
            {
                "file": r["file"],
                "name": r["name"],
                "link": r["link"],
                "status": r["status"],
                "captured_date": r["captured_date"],
                "captured_date_raw": r["captured_date_raw"],
                "current_date": r["current_date"],
                "elevated": r["elevated"],
                "watch": r["watch"],
                "reason": r["reason"],
                "sunset_status": r.get("sunset_status"),
                "authorization_expires": r.get("authorization_expires"),
                "sunset_days": r.get("sunset_days"),
                "sunset_verified": r.get("sunset_verified"),
                "sunset_kind": r.get("sunset_kind"),
                "quarantined": r.get("quarantined", False),
            }
            for r in sorted(results, key=lambda r: r["file"])
        ],
    }
    print("\n--- JSON SUMMARY ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Self-test — proves OK / DRIFTED / UNREACHABLE detection without a network
# ---------------------------------------------------------------------------

def run_selftest():
    print("=" * 78)
    print("FRESHNESS CHECKER — SELF-TEST (offline, no network)")
    print("=" * 78)
    body = ("This statute text contains a stable load-bearing passage about "
            "purchasing services and commodities that must remain present verbatim.")
    probe = load_bearing_probe(body)

    cases = []

    # 1) OK: current revision equals captured, passage intact.
    rec = {"file": "fixture-ok.md", "name": "OK fixture",
           "date_raw": "Current revision as of 2020-01-15", "link": "x", "body": body}
    content = "Updated 2020-01-15. " + body
    cur = extract_current_date(content)
    cap, _, _ = parse_rule_date(rec["date_raw"])
    ok_status = "OK" if (cap and cur and cur <= cap and probe in normalize(content)) else "?"
    cases.append(("OK when nothing changed", ok_status, "OK"))

    # 2) DRIFTED (date): live revision newer than captured.
    content2 = "Current revision as of 2026-05-01. " + body
    cur2 = extract_current_date(content2)
    drift_date = "DRIFTED" if (cap and cur2 and cur2 > cap) else "?"
    cases.append(("DRIFTED when source date is newer", drift_date, "DRIFTED"))

    # 3) DRIFTED (content): load-bearing passage missing.
    content3 = "Current revision as of 2020-01-15. Totally different page body now."
    drift_content = "DRIFTED" if (probe and normalize(content3) and probe not in normalize(content3)) else "?"
    cases.append(("DRIFTED when load-bearing passage vanishes", drift_content, "DRIFTED"))

    # 4) UNREACHABLE: fetch fails (empty snapshot dir).
    ok, _ = fetch("https://example.invalid/x", snapshot_dir="/nonexistent-snapshot-dir")
    unreach = "UNREACHABLE" if not ok else "?"
    cases.append(("UNREACHABLE when fetch fails", unreach, "UNREACHABLE"))

    # 5) End-to-end via assess(): altered Date in a fixture → DRIFTED.
    rec5 = {"file": "source-stf-163-fixture.md", "name": "163 fixture",
            "date_raw": "Current revision as of 2026-06-19", "link": "https://x/163",
            "body": body}
    # Snapshot advertises a newer revision than the captured 2026-06-19.
    import tempfile
    snap = tempfile.mkdtemp(prefix="freshness-selftest-")
    with open(_snapshot_path(snap, rec5["link"]), "w", encoding="utf-8") as fh:
        fh.write("Current revision as of 2099-01-01. " + body)
    res5 = assess(rec5, snapshot_dir=snap)
    cases.append(("assess() flags an altered/newer Date as DRIFTED", res5["status"], "DRIFTED"))

    # 6) Sunset classification: OK (>=180 days), APPROACHING (<180), LAPSED (past).
    cases.append(("sunset OK when >180 days out",
                  classify_sunset(TODAY + datetime.timedelta(days=400))[0], "OK"))
    cases.append(("sunset APPROACHING when <180 days out",
                  classify_sunset(TODAY + datetime.timedelta(days=90))[0], "APPROACHING"))
    cases.append(("sunset LAPSED when past",
                  classify_sunset(TODAY - datetime.timedelta(days=1))[0], "LAPSED"))

    # 7) Inline sunset read: a file declaring sunset_watch:true is picked up and,
    #    when the authorization has lapsed, is quarantined from "green".
    lapsed_raw = ("## SUNSET / AUTHORIZATION\n- sunset_watch: true\n"
                  "- authorization_expires: 2020-01-01\n- sunset_date_verified: pending\n")
    rec7 = {"file": "source-fixture-sunset.md", "name": "sunset fixture",
            "date_raw": "", "link": "https://x/sunset", "body": body, "raw": lapsed_raw}
    res7 = assess(rec7, snapshot_dir="/nonexistent-snapshot-dir")
    cases.append(("inline sunset_watch parsed → LAPSED", res7.get("sunset_status"), "LAPSED"))
    cases.append(("LAPSED authorization quarantines the rule", res7.get("quarantined"), True))

    # 8) Seeded sunset (§163 repeal date 2031-06-30) classifies OK today.
    rec8 = {"file": "source-stf-163.md", "name": "163", "date_raw": "", "link": "https://x/163b",
            "body": body, "raw": ""}
    res8 = assess(rec8, snapshot_dir="/nonexistent-snapshot-dir")
    cases.append(("seeded §163 repeal date → sunset OK", res8.get("sunset_status"), "OK"))

    print()
    all_pass = True
    for desc, got, want in cases:
        ok = got == want
        all_pass = all_pass and ok
        print("  [{}] {:<48} got={} want={}".format("PASS" if ok else "FAIL", desc, got, want))
    print("=" * 78)
    print("SELF-TEST: {}".format("ALL PASS" if all_pass else "FAILURES PRESENT"))
    print("=" * 78)
    return 0 if all_pass else 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="NYS Procurement Vendor freshness checker")
    ap.add_argument("--snapshot", metavar="DIR",
                    help="read current source content from local snapshots in DIR "
                         "(offline mode) instead of fetching over the network")
    ap.add_argument("--selftest", action="store_true",
                    help="run the offline drift-detection self-test and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        return run_selftest()

    root = find_golden_copy_root()
    if root is None:
        print("FATAL: could not locate golden-copy/sources.")
        print(json.dumps({"status": "FAIL", "reason": "golden-copy not found"}))
        return 1

    sources_dir = os.path.join(root, "sources")
    files = sorted(
        os.path.join(sources_dir, n) for n in os.listdir(sources_dir)
        if n.startswith("source-") and n.endswith(".md")
    )

    if args.snapshot:
        print("(offline mode: reading current content from snapshots in {})\n".format(args.snapshot))

    results = []
    for path in files:
        rec = extract_record(path)
        results.append(assess(rec, snapshot_dir=args.snapshot))

    all_ok, counts = print_report(results)
    emit_json(results, counts, all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
