#!/usr/bin/env python3
"""
Phase 2, Step 1 — NYS Procurement Vendor: Golden-Copy Parser + Integrity Check.

Parses every verbatim `source-*.md` file in the golden copy, extracts and
asserts the four header labels (Name, Date, Issued by, Link) plus the
"Copied exactly on" stamp, captures the `## STATE TEXT (verbatim)` body and the
`## CITATIONS ...` section verbatim, and cross-checks the parsed file count
against the golden-copy INDEX and the VERIFICATION-REPORT (all three must be 37).

Design constraints (per spec):
  * Read markdown EXACTLY as written. No reinterpretation or paraphrasing.
  * Do not guess or infer missing fields.
  * On a malformed file: print the filename + reason, collect the failure, skip.
  * Print BOTH a human-readable report and a machine-readable JSON summary.
  * Exit 0 if every check passes, 1 if any check fails.

Run:
    python3 parse_golden_copy.py
"""

import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Configuration / constants
# ---------------------------------------------------------------------------

EXPECTED_COUNT = 44

# The four required header labels plus the copy stamp. "Link" is matched by a
# prefix because the source files carry several verbatim variants of the label
# (e.g. "Link (permanent identifier)", "Link (PDF)", "Link (primary)").
REQUIRED_FIELDS = ["Name", "Date", "Issued by", "Link", "Copied exactly on"]

# Structural section heading markers. These bound the verbatim body. They are
# matched as exact heading prefixes so that web-page subheadings copied *inside*
# the verbatim body (e.g. "## Contact", "## Get Certified") are NOT treated as
# section boundaries and remain part of the body, exactly as written.
H_STATE_TEXT = "## STATE TEXT (verbatim)"
H_CITATIONS = "## CITATIONS"          # full: "## CITATIONS THIS TEXT POINTS TO ..."
H_AGENCY_GUIDANCE = "## AGENCY GUIDANCE"  # non-verbatim overlay; ends the body

# A header label line, e.g.  - **Issued by:** New York State Legislature
LABEL_RE = re.compile(r"^- \*\*(?P<label>[^:*]+):\*\*\s?(?P<value>.*)$")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def find_golden_copy_root():
    """Locate the directory that contains `sources/`, the INDEX and the report.

    Tries, in order: the directory holding this script, then `/mnt/project`
    (the deployment path named in the spec). Returns the first that contains a
    `golden-copy/sources` tree, else None.
    """
    candidates = [
        os.path.dirname(os.path.abspath(__file__)),
        "/mnt/project",
    ]
    for base in candidates:
        sources = os.path.join(base, "golden-copy", "sources")
        if os.path.isdir(sources):
            return os.path.join(base, "golden-copy")
    return None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class ParseFailure(Exception):
    """Raised when a single source file is malformed."""


