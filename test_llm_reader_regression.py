#!/usr/bin/env python3
"""
Regression harness for llm_reader.py.

Runs llm_reader against a fixed set of tenders and reports, per tender:
  - total requirement count
  - category breakdown (count per category)
  - MWBE line present (y/n)
  - Appendix-A / standard-clause items surfaced

Usage:
  python3 test_llm_reader_regression.py [--json]

The two real tenders are treated as merged inputs:
  mediation RFP  = rfp25003mediation.pdf + rfp25003submissiontemplate.pdf
  vehicle IFB    = ifb25001vehiclemodification.pdf + ifb25001submissiondocuments.pdf
"""

import json
import sys
from collections import Counter
from pathlib import Path

from tender_extractor import extract as _extract

# llm_reader pulls in the optional `anthropic` SDK at import. When that package
# isn't installed (e.g. a minimal CI container), skip this suite cleanly rather
# than hard-failing on an environment issue — the checks below are unchanged and
# still run in full whenever the dependency IS present.
try:
    from llm_reader import read_requirements, render_checklist
    _LLM_READER_AVAILABLE = True
    _LLM_READER_IMPORT_ERROR = None
except ImportError as _exc:  # ModuleNotFoundError is a subclass
    read_requirements = render_checklist = None
    _LLM_READER_AVAILABLE = False
    _LLM_READER_IMPORT_ERROR = _exc

# Known Appendix-A standard clauses (statute key → display label).
APPENDIX_A_STATUTES = {
    "prevailing wage": "Prevailing Wage (Labor Law §220)",
    "220-i": "NYSDOL Cert of Registration (Labor Law §220-i)",
    "workers' comp": "Workers' Compensation (WCL §57)",
    "wcl": "Workers' Compensation (WCL §57)",
    "non-collusion": "Non-Collusion (§139-d)",
    "139-d": "Non-Collusion (§139-d)",
    "iran divestment": "Iran Divestment (§165-a)",
    "165-a": "Iran Divestment (§165-a)",
    "sexual harassment": "Sexual Harassment (§139-l)",
    "139-l": "Sexual Harassment (§139-l)",
    "gender-based violence": "Gender-Based Violence (§139-m)",
    "139-m": "Gender-Based Violence (§139-m)",
    "tax law 5-a": "Sales Tax Cert (Tax Law §5-a)",
    "5-a": "Sales Tax Cert (Tax Law §5-a)",
    "international boycott": "International Boycott (§139-h)",
    "139-h": "International Boycott (§139-h)",
    "vendrep": "Vendor Responsibility (VendRep)",
    "vendor responsibility": "Vendor Responsibility (VendRep)",
    "prompt payment": "Prompt Payment Interest",
    "mwbe": "MWBE (§316)",
    "sdvob": "SDVOB",
}


def _merge_extract(paths):
    """Extract multiple PDFs and merge their pages into one structure."""
    merged_pages = []
    source_labels = []
    for p in paths:
        if not Path(p).exists():
            raise FileNotFoundError(p)
        r = _extract(p)
        merged_pages.extend(r.get("pages", []))
        source_labels.append(Path(p).name)
    return {
        "pages": merged_pages,
        "has_text_layer": True,
        "source": " + ".join(source_labels),
    }


def _find_appendix_a(requirements):
    """Return list of matched Appendix-A labels for the given requirements list."""
    found = {}
    for req in requirements:
        text = " ".join([
            req.get("item", ""),
            req.get("requirement", ""),
            req.get("source_quote", ""),
            req.get("category", ""),
        ]).lower()
        for key, label in APPENDIX_A_STATUTES.items():
            if key in text and label not in found.values():
                found[key] = label
    return sorted(set(found.values()))


def _has_mwbe_line(requirements):
    """True if there is at least one requirement whose category is 'MWBE' or
    whose item/requirement mentions MWBE independently (not folded into another)."""
    for req in requirements:
        cat = req.get("category", "").upper()
        item = req.get("item", "").upper()
        if cat == "MWBE" or "MWBE" in item:
            return True
    return False


