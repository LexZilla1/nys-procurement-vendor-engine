#!/usr/bin/env python3
"""
Tests for the full statutory payment clock (PR 2b):
engine/invoice_clock.py + engine/invoice_status.py.

Runnable as `python3 test_invoice_clock.py` or under pytest. No live network;
all rule text is read from the in-repo goldens via validator.GoldenCopy.

Matrix coverage (named tests):
  1 MIR later-of (§179-e)            : test_mir_later_of_*, test_mir_date_check_*
  2 net-due branches (§179-f)        : test_branch_*, test_required_payment_date_*
  3 VERIFY mir -> net_due BLOCKED     : test_verify_mir_blocks_invoice_net_due
  4 MIR_DATE_CHECK categorical flag   : test_mir_date_check_*
  5 prompt_payment_note / rate_lookup : test_rate_lookup_*, test_prompt_payment_note_*
  6 invoice status DRAFT->PREFLIGHT   : test_status_*
  7 §109 semantic-concept variant     : test_109_semantic_*
  8 never-green over new fields        : test_never_green_*
"""

import datetime
import glob
import json
import os
import sys

from engine import invoice_clock as ic
from engine import payment_clock as pc
from engine.payment_clock import PaymentClock, KNOWN, VERIFY
from engine.dated_objects import BLOCKED, VERIFY as OBL_VERIFY
from engine import invoice_status as ist
from engine.invoice_status import (
    InvoiceStatusMachine, IllegalInvoiceTransition, preflight_109_semantic,
    PREFLIGHT_PASS, PREFLIGHT_FLAG, DRAFT)
from validator import GoldenCopy

APPROVED = PaymentClock(approved=True)   # simulate the attorney-approved flip
GATED = PaymentClock(approved=False)     # the shipped state
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "schemas")
FORBIDDEN_SCORE_TOKENS = ("confidence", "score", "probability", "likelihood",
                          "risk_score", "rating")


# ============================ 1. MIR later-of ==============================

def test_mir_later_of_semantics():
    # later of invoice(6/10) and goods(6/15) = 6/15
    mir, check, cite = ic.mir_receipt(
        {"invoice_received_date": "2026-06-10", "goods_received_date": "2026-06-15"})
    assert mir == datetime.date(2026, 6, 15)
    assert check == ic.MIR_KNOWN
    assert cite.source_id == ic.STF179E
    # and the other ordering
    mir2, _, _ = ic.mir_receipt(
        {"invoice_received_date": "2026-06-20", "goods_received_date": "2026-06-15"})
    assert mir2 == datetime.date(2026, 6, 20)


def test_mir_later_of_verify_when_a_date_missing():
    assert ic.mir_receipt({"invoice_received_date": "2026-06-10"})[1] == ic.MIR_VERIFY
    assert ic.mir_receipt({"goods_received_date": "2026-06-10"})[1] == ic.MIR_VERIFY
    assert ic.mir_receipt({})[1] == ic.MIR_VERIFY


def test_mir_highway_verify_not_in_goldens():
    mir, check, _ = ic.mir_receipt({"highway_final_payment": True})
    assert mir is None and check == ic.MIR_HIGHWAY_VERIFY


def test_mir_date_check_categorical():
    chk = ic.mir_date_check(
        {"invoice_received_date": "2026-06-10", "goods_received_date": "2026-06-15"})
    assert chk["check"] in ic.MIR_DATE_CHECKS
    assert chk["check"] == ic.MIR_KNOWN
    assert chk["governing"] == "goods_received"
    assert chk["mir_date"] == "2026-06-15"
    # categorical only — no numeric value anywhere in the flag
    assert not isinstance(chk["check"], (int, float))


# ============================ 2. net-due branches ==========================

def test_branch_30_standard():
    b, days, cite, _ = ic.net_due_branch({})
    assert b == ic.BRANCH_30 and days == 30
    assert cite.source_id == ic.STF179F


def test_branch_15_small_business_requires_both_conjuncts():
    b, days, cite, _ = ic.net_due_branch(
        {"sb_15day_certified": True, "submitted_electronically": True})
    assert b == ic.BRANCH_15_SB and days == 15
    # the citation IS the conjunctive verbatim anchor
    assert cite.quote == ic.NET_DUE_15_SB_QUOTE
    GoldenCopy().cite(ic.STF179F, cite.quote)   # verbatim