def parse_source_file(path):
    """Parse one `source-*.md` file.

    Returns a dict with the extracted fields. Raises ParseFailure (with a
    human-readable reason) if the file is malformed in any way.
    """
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.split("\n")

    # -- Locate the structural section headings ----------------------------
    idx_state = None
    idx_citations = None
    idx_agency = None
    for i, line in enumerate(lines):
        if idx_state is None and line.startswith(H_STATE_TEXT):
            idx_state = i
        elif idx_citations is None and line.startswith(H_CITATIONS):
            idx_citations = i
        elif idx_agency is None and line.startswith(H_AGENCY_GUIDANCE):
            idx_agency = i

    if idx_state is None:
        raise ParseFailure("missing '## STATE TEXT (verbatim)' section")
    if idx_citations is None:
        raise ParseFailure("missing '## CITATIONS ...' section")
    if idx_citations < idx_state:
        raise ParseFailure("'## CITATIONS' appears before '## STATE TEXT'")

    # -- Header labels (everything above the STATE TEXT heading) -----------
    # A label's value may be inline (`- **Link:** http://...`) OR carried on
    # the indented continuation lines that follow it (e.g. `- **Link (primary):**`
    # followed by an indented sub-bullet list of URLs, as in stf-109). We read
    # exactly as written: the value is the inline text plus every following
    # indented (whitespace-led) line, joined into one string.
    fields = {}
    header_lines = lines[:idx_state]
    i = 0
    while i < len(header_lines):
        m = LABEL_RE.match(header_lines[i])
        if not m:
            i += 1
            continue
        label = m.group("label").strip()
        parts = [m.group("value").strip()]
        # Gather indented continuation lines belonging to this label. Stop at a
        # blank line, the next label line, or any non-indented content.
        j = i + 1
        while j < len(header_lines):
            nxt = header_lines[j]
            if nxt.strip() == "" or not (nxt.startswith(" ") or nxt.startswith("\t")):
                break
            parts.append(nxt.strip())
            j += 1
        value = "\n".join(p for p in parts if p).strip()
        # Normalise the variable "Link (...)" label to the canonical "Link".
        key = "Link" if label.startswith("Link") else label
        # Keep the first occurrence; do not let later lines clobber it.
        fields.setdefault(key, value)
        i = j

    missing = [f for f in REQUIRED_FIELDS if f not in fields]
    if missing:
        raise ParseFailure("missing header label(s): " + ", ".join(missing))
    empty = [f for f in REQUIRED_FIELDS if not fields[f].strip()]
    if empty:
        raise ParseFailure("empty header label(s): " + ", ".join(empty))

    # -- STATE TEXT (verbatim) body ----------------------------------------
    # Body runs from just after the STATE TEXT heading up to the first
    # structural boundary that follows it: CITATIONS, or an AGENCY GUIDANCE
    # overlay if one appears earlier. Web-page subheadings inside the body are
    # intentionally preserved (not treated as boundaries).
    body_end = idx_citations
    if idx_agency is not None and idx_state < idx_agency < body_end:
        body_end = idx_agency
    body = "\n".join(lines[idx_state + 1:body_end]).strip()
    if not body:
        raise ParseFailure("'## STATE TEXT (verbatim)' body is empty")

    # -- CITATIONS section (verbatim, heading through end of file) ---------
    citations = "\n".join(lines[idx_citations:]).strip()
    if not citations:
        raise ParseFailure("'## CITATIONS' section is empty")

    return {
        "file": os.path.basename(path),
        "name": fields["Name"],
        "date": fields["Date"],
        "issued_by": fields["Issued by"],
        "link": fields["Link"],
        "copied_on": fields["Copied exactly on"],
        "body_chars": len(body),
        "citations_chars": len(citations),
    }


# ---------------------------------------------------------------------------
# Cross-check counts
# ---------------------------------------------------------------------------

