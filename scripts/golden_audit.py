#!/usr/bin/env python3
"""
scripts/golden_audit.py — Golden Copy Reliability Audit (CI-runnable).

Audits every golden source for citation eligibility and metadata integrity. It
does NOT re-implement the freshness diff; it CONSUMES the latest freshness report
(docs/freshness/*.md) for DIVERGENT / sunset-stale signals, and reuses the same
parser (parse_golden_copy) and status derivation (engine/golden_status) the
runtime guardrail uses.

Per source it checks:
  * source / API URL present (a Link line);
  * capture date present (Copied exactly on);
  * Covers field present;
  * STATE TEXT block parseable (parse_golden_copy);
  * an INDEX entry exists (a `Verbatim file:` line);
  * a VERIFICATION-REPORT row exists;
  * NB/repeal flags preserved where the source is a sunset statute;
  * effective-date metadata (API activeDate) where the source is API-captured;
  * a derivable explicit status (else a finding);
  * L-grade provisions listed separately from the verified text.

It also statically reports engine/validator citations that reach L-grade or
non-citable sources (for human review), and prints the discovered source count,
per-source pass/fail, and all findings. Exit code is non-zero on any HARD
failure (unparseable source, missing INDEX entry / REPORT row, or no derivable
status).

    python3 scripts/golden_audit.py            # human report
    python3 scripts/golden_audit.py --json out.json
"""

import argparse
import glob
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from engine import golden_status as gs  # noqa: E402
import parse_golden_copy as pg  # noqa: E402

SOURCES_DIR = os.path.join(REPO_ROOT, "golden-copy", "sources")
INDEX_PATH = os.path.join(REPO_ROOT, "golden-copy", "golden-copy-INDEX.md")
REPORT_PATH = os.path.join(REPO_ROOT, "golden-copy", "VERIFICATION-REPORT.md")
FRESHNESS_DIR = os.path.join(REPO_ROOT, "docs", "freshness")
ENGINE_SCAN_FILES = (
    glob.glob(os.path.join(REPO_ROOT, "engine", "*.py"))
    + [os.path.join(REPO_ROOT, "validator.py")])

_MONTHS = None  # unused; kept minimal


# ---- freshness consumption ------------------------------------------------

def load_latest_freshness():
    """Parse the most recent docs/freshness/*.md report into
    {source_file: (verdict, sunset_stale)}. Empty if none exists."""
    # Only dated freshness reports (YYYY-MM-DD.md); ignore README.md etc.
    reports = sorted(p for p in glob.glob(os.path.join(FRESHNESS_DIR, "*.md"))
                     if re.match(r"\d{4}-\d{2}-\d{2}\.md$", os.path.basename(p)))
    if not reports:
        return {}, None
    path = reports[-1]
    text = open(path, encoding="utf-8").read()
    out = {}
    # per-source rows: "| <short> | <law> | <verdict> | ... | <sunset flags> |"
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        short, verdict, sunset = cells[0], cells[2], cells[-1]
        if short in ("source", "verdict") or set(short) <= set("-"):
            continue
        fn = "source-%s.md" % short
        out[fn] = (verdict, sunset not in ("", "—", "-"))
    return out, os.path.basename(path)


# ---- per-source signals ---------------------------------------------------

def _has(raw, label_re):
    return bool(re.search(label_re, raw, re.M))


def index_files():
    if not os.path.isfile(INDEX_PATH):
        return set()
    text = open(INDEX_PATH, encoding="utf-8").read()
    return set(re.findall(r"sources/(source-[A-Za-z0-9.\-]+\.md)", text))


def report_files():
    if not os.path.isfile(REPORT_PATH):
        return set()
    text = open(REPORT_PATH, encoding="utf-8").read()
    files = set()
    for line in text.split("\n"):
        if line.startswith("|"):
            files.update(re.findall(r"source-[A-Za-z0-9.\-]+\.md", line))
    return files