def test_branch_15_falls_back_without_electronic():
    """Missing the electronic-submission conjunct must NOT yield a 15-day clock."""
    b, days, _, note = ic.net_due_branch({"sb_15day_certified": True})
    assert b == ic.BRANCH_30 and days == 30
    assert "electronic" in note.lower()


def test_branch_15_falls_back_without_certification():
    b, days, _, note = ic.net_due_branch({"submitted_electronically": True})
    assert b == ic.BRANCH_30 and days == 30
    assert "certification" in note.lower()


def test_branch_75_highway_final_payment():
    b, days, cite, _ = ic.net_due_branch({"highway_final_payment": True})
    assert b == ic.BRANCH_75_HWY and days == 75
    assert cite.quote == ic.NET_DUE_75_HWY_QUOTE


def test_required_payment_date_verify_while_gated():
    inv = {"id": "i", "invoice_received_date": "2026-06-10",
           "goods_received_date": "2026-06-15"}
    r = ic.required_payment_date(inv, clock=GATED)
    assert r.status == VERIFY and r.deadline is None
    assert "attorney review" in r.message.lower()


def test_all_branches_inherit_holiday_gate():
    """Every branch (30/15/75) is 'excluding legal holidays' -> holiday-dependent
    -> VERIFY while the gate is False."""
    invoices = [
        {"id": "a", "invoice_received_date": "2026-06-10", "goods_received_date": "2026-06-15"},
        {"id": "b", "invoice_received_date": "2026-06-10", "goods_received_date": "2026-06-15",
         "sb_15day_certified": True, "submitted_electronically": True},
    ]
    for inv in invoices:
        assert ic.required_payment_date(inv, clock=GATED).status == VERIFY


def test_required_payment_date_confident_when_approved_is_business_day():
    inv = {"id": "i", "invoice_received_date": "2026-06-10",
           "goods_received_date": "2026-06-15"}
    r = ic.required_payment_date(inv, clock=APPROVED)
    assert r.status == KNOWN
    d = r.deadline
    # the result must be a business day (Sat/Sun roll + holiday exclusion inherited)
    assert APPROVED.calendar.is_business_day(d)
    # excluding legal holidays only pushes the date out, never earlier than +30
    assert d >= datetime.date(2026, 6, 15) + datetime.timedelta(days=30)


def test_confident_excludes_legal_holidays_exact_no_holiday_window():
    """A window with no public holidays: 30 days excluding holidays == +30 days,
    then rolled off any weekend. Independently computed here."""
    mir = datetime.date(2026, 3, 2)   # Mar-Apr 2026 has none of the 13 holidays
    inv = {"id": "i", "invoice_received_date": "2026-03-02",
           "goods_received_date": "2026-03-02"}
    # confirm the window truly has no public holidays
    hset = APPROVED.calendar.public_holidays(2026)
    span = {mir + datetime.timedelta(days=k) for k in range(1, 41)}
    assert not (span & hset), "test precondition: window must be holiday-free"
    raw = mir + datetime.timedelta(days=30)
    while raw.weekday() >= 5:
        raw += datetime.timedelta(days=1)
    assert ic.required_payment_date(inv, clock=APPROVED).deadline == raw


def test_confident_holiday_in_window_pushes_date_out():
    """A window containing a public holiday yields a later date than the same
    span with the holiday removed (proving 'excluding legal holidays')."""
    inv = {"id": "i", "invoice_received_date": "2026-06-15",
           "goods_received_date": "2026-06-15"}  # window includes Juneteenth 6/19
    due = ic.required_payment_date(inv, clock=APPROVED).deadline
    naive = datetime.date(2026, 6, 15) + datetime.timedelta(days=30)
    assert due > naive   # at least one legal holiday excluded from the count


def test_branch_citations_all_verbatim():
    g = GoldenCopy()
    for b in (ic.BRANCH_30, ic.BRANCH_15_SB, ic.BRANCH_75_HWY):
        g.cite(ic.STF179F, ic._branch_citation(b).quote)