def count_index_entries(index_path):
    """Count entries in golden-copy-INDEX.md.

    Each entry carries exactly one `- **Verbatim file:**` line pointing at a
    `sources/source-*.md` path. We count those lines.
    """
    if not os.path.isfile(index_path):
        return None
    with open(index_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    return len(re.findall(r"^- \*\*Verbatim file:\*\*", text, flags=re.MULTILINE))


def count_verification_rows(report_path):
    """Count data rows in VERIFICATION-REPORT.md.

    Result tables list one markdown row per file. We count table rows that
    reference a `source-*.md` filename, which excludes header and separator
    rows automatically.
    """
    if not os.path.isfile(report_path):
        return None
    with open(report_path, "r", encoding="utf-8") as fh:
        text = fh.read()
    rows = 0
    for line in text.split("\n"):
        if line.startswith("|") and re.search(r"source-[A-Za-z0-9.\-]+\.md", line):
            rows += 1
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("NYS Procurement Vendor — Golden-Copy Parser + Integrity Check")
    print("=" * 72)

    root = find_golden_copy_root()
    if root is None:
        print("FATAL: could not locate a 'golden-copy/sources' directory.")
        print("       Looked next to this script and in /mnt/project.")
        print(json.dumps({"status": "FAIL", "reason": "golden-copy not found"}))
        return 1

    sources_dir = os.path.join(root, "sources")
    index_path = os.path.join(root, "golden-copy-INDEX.md")
    report_path = os.path.join(root, "VERIFICATION-REPORT.md")
    print("Golden-copy root : {}".format(root))
    print("Sources dir      : {}".format(sources_dir))
    print()

    # -- Discover source files ---------------------------------------------
    source_files = sorted(
        os.path.join(sources_dir, n)
        for n in os.listdir(sources_dir)
        if n.startswith("source-") and n.endswith(".md")
    )
    print("Discovered {} source-*.md file(s).".format(len(source_files)))
    print("-" * 72)

    # -- Parse each file ----------------------------------------------------
    parsed = []
    failures = []  # list of {file, reason}
    for path in source_files:
        name = os.path.basename(path)
        try:
            rec = parse_source_file(path)
        except ParseFailure as exc:
            failures.append({"file": name, "reason": str(exc)})
            print("  [FAIL] {}: {}".format(name, exc))
            continue
        except Exception as exc:  # unexpected read/parse error — still collect
            failures.append({"file": name, "reason": "unexpected error: {}".format(exc)})
            print("  [FAIL] {}: unexpected error: {}".format(name, exc))
            continue
        parsed.append(rec)
        print("  [ OK ] {:<48} body={:>6}c  citations={:>5}c".format(
            name, rec["body_chars"], rec["citations_chars"]))

    print("-" * 72)
    print("Parsed OK : {}".format(len(parsed)))
    print("Failed    : {}".format(len(failures)))
    print()

    # -- Count checks -------------------------------------------------------
    index_count = count_index_entries(index_path)
    report_count = count_verification_rows(report_path)

    checks = []

    def record(label, actual, ok, detail=""):
        checks.append({"check": label, "actual": actual, "passed": ok, "detail": detail})
        status = "PASS" if ok else "FAIL"
        line = "  [{}] {:<34} expected={} actual={}".format(
            status, label, EXPECTED_COUNT, actual)
        if detail:
            line += "  ({})".format(detail)
        print(line)

    print("Integrity counts (each must equal {}):".format(EXPECTED_COUNT))

    no_failures = len(failures) == 0
    record("source files parsed", len(parsed),
           len(parsed) == EXPECTED_COUNT and no_failures,
           "" if no_failures else "{} file(s) malformed".format(len(failures)))

    if index_count is None:
        record("golden-copy-INDEX.md entries", "missing", False, "file not found")
    else:
        record("golden-copy-INDEX.md entries", index_count, index_count == EXPECTED_COUNT)

    if report_count is None:
        record("VERIFICATION-REPORT.md rows", "missing", False, "file not found")
    else:
        record("VERIFICATION-REPORT.md rows", report_count, report_count == EXPECTED_COUNT)

    print()

    all_passed = no_failures and all(c["passed"] for c in checks)

    # -- Human-readable verdict --------------------------------------------
    print("=" * 72)
    if all_passed:
        print("RESULT: PASS — all {} files parsed and all counts match {}.".format(
            EXPECTED_COUNT, EXPECTED_COUNT))
    else:
        print("RESULT: FAIL — see mismatches above.")
        if failures:
            print("Malformed files:")
            for f in failures:
                print("  - {}: {}".format(f["file"], f["reason"]))
        for c in checks:
            if not c["passed"]:
                print("  - count mismatch: {} = {} (expected {})".format(
                    c["check"], c["actual"], EXPECTED_COUNT))
    print("=" * 72)

    # -- Machine-readable JSON summary -------------------------------------
    summary = {
        "status": "PASS" if all_passed else "FAIL",
        "expected_count": EXPECTED_COUNT,
        "counts": {
            "source_files_discovered": len(source_files),
            "source_files_parsed": len(parsed),
            "source_files_failed": len(failures),
            "index_entries": index_count,
            "verification_rows": report_count,
        },
        "checks": checks,
        "failures": failures,
        "files": [
            {
                "file": r["file"],
                "name": r["name"],
                "date": r["date"],
                "issued_by": r["issued_by"],
                "link": r["link"],
                "copied_on": r["copied_on"],
                "body_chars": r["body_chars"],
                "citations_chars": r["citations_chars"],
            }
            for r in parsed
        ],
    }
    print()
    print("--- JSON SUMMARY ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