def audit_source(fn, raw, in_index, in_report, freshness):
    """Return a per-source dict: status, checks (name->bool), findings, hard_fail."""
    findings = []
    checks = {}

    # structural / metadata presence
    checks["link_present"] = _has(raw, r"^- \*\*Link[^:*]*:\*\*\s*\S")
    checks["capture_date_present"] = _has(raw, r"^- \*\*Copied exactly on:\*\*\s*\S")
    checks["covers_present"] = _has(raw, r"^- \*\*Covers[^:*]*:\*\*\s*\S")

    # STATE TEXT parseable (reuse the canonical parser)
    parse_ok = True
    try:
        pg.parse_source_file(os.path.join(SOURCES_DIR, fn))
    except Exception as exc:  # ParseFailure or unexpected
        parse_ok = False
        findings.append("STATE TEXT not parseable: %s" % exc)
    checks["state_text_parseable"] = parse_ok

    checks["index_entry_exists"] = in_index
    if not in_index:
        findings.append("no INDEX entry (golden-copy-INDEX.md)")
    checks["verification_row_exists"] = in_report
    if not in_report:
        findings.append("no VERIFICATION-REPORT row")

    # API-captured sources should carry an effective-date (API activeDate)
    api_captured = "openleg-api-v3" in raw or _has(raw, r"^- \*\*API activeDate:\*\*")
    if api_captured:
        ok = _has(raw, r"^- \*\*API activeDate:\*\*\s*\S")
        checks["effective_date_metadata"] = ok
        if not ok:
            findings.append("API-captured but missing API activeDate metadata")

    # sunset statutes must preserve NB/repeal flags in the STATE TEXT
    is_sunset = bool(re.search(r"sunset_watch:\s*true|NB Repealed", raw, re.I))
    if is_sunset:
        nb_ok = bool(re.search(r"^\*+\s*NB\b", raw, re.M))
        checks["nb_flags_preserved"] = nb_ok
        if not nb_ok:
            findings.append("sunset statute but no NB/repeal flag in STATE TEXT")

    # derived status
    verdict, stale = freshness.get(fn, (None, False))
    status, reasons = gs.derive_status(raw, freshness_verdict=verdict,
                                       sunset_stale=stale)
    checks["status_derivable"] = status is not None
    if status is None:
        findings.append("no derivable status: %s" % "; ".join(reasons))

    # L-grade provisions must be listed separately (annotation present)
    lgrade = gs.lgrade_provisions(raw)
    if status == gs.L_GRADE_INTERPRETIVE and not lgrade:
        findings.append("L-grade status but no separately-listed GRADE annotation")

    hard_fail = (not parse_ok) or (not in_index) or (not in_report) or (status is None)
    return {
        "file": fn, "status": status, "status_reasons": reasons,
        "checks": checks, "findings": findings, "hard_fail": hard_fail,
        "lgrade_provisions": lgrade,
        "freshness_verdict": verdict,
    }


# ---- static engine-citation reachability ----------------------------------

def engine_citation_reach(status_by_file):
    """Report golden sources referenced in engine/validator code whose status is
    L-grade or non-citable — for human review of citation context. Heuristic
    static scan of source-*.md literals in the code."""
    reach = {}
    for path in ENGINE_SCAN_FILES:
        try:
            code = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for fn in set(re.findall(r"source-[A-Za-z0-9.\-]+\.md", code)):
            reach.setdefault(fn, set()).add(os.path.relpath(path, REPO_ROOT))
    flagged = []
    for fn, files in sorted(reach.items()):
        status = status_by_file.get(fn)
        if status in gs.CITABLE_GATED_ONLY or status in gs.NOT_CITABLE:
            flagged.append({"file": fn, "status": status,
                            "referenced_in": sorted(files)})
    return flagged


# ---- run ------------------------------------------------------------------

def run():
    files = sorted(os.path.basename(p) for p in
                   glob.glob(os.path.join(SOURCES_DIR, "source-*.md")))
    freshness, fresh_report = load_latest_freshness()
    idx, rpt = index_files(), report_files()
    results = []
    for fn in files:
        raw = open(os.path.join(SOURCES_DIR, fn), encoding="utf-8").read()
        results.append(audit_source(fn, raw, fn in idx, fn in rpt, freshness))
    status_by_file = {r["file"]: r["status"] for r in results}
    reach = engine_citation_reach(status_by_file)
    return {
        "discovered_count": len(files),
        "freshness_report_used": fresh_report,
        "results": results,
        "engine_citation_reach": reach,
    }


def render(report):
    L = []
    L.append("=" * 78)
    L.append("GOLDEN COPY RELIABILITY AUDIT")
    L.append("=" * 78)
    L.append("Discovered sources : %d" % report["discovered_count"])
    L.append("Freshness report   : %s" % (report["freshness_report_used"] or
                                          "(none found — DIVERGENT/STALE not overlaid)"))
    counts = {}
    for r in report["results"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    L.append("")
    L.append("Status tally:")
    for s in gs.ALL_STATUSES + (None,):
        if counts.get(s):
            L.append("  %-28s %d" % (s or "(no derivable status)", counts[s]))
    L.append("")
    hard = [r for r in report["results"] if r["hard_fail"]]
    findings = [r for r in report["results"] if r["findings"]]
    L.append("Per-source:")
    for r in report["results"]:
        mark = "FAIL" if r["hard_fail"] else ("warn" if r["findings"] else " ok ")
        L.append("  [%s] %-48s %s" % (mark, r["file"], r["status"]))
        for f in r["findings"]:
            L.append("        - %s" % f)
    L.append("")
    if report["engine_citation_reach"]:
        L.append("Engine/validator citations to L-grade or non-citable sources "
                 "(review citation context):")
        for e in report["engine_citation_reach"]:
            L.append("  - %s (%s) referenced in %s"
                     % (e["file"], e["status"], ", ".join(e["referenced_in"])))
        L.append("")
    L.append("-" * 78)
    L.append("HARD FAILURES: %d   |   sources with findings: %d"
             % (len(hard), len(findings)))
    L.append("RESULT: %s" % ("FAIL" if hard else "PASS"))
    L.append("=" * 78)
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Golden Copy Reliability Audit")
    ap.add_argument("--json", help="write the full report as JSON to this path")
    args = ap.parse_args(argv)
    report = run()
    print(render(report))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, default=lambda o: sorted(o)
                      if isinstance(o, set) else str(o))
    return 1 if any(r["hard_fail"] for r in report["results"]) else 0


if __name__ == "__main__":
    sys.exit(main())
