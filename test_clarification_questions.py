#!/usr/bin/env python3
"""
Tests for the Step 4.5 clarification-question generator.

Runnable as `python3 test_clarification_questions.py` (built-in runner) or pytest.

Required cases (task): (a) window open + gaps → draft; (b) deadline passed → null;
(c) no gaps → null; (d) no question block → null. Plus boundary/behaviour checks:
questions are factual/clarifying, each tagged with its RFP citation, format honored,
unparseable/absent deadline treated as open (unknown-safe), and no auto-send.
"""

import datetime
import sys

import clarification_questions as CQ

RUN = datetime.date(2026, 7, 2)

_QS = {
    "contact": "procurement.questions@example.ny.gov",
    "deadline": "August 15, 2026",
    "format": "Exhibit 1 – Bidder Questions form",
    "citation_requirement": "cite the RFP page, section, and paragraph",
    "source_citation": "§3.1",
}
_GAPS = [
    {"requirement": "MWBE utilization plan", "rfp_citation": "§5.2, p. 14"},
    {"requirement": "Workers' compensation coverage", "rfp_citation": "Appendix A, p. 31"},
]


# --------------------------------------------------------------------------
# (a) window open + gaps → draft
# --------------------------------------------------------------------------

def test_window_open_with_gaps_produces_draft():
    r = CQ.generate(_QS, _GAPS, run_date=RUN)
    assert r["reason"] is None
    assert r["draft"] is not None
    assert r["question_count"] == 2
    # Addressed to the printed contact.
    assert "procurement.questions@example.ny.gov" in r["draft"]
    # Formatted to the stated format.
    assert "Exhibit 1 – Bidder Questions form" in r["draft"]


def test_each_question_is_tagged_with_its_rfp_citation():
    r = CQ.generate(_QS, _GAPS, run_date=RUN)
    assert "[RFP §5.2, p. 14]" in r["draft"]
    assert "[RFP Appendix A, p. 31]" in r["draft"]
    assert all(q["rfp_citation"] for q in r["questions"])


def test_questions_are_factual_clarifying_not_strategy():
    r = CQ.generate(_QS, _GAPS, run_date=RUN)
    for q in r["questions"]:
        t = q["text"].lower()
        assert "can you confirm exactly what a bidder must" in t   # asks what the spec IS
    # No scope/strategy language anywhere in the draft.
    lowered = r["draft"].lower()
    for banned in ("we propose", "change the scope", "waive", "extend the deadline",
                   "reduce the requirement", "strategy"):
        assert banned not in lowered


def test_citation_requirement_surfaced_in_intro():
    r = CQ.generate(_QS, _GAPS, run_date=RUN)
    assert "cite the RFP page, section, and paragraph" in r["draft"]


# --------------------------------------------------------------------------
# (b) deadline passed → null
# --------------------------------------------------------------------------

def test_deadline_passed_returns_null():
    r = CQ.generate(_QS, _GAPS, run_date=datetime.date(2026, 9, 1))  # after Aug 15
    assert r["draft"] is None
    assert r["reason"] == CQ.DEADLINE_PASSED


def test_deadline_on_run_date_is_still_open():
    """Deadline == run date is not 'passed' (unknown-safe: only strictly-before suppresses)."""
    qs = dict(_QS, deadline="2026-07-02")
    r = CQ.generate(qs, _GAPS, run_date=RUN)
    assert r["draft"] is not None


def test_absent_or_unparseable_deadline_treated_as_open():
    qs_none = dict(_QS, deadline=None)
    assert CQ.generate(qs_none, _GAPS, run_date=RUN)["draft"] is not None
    qs_bad = dict(_QS, deadline="see the addendum")
    assert CQ.generate(qs_bad, _GAPS, run_date=RUN)["draft"] is not None


# --------------------------------------------------------------------------
# (c) no gaps → null
# --------------------------------------------------------------------------

def test_no_gaps_returns_null():
    assert CQ.generate(_QS, [], run_date=RUN) == {"draft": None, "reason": CQ.NO_GAPS} \
        or CQ.generate(_QS, [], run_date=RUN)["reason"] == CQ.NO_GAPS


def test_no_gaps_none_returns_null():
    r = CQ.generate(_QS, None, run_date=RUN)
    assert r["draft"] is None and r["reason"] == CQ.NO_GAPS


# --------------------------------------------------------------------------
# (d) no question block → null
# --------------------------------------------------------------------------

def test_no_question_block_returns_null():
    r = CQ.generate(None, _GAPS, run_date=RUN)
    assert r["draft"] is None and r["reason"] == CQ.NO_WINDOW


# --------------------------------------------------------------------------
# Boundaries / robustness
# --------------------------------------------------------------------------

def test_missing_contact_is_flagged_not_invented():
    qs = dict(_QS, contact=None)
    r = CQ.generate(qs, _GAPS, run_date=RUN)
    assert "designated contact not stated" in r["draft"]
    assert r["contact"] is None


def test_gap_without_citation_flags_verify():
    r = CQ.generate(_QS, [{"requirement": "Some form"}], run_date=RUN)
    assert "[RFP citation: please verify location]" in r["draft"]


def test_page_only_citation_renders():
    r = CQ.generate(_QS, [{"item": "Bid bond", "page": 22}], run_date=RUN)
    assert "[RFP p. 22]" in r["draft"]


def test_deadline_precedence_over_gaps_reason():
    """When both the deadline has passed and gaps exist, the reason is the deadline."""
    r = CQ.generate(_QS, _GAPS, run_date=datetime.date(2027, 1, 1))
    assert r["reason"] == CQ.DEADLINE_PASSED


def test_result_carries_no_send_disclaimer():
    r = CQ.generate(_QS, _GAPS, run_date=RUN)
    assert "does not send" in r["disclaimer"] and "does not contact the agency" in r["disclaimer"]


# --------------------------------------------------------------------------
# Built-in runner
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("CLARIFICATION-QUESTION GENERATOR — TEST SUITE ({} tests)".format(len(tests)))
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
