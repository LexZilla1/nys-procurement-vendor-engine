#!/usr/bin/env python3
"""
Tests for the daily-habit backend state primitives (PR 1).

Runnable as `python3 test_daily_habit_backend.py` or under pytest. No network,
no external deps. Golden-citation verification reuses validator.GoldenCopy, the
same verbatim choke-point the validator uses. No tier-3 data anywhere.
"""

import datetime
import glob
import json
import os
import re

from engine.citation import (Citation, CitationError, GOLDEN_RULE, USER_ENTERED,
                             OBSERVED_PATTERN, SOLICITATION)
from engine.dated_objects import (
    DatedObligation, ObligationGraph, parse_date,
    KNOWN, VERIFY_AT_SOURCE, NOT_APPLICABLE,
    PENDING, DUE_SOON, OVERDUE, DONE, VERIFY, LAPSED, BLOCKED, STATES,
    CREDENTIAL_STATUSES, CRED_OK, CRED_RECERT_PRESUMPTION_PENDING,
    credential_is_ok, make_cert_expiry, make_nfp_renewal_watch,
    make_user_obligation, NFP_RENEWAL_WATCH_MESSAGE, DEFAULT_LEAD_TIMES)
from engine.state_machine import (
    TenderStateMachine, IllegalTransition, render_transition_table,
    WATCHING, TRIAGED, PREPARING, READY_TO_SUBMIT, SUBMITTED, AWARDED, LOST,
    NO_BID, CONTRACT_EXECUTION, ACTIVE, CLOSE_OUT, CLOSED, BIDDABLE)
from engine.outcome_log import (OutcomeLog, OutcomeLogError, OBSERVED_PATTERN_LABEL,
                               ACCEPTED, REJECTED, WON, REASON_PRICE)

from validator import GoldenCopy

TODAY = datetime.date(2026, 7, 5)
SCHEMA_DIR = os.path.join("data", "schemas")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _outcome():
    """A minimal outcome record object (any non-None value satisfies the SM)."""
    return {"result": "LOST", "reason": "test"}


def _reach_submitted():
    sm = TenderStateMachine("t1")
    sm.transition(TRIAGED, "USER", "u1", "triaged", triage_verdict=BIDDABLE)
    sm.transition(PREPARING, "USER", "u1", "prep")
    sm.transition(READY_TO_SUBMIT, "USER", "u1", "ready")
    sm.transition(SUBMITTED, "USER", "u1", "submitted")
    return sm


# ---------------------------------------------------------------------------
# state machine — legality
# ---------------------------------------------------------------------------

def test_illegal_transition_raises():
    sm = TenderStateMachine("t1")            # WATCHING
    try:
        sm.transition(ACTIVE, "USER", "u1", "jump")   # not in table
        assert False, "expected IllegalTransition"
    except IllegalTransition:
        pass
    # a legal one succeeds
    sm.transition(TRIAGED, "USER", "u1", "ok", triage_verdict=BIDDABLE)
    assert sm.state == TRIAGED


def test_no_bid_after_submitted_is_illegal():
    sm = _reach_submitted()
    try:
        sm.transition(NO_BID, "USER", "u1", "changed mind", outcome=_outcome())
        assert False, "NO_BID after SUBMITTED must be illegal"
    except IllegalTransition as exc:
        assert "before SUBMITTED" in str(exc)


def test_no_bid_before_submitted_is_legal_with_outcome():
    sm = TenderStateMachine("t1")
    sm.transition(NO_BID, "USER", "u1", "not worth it", outcome=_outcome())
    assert sm.state == NO_BID


def test_no_bid_requires_outcome_record():
    sm = TenderStateMachine("t1")
    try:
        sm.transition(NO_BID, "USER", "u1", "no outcome")
        assert False, "NO_BID requires an outcome record"
    except IllegalTransition as exc:
        assert "outcome" in str(exc)


def test_lost_before_submitted_illegal_without_override_and_outcome():
    sm = TenderStateMachine("t1")
    sm.transition(TRIAGED, "USER", "u1", "t", triage_verdict=BIDDABLE)
    # no override, no outcome -> illegal
    try:
        sm.transition(LOST, "USER", "u1", "lost?")
        assert False, "LOST before SUBMITTED must be illegal without override+outcome"
    except IllegalTransition:
        pass
    # override=True but still missing outcome -> illegal
    try:
        sm.transition(LOST, "ADMIN", "a1", "correction", override=True)
        assert False, "override without outcome must still be illegal"
    except IllegalTransition:
        pass
    # override + outcome + actor + reason -> allowed
    sm.transition(LOST, "ADMIN", "a1", "administrative correction",
                  override=True, outcome=_outcome())
    assert sm.state == LOST