def _find_verify_flags(requirements):
    """Return list of (item, requirement) tuples where the model flagged
    applicability uncertainty. Uses prefix match so both the bare token
    '[verify applicability]' and extended forms like
    '[verify applicability – <reason>]' are caught."""
    MARKER = "[verify applicability"
    flags = []
    for req in requirements:
        if MARKER in req.get("requirement", ""):
            flags.append((req.get("item", "(unnamed)"), req.get("requirement", "")))
    return flags


def _report_tender(label, extracted):
    parsed, meta = read_requirements(extracted)
    if parsed is None:
        return {"label": label, "error": str(meta)}

    reqs = parsed.get("requirements", [])
    cat_counts = Counter(r.get("category", "unknown") for r in reqs)
    appendix_a = _find_appendix_a(reqs)
    mwbe_present = _has_mwbe_line(reqs)
    verify_flags = _find_verify_flags(reqs)

    return {
        "label": label,
        "tender_title": parsed.get("tender_title"),
        "submission_deadline": parsed.get("submission_deadline"),
        "total_requirements": len(reqs),
        "category_breakdown": dict(sorted(cat_counts.items())),
        "mwbe_line_present": mwbe_present,
        "appendix_a_surfaced": appendix_a,
        "verify_applicability_flags": verify_flags,
        "meta": meta,
    }


def _print_report(result):
    if "error" in result:
        print("  ERROR: {}".format(result["error"]))
        return
    print("  Title:        {}".format(result.get("tender_title") or "(not extracted)"))
    print("  Deadline:     {}".format(result.get("submission_deadline") or "(not extracted)"))
    print("  Total reqs:   {}".format(result["total_requirements"]))
    print("  MWBE line:    {}".format("YES" if result["mwbe_line_present"] else "NO"))
    flags = result.get("verify_applicability_flags", [])
    print("  [verify applicability] flags: {}".format(len(flags)))
    for item, req in flags:
        print("    → {}".format(item))
    print("  Category breakdown:")
    for cat, n in result["category_breakdown"].items():
        print("    {:30s} {}".format(cat, n))
    print("  Appendix A / standard clauses surfaced:")
    for clause in result["appendix_a_surfaced"]:
        print("    - {}".format(clause))
    if not result["appendix_a_surfaced"]:
        print("    (none detected)")
    m = result["meta"]
    print("  Tokens: in={} out={} stop={}".format(
        m["input_tokens"], m["output_tokens"], m["stop_reason"]))


TENDERS = [
    {
        "label": "sample-tender (Facilities Maintenance IFB)",
        "files": ["sample-tender.pdf"],
    },
    {
        "label": "RFP-25-003 Mediation Services RFP",
        "files": [
            "test-tenders/rfp25003mediation.pdf",
            "test-tenders/rfp25003submissiontemplate.pdf",
        ],
    },
    {
        "label": "IFB-25-001 Vehicle Modification IFB",
        "files": [
            "test-tenders/ifb25001vehiclemodification.pdf",
            "test-tenders/ifb25001submissiondocuments.pdf",
        ],
    },
]


def main():
    if not _LLM_READER_AVAILABLE:
        print("SKIP: test_llm_reader_regression — optional dependency unavailable "
              "({}). Install the 'anthropic' package to run this suite.".format(
                  _LLM_READER_IMPORT_ERROR))
        return 0

    as_json = "--json" in sys.argv
    results = []
    for spec in TENDERS:
        print("\nRunning: {} ...".format(spec["label"]), flush=True)
        extracted = _merge_extract(spec["files"])
        result = _report_tender(spec["label"], extracted)
        results.append(result)
        if not as_json:
            print()
            print("=" * 70)
            print("  {}".format(spec["label"]))
            print("=" * 70)
            _print_report(result)

    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        for r in results:
            if "error" in r:
                print("  {:50s}  ERROR".format(r["label"]))
                continue
            print("  {:50s}  {:3d} reqs   MWBE={}   AppA={}   flags={}".format(
                r["label"][:50],
                r["total_requirements"],
                "Y" if r["mwbe_line_present"] else "N",
                len(r["appendix_a_surfaced"]),
                len(r.get("verify_applicability_flags", [])),
            ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
