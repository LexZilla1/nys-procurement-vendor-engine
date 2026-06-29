#!/usr/bin/env python3
"""
Tests for the Phase 2 validation engine (PHASE2-BUILD-SPEC §6).

Runnable two ways:
    python3 test_validator.py      # built-in runner, no dependencies
    pytest test_validator.py       # also works (functions are named test_*)

Covers:
  * Citation-integrity — every emitted citation_quote is verbatim in its source
    file, AND a deliberate quote mismatch raises (a build-failing condition).
  * RM-5 — pass fixture PASSes; missing-§109-cert fixture FAILs with the §109
    citation; normal-course-invoice exception softens to WARN.
  * MUST/SHOULD — a missing MUST field FAILs; a missing SHOULD field WARNs;
    never inverted.
  * RM-1 — 11% on $2M FAIL; 4% on $2M PASS; 6% on $7M FAIL; names the threshold.
"""

import json
import os
import sys

import validator as V

HERE = os.path.dirname(os.path.abspath(__file__))
GC = V.GoldenCopy()


def _load(name):
    with open(os.path.join(HERE, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# Citation-integrity
# --------------------------------------------------------------------------

def test_every_emitted_citation_is_verbatim():
    """Run both validators across all fixtures; assert each finding's
    citation_quote is found verbatim in its named source file's body."""
    val = V.Validator(golden=GC)
    results = [
        val.check_invoice(_load("sample-invoice-pass.json")),
        val.check_invoice(_load("sample-invoice-fail-missing-cert.json")),
        val.check_budget(_load("sample-budget-pass.json")),
        val.check_budget(_load("sample-budget-fail.json")),
    ]
    n = 0
    for r in results:
        for f in r.findings:
            assert f.citation_quote in GC.body(f.source_file), \
                "NON-VERBATIM citation in {}: {!r}".format(f.source_file, f.citation_quote[:60])
            n += 1
    assert n > 0, "no findings were produced"


def test_deliberate_quote_mismatch_raises():
    """A quote that is NOT in the source file must raise CitationError — this is
    the guard that fails the build if the engine ever paraphrases."""
    raised = False
    try:
        GC.cite("source-xii-4-f-proper-invoice.md",
                "This sentence is fabricated and not in the source file.")
    except V.CitationError:
        raised = True
    assert raised, "cite() accepted a non-verbatim quote — citation integrity is broken"


def test_finding_builder_rejects_bad_citation():
    """The Finding builder gates citations too, so no Finding can carry a paraphrase."""
    val = V.Validator(golden=GC)
    raised = False
    try:
        val._f("RM-X", "source-xii-4-f-proper-invoice.md", "totally made up quote",
               V.FAIL, "bogus", False)
    except V.CitationError:
        raised = True
    assert raised


# --------------------------------------------------------------------------
# RM-5 — invoice pre-flight
# --------------------------------------------------------------------------

def test_rm5_pass_fixture_passes():
    val = V.Validator(golden=GC)
    res = val.check_invoice(_load("sample-invoice-pass.json"))
    assert res.overall_status == V.STATUS_PASS, \
        "expected PASS, got {}".format(res.overall_status)


def test_rm5_missing_cert_fails_with_109_citation():
    val = V.Validator(golden=GC)
    res = val.check_invoice(_load("sample-invoice-fail-missing-cert.json"))
    assert res.overall_status == V.STATUS_FAIL
    cert_fails = [f for f in res.findings
                  if f.source_file == V.STF109 and f.severity == V.FAIL and not f.passed]
    assert cert_fails, "expected a FAIL grounded in the §109 source file"
    assert "just, true and correct" in cert_fails[0].citation_quote


def test_rm5_normal_course_exception_warns_not_fails():
    """§109(1-a): a normal-course invoice without a separate certificate, where
    certification is not required, softens to WARN citing the exception."""
    val = V.Validator(golden=GC)
    inv = _load("sample-invoice-pass.json")
    inv["certification"] = None
    inv["normal_course_invoice"] = True
    inv["certification_required"] = False
    res = val.check_invoice(inv)
    cert = [f for f in res.findings if f.source_file == V.STF109]
    assert cert and cert[0].severity == V.WARN
    assert "normal course of business" in cert[0].citation_quote
    assert res.overall_status == V.STATUS_WARN


# --------------------------------------------------------------------------
# MUST/SHOULD — never inverted
# --------------------------------------------------------------------------

def test_missing_must_field_fails():
    val = V.Validator(golden=GC)
    inv = _load("sample-invoice-pass.json")
    del inv["amount"]  # a MUST field (Amount requested)
    res = val.check_invoice(inv)
    assert res.overall_status == V.STATUS_FAIL
    amount = [f for f in res.findings if f.evidence.get("field") == "amount"]
    assert amount and amount[0].severity == V.FAIL and not amount[0].passed


def test_missing_should_field_warns_not_fails():
    val = V.Validator(golden=GC)
    inv = _load("sample-invoice-pass.json")
    del inv["invoice_date"]  # a SHOULD field
    res = val.check_invoice(inv)
    date = [f for f in res.findings if f.evidence.get("field") == "invoice_date"]
    assert date and date[0].severity == V.WARN and not date[0].passed
    # Missing only a SHOULD field must NOT produce an overall FAIL.
    assert res.overall_status != V.STATUS_FAIL


# --------------------------------------------------------------------------
# RM-1 — budget variance thresholds
# --------------------------------------------------------------------------

def _budget(total, moved, **extra):
    d = {"total_contract_value": total, "transfer_amount": moved}
    d.update(extra)
    return d


def test_rm1_11pct_on_2m_fails_naming_10pct_threshold():
    val = V.Validator(golden=GC)
    res = val.check_budget(_budget(2_000_000, 220_000))  # 11%
    assert res.overall_status == V.STATUS_FAIL
    th = [f for f in res.findings if "threshold_pct" in f.evidence]
    assert th and th[0].evidence["threshold_pct"] == 10.0
    assert th[0].evidence["crosses"] is True
    assert "ten percent" in th[0].citation_quote


def test_rm1_4pct_on_2m_passes():
    val = V.Validator(golden=GC)
    res = val.check_budget(_budget(2_000_000, 80_000))  # 4%
    assert res.overall_status == V.STATUS_PASS


def test_rm1_6pct_on_7m_fails_naming_5pct_threshold():
    val = V.Validator(golden=GC)
    res = val.check_budget(_budget(7_000_000, 420_000))  # 6%
    assert res.overall_status == V.STATUS_FAIL
    th = [f for f in res.findings if "threshold_pct" in f.evidence]
    assert th and th[0].evidence["threshold_pct"] == 5.0
    assert "five percent" in th[0].citation_quote


def test_rm1_amount_scope_term_change_is_surfaced_as_amendment_track():
    val = V.Validator(golden=GC)
    res = val.check_budget(_budget(2_000_000, 80_000, changes_amount_scope_or_term=True))
    amend = [f for f in res.findings if "contract amendment" in f.citation_quote]
    assert amend and amend[0].severity == V.INFO


# --------------------------------------------------------------------------
# Built-in runner (no pytest dependency)
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("VALIDATION ENGINE — TEST SUITE ({} tests)".format(len(tests)))
    print("=" * 78)
    for name, fn in tests:
        try:
            fn()
            print("  [PASS] {}".format(name))
            passed += 1
        except AssertionError as exc:
            print("  [FAIL] {} :: {}".format(name, exc))
            failed += 1
        except Exception as exc:
            print("  [ERROR] {} :: {}: {}".format(name, type(exc).__name__, exc))
            failed += 1
    print("-" * 78)
    print("Totals: {} passed, {} failed".format(passed, failed))
    print("=" * 78)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(_run())
