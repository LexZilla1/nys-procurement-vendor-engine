#!/usr/bin/env python3
"""
Tests for cert_renewal.py (BUILD SPEC v2 Part B — certified firms only).

Runnable two ways:
    python3 test_cert_renewal.py
    pytest test_cert_renewal.py

Covers:
  * MWBE 5-year validity is cited VERBATIM from §314(5) through the choke-point.
  * 90-day renewal window logic: GREEN > 90d, YELLOW within window, RED expired.
  * The 90-day window is labelled agency guidance (not statutory).
  * SDVOB cycle is user-provided and ALWAYS flagged "not confirmed".
  * Non-certified input → panel reports N/A (certified firms only).
"""

import os
import sys
import datetime

import validator as V
import cert_renewal as CR

HERE = os.path.dirname(os.path.abspath(__file__))
GC = V.GoldenCopy()


def _data(**overrides):
    d = {
        "vendor_name": "Test Vendor",
        "today": "2026-06-30",
        "mwbe_certified": True,
        "mwbe_cert_expiry": "2026-08-15",
        "sdvob_certified": True,
        "sdvob_cert_expiry": "2026-09-30",
        "sdvob_cycle_years_user_provided": 5,
    }
    d.update(overrides)
    return d


def _items(data):
    rep = CR.check_cert_renewal(data, golden=GC)
    return {i.program: i for i in rep.items}


def test_mwbe_five_year_validity_cited_verbatim():
    it = _items(_data())["MWBE"]
    assert it.grounding is not None
    assert it.grounding["source_file"] == CR.EXEC314
    # The real choke-point: must be verbatim in §314(5) STATE TEXT.
    assert GC.cite(it.grounding["source_file"], it.grounding["citation_quote"])
    assert "five years" in it.grounding["citation_quote"]


def test_cert_renewal_grounding_is_confident_gated_both_directions():
    """The migrated cert_renewal cites at output_context=CONFIDENT. Forward: the
    REAL MWBE grounding it emits is confident-eligible (its §314(5)(a) quote passes
    CONFIDENT). Reverse: the CONFIDENT gate is load-bearing — the §314(5)(b)-(c)
    rebuttable-presumption quote (L-grade) is BLOCKED at CONFIDENT and allowed only
    into VERIFY / attorney-gated, so a non-confident-eligible quote could not slip
    through this runtime site."""
    import engine.golden_status as gs
    it = _items(_data())["MWBE"]
    src, q = it.grounding["source_file"], it.grounding["citation_quote"]
    assert GC.cite(src, q, output_context=gs.OUTPUT_CONFIDENT) == q          # forward
    pres = "there shall be a rebuttable presumption"
    assert pres in GC.body(src)                                              # verbatim, non-5(a)
    try:
        GC.cite(src, pres, output_context=gs.OUTPUT_CONFIDENT)              # reverse: blocked
        raise AssertionError("§314(5)(b)-(c) presumption must not be confident-eligible")
    except V.GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
    assert GC.cite(src, pres, output_context=gs.OUTPUT_VERIFY) == pres       # allowed VERIFY


def test_mwbe_90day_window_is_agency_guidance_not_statutory():
    it = _items(_data())["MWBE"]
    d = it.to_dict()
    assert "agency_guidance" in d
    assert d["agency_guidance"]["statutory"] is False


def test_mwbe_within_90_days_is_yellow():
    # expiry 2026-08-15, today 2026-06-30 → 46 days → inside window
    it = _items(_data())["MWBE"]
    assert it.status == CR.YELLOW
    assert 0 <= it.days_to_expiry <= 90


def test_mwbe_far_out_is_green():
    it = _items(_data(mwbe_cert_expiry="2027-06-30"))["MWBE"]
    assert it.status == CR.GREEN
    assert it.days_to_expiry > 90


def test_mwbe_expired_is_red():
    it = _items(_data(mwbe_cert_expiry="2026-06-01"))["MWBE"]
    assert it.status == CR.RED
    assert it.days_to_expiry < 0


def test_mwbe_window_boundary_exactly_90_days_is_yellow():
    # today 2026-06-30 + 90 days = 2026-09-28 → exactly at the window edge
    edge = (datetime.date(2026, 6, 30) + datetime.timedelta(days=90)).isoformat()
    it = _items(_data(mwbe_cert_expiry=edge))["MWBE"]
    assert it.days_to_expiry == 90
    assert it.status == CR.YELLOW


def test_mwbe_window_boundary_91_days_is_green():
    edge = (datetime.date(2026, 6, 30) + datetime.timedelta(days=91)).isoformat()
    it = _items(_data(mwbe_cert_expiry=edge))["MWBE"]
    assert it.days_to_expiry == 91
    assert it.status == CR.GREEN


def test_sdvob_cycle_always_flagged_not_confirmed():
    it = _items(_data())["SDVOB"]
    d = it.to_dict()
    assert "not_confirmed" in d
    assert "user-provided" in d["not_confirmed"].lower()
    assert "ogs" in d["not_confirmed"].lower()


def test_sdvob_program_context_cited_but_cycle_not():
    """SDVOB program text is citable; the CYCLE is not — both must coexist."""
    it = _items(_data())["SDVOB"]
    assert it.grounding is not None
    assert GC.cite(it.grounding["source_file"], it.grounding["citation_quote"])
    assert it.not_confirmed  # cycle still unconfirmed alongside the program cite


def test_non_certified_firm_panel_is_na():
    rep = CR.check_cert_renewal(
        _data(mwbe_certified=False, sdvob_certified=False), golden=GC)
    assert rep.is_certified_firm is False
    assert any("certified firms only" in i.message for i in rep.items)


def test_missing_expiry_does_not_crash_and_asks_for_date():
    data = _data()
    data.pop("mwbe_cert_expiry")
    it = _items(data)["MWBE"]
    assert it.days_to_expiry is None
    assert "expiry" in it.message.lower()


def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("CERT-RENEWAL (Part B) — TEST SUITE ({} tests)".format(len(tests)))
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
