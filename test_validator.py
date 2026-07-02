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
        val.check_vendrep(_load("sample-vendrep-pass.json")),
        val.check_vendrep(_load("sample-vendrep-fail-material-change.json")),
        val.check_bid(_load("sample-bid-pass.json")),
        val.check_bid(_load("sample-bid-fail-missing-eeo.json")),
        val.check_bid(_load("sample-bid-fail-overdue.json")),
        val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json")),
        val.validate_rm2_interest(_load("sample-contract-no-interest-directive-suspended.json")),
        val.validate_rm2_interest(_load("sample-contract-no-interest-no-directive.json")),
        val.validate_rm2_interest(_load("sample-contract-excluded-local-government.json")),
        val.validate_rm2_interest(_load("sample-contract-below-de-minimis.json")),
        val.validate_rm2_interest(_load("sample-contract-excluded-court-judgment.json")),
        val.validate_rm2_interest(_load("sample-contract-excluded-nonstate-intermediary.json")),
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
# RM-3 — VendRep stale-certification monitor
# --------------------------------------------------------------------------

def test_rm3_clean_questionnaire_passes():
    val = V.Validator(golden=GC)
    res = val.check_vendrep(_load("sample-vendrep-pass.json"))
    assert res.overall_status == V.STATUS_PASS, res.overall_status


def test_rm3_material_change_fails_requiring_recert():
    val = V.Validator(golden=GC)
    res = val.check_vendrep(_load("sample-vendrep-fail-material-change.json"))
    assert res.overall_status == V.STATUS_FAIL
    mc = [f for f in res.findings if f.evidence.get("material_change") == "ownership_change"]
    assert mc and mc[0].severity == V.FAIL and not mc[0].passed
    assert "material changes" in mc[0].citation_quote


def test_rm3_unsigned_certification_fails():
    val = V.Validator(golden=GC)
    doc = _load("sample-vendrep-pass.json")
    doc["certification"]["signed"] = False
    res = val.check_vendrep(doc)
    sig = [f for f in res.findings if "penalties of perjury" in f.citation_quote]
    assert sig and sig[0].severity == V.FAIL and not sig[0].passed
    assert res.overall_status == V.STATUS_FAIL


def test_rm3_recert_after_change_clears_to_pass():
    val = V.Validator(golden=GC)
    doc = _load("sample-vendrep-fail-material-change.json")
    doc["recertified_since_change"] = True
    res = val.check_vendrep(doc)
    assert res.overall_status == V.STATUS_PASS


def test_rm3_cites_the_form_specific_source_file():
    val = V.Validator(golden=GC)
    doc = _load("sample-vendrep-pass.json")
    doc["form"] = "AC 3293-S"
    res = val.check_vendrep(doc)
    assert all(f.source_file == V.VENDREP_FORMS["AC 3293-S"] for f in res.findings)
    # And the citation is genuinely verbatim in that specific file.
    for f in res.findings:
        assert f.citation_quote in GC.body(f.source_file)


# --------------------------------------------------------------------------
# RM-4 — MWBE deadline cascade + §143.3(c) EEO hard-block
# --------------------------------------------------------------------------

def test_rm4_all_met_passes():
    val = V.Validator(golden=GC)
    res = val.check_bid(_load("sample-bid-pass.json"))
    assert res.overall_status == V.STATUS_PASS, res.overall_status


def test_rm4_missing_eeo_is_hard_block_fail():
    val = V.Validator(golden=GC)
    res = val.check_bid(_load("sample-bid-fail-missing-eeo.json"))
    assert res.overall_status == V.STATUS_FAIL
    eeo = [f for f in res.findings if "EEO policy statement" in f.citation_quote]
    assert eeo and eeo[0].severity == V.FAIL and not eeo[0].passed


def test_rm4_overdue_utilization_plan_fails():
    val = V.Validator(golden=GC)
    res = val.check_bid(_load("sample-bid-fail-overdue.json"))
    assert res.overall_status == V.STATUS_FAIL
    up = [f for f in res.findings if f.evidence.get("deadline") == "Utilization plan"]
    assert up and up[0].evidence.get("status") == "OVERDUE" and not up[0].passed


def test_rm4_eeo_carveout_softens_to_warn():
    """A work force of 10 or fewer invokes the §143.3(c) staffing-plan carve-out;
    a missing EEO policy statement with written justification is a WARN, not FAIL."""
    val = V.Validator(golden=GC)
    doc = _load("sample-bid-pass.json")
    doc["eeo_policy_statement_submitted"] = False
    doc["eeo_justification_provided"] = True
    res = val.check_bid(doc)
    eeo = [f for f in res.findings if "EEO policy statement" in f.citation_quote]
    assert eeo and eeo[0].severity == V.WARN
    assert res.overall_status != V.STATUS_FAIL


