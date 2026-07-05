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

def _disposition(raw, status):
    """How a gated/non-citable engine-reachable source is resolved for the
    enforcement migration, from its PROVISION ELIGIBILITY markers:
      CLEARED_BY_PROVISION — a confident per-provision marker exists (the engine's
                             mechanical cite targets it), e.g. EXC/314 § 314(5)(a).
      INTERIM_VERIFY_GATE  — an interim gate (mixed/PARTIAL capture citable only
                             into VERIFY/attorney-gated pending clean recapture).
      GATED_LGRADE         — an L-grade source; citable only into VERIFY/attorney-
                             gated (a gating test should confirm the engine's use).
      BLOCKING             — none of the above: a genuine blocker.
    """
    if gs.has_confident_provision(raw):
        return "CLEARED_BY_PROVISION"
    if gs.has_interim_verify_marker(raw):
        return "INTERIM_VERIFY_GATE"
    if status == gs.L_GRADE_INTERPRETIVE:
        return "GATED_LGRADE"
    return "BLOCKING"


def engine_citation_reach(status_by_file, raw_by_file):
    """Golden sources referenced in engine/validator code whose whole-file status
    is L-grade or non-citable, each tagged with its enforcement disposition
    (from PROVISION ELIGIBILITY markers). Heuristic static scan of source-*.md
    literals in the code."""
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
                            "referenced_in": sorted(files),
                            "disposition": _disposition(raw_by_file.get(fn, ""), status)})
    return flagged


# Enumerated exclusions for the bare-cite ban: runtime `.cite(` call sites under
# engine/ + validator.py that are DELIBERATELY bare (no output_context) and are
# therefore not counted as unmigrated. Each entry is "<relpath>:<line>" and MUST
# carry a justification here — the ban is an allowlist, not a heuristic, so a new
# bare cite fails the scan unless it is explicitly enumerated below. The
# enforcement migration left NONE: all three former sites (engine/citation.py
# verify_golden, engine/payment_clock.py holiday anchor, validator.py _f) now pass
# an explicit output_context, so this allowlist is intentionally empty.
BARE_CITE_ALLOWLIST = frozenset()


def unmigrated_cite_sites():
    """Runtime cite() call sites under engine/ + validator.py that do NOT pass an
    output_context (so the runtime guardrail is bypassed) AND are not in the
    enumerated BARE_CITE_ALLOWLIST. While any remain, the enforcement migration is
    incomplete — end-to-end enforcement is NOT claimed. Heuristic for the bare
    call: a `.cite(` with no `output_context` within the next 400 chars; the
    allowlist is the exact-enumeration escape hatch for a deliberately bare site."""
    sites = []
    for path in ENGINE_SCAN_FILES:
        try:
            code = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for m in re.finditer(r"\.cite\(", code):
            window = code[m.start():m.start() + 400].split("\n\n", 1)[0]
            if "output_context" in window:
                continue
            relpath = os.path.relpath(path, REPO_ROOT)
            line = code[:m.start()].count("\n") + 1
            if ("%s:%d" % (relpath, line)) in BARE_CITE_ALLOWLIST:
                continue
            sites.append({"file": relpath, "line": line})
    return sites


# ---- run ------------------------------------------------------------------

