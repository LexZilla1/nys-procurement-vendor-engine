#!/usr/bin/env python3
"""
Manual statute capture from the NY Senate Open Legislation API v3.

This is the SANCTIONED egress-blocked capture path: interactive Claude Code
cloud sessions cannot reach legislation.nysenate.gov and do not inherit
NYSLEG_API_KEY, so statute pulls run from GitHub Actions (which holds the key
as a secret and can reach OpenLeg, as the monthly freshness automation proves).
The workflow .github/workflows/statute-capture.yml runs this script and opens a
PR; a human reviews and merges. Nothing here marks anything verified golden.

Two capture modes, driven by data/config/statute_capture_registry.json:

  NEW  (e.g. GCN/24, GCN/25-A) -- no stored golden yet. Fetches the full
       section, reflows it to the house one-line-per-subdivision style (words
       untouched -- same reflow the freshness checker uses), and writes a
       golden-copy CANDIDATE carrying the standard metadata header, the
       ``## STATE TEXT (verbatim)`` block with every NB effective/repeal flag
       preserved verbatim, ``Covers: full section``, and an explicit
       ``Tier: PENDING HUMAN READ -- not golden until human-verified`` marker.
       The candidate is freshness-registered via the registry (it joins the
       monthly check once its file exists on disk).

  EXISTING (e.g. EXC/314) -- DIFF ONLY against the stored golden STATE TEXT.
       FULL-MATCH  -> recorded in the capture report; the golden file is NOT
                      edited (repo convention: report, do not rewrite).
       DIVERGENT   -> the PR is flagged for human review with the diff shown;
                      statute text is NEVER auto-reconciled.

Fail-closed (the run FAILS and NOTHING is written to golden-copy/) on: missing
NYSLEG_API_KEY; API error; empty response; truncated/missing statute body;
parse failure; missing subdivision structure where expected; missing or
unreadable NB flags where expected. Validation of ALL requested sections
completes before any file is written, so a partial capture is never committed.

Security: the API key is read from the environment only. It is never printed,
never written to disk, and never placed in any logged URL, PR body, or report.
The ``law_ids`` input is validated as a comma-separated list of OpenLeg law
coordinates and intersected with the registry whitelist -- unknown or
suspicious input is rejected.

Usage (in Actions):
    NYSLEG_API_KEY=... python3 scripts/statute_capture.py --law-ids "GCN/24,GCN/25-A,EXC/314"

Offline self-test (no key, no network -- synthesizes API responses):
    python3 scripts/statute_capture.py --selftest
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

# Reuse the freshness checker's verbatim-safe text handling (unescape + reflow +
# classify + stored-text extraction) so capture and the monthly diff agree
# byte-for-byte on what "the same text" means. Import by absolute location so it
# works regardless of the caller's CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import freshness_check as fc  # noqa: E402

REPO_ROOT = fc.REPO_ROOT
SOURCES_DIR = fc.SOURCES_DIR
API_BASE = fc.API_BASE  # https://legislation.nysenate.gov/api/3/laws
PUBLIC_URL_BASE = "https://www.nysenate.gov/legislation/laws"
REGISTRY_PATH = os.path.join(REPO_ROOT, "data", "config",
                             "statute_capture_registry.json")
REPORT_DIR = os.path.join(REPO_ROOT, "docs", "statute-capture")

# A well-formed OpenLeg law coordinate: uppercase law id, slash, numeric
# location with optional -SUFFIX chunks. Matches GCN/24, GCN/25-A, EXC/314,
# STF/139-J. Rejects lowercase, whitespace, path traversal, query strings,
# and anything that could be smuggled into a URL or filesystem path.
LAW_ID_RE = re.compile(r"^[A-Z]{2,4}/[0-9]+(?:-[0-9A-Z]+)*$")

# Top-level subdivision marker at a line start ("1.", "2.", "2-a.", allowing a
# leading annotation star as in "** 5."). Nested "(a)"/"(i)" markers are NOT
# counted -- this measures section-level structure only.
SUBDIV_RE = re.compile(r"^\s*(?:\*+\s*)?(\d+(?:-[a-z])?)\.\s", re.M | re.I)

# Inline subdivision marker following the section-title sentence on the SAME
# physical line, e.g. reflow puts subdivision 1 on the "§" heading line:
#   "§ 25-a. Public holiday ... public holiday. 1. When any period ..."
# The line-start SUBDIV_RE misses that "1." because it is mid-line. Require a
# preceding sentence break (". " / "; ") and a following word so section
# numbers ("§ 25-a.") and dates ("July 1, 2028") are not miscounted. Applied
# ONLY to the section-heading line (see ordered_subdivisions), which bounds any
# false positive to that one line.
INLINE_SUBDIV_RE = re.compile(r"[.;]\s+(\d+(?:-[a-z])?)\.\s+[A-Za-z]")

# An NB annotation line, e.g. "** NB Effective July 1, 2026" / "* NB Repealed
# July 1, 2028". These carry the effective/repeal semantics and must survive
# capture verbatim.
NB_LINE_RE = re.compile(r"^\*+\s*NB\b.*$", re.M)

# Minimum body length (chars, after reflow) below which we treat the response as
# truncated rather than a real section.
MIN_BODY_CHARS = 40


class CaptureError(Exception):
    """A fail-closed condition: abort the run, write nothing."""


def die(msg, code=1):
    print("FATAL: %s" % msg, file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def parse_law_ids(raw):
    """Validate and de-duplicate a comma-separated law_ids input string.

    Raises CaptureError on any token that is not a clean OpenLeg coordinate.
    """
    if raw is None or not raw.strip():
        raise CaptureError("law_ids input is empty")
    ids, seen = [], set()
    for tok in raw.split(","):
        t = tok.strip()
        if not t:
            continue
        if not LAW_ID_RE.match(t):
            raise CaptureError(
                "invalid law id %r -- expected a coordinate like 'GCN/24' "
                "(uppercase law id / numeric location). Rejecting suspicious "
                "input." % t)
        if t not in seen:
            seen.add(t)
            ids.append(t)
    if not ids:
        raise CaptureError("law_ids input contained no usable law ids")
    return ids


def load_registry():
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        reg = json.load(fh)
    targets = reg.get("targets") or {}
    if not targets:
        raise CaptureError("registry has no targets: %s" % REGISTRY_PATH)
    return targets


# ---------------------------------------------------------------------------
# Text structure helpers (all operate on already-reflowed text)
# ---------------------------------------------------------------------------

def ordered_subdivisions(text):
    """Distinct top-level subdivision markers, in document order.

    Counts line-start markers AND an inline marker that reflow parks on the
    section-heading line (the "§ ... 1. When ..." case), so a section whose
    subdivision 1 shares the heading line is not under-counted. The inline scan
    is confined to the heading line to avoid matching numbers in body prose.
    """
    marks = []  # (position, key)
    for m in SUBDIV_RE.finditer(text):
        marks.append((m.start(1), m.group(1).lower()))
    stripped = text.lstrip()
    first_line = stripped.split("\n", 1)[0]
    if re.sub(r"^\*+\s*", "", first_line).startswith("§"):
        base = text.find(first_line)
        for m in INLINE_SUBDIV_RE.finditer(first_line):
            marks.append((base + m.start(1), m.group(1).lower()))
    out, seen = [], set()
    for _pos, k in sorted(marks):
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def extract_nb_flags(text):
    return [ln.strip() for ln in NB_LINE_RE.findall(text)]


def nb_flag_readable(flag):
    """A readable NB flag has real content after 'NB' (not just a bare marker)."""
    m = re.match(r"^\*+\s*NB\s+(.+?)\s*$", flag)
    return bool(m and m.group(1).strip())


def section_body_ok(reflowed, loc):
    """True iff the reflowed text looks like a complete, untruncated section:
    non-trivial length and opening at a '§' section heading (a leading
    annotation star is allowed, matching the golden convention). Returns
    (ok, reason)."""
    body = reflowed.strip()
    if len(body) < MIN_BODY_CHARS:
        return False, "body is %d chars (< %d) -- looks truncated/empty" % (
            len(body), MIN_BODY_CHARS)
    first = re.sub(r"^\*+\s*", "", body.lstrip())
    if not first.startswith("§"):
        return False, ("does not begin at a '§' section heading (starts %r) -- "
                       "possible truncation or wrong document" % first[:40])
    return True, ""


def _state_text_from_md(md):
    """Extract the STATE TEXT (verbatim) body from a built golden markdown
    string -- mirrors freshness_check.stored_state_text but on an in-memory
    string, so we can verify what the writer actually saved."""
    m = re.search(r"^##\s*STATE TEXT[^\n]*\n(.*?)(?=^##\s|\Z)", md, re.M | re.S)
    body = m.group(1) if m else ""
    return re.sub(r"\n?-{3,}\s*$", "", body).strip()


# ---------------------------------------------------------------------------
# API fetch (injectable so tests never touch the network)
# ---------------------------------------------------------------------------

def http_fetcher(key):
    def fetch(law, loc):
        params = urllib.parse.urlencode({"key": key})
        url = "%s/%s/%s?%s" % (API_BASE, law, loc, params)  # never logged
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if not payload.get("success", False):
            # Report the coordinate and message, NEVER the URL (it holds the key).
            raise CaptureError("API success=false for %s/%s: %s"
                               % (law, loc, payload.get("message")))
        return payload.get("result") or {}
    return fetch


# ---------------------------------------------------------------------------
# Golden-candidate builder (NEW mode)
# ---------------------------------------------------------------------------

def build_golden_candidate(coord, spec, raw, reflowed, capture_date):
    """Render a PENDING-HUMAN-READ golden candidate markdown for a NEW capture.

    Uses the established header/section layout (parse_golden_copy-compatible):
    metadata labels, ``## STATE TEXT (verbatim)`` with the reflowed body
    (NB flags preserved verbatim inside it), and a ``## CITATIONS`` section.
    """
    law, loc = coord.split("/", 1)
    api_title = (raw.get("title") or "").strip()
    active = raw.get("activeDate") or "unknown"
    name = api_title or ("%s § %s" % (law, loc))
    lines = []
    lines.append("# SOURCE TEXT — NY %s Law § %s%s"
                 % (law, loc, (" (%s)" % api_title if api_title else "")))
    lines.append("")
    lines.append("- **Name:** %s" % name)
    lines.append("- **Date:** current revision per NY Open Legislation "
                 "(API activeDate %s; confirm exact revision on human read)"
                 % active)
    lines.append("- **Issued by:** New York State Legislature; published via "
                 "NY State Senate Open Legislation")
    lines.append("- **Link (permanent identifier):** %s/%s/%s"
                 % (PUBLIC_URL_BASE, law, loc))
    lines.append("- **Copied exactly on:** %s" % capture_date)
    lines.append("- **API activeDate:** %s" % active)
    lines.append("- **Capture method:** openleg-api-v3")
    lines.append("- **Covers:** full section")
    lines.append("- **Tier:** PENDING HUMAN READ — not golden until "
                 "human-verified")
    lines.append("- **Freshness-registered:** yes "
                 "(data/config/statute_capture_registry.json)")
    lines.append("")
    lines.append("> Captured automatically by the sanctioned GitHub Actions "
                 "statute-capture workflow (.github/workflows/statute-capture.yml) "
                 "because interactive Claude Code sessions are egress-blocked "
                 "from legislation.nysenate.gov. The body below is the verbatim "
                 "Open Legislation API `text` field, reflowed to the house "
                 "one-line-per-subdivision style (words unchanged). This is NOT "
                 "verified golden: a human must read it against the primary "
                 "source (nysenate.gov / Open Legislation) before the engine "
                 "cites it.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## STATE TEXT (verbatim)")
    lines.append("")
    lines.append(reflowed.strip())
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## CITATIONS THIS TEXT POINTS TO (tagged for traceability — "
                 "not part of the rule)")
    lines.append("")
    lines.append("- (pending human read — citations to be tagged when this "
                 "capture is verified against the primary source)")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-section processing (validate + build, in memory only)
# ---------------------------------------------------------------------------

def process_section(coord, spec, raw, capture_date):
    """Validate one fetched section and build its capture result in memory.

    Raises CaptureError on any fail-closed condition. Never writes to disk.
    Returns a dict describing the section (used for report + write phase).
    """
    law, loc = coord.split("/", 1)
    mode = spec.get("mode")
    if mode not in ("new", "existing"):
        raise CaptureError("%s: registry mode must be 'new' or 'existing', "
                           "got %r" % (coord, mode))

    # -- empty response ----------------------------------------------------
    text_raw = raw.get("text")
    if not text_raw or not str(text_raw).strip():
        raise CaptureError("%s: empty API response text (fail-closed)" % coord)

    # -- reflow (unescape literal \n runs + join hard wraps; words untouched) -
    reflowed = fc.reflow(text_raw)
    if not reflowed.strip():
        raise CaptureError("%s: text empty after reflow (fail-closed)" % coord)

    # -- truncated / missing body -----------------------------------------
    ok, why = section_body_ok(reflowed, loc)
    if not ok:
        raise CaptureError("%s: truncated/missing statute body: %s" % (coord, why))

    # -- subdivision structure --------------------------------------------
    subdiv = ordered_subdivisions(reflowed)
    # A single-paragraph section legitimately has no numbered subdivisions;
    # count it as one implicit subdivision so min_subdivisions=1 accepts a
    # complete short section while still rejecting an empty/truncated body.
    api_subdiv_count = len(subdiv) if subdiv else 1
    min_sub = int(spec.get("min_subdivisions", 1))
    if api_subdiv_count < min_sub:
        raise CaptureError(
            "%s: missing subdivision structure where expected "
            "(found %d, require >= %d)" % (coord, api_subdiv_count, min_sub))

    # -- NB flags (verbatim; unreadable => fail; expected-but-absent => fail) --
    nb_flags = extract_nb_flags(reflowed)
    for f in nb_flags:
        if not nb_flag_readable(f):
            raise CaptureError("%s: unreadable NB flag: %r (fail-closed)"
                               % (coord, f))
    if spec.get("expect_nb_flags") and not nb_flags:
        raise CaptureError("%s: expected NB flags but none were found "
                           "(fail-closed)" % coord)

    result = {
        "coord": coord, "law": law, "loc": loc, "mode": mode,
        "endpoint": "%s/%s/%s" % (API_BASE, law, loc),  # NO key
        "public_link": "%s/%s/%s" % (PUBLIC_URL_BASE, law, loc),
        "activeDate": raw.get("activeDate"),
        "api_subdiv_count": api_subdiv_count,
        "nb_flags": nb_flags,
        "file": spec.get("file"),
        "write_path": None,
        "content": None,
        "diff": None,
    }

    if mode == "new":
        content = build_golden_candidate(coord, spec, raw, reflowed, capture_date)
        # Verify the writer preserved structure: subdivisions saved == from API.
        saved_body = _state_text_from_md(content)
        saved = ordered_subdivisions(saved_body)
        result["saved_subdiv_count"] = len(saved) if saved else 1
        if result["saved_subdiv_count"] != api_subdiv_count:
            raise CaptureError(
                "%s: subdivision count drift building candidate "
                "(API %d != saved %d)" % (coord, api_subdiv_count,
                                          result["saved_subdiv_count"]))
        # Sanity: NB flags must survive into the saved body verbatim.
        for f in nb_flags:
            if f not in saved_body:
                raise CaptureError("%s: NB flag lost in candidate body: %r"
                                   % (coord, f))
        result["content"] = content
        result["write_path"] = os.path.join(SOURCES_DIR, spec["file"])
        result["verdict"] = "NEW"
        return result

    # -- existing: diff only -----------------------------------------------
    fn = spec.get("file")
    stored_path = os.path.join(SOURCES_DIR, fn)
    if not os.path.exists(stored_path):
        raise CaptureError("%s: mode 'existing' but stored golden %s is missing"
                           % (coord, fn))
    stored = fc.stored_state_text(fn)
    saved = ordered_subdivisions(stored)
    result["saved_subdiv_count"] = len(saved) if saved else 1
    verdict = fc.classify(stored, reflowed)
    if verdict == "FULL-MATCH":
        result["verdict"] = "FULL-MATCH"
    else:
        # FRAGMENT / DIVERGENT / anything else -> human review. Show the diff.
        result["verdict"] = "DIVERGENT"
        result["classify_detail"] = verdict
        result["diff"] = "\n".join(difflib.unified_diff(
            fc.norm(stored).split(), fc.norm(reflowed).split(),
            fromfile="stored (golden)", tofile="live (API)", lineterm="", n=3))
    return result


# ---------------------------------------------------------------------------
# Report / PR body
# ---------------------------------------------------------------------------

def render_report(sections, date_str):
    has_new = any(s["mode"] == "new" for s in sections)
    divergent = [s for s in sections if s["verdict"] == "DIVERGENT"]
    L = []
    L.append("# Statute capture — %s" % date_str)
    L.append("")
    L.append("Manual Open Legislation capture via the sanctioned GitHub Actions "
             "workflow (`.github/workflows/statute-capture.yml`). Interactive "
             "Claude Code sessions are egress-blocked from "
             "legislation.nysenate.gov; Actions holds `NYSLEG_API_KEY` and can "
             "reach the API.")
    L.append("")
    if has_new:
        L.append("> **NOT VERIFIED GOLDEN.** Any NEW capture below (including "
                 "GCN/24 and GCN/25-A) is a **PENDING HUMAN READ** candidate. "
                 "It is not golden and must not be cited by the engine until a "
                 "human verifies it against the primary source.")
        L.append("")
    L.append("| law | mode | result | subdivs (API / saved) | NB flags |")
    L.append("|---|---|---|---|---|")
    for s in sections:
        L.append("| %s | %s | %s | %d / %d | %d |" % (
            s["coord"], s["mode"].upper(), s["verdict"],
            s["api_subdiv_count"], s.get("saved_subdiv_count", 0),
            len(s["nb_flags"])))
    L.append("")
    for s in sections:
        L.append("## %s — %s" % (s["coord"], s["verdict"]))
        L.append("")
        L.append("- **Law ID:** %s" % s["coord"])
        L.append("- **Source / API endpoint (key omitted):** `%s`" % s["endpoint"])
        L.append("- **Primary source (human-read target):** %s" % s["public_link"])
        L.append("- **Capture mode:** %s" % s["mode"].upper())
        L.append("- **API activeDate:** %s" % (s["activeDate"] or "unknown"))
        L.append("- **Subdivision count (from API):** %d" % s["api_subdiv_count"])
        L.append("- **Subdivision count (saved in file):** %d"
                 % s.get("saved_subdiv_count", 0))
        if s["nb_flags"]:
            L.append("- **NB flags found (verbatim):**")
            for f in s["nb_flags"]:
                L.append("  - `%s`" % f)
        else:
            L.append("- **NB flags found:** none")
        L.append("- **Diff result:** %s" % s["verdict"])
        if s["mode"] == "new":
            L.append("- **Written to:** `golden-copy/sources/%s`" % s["file"])
            L.append("- **Tier:** PENDING HUMAN READ — not golden until "
                     "human-reviewed against the primary source.")
        if s["verdict"] == "FULL-MATCH":
            L.append("- Golden file left unchanged (repo convention: audit "
                     "recorded here, golden body not rewritten on a match).")
        if s["verdict"] == "DIVERGENT":
            L.append("- **Human review required.** Live API text differs from "
                     "the stored golden (classify: %s). Statute text is **not** "
                     "auto-reconciled. Diff (normalized, word-level):"
                     % s.get("classify_detail", "DIVERGENT"))
            L.append("")
            L.append("```diff")
            L.append(s["diff"] or "(no diff captured)")
            L.append("```")
        L.append("")
    L.append("## Human-read checklist before promoting any NEW capture")
    L.append("")
    L.append("- [ ] GCN/24 and GCN/25-A are **not verified golden** in this PR; "
             "read each against nysenate.gov / Open Legislation.")
    L.append("- [ ] Confirm the STATE TEXT is verbatim (words, punctuation, and "
             "every NB effective/repeal flag).")
    L.append("- [ ] Remove the `Tier: PENDING HUMAN READ` marker and add the "
             "`Verified:` stamp only after a comma-by-comma check.")
    if divergent:
        L.append("- [ ] Resolve each DIVERGENT section by hand; never accept the "
                 "auto-diff as a reconciliation.")
    L.append("")
    L.append("_Generated by scripts/statute_capture.py. The API key is never "
             "logged, written, or included in any endpoint shown above._")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# GitHub Actions output signaling
# ---------------------------------------------------------------------------

def emit_output(**kv):
    gh = os.environ.get("GITHUB_OUTPUT")
    if not gh:
        return
    with open(gh, "a", encoding="utf-8") as fh:
        for k, v in kv.items():
            fh.write("%s=%s\n" % (k, v))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

# The human trust stamp: the `- **Verified:**` header line a reviewer writes ONLY
# after a comma-by-comma read (see the human-read checklist in render_report). Its
# presence is the SOLE authority on overwrite-safety, independent of registry mode.
VERIFIED_STAMP_RE = re.compile(r"^-\s*\*\*Verified\b", re.M)


def _has_verified_stamp(path):
    """True iff an existing golden file carries a human `Verified:` stamp. A
    missing/unreadable file is treated as unverified (False) -- the guard only
    ever REFUSES on a positively-confirmed stamp, never on absence."""
    try:
        with open(path, encoding="utf-8") as fh:
            return bool(VERIFIED_STAMP_RE.search(fh.read()))
    except OSError:
        return False


def capture(law_ids, fetch, capture_date, write=True):
    """Fetch + validate + build ALL requested sections before writing anything
    (atomic: a fail-closed abort leaves no partial capture). Returns the list
    of section results. Writes NEW candidates + the report only when write=True
    and every section validated."""
    targets = load_registry()
    requested = []
    for coord in law_ids:
        if coord not in targets:
            raise CaptureError(
                "%s is not a registered capture target. Add it to "
                "data/config/statute_capture_registry.json first (whitelist)."
                % coord)
        requested.append(coord)

    # ---- Phase A: fetch + validate + build in memory (no writes) ---------
    sections = []
    for coord in requested:
        law, loc = coord.split("/", 1)
        try:
            raw = fetch(law, loc)
        except CaptureError:
            raise
        except Exception as exc:  # network/parse error -> STOP, no fallback
            raise CaptureError("%s: API request failed: %s "
                               "(stopping; no scraping fallback)" % (coord, exc))
        if not isinstance(raw, dict):
            raise CaptureError("%s: API result was not an object" % coord)
        sections.append(process_section(coord, targets[coord], raw, capture_date))

    if not write:
        return sections

    # ---- Phase B: write (only reached if every section validated) --------
    # TRUST GUARD (fail-closed, atomic, mode-INDEPENDENT): overwrite-safety is a
    # TRUST question, governed ONLY by the human `Verified:` stamp -- never by
    # registry mode. Before writing ANYTHING, refuse the whole run if any target
    # would overwrite a human-verified golden. (mode says whether we possess the
    # section / how to diff it; it must never authorize clobbering verified text.)
    for s in sections:
        if s.get("write_path") and _has_verified_stamp(s["write_path"]):
            raise CaptureError(
                "%s: refusing to overwrite a human-verified golden -- %s carries a "
                "'Verified:' stamp. A capture run NEVER overwrites verified text; this "
                "is governed by the Verified stamp, not by registry mode. Re-verify a "
                "fresh recapture into place deliberately instead."
                % (s["coord"], s["file"]))
    for s in sections:
        if s["mode"] == "new":
            os.makedirs(os.path.dirname(s["write_path"]), exist_ok=True)
            with open(s["write_path"], "w", encoding="utf-8") as fh:
                fh.write(s["content"])
    os.makedirs(REPORT_DIR, exist_ok=True)
    report = render_report(sections, capture_date)
    report_rel = os.path.join("docs", "statute-capture", "%s.md" % capture_date)
    with open(os.path.join(REPO_ROOT, report_rel), "w", encoding="utf-8") as fh:
        fh.write(report)

    has_new = any(s["mode"] == "new" for s in sections)
    divergent = any(s["verdict"] == "DIVERGENT" for s in sections)
    labels = ["statute-capture"]
    if has_new:
        labels.append("pending-human-read")
    if divergent:
        labels.append("statute-divergent")
    emit_output(
        changed="true",
        has_new="true" if has_new else "false",
        divergent="true" if divergent else "false",
        draft="true" if (has_new or divergent) else "false",
        labels=",".join(labels),
        date=capture_date,
        report=report_rel,
        branch="statute-capture/%s" % capture_date,
    )
    print("statute capture %s: sections=%d new=%s divergent=%s report=%s"
          % (capture_date, len(sections), has_new, divergent, report_rel))
    return sections


# ---------------------------------------------------------------------------
# Offline self-test (no key, no network)
# ---------------------------------------------------------------------------

def _selftest():
    import tempfile

    # A synthetic NEW-section response (placeholder text, NOT statute text):
    # opens at "§", has numbered subdivisions and an NB flag, carries literal
    # escaped newlines exactly like the live API.
    new_text = (
        "  \\u00a7 24. Placeholder public holidays. The following are\\n"
        "  placeholder holidays for formatter testing only.\\n"
        "  1. First placeholder subdivision text goes here for the\\n"
        "  reflow to join into one line.\\n"
        "  2. Second placeholder subdivision text.\\n"
        "  * NB Effective January 1, 2099\\n").replace("\\u00a7", "§")

    def fake_new(law, loc):
        return {"text": new_text, "activeDate": "2099-01-01",
                "title": "Placeholder holidays", "repealed": False}

    date = "2099-01-01"
    secs = capture(["GCN/24"], fake_new, date, write=False)
    s = secs[0]
    assert s["verdict"] == "NEW", s
    assert s["api_subdiv_count"] == 2, s["api_subdiv_count"]
    assert s["saved_subdiv_count"] == 2, s["saved_subdiv_count"]
    assert any("NB Effective" in f for f in s["nb_flags"]), s["nb_flags"]
    md = s["content"]
    for label in ("- **Name:**", "- **Covers:** full section",
                  "- **Capture method:** openleg-api-v3", "## STATE TEXT (verbatim)",
                  "PENDING HUMAN READ", "## CITATIONS"):
        assert label in md, "missing %r in candidate" % label
    assert "* NB Effective January 1, 2099" in _state_text_from_md(md)

    # EXISTING FULL-MATCH: feed the stored golden back as the live response.
    golden = fc.stored_state_text("source-exec-314-mwbe-cert-validity.md")

    def fake_existing_match(law, loc):
        return {"text": golden, "activeDate": "2026-02-20", "repealed": False}

    secs = capture(["EXC/314"], fake_existing_match, date, write=False)
    assert secs[0]["verdict"] == "FULL-MATCH", secs[0]
    assert secs[0]["content"] is None  # existing mode never writes

    # EXISTING DIVERGENT: mutate the live text -> human review, diff shown.
    def fake_existing_divergent(law, loc):
        return {"text": "* § 314. TOTALLY DIFFERENT amended text that no longer "
                        "matches the stored capture at all. 1. one. 2. two.",
                "activeDate": "2099-01-01", "repealed": False}

    secs = capture(["EXC/314"], fake_existing_divergent, date, write=False)
    assert secs[0]["verdict"] == "DIVERGENT", secs[0]
    assert secs[0]["diff"], "expected a diff for a DIVERGENT section"

    # Fail-closed cases -----------------------------------------------------
    def _expect_fail(fetcher, ids=("GCN/24",)):
        try:
            capture(list(ids), fetcher, date, write=False)
        except CaptureError:
            return True
        raise AssertionError("expected CaptureError, got success")

    assert _expect_fail(lambda l, s: {"text": ""})            # empty
    assert _expect_fail(lambda l, s: {"text": "   \\n  "})    # empty after reflow
    assert _expect_fail(lambda l, s: {"text": "§ 24. x"})     # truncated (too short)
    assert _expect_fail(lambda l, s: {"text": "1. no section heading here at all, "
                                               "this body never opens with a section "
                                               "sign so it reads as truncated."})

    def boom(law, loc):
        raise RuntimeError("simulated network failure")
    assert _expect_fail(boom)  # API error -> fail-closed, no fallback

    # unreadable NB flag
    bad_nb = ("§ 24. Placeholder body long enough to pass the length gate for "
              "the truncation check. 1. one.\\n** NB\\n")
    assert _expect_fail(lambda l, s: {"text": bad_nb})

    # unknown target rejected (whitelist)
    try:
        capture(["ZZZ/999"], fake_new, date, write=False)
    except CaptureError:
        pass
    else:
        raise AssertionError("expected unknown target to be rejected")

    # law_ids input validation
    for bad in ("gcn/24", "GCN 24", "GCN/24; rm -rf", "../etc/passwd", ""):
        try:
            parse_law_ids(bad)
        except CaptureError:
            pass
        else:
            raise AssertionError("expected %r to be rejected" % bad)
    assert parse_law_ids("GCN/24, GCN/25-A ,EXC/314") == ["GCN/24", "GCN/25-A", "EXC/314"]
    assert parse_law_ids("GCN/24,GCN/24") == ["GCN/24"]  # dedupe

    # Report renders for a mixed run without error.
    mixed = capture(["GCN/24"], fake_new, date, write=False) + \
        capture(["EXC/314"], fake_existing_divergent, date, write=False)
    rep = render_report(mixed, date)
    assert "PENDING HUMAN READ" in rep and "DIVERGENT" in rep
    assert "not verified golden" in rep.lower()

    # Full write path into a throwaway golden tree (atomicity + real files).
    _selftest_write(tempfile, fake_new, fake_existing_match)

    print("SELF-TEST: ALL PASS")
    print("  NEW formatting, EXISTING FULL-MATCH (no write), DIVERGENT diff,")
    print("  fail-closed (empty/truncated/API-error/unreadable-NB/unknown-target),")
    print("  input validation, report render, atomic write.")
    return 0


def _selftest_write(tempfile, fake_new, fake_existing_match):
    """Exercise the real write phase against a temp golden tree, and prove the
    atomic guarantee: a run that fails validation writes nothing."""
    global SOURCES_DIR, REPORT_DIR, REPO_ROOT
    orig = (SOURCES_DIR, REPORT_DIR, REPO_ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        REPO_ROOT = tmp
        SOURCES_DIR = os.path.join(tmp, "golden-copy", "sources")
        REPORT_DIR = os.path.join(tmp, "docs", "statute-capture")
        os.makedirs(SOURCES_DIR)
        try:
            capture(["GCN/24"], fake_new, "2099-01-01", write=True)
            written = os.path.join(SOURCES_DIR, "source-gcn-24-public-holidays.md")
            assert os.path.exists(written), "NEW candidate was not written"
            report = os.path.join(tmp, "docs", "statute-capture", "2099-01-01.md")
            assert os.path.exists(report), "report was not written"

            # Atomic fail-closed: GCN/25-A fails -> NOTHING new written this run.
            before = set(os.listdir(SOURCES_DIR))

            def one_ok_one_bad(law, loc):
                if loc == "24":
                    return fake_new(law, loc)
                return {"text": ""}  # GCN/25-A empty -> fail-closed
            try:
                capture(["GCN/25-A"], one_ok_one_bad, "2099-01-02", write=True)
            except CaptureError:
                pass
            else:
                raise AssertionError("expected fail-closed on empty GCN/25-A")
            after = set(os.listdir(SOURCES_DIR))
            assert before == after, "fail-closed run wrote a partial capture"
        finally:
            SOURCES_DIR, REPORT_DIR, REPO_ROOT = orig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description="Manual OpenLeg statute capture")
    ap.add_argument("--law-ids", help="comma-separated law ids, e.g. "
                    "'GCN/24,GCN/25-A,EXC/314'")
    ap.add_argument("--date", help="override capture date (YYYY-MM-DD)")
    ap.add_argument("--selftest", action="store_true",
                    help="run offline against synthesized responses (no key)")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    key = os.environ.get("NYSLEG_API_KEY")
    if not key:
        die("NYSLEG_API_KEY is not set (add it as a repo Actions secret). "
            "Fail-closed: no capture attempted.", code=2)

    try:
        law_ids = parse_law_ids(args.law_ids)
        date_str = args.date or datetime.date.today().isoformat()
        capture(law_ids, http_fetcher(key), date_str, write=True)
    except CaptureError as exc:
        die(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
