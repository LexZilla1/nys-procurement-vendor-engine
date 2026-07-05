#!/usr/bin/env python3
"""
Tests for engine/payment_clock.py (PR 2 — payment-clock deadline / holiday).

Runnable as `python3 test_payment_clock.py` (built-in runner) or under pytest.

Proves the binding design rules:
  * SOURCE-BACKED: the holiday calendar is parsed from the in-repo GCN §24 /
    §25-a golden bodies (not hardcoded); construction FAILS CLOSED when a golden
    source is missing.
  * ATTORNEY GATE: (a) the holiday-dependent path returns VERIFY while
    HOLIDAY_MAPPING_ATTORNEY_APPROVED is False; (b) flipping the flag enables the
    confident path; (c) the pure day-count path is unaffected by the flag.
  * Law-derived results carry verbatim golden citations.

No live network. Golden-citation verification reuses validator.GoldenCopy.
"""

import datetime
import os
import sys

import engine.payment_clock as pc
from engine.payment_clock import (
    PaymentClock, HolidayCalendarProvider, HolidaySourceUnavailable,
    ClockResult, KNOWN, VERIFY, BASIS_PURE, BASIS_ADJUSTED,
    GCN24_SOURCE, GCN25A_SOURCE)
from validator import GoldenCopy


# --------------------------------------------------------------------------
# Fakes for the fail-closed (missing-source) case
# --------------------------------------------------------------------------

class _FakeGolden:
    """Minimal GoldenCopy-like object missing the GCN sources."""

    def has(self, src):
        return False

    def cite(self, src, quote):
        raise KeyError(src)

    def body(self, src):
        return ""


# --------------------------------------------------------------------------
# Binding invariant: the shipped flag is OFF
# --------------------------------------------------------------------------

def test_attorney_flag_ships_false():
    assert pc.HOLIDAY_MAPPING_ATTORNEY_APPROVED is False, \
        "the holiday-mapping attorney gate must ship closed (False)"


# --------------------------------------------------------------------------
# Source-backed provider
# --------------------------------------------------------------------------

def test_provider_is_source_backed_not_hardcoded():
    """The enumerable holidays must be derived from the GCN §24 golden text."""
    prov = HolidayCalendarProvider(golden=GoldenCopy())
    hols = prov.public_holidays(2026)
    # A representative, checkable subset (dates computed from §24's prose rules).
    assert datetime.date(2026, 1, 1) in hols     # New Year's day
    assert datetime.date(2026, 1, 19) in hols    # 3rd Monday of January (MLK)
    assert datetime.date(2026, 5, 25) in hols    # last Monday in May (Memorial)
    assert datetime.date(2026, 6, 19) in hols    # Juneteenth
    assert datetime.date(2026, 11, 26) in hols   # 4th Thursday in Nov (Thanksgiving)
    assert datetime.date(2026, 12, 25) in hols   # Christmas
    assert len(hols) >= 13
    assert prov.has_dynamic_holidays is True     # §24 President/Governor days
    assert prov.sunday_roll is True


def test_provider_fails_closed_when_source_missing():
    try:
        HolidayCalendarProvider(golden=_FakeGolden())
    except HolidaySourceUnavailable:
        return
    raise AssertionError("expected HolidaySourceUnavailable when GCN source absent")


def test_sunday_observed_roll_from_section_24():
    """§24: a fixed-date holiday on Sunday is observed the next day. 2022-12-25
    (Christmas) fell on a Sunday -> 2022-12-26 is also a holiday."""
    prov = HolidayCalendarProvider(golden=GoldenCopy())
    hols = prov.public_holidays(2022)
    assert datetime.date(2022, 12, 25) in hols
    assert datetime.date(2022, 12, 26) in hols   # observed roll


# --------------------------------------------------------------------------
# (a) holiday-dependent path returns VERIFY while the flag is False
# --------------------------------------------------------------------------

def test_holiday_dependent_is_verify_when_flag_false():
    clk = PaymentClock(approved=False)
    r = clk.net_due_adjusted("2026-06-15", 30)
    assert r.status == VERIFY
    assert r.deadline is None            # NEVER a confident date while gated
    assert r.basis == BASIS_ADJUSTED
    assert "verify" in r.message.lower()
    assert r.citation is not None and r.citation.source_id == GCN25A_SOURCE


def test_default_clock_uses_module_flag_and_is_gated():
    """A PaymentClock with no override inherits the shipped (False) flag."""
    clk = PaymentClock()
    assert clk.approved is False
    assert clk.net_due_adjusted("2026-06-15", 30).status == VERIFY


# --------------------------------------------------------------------------
# (b) flipping the flag enables the confident path
# --------------------------------------------------------------------------

def test_flipping_flag_enables_confident_path():
    clk = PaymentClock(approved=True)
    r = clk.net_due_adjusted("2026-06-15", 30)   # Jul 15 2026 is a Wednesday
    assert r.status == KNOWN
    assert r.deadline == datetime.date(2026, 7, 15)
    assert r.basis == BASIS_ADJUSTED