def test_rm4_remedy_and_waiver_clocks_from_deficiency():
    """A deficiency notice starts the 7-bd remedy clock; if a waiver is requested,
    the 5-bd waiver clock. An unmet, overdue remedy FAILs."""
    val = V.Validator(golden=GC)
    doc = _load("sample-bid-pass.json")
    doc["deficiency_notice_date"] = "2026-06-19"
    doc["written_remedy_submitted_date"] = None
    doc["waiver_requested"] = True
    doc["waiver_form_submitted_date"] = None
    doc["today"] = "2026-07-06"  # well past both 7-bd and 5-bd cliffs
    res = val.check_bid(doc)
    remedy = [f for f in res.findings if f.evidence.get("deadline") == "Written remedy to deficiency"]
    waiver = [f for f in res.findings if f.evidence.get("deadline") == "Waiver form"]
    assert remedy and remedy[0].evidence.get("status") == "OVERDUE"
    assert waiver and waiver[0].evidence.get("status") == "OVERDUE"
    assert "seven (7) business days" in remedy[0].citation_quote
    assert "five (5) business days" in waiver[0].citation_quote
    assert res.overall_status == V.STATUS_FAIL


# --------------------------------------------------------------------------
# RM-2 — §179-v NFP interest calculator (GATED)
# --------------------------------------------------------------------------

def test_rm2_entitled_contract_computes_positive_interest():
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json"))
    assert res.extra["entitlement_arises"] is True
    assert res.extra["interest_amount_indicative"] > 0
    # Quarter-aware accrual across 2026-Q1 (6.0%) and Q2 (5.0%) on the two late
    # $100k payments. Locks the calculation against silent drift.
    assert abs(res.extra["interest_amount_indicative"] - 1635.62) < 0.01


def test_rm2_directive_suspended_blocks_interest():
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-no-interest-directive-suspended.json"))
    assert res.extra["entitlement_arises"] is False
    assert res.extra["interest_amount_indicative"] == 0.0
    susp = [f for f in res.findings if "suspend a written directive" in f.citation_quote]
    assert susp and not susp[0].passed


def test_rm2_no_written_directive_no_entitlement():
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-no-interest-no-directive.json"))
    assert res.extra["entitlement_arises"] is False
    assert res.extra["interest_amount_indicative"] == 0.0


def test_rm2_warranted_waiver_blocks_interest():
    val = V.Validator(golden=GC)
    doc = _load("sample-contract-entitled-to-interest.json")
    doc["warranted_waiver"] = True
    res = val.validate_rm2_interest(doc)
    assert res.extra["entitlement_arises"] is False
    waiver = [f for f in res.findings if "may mutually" in f.citation_quote]
    assert waiver and not waiver[0].passed


def test_rm2_ag_disapproval_blocks_interest():
    val = V.Validator(golden=GC)
    doc = _load("sample-contract-entitled-to-interest.json")
    doc["ag_approval"] = False
    res = val.validate_rm2_interest(doc)
    assert res.extra["entitlement_arises"] is False
    dis = [f for f in res.findings if "disapprove" in f.citation_quote]
    assert dis and not dis[0].passed


def test_rm2_uses_overpayment_rate_column_not_underpayment():
    """The repo's verified data README maps §179-v interest to the §1096(e)
    overpayment column; the calculator must use it (not the underpayment column)."""
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json"))
    assert res.extra["interest_rate_basis"]["column"] == "overpayment_rate_pct"


def test_rm2_is_gated_for_attorney_review():
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json"))
    assert res.attorney_review_required is True
    assert res.extra["attorney_review_required"] is True
    assert "licensed-attorney" in res.extra["gating_notice"]


def test_rm2_citing_quote_is_verbatim_entitlement_clause():
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json"))
    quote = res.extra["citing_quote"]
    assert quote in GC.body(V.STF179V)
    assert "scheduled commencement date" in quote


def test_rm2_never_hardcodes_rate_reads_from_csv():
    """Swapping in a different rate dataset changes the computed figure — proving
    the rate is read from data, not embedded in code."""
    doubled = V.InterestRates.__new__(V.InterestRates)
    doubled.column = "overpayment_rate_pct"
    base = V.InterestRates()
    doubled.rows = [(ps, pe, rate * 2, url, key) for (ps, pe, rate, url, key) in base.rows]
    val = V.Validator(golden=GC, rates=doubled)
    res = val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json"))
    assert abs(res.extra["interest_amount_indicative"] - 1635.62 * 2) < 0.02