def test_lost_from_submitted_is_legal_with_outcome():
    sm = _reach_submitted()
    sm.transition(LOST, "USER", "u1", "not selected", outcome=_outcome())
    assert sm.state == LOST


def test_full_happy_path_to_closed():
    sm = _reach_submitted()
    sm.transition(AWARDED, "SYSTEM", "sys", "award notice")
    sm.transition(CONTRACT_EXECUTION, "USER", "u1", "executing")
    sm.transition(ACTIVE, "USER", "u1", "active")
    sm.transition(CLOSE_OUT, "USER", "u1", "closing")
    sm.transition(CLOSED, "USER", "u1", "closed")
    assert sm.state == CLOSED
    # 4 transitions to reach SUBMITTED + AWARDED, CONTRACT_EXECUTION, ACTIVE,
    # CLOSE_OUT, CLOSED = 9 logged transitions.
    assert len(sm.log) == 9


def test_transition_log_shape():
    sm = TenderStateMachine("t1")
    sm.transition(TRIAGED, "USER", "u1", "triaged", triage_verdict=BIDDABLE)
    e = sm.log[-1].to_dict()
    assert set(e.keys()) == {"actor_type", "actor_id", "timestamp", "from_state",
                             "to_state", "reason", "citation"}
    assert e["actor_type"] == "USER" and e["from_state"] == WATCHING
    assert e["to_state"] == TRIAGED and e["citation"] is None


# ---------------------------------------------------------------------------
# state machine — AWARDED spawns exactly one Contract (idempotent, replay-safe)
# ---------------------------------------------------------------------------

def test_awarded_spawns_exactly_one_contract_idempotent():
    sm = _reach_submitted()
    sm.transition(AWARDED, "SYSTEM", "sys", "award")
    c1 = sm.contract
    assert c1 is not None and c1.tender_id == "t1"
    # replay the award (idempotent) — must NOT create a second Contract
    sm.transition(AWARDED, "SYSTEM", "sys", "replay award")
    assert sm.contract is c1
    # a second, independent award attempt on the same machine is still the same one
    sm.transition(AWARDED, "IMPORT", "imp", "import replay")
    assert sm.contract is c1


# ---------------------------------------------------------------------------
# dated objects — verify-first
# ---------------------------------------------------------------------------

def test_unknown_date_becomes_verify_at_source_never_a_default():
    # a value that cannot be parsed
    o = DatedObligation("o1", "bid_deadline", "t1", due_date="not-a-date")
    assert o.due_date is None
    assert o.date_status == VERIFY_AT_SOURCE
    # a missing date
    o2 = DatedObligation("o2", "bid_deadline", "t1", due_date=None)
    assert o2.due_date is None and o2.date_status == VERIFY_AT_SOURCE
    # never silently defaulted to today or any date
    assert o.due_date != TODAY and o2.due_date != TODAY
    g = ObligationGraph([o, o2])
    assert g.state_of("o1", TODAY) == VERIFY
    assert g.state_of("o2", TODAY) == VERIFY


def test_known_without_date_is_rejected():
    try:
        DatedObligation("o1", "bid_deadline", "t1", due_date=None, date_status=KNOWN)
        assert False, "KNOWN without a date must raise"
    except ValueError:
        pass


def test_direct_not_applicable_construction_raises():
    # NOT_APPLICABLE is a factory-returns-None signal, never a live obligation.
    # Constructing one directly is a programming error and must RAISE — it must
    # never silently collapse to DONE (which would contaminate future
    # outcome/defects-prevented counts).
    try:
        DatedObligation("o1", "bid_deadline", "t1",
                        due_date="2026-09-01", date_status=NOT_APPLICABLE)
        assert False, "date_status=NOT_APPLICABLE must raise on direct construction"
    except ValueError as exc:
        assert "NOT_APPLICABLE" in str(exc)
    # the sanctioned inapplicable path (factory returns None) is unaffected
    assert make_nfp_renewal_watch("w", "k", "2026-12-31", xi4a_covered=False) is None