# ==================== 3. VERIFY mir -> net_due BLOCKED =====================

def test_verify_mir_blocks_invoice_net_due():
    # goods date missing -> MIR VERIFY -> invoice_net_due BLOCKED (dependency)
    g = ic.build_invoice_obligations({"id": "x", "invoice_received_date": "2026-06-10"})
    assert g.state_of("x:mir") == OBL_VERIFY
    assert g.state_of("x:net_due") == BLOCKED


def test_highway_mir_verify_blocks_net_due():
    g = ic.build_invoice_obligations({"id": "h", "highway_final_payment": True})
    assert g.state_of("h:net_due") == BLOCKED


def test_known_mir_gated_net_due_is_verify_not_blocked():
    # MIR known but holiday gate off -> net_due VERIFY (date unknown), NOT blocked
    g = ic.build_invoice_obligations(
        {"id": "y", "invoice_received_date": "2026-06-10",
         "goods_received_date": "2026-06-15"}, clock=GATED)
    assert g.state_of("y:mir") != OBL_VERIFY   # mir resolved
    assert g.state_of("y:net_due") == OBL_VERIFY


def test_confident_mir_net_due_known_when_approved():
    g = ic.build_invoice_obligations(
        {"id": "z", "invoice_received_date": "2026-06-10",
         "goods_received_date": "2026-06-15"}, clock=APPROVED)
    o = g.get("z:net_due")
    assert o.date_status == "KNOWN" and o.due_date is not None


# ==================== 5. prompt_payment_note / rate_lookup =================

def test_rate_lookup_known():
    r = ic.rate_lookup("2026-06-15")
    assert r["status"] == ic.RATE_KNOWN and r["rate"] is not None and r["quarter"]


def test_rate_lookup_verify_when_stale_out_of_coverage():
    assert ic.rate_lookup("1990-01-01")["status"] == ic.RATE_VERIFY_AT_SOURCE


def test_rate_lookup_verify_when_no_date():
    assert ic.rate_lookup(None)["status"] == ic.RATE_VERIFY_AT_SOURCE


def test_prompt_payment_note_non_promissory():
    n = ic.prompt_payment_note(
        {"id": "i", "invoice_received_date": "2026-06-10",
         "goods_received_date": "2026-06-15"})
    txt = n["note"].lower()
    # non-promissory: must hedge, must not promise interest is owed
    assert "not a promise" in txt
    assert "may provide" in txt
    for banned in ("you will receive", "interest is owed", "guaranteed",
                   "we will pay"):
        assert banned not in txt
    # while gated, the required date is not asserted
    assert n["required_payment_status"] == VERIFY


# ==================== 6. invoice status machine ===========================

def test_status_gate_draft_to_preflight_pass():
    m = InvoiceStatusMachine("i")
    assert m.status == DRAFT
    res = m.run_preflight({"cert_just_true_correct": True,
                           "cert_not_previously_paid": True,
                           "cert_actually_due_owing": True})
    assert res["verdict"] == PREFLIGHT_PASS
    assert m.status == PREFLIGHT_PASS


def test_status_gate_draft_to_preflight_flag():
    m = InvoiceStatusMachine("i")
    m.run_preflight({"cert_just_true_correct": True})   # two concepts missing
    assert m.status == PREFLIGHT_FLAG


def test_illegal_status_transition_raises():
    m = InvoiceStatusMachine("i")
    try:
        m.transition("PREFLIGHT_PASS")   # not a real move? DRAFT->PASS is legal
    except IllegalInvoiceTransition:
        raise AssertionError("DRAFT->PREFLIGHT_PASS should be legal")
    # now PASS -> DRAFT is NOT in the table
    try:
        m.transition(DRAFT)
    except IllegalInvoiceTransition:
        return
    raise AssertionError("PREFLIGHT_PASS -> DRAFT should be illegal")


def test_flagged_invoice_can_be_corrected_and_rerun():
    m = InvoiceStatusMachine("i")
    m.run_preflight({"cert_just_true_correct": True})     # FLAG
    m.transition(DRAFT, reason="corrected")               # FLAG -> DRAFT ok
    m.run_preflight({"cert_just_true_correct": True,
                     "cert_not_previously_paid": True,
                     "cert_actually_due_owing": True})     # -> PASS
    assert m.status == PREFLIGHT_PASS