def test_flipping_module_flag_enables_confident_path_end_to_end():
    """Flipping HOLIDAY_MAPPING_ATTORNEY_APPROVED itself (the single gate) must
    enable the confident path with no other change."""
    saved = pc.HOLIDAY_MAPPING_ATTORNEY_APPROVED
    try:
        pc.HOLIDAY_MAPPING_ATTORNEY_APPROVED = True
        clk = PaymentClock()                      # inherits the (now True) flag
        assert clk.approved is True
        r = clk.net_due_adjusted("2026-06-15", 30)
        assert r.status == KNOWN and r.deadline == datetime.date(2026, 7, 15)
    finally:
        pc.HOLIDAY_MAPPING_ATTORNEY_APPROVED = saved
    # invariant restored
    assert pc.HOLIDAY_MAPPING_ATTORNEY_APPROVED is False


def test_confident_path_rolls_off_holiday():
    """+7 days from 2025-12-25 lands on 2026-01-01 (New Year's) -> next business
    day 2026-01-02."""
    clk = PaymentClock(approved=True)
    r = clk.net_due_adjusted("2025-12-25", 7)
    assert r.status == KNOWN
    assert r.deadline == datetime.date(2026, 1, 2)
    assert "next succeeding business day" in r.message


def test_confident_path_rolls_off_weekend():
    """A raw due date on a Saturday rolls to Monday (unless Monday is a holiday)."""
    clk = PaymentClock(approved=True)
    # 2026-07-11 is a Saturday -> Monday 2026-07-13
    r = clk.net_due_adjusted("2026-07-04", 7)
    assert r.status == KNOWN
    assert r.deadline == datetime.date(2026, 7, 13)


# --------------------------------------------------------------------------
# (c) pure day-count path is unaffected by the flag
# --------------------------------------------------------------------------

def test_pure_day_count_unaffected_by_flag():
    off = PaymentClock(approved=False).net_due_pure("2026-06-15", 30)
    on = PaymentClock(approved=True).net_due_pure("2026-06-15", 30)
    assert off.status == KNOWN and on.status == KNOWN
    assert off.deadline == on.deadline == datetime.date(2026, 7, 15)
    assert off.basis == BASIS_PURE
    assert off.to_dict() == on.to_dict()          # flag makes zero difference


def test_pure_day_count_verify_first_on_unknown_inputs():
    clk = PaymentClock()
    assert clk.net_due_pure(None, 30).status == VERIFY
    assert clk.net_due_pure("2026-06-15", None).status == VERIFY
    assert clk.net_due_pure("not-a-date", 30).status == VERIFY
    # a VERIFY result must never carry a date
    assert clk.net_due_pure(None, 30).deadline is None


# --------------------------------------------------------------------------
# Citations are verbatim golden
# --------------------------------------------------------------------------

def test_adjusted_citation_is_verbatim_golden():
    golden = GoldenCopy()
    r = PaymentClock(approved=True).net_due_adjusted("2026-06-15", 30)
    r.citation.verify_golden(golden)              # raises if not verbatim
    assert r.citation.source_id == GCN25A_SOURCE


def test_all_module_anchor_quotes_are_verbatim():
    golden = GoldenCopy()
    golden.cite(GCN25A_SOURCE, pc.GCN25A_ROLL_QUOTE)
    golden.cite(GCN24_SOURCE, pc.GCN24_ANCHOR_QUOTE)
    golden.cite(GCN24_SOURCE, pc.GCN24_SUNDAY_ROLL_QUOTE)
    golden.cite(GCN24_SOURCE, pc.GCN24_DYNAMIC_QUOTE)


# --------------------------------------------------------------------------
# ClockResult invariants
# --------------------------------------------------------------------------

def test_clockresult_rejects_incoherent_states():
    for bad in (
        lambda: ClockResult(KNOWN, None, BASIS_PURE),          # KNOWN w/o date
        lambda: ClockResult(VERIFY, datetime.date(2026, 1, 1), BASIS_PURE),  # VERIFY w/ date
        lambda: ClockResult("BOGUS", None, BASIS_PURE),        # bad status
    ):
        try:
            bad()
        except (ValueError, TypeError):
            continue
        raise AssertionError("ClockResult accepted an incoherent state")


# --------------------------------------------------------------------------
# Invoice-shell fill
# --------------------------------------------------------------------------

def test_invoice_due_dates_fills_shell_gated():
    invoice = {"id": "inv1", "contract_id": "c1",
               "received_date": "2026-06-15", "net_terms_days": 30}
    out = PaymentClock(approved=False).invoice_due_dates(invoice)
    assert out["pure_day_count"].status == KNOWN
    assert out["pure_day_count"].deadline == datetime.date(2026, 7, 15)
    assert out["holiday_adjusted"].status == VERIFY      # gated
    # input not mutated
    assert set(invoice) == {"id", "contract_id", "received_date", "net_terms_days"}


def test_invoice_due_dates_confident_when_approved():
    invoice = {"id": "inv1", "contract_id": "c1",
               "received_date": "2025-12-25", "net_terms_days": 7}
    out = PaymentClock(approved=True).invoice_due_dates(invoice)
    assert out["holiday_adjusted"].status == KNOWN
    assert out["holiday_adjusted"].deadline == datetime.date(2026, 1, 2)


# --------------------------------------------------------------------------
# Built-in runner
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("PAYMENT CLOCK — TEST SUITE ({} tests)".format(len(tests)))
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