def run():
    files = sorted(os.path.basename(p) for p in
                   glob.glob(os.path.join(SOURCES_DIR, "source-*.md")))
    freshness, fresh_report = load_latest_freshness()
    idx, rpt = index_files(), report_files()
    results = []
    raw_by_file = {}
    for fn in files:
        raw = open(os.path.join(SOURCES_DIR, fn), encoding="utf-8").read()
        raw_by_file[fn] = raw
        results.append(audit_source(fn, raw, fn in idx, fn in rpt, freshness))
    status_by_file = {r["file"]: r["status"] for r in results}
    reach = engine_citation_reach(status_by_file, raw_by_file)

    # Finding classes (audit contract):
    #  * hard_failures        — block merge (unparseable / missing INDEX or
    #    REPORT row / no derivable status).
    #  * blocking_to_enforcement — engine/validator citations reaching a source
    #    that is NOT resolved for enforcement (disposition BLOCKING). A source
    #    with a confident per-provision marker (CLEARED_BY_PROVISION), an interim
    #    VERIFY gate (INTERIM_VERIFY_GATE), or L-grade gated use (GATED_LGRADE) is
    #    NOT a blocker — those are tracked separately below.
    #  * advisory             — everything else (metadata gaps that don't block).
    hard_failures = [{"file": r["file"], "findings": r["findings"]}
                     for r in results if r["hard_fail"]]
    by_disp = lambda d: [e for e in reach if e["disposition"] == d]
    blocking = by_disp("BLOCKING")
    cleared_by_provision = by_disp("CLEARED_BY_PROVISION")
    interim_verify_gate = by_disp("INTERIM_VERIFY_GATE")
    gated_lgrade = by_disp("GATED_LGRADE")
    reach_files = {e["file"] for e in reach}
    advisory = []
    for r in results:
        if r["hard_fail"]:
            continue
        for f in r["findings"]:
            advisory.append({"file": r["file"], "finding": f,
                             "also_blocking_to_enforcement": r["file"] in
                             {e["file"] for e in blocking}})

    # End-to-end enforcement requires BOTH: no blocking findings AND every
    # runtime cite() call site migrated to an output_context. Micro-PR A is
    # source-structure only, so migration is deliberately still pending.
    unmigrated = unmigrated_cite_sites()
    return {
        "discovered_count": len(files),
        "freshness_report_used": fresh_report,
        "results": results,
        "engine_citation_reach": reach,
        "hard_failures": hard_failures,
        "blocking_to_enforcement": blocking,
        "cleared_by_provision": cleared_by_provision,
        "interim_verify_gate": interim_verify_gate,
        "gated_lgrade": gated_lgrade,
        "advisory": advisory,
        "unmigrated_cite_sites": unmigrated,
        "bare_cite_allowlist": sorted(BARE_CITE_ALLOWLIST),
        "enforcement_complete": len(blocking) == 0 and len(unmigrated) == 0,
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
    L.append("Finding classes:")
    L.append("  (1) HARD FAILURES (block merge): %d" % len(report["hard_failures"]))
    for h in report["hard_failures"]:
        L.append("      - %s: %s" % (h["file"], "; ".join(h["findings"])))
    L.append("  (2) BLOCKING-TO-ENFORCEMENT (engine citations reaching a source "
             "NOT resolved for enforcement — block the migration, NOT advisory): "
             "%d" % len(report["blocking_to_enforcement"]))
    for e in report["blocking_to_enforcement"]:
        L.append("      - %s (%s) reachable via bare cite() in %s"
                 % (e["file"], e["status"], ", ".join(e["referenced_in"])))
    L.append("  (2a) RESOLVED engine-reachable sources (tracked, not blocking):")
    for e in report["cleared_by_provision"]:
        L.append("      - CLEARED  %s (%s) — confident per-provision marker; %s"
                 % (e["file"], e["status"], ", ".join(e["referenced_in"])))
    for e in report["interim_verify_gate"]:
        L.append("      - INTERIM  %s (%s) — interim VERIFY gate (VERIFY/attorney-"
                 "gated only, pending clean recapture); %s"
                 % (e["file"], e["status"], ", ".join(e["referenced_in"])))
    for e in report["gated_lgrade"]:
        L.append("      - GATED    %s (%s) — L-grade, cite only into VERIFY/attorney-"
                 "gated (confirm with a gating test); %s"
                 % (e["file"], e["status"], ", ".join(e["referenced_in"])))
    L.append("  (3) ADVISORY (metadata gaps; do not block): %d"
             % len(report["advisory"]))
    for a in report["advisory"]:
        tag = " [also blocking-to-enforcement]" if a["also_blocking_to_enforcement"] else ""
        L.append("      - %s: %s%s" % (a["file"], a["finding"], tag))
    L.append("")
    L.append("-" * 78)
    L.append("HARD FAILURES: %d (merge gate)   |   BLOCKING-TO-ENFORCEMENT: %d   "
             "|   ADVISORY: %d"
             % (len(report["hard_failures"]), len(report["blocking_to_enforcement"]),
                len(report["advisory"])))
    unmig = report.get("unmigrated_cite_sites", [])
    L.append("MIGRATION: %d runtime cite() site(s) still bypass the guardrail "
             "(no output_context)%s"
             % (len(unmig),
                (": " + ", ".join("%s:%d" % (s["file"], s["line"]) for s in unmig))
                if unmig else ""))
    L.append("CITATION ELIGIBILITY ENFORCED END-TO-END: %s"
             % ("YES — no blocking-to-enforcement findings AND the bare-cite scan "
                "is clean (every runtime cite() site under engine/ + validator.py "
                "passes an explicit output_context; enumerated bare-cite "
                "exclusions: %d)." % len(report.get("bare_cite_allowlist", []))
                if report["enforcement_complete"] else
                "NO — findings are now detectable and the four blockers are "
                "cleared/downgraded (per-provision markers + interim VERIFY gates), "
                "but the call-site migration has NOT run: %d runtime cite() site(s) "
                "still bypass the guardrail via bare cite(). Migration is a "
                "follow-up (see BACKLOG)." % len(unmig)))
    L.append("RESULT (merge gate = hard failures only): %s"
             % ("FAIL" if hard else "PASS"))
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