def test_date_math_pending_due_soon_overdue():
    far = DatedObligation("far", "bid_deadline", "t1",
                          due_date=(TODAY + datetime.timedelta(days=200)).isoformat())
    soon = DatedObligation("soon", "bid_deadline", "t1",
                           due_date=(TODAY + datetime.timedelta(days=10)).isoformat())
    past = DatedObligation("past", "bid_deadline", "t1",
                           due_date=(TODAY - datetime.timedelta(days=1)).isoformat())
    g = ObligationGraph([far, soon, past])
    assert g.state_of("far", TODAY) == PENDING       # beyond max lead (90)
    assert g.state_of("soon", TODAY) == DUE_SOON      # within 90-day window
    assert g.state_of("past", TODAY) == OVERDUE


def test_done_and_lapsed_flags_win():
    o = DatedObligation("o", "bid_deadline", "t1",
                        due_date=(TODAY - datetime.timedelta(days=5)).isoformat(),
                        done=True)
    assert ObligationGraph([o]).state_of("o", TODAY) == DONE
    lp = DatedObligation("lp", "cert_expiry", "c1",
                         due_date=(TODAY - datetime.timedelta(days=5)).isoformat(),
                         lapsed=True)
    assert ObligationGraph([lp]).state_of("lp", TODAY) == LAPSED


# ---------------------------------------------------------------------------
# dated objects — BLOCKED propagation + blast radius
# ---------------------------------------------------------------------------

def test_dependent_of_verify_object_is_blocked():
    dep = DatedObligation("dep", "bid_deadline", "t1", due_date=None)  # VERIFY_AT_SOURCE
    child = DatedObligation("child", "contract_deliverable", "t1",
                            due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                            depends_on=["dep"])
    g = ObligationGraph([dep, child])
    assert g.state_of("dep", TODAY) == VERIFY
    assert g.state_of("child", TODAY) == BLOCKED


def test_blocked_propagates_transitively():
    dep = DatedObligation("dep", "bid_deadline", "t1", due_date=None)
    mid = DatedObligation("mid", "contract_deliverable", "t1",
                          due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                          depends_on=["dep"])
    leaf = DatedObligation("leaf", "contract_deliverable", "t1",
                           due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                           depends_on=["mid"])
    g = ObligationGraph([dep, mid, leaf])
    assert g.state_of("leaf", TODAY) == BLOCKED


def test_dependency_cycle_is_blocked_not_crash():
    a = DatedObligation("a", "contract_deliverable", "t1",
                        due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                        depends_on=["b"])
    b = DatedObligation("b", "contract_deliverable", "t1",
                        due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                        depends_on=["a"])
    g = ObligationGraph([a, b])
    assert g.state_of("a", TODAY) == BLOCKED
    assert g.state_of("b", TODAY) == BLOCKED


def test_blast_radius_returns_all_live_dependents():
    a = DatedObligation("a", "cert_expiry", "c1",
                        due_date=(TODAY + datetime.timedelta(days=5)).isoformat())
    b = DatedObligation("b", "contract_deliverable", "t1",
                        due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                        depends_on=["a"])
    c = DatedObligation("c", "contract_deliverable", "t1",
                        due_date=(TODAY + datetime.timedelta(days=5)).isoformat(),
                        depends_on=["b"])
    g = ObligationGraph([a, b, c])
    assert g.dependents("a", TODAY) == ["b", "c"]
    # a DONE dependent drops out of the live blast radius
    c.done = True
    assert g.dependents("a", TODAY) == ["b"]


# ---------------------------------------------------------------------------
# never-green — no numeric confidence/score fields in any schema
# ---------------------------------------------------------------------------

FORBIDDEN_SCORE_TOKENS = ("confidence", "score", "probability", "likelihood",
                          "risk_score", "rating")