def test_rm2_de_minimis_floor_blocks_small_interest():
    """§179-f: a computed interest below $10 yields no entitlement, cited to §179-f."""
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-below-de-minimis.json"))
    assert res.extra["entitlement_arises"] is False
    assert 0 < res.extra["interest_amount_indicative"] < 10
    assert res.extra["de_minimis_floor_applies"] is True
    floor = [f for f in res.findings if "less than ten dollars" in f.citation_quote]
    assert floor and not floor[0].passed
    assert floor[0].source_file == V.STF179F


def test_rm2_excluded_local_government_blocks_interest():
    """§179-p clause 3: a local-government payee is excluded, no interest
    computed, cited verbatim to the §179-p exclusion clause."""
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-excluded-local-government.json"))
    assert res.extra["entitlement_arises"] is False
    assert res.extra["excluded"] is True
    assert res.extra["interest_amount_indicative"] == 0.0
    excl = [f for f in res.findings if f.evidence.get("excluded") is True]
    assert excl and excl[0].source_file == V.STF179P
    assert "unit of local government" in excl[0].citation_quote


def test_rm2_public_authority_and_payment_type_exclusions():
    """Each excluded payee category / payment type is caught and cited verbatim to §179-p."""
    val = V.Validator(golden=GC)
    for cat, needle in [("public_authority", "public authority or public benefit corporation"),
                        ("state_employee", "employees of state agencies when acting in"),
                        ("third_party_payment_contractor", "third party payment agreements")]:
        doc = _load("sample-contract-entitled-to-interest.json")
        doc["payee_category"] = cat
        res = val.validate_rm2_interest(doc)
        assert res.extra["excluded"] is True, cat
        excl = [f for f in res.findings if f.evidence.get("excluded") is True]
        assert excl and needle in excl[0].citation_quote, cat
        assert excl[0].source_file == V.STF179P, cat
    doc = _load("sample-contract-entitled-to-interest.json")
    doc["payment_type"] = "eminent_domain"
    res = val.validate_rm2_interest(doc)
    assert res.extra["excluded"] is True
    excl = [f for f in res.findings if f.evidence.get("excluded") is True]
    assert excl and "eminent domain procedure law" in excl[0].citation_quote


def test_rm2_court_judgment_payment_excluded():
    """§179-p clause 2 (NEW): interest on a non-Article-11-A court judgment is excluded."""
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-excluded-court-judgment.json"))
    assert res.extra["entitlement_arises"] is False
    assert res.extra["excluded"] is True
    assert res.extra["interest_amount_indicative"] == 0.0
    excl = [f for f in res.findings if f.evidence.get("excluded") is True]
    assert excl and excl[0].source_file == V.STF179P
    assert "judgments rendered by a court" in excl[0].citation_quote


def test_rm2_non_state_agency_intermediary_payee_excluded():
    """§179-p clause 5 (NEW): an entity receiving state funds via a non-state-agency
    intermediary is excluded."""
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-excluded-nonstate-intermediary.json"))
    assert res.extra["entitlement_arises"] is False
    assert res.extra["excluded"] is True
    assert res.extra["interest_amount_indicative"] == 0.0
    excl = [f for f in res.findings if f.evidence.get("excluded") is True]
    assert excl and excl[0].source_file == V.STF179P
    assert "intermediary organization other than a state agency" in excl[0].citation_quote


def test_rm2_setoff_exclusion_grounds_179e_definition():
    """§179-p clause 6 set-off is excluded and additionally grounded in the
    §179-e(8) definition of 'Set-off'."""
    val = V.Validator(golden=GC)
    doc = _load("sample-contract-entitled-to-interest.json")
    doc["payment_type"] = "set_off"
    res = val.validate_rm2_interest(doc)
    assert res.extra["excluded"] is True
    excl = [f for f in res.findings if f.evidence.get("excluded") is True]
    assert excl and "legally authorized set-off" in excl[0].citation_quote
    setoff_def = [f for f in res.findings if f.source_file == V.STF179E
                  and "reduction by the comptroller" in f.citation_quote]
    assert setoff_def, "expected a §179-e(8) set-off definition grounding finding"


def test_rm2_refinements_keep_attorney_review_gate():
    """The de minimis / exclusion refinements must not drop the attorney-review gate."""
    val = V.Validator(golden=GC)
    for fx in ("sample-contract-below-de-minimis.json",
               "sample-contract-excluded-local-government.json",
               "sample-contract-excluded-court-judgment.json",
               "sample-contract-excluded-nonstate-intermediary.json"):
        res = val.validate_rm2_interest(_load(fx))
        assert res.attorney_review_required is True


def test_rm2_normal_payee_not_excluded_stays_entitled():
    """A non-excluded payee with a normal payment type is not screened out."""
    val = V.Validator(golden=GC)
    res = val.validate_rm2_interest(_load("sample-contract-entitled-to-interest.json"))
    assert res.extra["excluded"] is False
    assert res.extra["entitlement_arises"] is True


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