# ==================== 7. §109 semantic-concept variant ====================

def test_109_semantic_all_concepts_pass():
    r = preflight_109_semantic({"cert_just_true_correct": True,
                                "cert_not_previously_paid": True,
                                "cert_actually_due_owing": True})
    assert r["verdict"] == PREFLIGHT_PASS and r["missing"] == []


def test_109_semantic_missing_concept_flags():
    r = preflight_109_semantic({"cert_just_true_correct": True,
                                "cert_actually_due_owing": True})
    assert r["verdict"] == PREFLIGHT_FLAG
    assert "not_previously_paid" in r["missing"]


def test_109_semantic_is_beyond_field_presence():
    """Semantic-concept check keys on the THREE §109 attestation concepts, not a
    single certificate field/signature. A cert 'present' but missing a concept
    still FLAGS — distinguishing it from the pre-existing field/cert check."""
    r = preflight_109_semantic({"certificate_present": True,   # field-style flag
                                "cert_just_true_correct": True,
                                "cert_not_previously_paid": True})
    assert r["verdict"] == PREFLIGHT_FLAG          # actually_due_owing concept absent
    assert r["missing"] == ["actually_due_owing"]


def test_109_concept_anchors_verbatim():
    g = GoldenCopy()
    for quote in ist.CONCEPT_ANCHORS.values():
        g.cite(ist.STF109, quote)


# ==================== 8. never-green over new fields =======================

def test_never_green_new_invoice_fields_have_no_score_tokens():
    schema = json.load(open(os.path.join(SCHEMA_DIR, "invoice.schema.json"),
                            encoding="utf-8"))
    for name in schema["properties"]:
        low = name.lower()
        for tok in FORBIDDEN_SCORE_TOKENS:
            assert tok not in low, "score-like field %r in invoice schema" % name
    # the new clock/cert fields are all categorical/date/bool — assert presence
    for f in ("invoice_received_date", "goods_received_date", "sb_15day_certified",
              "submitted_electronically", "highway_final_payment", "status",
              "cert_just_true_correct", "cert_not_previously_paid",
              "cert_actually_due_owing"):
        assert f in schema["properties"]


def test_never_green_clock_outputs_have_no_score_keys():
    inv = {"id": "i", "invoice_received_date": "2026-06-10",
           "goods_received_date": "2026-06-15"}
    outs = [
        ic.mir_date_check(inv),
        ic.required_payment_date(inv, clock=APPROVED).to_dict(),
        ic.rate_lookup("2026-06-15"),
        ic.prompt_payment_note(inv),
        preflight_109_semantic({"cert_just_true_correct": True}),
    ]
    def _keys(o, acc):
        if isinstance(o, dict):
            for k, v in o.items():
                acc.append(k); _keys(v, acc)
        elif isinstance(o, list):
            for v in o:
                _keys(v, acc)
    for o in outs:
        keys = []
        _keys(o, keys)
        for k in keys:
            for tok in FORBIDDEN_SCORE_TOKENS:
                assert tok not in str(k).lower(), "score-like key %r" % k


def test_invoice_schema_is_valid_json():
    json.load(open(os.path.join(SCHEMA_DIR, "invoice.schema.json"), encoding="utf-8"))


def test_all_anchor_quotes_are_verbatim():
    g = GoldenCopy()
    g.cite(ic.STF179E, ic.MIR_LATER_OF_QUOTE)
    for q in (ic.NET_DUE_30_QUOTE, ic.NET_DUE_15_SB_QUOTE, ic.NET_DUE_75_HWY_QUOTE):
        g.cite(ic.STF179F, q)
    for q in ist.CONCEPT_ANCHORS.values():
        g.cite(ist.STF109, q)


# ==================== gate invariant ======================================

def test_module_flag_still_ships_false():
    assert pc.HOLIDAY_MAPPING_ATTORNEY_APPROVED is False


# ==================== runner ==============================================

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("INVOICE CLOCK (PR 2b) — TEST SUITE ({} tests)".format(len(tests)))
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