def _walk_property_names(node, out):
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            for name in props:
                out.append(name)
        for v in node.values():
            _walk_property_names(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_property_names(v, out)


def test_never_green_no_numeric_score_fields_in_schemas():
    files = glob.glob(os.path.join(SCHEMA_DIR, "*.json"))
    assert files, "no schema files found"
    for path in files:
        schema = json.load(open(path, encoding="utf-8"))
        names = []
        _walk_property_names(schema, names)
        for n in names:
            low = n.lower()
            for tok in FORBIDDEN_SCORE_TOKENS:
                assert tok not in low, \
                    "forbidden score-like field %r in %s" % (n, os.path.basename(path))


def test_obligation_serialization_has_no_score_key():
    o = make_user_obligation("o", "bid_deadline", "t1",
                             (TODAY + datetime.timedelta(days=3)).isoformat())
    d = o.to_dict(state=DUE_SOON)
    for k in d:
        for tok in FORBIDDEN_SCORE_TOKENS:
            assert tok not in k.lower()


# ---------------------------------------------------------------------------
# credential_status — separate axis; presumption never OK, never an obligation state
# ---------------------------------------------------------------------------

def test_recert_presumption_only_in_credential_status_never_obligation_state():
    assert CRED_RECERT_PRESUMPTION_PENDING in CREDENTIAL_STATUSES
    assert CRED_RECERT_PRESUMPTION_PENDING not in STATES
    # and the presumption is never rendered as OK
    assert credential_is_ok(CRED_RECERT_PRESUMPTION_PENDING) is False
    assert credential_is_ok(CRED_OK) is True


def test_schemas_keep_presumption_out_of_obligation_state_enum():
    dob = json.load(open(os.path.join(SCHEMA_DIR, "dated_obligation.schema.json"),
                        encoding="utf-8"))
    state_enum = dob["properties"]["state"]["enum"]
    assert "RECERT_PRESUMPTION_PENDING" not in state_enum
    cred = json.load(open(os.path.join(SCHEMA_DIR, "credential_status.schema.json"),
                         encoding="utf-8"))
    assert "RECERT_PRESUMPTION_PENDING" in cred["enum"]


def test_cert_expiry_obligation_may_be_lapsed_while_credential_presumption_pending():
    # obligation timing (LAPSED) and credential legal status (presumption) are
    # independent axes that can hold different values at the same time.
    obl = make_cert_expiry("cert1", "cred1",
                           (TODAY - datetime.timedelta(days=10)).isoformat())
    obl.lapsed = True
    assert ObligationGraph([obl]).state_of("cert1", TODAY) == LAPSED
    # meanwhile the credential can be RECERT_PRESUMPTION_PENDING — still not OK
    assert credential_is_ok(CRED_RECERT_PRESUMPTION_PENDING) is False


# ---------------------------------------------------------------------------
# nfp_renewal_notice_watch — XI.4.A gating + fixed non-conclusory wording
# ---------------------------------------------------------------------------

def test_nfp_watch_only_instantiates_for_xi4a_covered_contracts():
    not_covered = make_nfp_renewal_watch("w1", "k1", "2026-12-31", xi4a_covered=False)
    assert not_covered is None
    covered = make_nfp_renewal_watch("w1", "k1", "2026-12-31", xi4a_covered=True)
    assert covered is not None
    assert covered.kind == "nfp_renewal_notice_watch"
    # watch fires 90 days before the contract end date
    assert covered.due_date == datetime.date(2026, 12, 31) - datetime.timedelta(days=90)
    assert covered.date_status == KNOWN


def test_nfp_watch_wording_is_fixed_and_non_conclusory():
    assert NFP_RENEWAL_WATCH_MESSAGE == (
        "No renewal notice recorded by the 90-day watch date; "
        "verify with agency/source.")
    low = NFP_RENEWAL_WATCH_MESSAGE.lower()
    # must not assert agency noncompliance as a legal conclusion
    for banned in ("failed", "violation", "noncompliance", "did not comply",
                   "in breach", "unlawful"):
        assert banned not in low
    assert "verify with agency/source" in low


def test_nfp_watch_done_when_notice_recorded():
    covered = make_nfp_renewal_watch("w1", "k1", "2026-12-31", xi4a_covered=True,
                                     notice_recorded=True)
    assert ObligationGraph([covered]).state_of("w1", TODAY) == DONE


# ---------------------------------------------------------------------------
# citations — law-derived => golden_rule (verbatim); user-entered never golden
# ---------------------------------------------------------------------------

def test_law_derived_obligations_carry_verbatim_golden_citations():
    golden = GoldenCopy()
    cert = make_cert_expiry("cert1", "cred1", "2027-01-01")
    nfp = make_nfp_renewal_watch("w1", "k1", "2026-12-31", xi4a_covered=True)
    for obl in (cert, nfp):
        assert obl.citation is not None
        assert obl.citation.source_type == GOLDEN_RULE
        # the quote must be verbatim in the named golden source
        obl.citation.verify_golden(golden)


def test_user_entered_obligations_are_never_golden_rule():
    o = make_user_obligation("o", "bid_deadline", "t1", "2026-09-01")
    assert o.citation.source_type == USER_ENTERED
    assert o.citation.source_type != GOLDEN_RULE


def test_bad_golden_quote_is_rejected():
    golden = GoldenCopy()
    bogus = Citation(source_id="source-exec-314-mwbe-cert-validity.md",
                     source_type=GOLDEN_RULE, locator="§314",
                     quote="certifications are valid for ten years",  # not verbatim
                     captured_at="2026-07-05")
    try:
        bogus.verify_golden(golden)
        assert False, "a non-verbatim golden quote must be rejected"
    except CitationError:
        pass


def test_citation_rejects_unknown_source_type():
    try:
        Citation("s", "made_up_type", "loc", "q", "2026-07-05")
        assert False, "unknown source_type must raise"
    except CitationError:
        pass


# ---------------------------------------------------------------------------
# outcome log — observations require the label + observed_pattern citation
# ---------------------------------------------------------------------------

def _obs_citation():
    return Citation(source_id="agency:OGS", source_type=OBSERVED_PATTERN,
                    locator="intake desk", quote="rejects invoices lacking a PO line",
                    captured_at="2026-07-05").to_dict()


def test_agency_observation_without_label_is_rejected():
    log = OutcomeLog()
    bad = {"agency": "OGS", "observation": "x", "citation": _obs_citation()}  # no label
    try:
        log.load_agency_observation(bad)
        assert False, "observation without the required label must be rejected"
    except OutcomeLogError as exc:
        assert "label" in str(exc)


def test_agency_observation_wrong_citation_source_type_is_rejected():
    log = OutcomeLog()
    wrong = {
        "label": OBSERVED_PATTERN_LABEL, "agency": "OGS", "observation": "x",
        "citation": Citation("agency:OGS", SOLICITATION, "loc", "q", "2026-07-05").to_dict(),
    }
    try:
        log.load_agency_observation(wrong)
        assert False, "observation citation must be source_type=observed_pattern"
    except OutcomeLogError:
        pass


def test_agency_observation_valid_is_accepted():
    log = OutcomeLog()
    good = {"label": OBSERVED_PATTERN_LABEL, "agency": "OGS",
            "observation": "PO line required", "citation": _obs_citation()}
    rec = log.load_agency_observation(good)
    assert rec.label == OBSERVED_PATTERN_LABEL
    assert rec.citation.source_type == OBSERVED_PATTERN
    assert len(log.agency_observations) == 1


def test_invoice_and_bid_outcomes_capture_only():
    log = OutcomeLog()
    log.add_invoice_outcome(invoice_id="i1", preflight_verdict="PASS", actual=ACCEPTED)
    log.add_invoice_outcome(invoice_id="i2", preflight_verdict="PASS",
                            actual=REJECTED, rejection_code="MISSING_PO")
    log.add_bid_outcome(tender_id="t1", result=WON)
    log.add_bid_outcome(tender_id="t2", result="LOST", reason_code=REASON_PRICE,
                        reason_text="undercut on price")
    d = log.to_dict()
    assert len(d["invoice_outcomes"]) == 2 and len(d["bid_outcomes"]) == 2
    # rejected requires a code; accepted forbids one
    try:
        log.add_invoice_outcome(invoice_id="i3", preflight_verdict="PASS", actual=REJECTED)
        assert False, "REJECTED requires a rejection_code"
    except OutcomeLogError:
        pass


def test_asked_questions_log():
    log = OutcomeLog()
    log.add_asked_question(question="Is a site visit mandatory?",
                           solicitation="RFP-123", date="2026-07-01")
    q = log.asked_questions[0]
    assert q.agency_answer is None       # unanswered until the agency replies
    assert q.to_dict()["question"] == "Is a site visit mandatory?"


# ---------------------------------------------------------------------------
# schema contracts — required fields must be present (presence vs. null is a
# distinct, enforced contract that PRs 2-3 depend on). Dependency-free checker.
# ---------------------------------------------------------------------------

def _load_schema(name):
    return json.load(open(os.path.join(SCHEMA_DIR, name), encoding="utf-8"))


def _validate(instance, schema):
    """Minimal, stdlib-only structural check: required-field presence,
    additionalProperties:false, and top-level enum membership. Returns a list of
    error strings (empty == valid). Enough to lock the presence-vs-null contract
    without adding a jsonschema dependency."""
    errors = []
    props = schema.get("properties", {})
    for r in schema.get("required", []):
        if r not in instance:
            errors.append("missing required field: %s" % r)
    if schema.get("additionalProperties") is False:
        for k in instance:
            if k not in props:
                errors.append("unexpected field: %s" % k)
    for k, v in instance.items():
        spec = props.get(k)
        if isinstance(spec, dict) and "enum" in spec and v not in spec["enum"]:
            errors.append("enum violation: %s=%r" % (k, v))
    return errors


def _assert_each_required_field_is_enforced(instance, schema, label):
    """The valid instance passes; omitting ANY required field fails."""
    assert _validate(instance, schema) == [], "%s: valid instance should pass" % label
    for field in schema["required"]:
        broken = dict(instance)
        broken.pop(field)
        errs = _validate(broken, schema)
        assert any("missing required field: %s" % field == e for e in errs), \
            "%s: omitting %r must fail validation" % (label, field)


def test_dated_obligation_schema_requires_all_fields():
    schema = _load_schema("dated_obligation.schema.json")
    # a full, valid serialization (citation present, depends_on empty, due_date null)
    obl = make_user_obligation("o", "bid_deadline", "t1", None)   # unknown date
    inst = obl.to_dict(state="VERIFY")
    assert inst["due_date"] is None and inst["depends_on"] == []
    assert inst["citation"] is not None
    assert set(schema["required"]) == {
        "id", "kind", "source_object_id", "due_date", "date_status",
        "lead_times", "citation", "depends_on", "state"}
    _assert_each_required_field_is_enforced(inst, schema, "DatedObligation")


def test_citation_schema_requires_locator():
    schema = _load_schema("citation.schema.json")
    assert "locator" in schema["required"]
    # golden_rule: meaningful locator
    golden = Citation("source-exec-314-mwbe-cert-validity.md", GOLDEN_RULE,
                      "§ 314(5)(a)", "quote text", "2026-07-03").to_dict()
    _assert_each_required_field_is_enforced(golden, schema, "Citation(golden)")
    # user_entered: empty-string locator is allowed (present but blank)
    ue = Citation("user_entered:t1", USER_ENTERED, "", "2026-09-01", "2026-07-05").to_dict()
    assert ue["locator"] == ""
    assert _validate(ue, schema) == []


def test_transition_log_schema_requires_reason_and_citation():
    schema = _load_schema("transition_log_entry.schema.json")
    assert "reason" in schema["required"] and "citation" in schema["required"]
    sm = TenderStateMachine("t1")
    sm.transition(TRIAGED, "USER", "u1", "triaged", triage_verdict=BIDDABLE)
    inst = sm.log[-1].to_dict()
    assert inst["citation"] is None      # citation present, may be null
    _assert_each_required_field_is_enforced(inst, schema, "TransitionLogEntry")


def test_tender_and_contract_require_nullable_entity_id():
    for name, inst in (
        ("tender.schema.json",
         {"id": "t1", "entity_id": None, "tender_state": "WATCHING"}),
        ("contract.schema.json",
         {"id": "c1", "tender_id": "t1", "entity_id": None}),
    ):
        schema = _load_schema(name)
        assert "entity_id" in schema["required"], name
        # entity_id is required AND nullable
        assert schema["properties"]["entity_id"]["type"] == ["string", "null"], name
        assert _validate(inst, schema) == [], "%s valid (entity_id=null) should pass" % name
        broken = dict(inst)
        broken.pop("entity_id")
        assert any("missing required field: entity_id" == e
                   for e in _validate(broken, schema)), \
            "%s: omitting entity_id must fail" % name


# ---------------------------------------------------------------------------
# transition table rendering (smoke)
# ---------------------------------------------------------------------------

def test_transition_table_renders():
    txt = render_transition_table()
    assert "WATCHING" in txt and "-> " in txt and "(terminal)" in txt


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 74)
    print("DAILY-HABIT BACKEND — STATE PRIMITIVES ({} tests)".format(len(tests)))
    print("=" * 74)
    for name, fn in tests:
        try:
            fn()
            print("  [PASS] {}".format(name))
            passed += 1
        except Exception as exc:
            print("  [FAIL] {} :: {}: {}".format(name, type(exc).__name__, exc))
            failed += 1
    print("-" * 74)
    print("Totals: {} passed, {} failed".format(passed, failed))
    print("=" * 74)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(_run())
