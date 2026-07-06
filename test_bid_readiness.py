#!/usr/bin/env python3
"""
Tests for bid_readiness.py (BUILD SPEC v2 Part A — the centerpiece).

Runnable two ways:
    python3 test_bid_readiness.py
    pytest test_bid_readiness.py

Covers:
  * PROVENANCE SPLIT — confirmed rules carry a verbatim golden-copy cite()
    (validated through the choke-point); tender excerpts are NEVER passed to
    cite(); unbacked requirements are flagged "not confirmed".
  * GREEN/YELLOW/RED logic, incl. GREEN requires BOTH satisfied AND grounded.
  * Transparent score: weighted mean, only over checkable requirements.
  * Gap + action lists; RED blockers surfaced.
  * "Show the work" summary counts (pages read / found / checked).
"""

import os
import sys

import validator as V
import bid_readiness as BR
from tender_extractor import extract, find_requirements

HERE = os.path.dirname(os.path.abspath(__file__))
GC = V.GoldenCopy()
PDF = os.path.join(HERE, "sample-tender.pdf")
PROFILE = os.path.join(HERE, "sample-vendor-profile.json")


def _profile(**overrides):
    import json
    with open(PROFILE, "r", encoding="utf-8") as fh:
        p = json.load(fh)
    p.update(overrides)
    return p


def _report(profile=None):
    return BR.score_bid(extract(PDF), profile or _profile(), golden=GC)


def test_grounding_quotes_are_verbatim_through_choke_point():
    """Every grounding candidate that survives must be verbatim in its source —
    i.e. it passed GoldenCopy.cite(). Auto-downgrade keeps the rest honest."""
    rules = BR._build_rules(GC)
    for kind, rule in rules.items():
        g = rule["grounding"]
        if g is not None:
            assert g["citation_quote"] in GC.body(g["source_file"]), kind


def test_confirmed_rules_cite_golden_copy():
    rep = _report()
    eeo = [r for r in rep.rows if r.kind == "eeo"][0]
    assert eeo.grounding is not None
    assert eeo.grounding["source_file"] == "source-mwbe-5nycrr-pass-fail.md"
    # And it is verbatim in golden copy (the real choke-point).
    assert GC.cite(eeo.grounding["source_file"], eeo.grounding["citation_quote"])


def test_eeo_mwbe_grounding_is_verify_gated_both_directions():
    """The migrated bid_readiness cite: the EEO rule's grounding is mwbe-5nycrr, a
    gated (INTERIM_VERIFY) source, cited with output_context=VERIFY. Both
    directions on the ACTUAL bid_readiness path:
      * forward — _build_rules produces the eeo grounding (the VERIFY floor admits
        the gated source) and it is verbatim golden;
      * reverse — the exact (source, quote) it grounds is BLOCKED in a CONFIDENT
        context and ALLOWED in VERIFY / attorney-gated: a gated citation, never a
        confident one."""
    import engine.golden_status as gs
    rules = BR._build_rules(GC)
    eeo = rules["eeo"]["grounding"]
    assert eeo is not None and eeo["source_file"] == "source-mwbe-5nycrr-pass-fail.md"
    src, q = eeo["source_file"], eeo["citation_quote"]
    assert q in GC.body(src)                                    # forward: attached + verbatim
    try:
        GC.cite(src, q, output_context=gs.OUTPUT_CONFIDENT)     # reverse: blocked confident
        raise AssertionError("eeo mwbe grounding must not be confident-eligible")
    except V.GoldenEligibilityError as e:
        assert e.status == gs.INTERIM_VERIFY
    assert GC.cite(src, q, output_context=gs.OUTPUT_VERIFY) == q            # allowed VERIFY
    assert GC.cite(src, q, output_context=gs.OUTPUT_ATTORNEY_GATED) == q    # allowed attorney-gated


def test_tender_excerpts_never_pass_through_cite():
    """A tender excerpt must NOT be citable as golden copy — proving we keep the
    provenance split. (If one happened to be verbatim, that would be an
    accident we still must not rely on; here we assert the design boundary.)"""
    rep = _report()
    for r in rep.rows:
        # The excerpt is tagged to the tender, page N — not a golden source.
        d = r.to_dict()
        assert d["tender_provenance"].startswith("this tender, page")
        # Unbacked requirements must be explicitly flagged not confirmed.
        if r.grounding is None:
            assert d["grounding"]["confirmed"] is False


def test_unbacked_requirement_flagged_not_confirmed():
    rep = _report()
    bond = [r for r in rep.rows if r.kind == "bonding"][0]
    assert bond.grounding is None
    assert bond.to_dict()["grounding"]["confirmed"] is False


def test_green_requires_satisfied_and_grounded():
    rep = _report()
    eeo = [r for r in rep.rows if r.kind == "eeo"][0]
    assert eeo.vendor_has is True and eeo.grounding is not None
    assert eeo.status == BR.GREEN


def test_met_but_unconfirmed_is_yellow_not_green():
    """NYS Vendor File registration is satisfied by the profile but has no
    golden-copy rule — it must be YELLOW, never a confident GREEN."""
    rep = _report()
    reg = [r for r in rep.rows if r.kind == "registration"][0]
    assert reg.vendor_has is True and reg.grounding is None
    assert reg.status == BR.YELLOW


def test_unmet_mandatory_is_red_blocker():
    rep = _report()
    mwbe = [r for r in rep.rows if r.kind == "mwbe"][0]
    assert mwbe.must is True and mwbe.vendor_has is False
    assert mwbe.status == BR.RED
    assert mwbe in rep.blocking


def test_unmet_goal_is_yellow_not_red():
    rep = _report()
    sdvob = [r for r in rep.rows if r.kind == "sdvob"][0]
    assert sdvob.must is False and sdvob.vendor_has is False
    assert sdvob.status == BR.YELLOW


def test_insurance_limit_shortfall_is_yellow_with_issue_and_fix():
    rep = _report()
    ins = [r for r in rep.rows if r.kind == "insurance"][0]
    assert ins.status == BR.YELLOW
    assert "1,000,000" in (ins.issue or "") and "2,000,000" in (ins.issue or "")
    assert "2,000,000" in (ins.fix or "")  # the FIX names the required limit


def test_all_satisfied_profile_scores_higher():
    """A profile that satisfies the mandatory checks must outscore the sample."""
    strong = _profile(mwbe_utilization_plan_ready=True, bid_bond_available=True,
                      general_liability_limit_usd=5000000)
    base = _report().score
    better = _report(strong).score
    assert better > base, (base, better)


def test_score_is_weighted_mean_over_checkable_only():
    rep = _report()
    # Score must be 0..100 and computed only over rows with a profile answer.
    assert 0.0 <= rep.score <= 100.0
    assert all(r.checkable for r in rep.checkable_rows)
    assert len(rep.checkable_rows) <= rep.requirements_found


def test_work_summary_shows_its_work():
    rep = _report()
    d = rep.to_dict()["work_summary"]
    assert d["pages_read"] == 3
    assert d["requirements_found"] >= 6
    assert d["requirements_checked_against_profile"] >= 5


def test_appendix_a_clause_grounded_confirmed_not_flagged():
    """Step-3 grounding: the Iran clause read from the tender carries a verbatim
    Appendix A citation instead of 'not confirmed'."""
    rep = _report()
    row = [r for r in rep.rows if r.kind == "iran_divestment"]
    assert row, "expected an iran_divestment row from the sample tender"
    g = row[0].grounding
    assert g is not None and g["source_file"] == "source-appendix-a-june2023.md"
    assert GC.cite(g["source_file"], g["citation_quote"])  # verbatim choke-point


def test_statute_grounded_rules_cite_dedicated_sources():
    """Rules with a dedicated statute file ground to it (verbatim), not to a
    'not confirmed' flag: §139-d (non-collusion), WCL §57 (workers' comp),
    §139-l (sexual harassment), §139-m (gender-based violence)."""
    rep = _report()
    expected = {
        "non_collusion": "source-stf-139-d-noncollusion.md",
        "insurance_workers": "source-wkc-57-workers-comp.md",
        "sexual_harassment": "source-stf-139-l-sexual-harassment.md",
        "gender_based_violence": "source-stf-139-m-gender-based-violence.md",
    }
    for kind, src in expected.items():
        row = [r for r in rep.rows if r.kind == kind]
        assert row, "expected a {} row from the sample tender".format(kind)
        g = row[0].grounding
        assert g is not None and g["source_file"] == src, kind
        assert GC.cite(g["source_file"], g["citation_quote"])  # verbatim


def test_workers_comp_now_grounded_is_green():
    """Workers' comp was 'not confirmed' (YELLOW); grounded to WCL §57 it is a
    confident GREEN when the profile satisfies it."""
    rep = _report()
    wc = [r for r in rep.rows if r.kind == "insurance_workers"][0]
    assert wc.vendor_has is True and wc.grounding is not None
    assert wc.status == BR.GREEN


def test_non_collusion_satisfied_and_grounded_is_green():
    """When the profile satisfies it, a statute-grounded rule goes GREEN with no
    issue/fix (the cure note still attaches — it describes the rule)."""
    rep = _report(_profile(non_collusion_certification_ready=True))
    nc = [r for r in rep.rows if r.kind == "non_collusion"][0]
    assert nc.vendor_has is True and nc.grounding is not None
    assert nc.status == BR.GREEN
    assert nc.issue is None and nc.fix is None


def test_iran_unsatisfied_mandatory_is_red_blocker_with_confirmed_cite():
    rep = _report()
    iran = [r for r in rep.rows if r.kind == "iran_divestment"][0]
    assert iran.must is True and iran.vendor_has is False
    assert iran.status == BR.RED and iran in rep.blocking
    assert iran.grounding is not None  # RED, yet citation-grounded (Track 1)


def test_action_list_collects_fixes_red_before_yellow():
    rep = _report()
    actions = rep.actions
    labels = {a["for"] for a in actions}
    assert "MWBE utilization plan" in labels
    assert "Bid bond" in labels
    # Every action carries a concrete FIX text, never an empty flag.
    assert all(a["fix"] for a in actions)
    # Ordering: all RED fixes precede all YELLOW fixes.
    statuses = [a["status"] for a in actions]
    last_red = max((i for i, s in enumerate(statuses) if s == BR.RED), default=-1)
    first_yellow = min((i for i, s in enumerate(statuses) if s == BR.YELLOW),
                       default=len(statuses))
    assert last_red < first_yellow, statuses


def test_every_nongreen_finding_has_issue_and_fix():
    """The core output rule: every RED/YELLOW explains itself; GREEN/N-A do not."""
    rep = _report()
    for r in rep.rows:
        if r.status in (BR.GREEN, BR.NA):
            assert r.issue is None and r.fix is None, r.label
        else:
            assert r.issue and r.fix, "{} ({}) missing issue/fix".format(
                r.label, r.status)


# --------------------------------------------------------------------------
# Threshold gating (contract-value-dependent rules)
# --------------------------------------------------------------------------

def test_contract_value_extracted_from_tender():
    assert _report().contract_value == 250000


def test_contract_value_zero_blank_invalid_are_unknown():
    """0 / null / non-numeric are NOT 'below threshold' — they are unknown."""
    assert BR._contract_value({"pages": []}, {}) is None
    assert BR._contract_value({}, {"contract_value_usd": 0}) is None
    assert BR._contract_value({}, {"contract_value_usd": None}) is None
    assert BR._contract_value({}, {"contract_value_usd": "abc"}) is None
    assert BR._contract_value({}, {"contract_value_usd": False}) is None
    assert BR._contract_value({}, {"contract_value_usd": 90000}) == 90000


def _sales_tax_row(rep):
    rows = [r for r in rep.rows if r.kind == "sales_tax_5a"]
    return rows[0] if rows else None


def test_value_above_threshold_rule_applies():
    # sample tender value 250000 > $100k §5-a threshold → rule applies, evaluated.
    rep = _report(_profile(sales_tax_certificate_of_authority=True))
    st = _sales_tax_row(rep)
    assert st is not None and st.status == BR.GREEN


def test_value_below_threshold_is_na_and_excluded_from_score():
    rep = _report(_profile(contract_value_usd=30000))
    st = _sales_tax_row(rep)
    assert st is not None and st.status == BR.NA
    assert "below" in (st.note or "") and "100,000" in (st.note or "")
    assert st.issue is None and st.fix is None
    # Excluded from scoring and from the GREEN/YELLOW/RED counts entirely.
    assert st not in rep.checkable_rows
    assert sum(rep.counts.values()) + len(rep.na_rows) == \
        len([r for r in rep.rows if r.status in (BR.GREEN, BR.YELLOW, BR.RED, BR.NA)])


def test_value_zero_is_not_below_threshold_but_unknown_yellow():
    """A zero contract value must NOT silently skip §5-a — it is YELLOW unknown."""
    rep = _report(_profile(contract_value_usd=0))
    st = _sales_tax_row(rep)
    assert st is not None and st.status == BR.YELLOW
    assert "couldn't be determined" in (st.issue or "")
    assert "100,000" in (st.issue or "") and "verify" in (st.fix or "").lower()
    assert st not in rep.na_rows  # NOT treated as N/A


def test_value_unknown_keeps_threshold_rule_visible_not_skipped():
    rep = _report(_profile(contract_value_usd=None))
    st = _sales_tax_row(rep)
    assert st is not None and st.status == BR.YELLOW  # surfaced, never dropped


def test_per_hour_rate_is_not_read_as_contract_value():
    """The real $50/hour mediation-rate pattern must resolve to UNKNOWN, not a
    $50 contract value that would void mandatory rules."""
    ex = {"pages": ["Mediation is held (not to exceed 3 hours) ($50 per hour). "
                    "Fee for each additional session ($175 for each additional)."]}
    assert BR._extract_contract_value(ex) is None
    assert BR._contract_value(ex, {}) is None


def test_wrong_positive_value_never_downgrades_mandatory_to_na():
    """A per-unit rate near a threshold-gated MANDATORY rule must leave it YELLOW
    'verify', never N/A. A wrong positive fails safe toward verify."""
    ex = {"pages": [
        "Bidders must submit an MWBE utilization plan.",
        "Contractor equal employment opportunity policy is required.",
        "Compensation is billed at ($50 per hour), not to exceed 3 hours."]}
    rep = BR.score_bid(ex, {}, golden=GC)
    for kind in ("mwbe", "eeo"):
        row = [r for r in rep.rows if r.kind == kind]
        if row:
            assert row[0].status != BR.NA, kind
            assert row[0].status == BR.YELLOW, kind


def test_quoted_statutory_threshold_is_not_contract_value():
    """Boilerplate thresholds ('in excess of $300,000', 'equal or exceed
    $100,000') are quoted rules, not this contract's value → UNKNOWN."""
    ex = {"pages": ["cumulative value in excess of $300,000 measured over a year",
                    "if the subcontract will equal or exceed $100,000 over the life"]}
    assert BR._extract_contract_value(ex) is None


def test_clean_total_value_label_still_extracts():
    ex = {"pages": ["The total contract value is $450,000 for the full term."]}
    assert BR._extract_contract_value(ex) == 450000
    ex2 = {"pages": ["Bids not to exceed $500,000 for this procurement."]}
    assert BR._extract_contract_value(ex2) == 500000


# --------------------------------------------------------------------------
# Flood suppression — unmapped passages are summarised, not one row each
# --------------------------------------------------------------------------

def test_unmapped_passages_are_clustered_not_flooded():
    lines = ["The contractor shall clean widget number {}.".format(i)
             for i in range(60)]
    lines += ["Bidders must submit an MWBE utilization plan."]
    rep = BR.score_bid({"pages": lines, "page_count": 1,
                        "source": "x", "has_text_layer": True}, {}, golden=GC)
    # None of the 60 boilerplate 'shall' lines become findings rows.
    assert all(r.kind not in ("general", "certification") for r in rep.rows)
    # They are captured as 'other', surfaced as a small clustered summary.
    assert len(rep.other_requirements) >= 60
    d = rep.to_dict()
    assert d["other_requirements"]["detected"] >= 60
    assert len(d["other_requirements"]["samples"]) <= 8
    # The mapped MWBE finding still shows up as a real row.
    assert any(r.kind == "mwbe" for r in rep.rows)


def test_cluster_other_dedupes_identical_passages():
    rep = BR.score_bid({"pages": ["The vendor shall do the thing."] * 20,
                        "page_count": 1, "source": "x", "has_text_layer": True},
                       {}, golden=GC)
    unique, samples = rep.cluster_other()
    assert unique == 1 and len(samples) == 1


# --------------------------------------------------------------------------
# Fix 3 — surface the real numbers near a keyword
# --------------------------------------------------------------------------

def test_mwbe_and_sdvob_goal_percent_surfaced():
    blob = ("The MWBE participation goal for this contract is 30%. "
            "The SDVOB participation goal is 6% of the total.")
    assert BR._goal_pct_near(blob, BR._MWBE_TERM_RE) == "30%"
    assert BR._goal_pct_near(blob, BR._SDVOB_TERM_RE) == "6%"


def test_goal_extraction_requires_a_goal_hint():
    # A bare percentage with no goal/rate hint is not surfaced as a goal.
    assert BR._goal_pct_near("MWBE firms completed 95% of prior work",
                             BR._MWBE_TERM_RE) is None


def test_insurance_minimum_extracted_from_amount_phrase():
    assert BR._insurance_limit(
        "must carry insurance in an amount not less than $1,000,000 per claim") \
        == 1000000


def test_mwbe_goal_detail_appears_on_the_finding():
    ex = {"pages": ["Bidders must submit an MWBE utilization plan.",
                    "The MWBE participation goal for this contract is 30%."],
          "page_count": 1, "source": "x", "has_text_layer": True}
    rep = BR.score_bid(ex, _profile(contract_value_usd=250000), golden=GC)
    mwbe = [r for r in rep.rows if r.kind == "mwbe"][0]
    assert mwbe.detail and "30%" in mwbe.detail


# --------------------------------------------------------------------------
# Scope gating (public-work / Article 8) — Labor Law §220-i
# --------------------------------------------------------------------------

def _pw_row(rep):
    rows = [r for r in rep.rows if r.kind == "public_work_registration"]
    return rows[0] if rows else None


def test_public_work_rule_grounded_verbatim():
    rep = _report()
    pw = _pw_row(rep)
    assert pw is not None and pw.grounding is not None
    assert pw.grounding["source_file"] == "source-lab-220-i-public-work-registration.md"
    assert GC.cite(pw.grounding["source_file"], pw.grounding["citation_quote"])


def test_public_work_unknown_is_yellow_not_skipped():
    """Default services tender: can't confirm Article 8 → YELLOW, never dropped."""
    rep = _report()
    pw = _pw_row(rep)
    assert pw.status == BR.YELLOW
    assert "couldn't determine" in (pw.issue or "").lower()
    assert "article 8" in (pw.issue or "").lower()


def test_public_work_false_is_na_not_red():
    rep = _report(_profile(public_work_project=False))
    pw = _pw_row(rep)
    assert pw.status == BR.NA and pw not in rep.checkable_rows
    assert "not an Article 8" in (pw.note or "")


def test_public_work_true_missing_registration_is_red_blocker():
    rep = _report(_profile(public_work_project=True,
                           public_work_contractor_registered=False))
    pw = _pw_row(rep)
    assert pw.status == BR.RED and pw in rep.blocking
    assert "Certificate of Registration" in (pw.fix or "")
    assert "application is not a substitute" in (pw.fix or "")


def test_public_work_true_registered_is_green():
    rep = _report(_profile(public_work_project=True,
                           public_work_contractor_registered=True))
    pw = _pw_row(rep)
    assert pw.status == BR.GREEN and pw.issue is None and pw.fix is None


# --------------------------------------------------------------------------
# §139-h international boycott — threshold $5k, WARN (never RED)
# --------------------------------------------------------------------------

def _boycott_row(rep):
    rows = [r for r in rep.rows if r.kind == "international_boycott"]
    return rows[0] if rows else None


def test_boycott_is_warn_never_red_even_when_unmet():
    """§139-h is a material condition (must=False) — unmet is YELLOW, not RED,
    even above the $5,000 threshold."""
    rep = _report(_profile(international_boycott_certification_ready=False))
    b = _boycott_row(rep)
    assert b is not None and b.must is False
    assert b.status == BR.YELLOW and b not in rep.blocking
    assert b.grounding["source_file"] == "source-stf-139-h-international-boycott.md"


def test_boycott_below_5k_threshold_is_na():
    rep = _report(_profile(contract_value_usd=3000))
    b = _boycott_row(rep)
    assert b is not None and b.status == BR.NA
    assert "5,000" in (b.note or "")


def test_noncollusion_carries_cure_note_others_do_not():
    """Part 3: §139-d gets the cure-provision note; §139-l/§139-m are absolute."""
    rep = _report()
    nc = [r for r in rep.rows if r.kind == "non_collusion"][0]
    assert nc.note and "cure provision" in nc.note
    assert "sole discretion" in nc.note
    for kind in ("sexual_harassment", "gender_based_violence"):
        row = [r for r in rep.rows if r.kind == kind][0]
        assert row.note is None, "{} must not carry a cure note".format(kind)


# --------------------------------------------------------------------------
# Coverage taxonomy + fail-closed coverage_complete gate (PR #45)
# --------------------------------------------------------------------------

def _mk(pages, profile=None):
    ex = {"pages": pages, "page_count": 1, "source": "x", "has_text_layer": True}
    return BR.score_bid(ex, profile or {}, golden=GC)


def test_coverage_taxonomy_three_statuses_present_on_sample():
    """VERIFIED_MATCH, NEEDS_REVIEW and UNMAPPED are all represented on the real
    sample tender, and the per-row coverage is exposed."""
    rep = _report()
    verified, needs_review = rep.coverage_buckets
    assert verified and needs_review                       # both present
    assert all(r.coverage == BR.VERIFIED_MATCH for r in verified)
    assert all(r.coverage == BR.NEEDS_REVIEW for r in needs_review)
    c = rep.coverage_counts
    assert c[BR.VERIFIED_MATCH] > 0 and c[BR.NEEDS_REVIEW] > 0 and c[BR.UNMAPPED] > 0


def test_verified_match_is_grounded_row():
    rep = _report()
    eeo = [r for r in rep.rows if r.kind == "eeo"][0]
    assert eeo.grounding is not None and eeo.coverage == BR.VERIFIED_MATCH


def test_similar_but_not_exact_requirement_is_needs_review_not_verified():
    """A requirement mapped to a kind that has NO golden-copy grounding (bid bond,
    insurance) is NEEDS_REVIEW / POSSIBLE_MATCH — never VERIFIED_MATCH."""
    rep = _report()
    for kind in ("bonding", "insurance", "registration"):
        row = [r for r in rep.rows if r.kind == kind][0]
        assert row.grounding is None
        assert row.coverage == BR.NEEDS_REVIEW
        assert row.coverage != BR.VERIFIED_MATCH
    assert BR.POSSIBLE_MATCH == BR.NEEDS_REVIEW           # spec alias


def test_missing_golden_match_is_not_treated_as_no_requirement():
    """A kind-mapped requirement with no golden grounding still appears as a real
    row (NEEDS_REVIEW) and blocks coverage — it is NOT silently 'no requirement'."""
    rep = _mk(["A bid bond equal to 5% of the bid amount is required."])
    bond = [r for r in rep.rows if r.kind == "bonding"]
    assert bond, "the bonding requirement must not be dropped"
    assert bond[0].coverage == BR.NEEDS_REVIEW
    assert rep.coverage_complete is False


def test_one_unmapped_item_forces_coverage_incomplete():
    """STANDING: a single UNMAPPED passage forces coverage_complete = False."""
    rep = _mk(["The contractor shall paint the widget green."])
    assert rep.other_requirements                          # captured, not dropped
    assert rep.coverage_counts[BR.UNMAPPED] >= 1
    assert rep.coverage_complete is False


def test_one_needs_review_item_forces_coverage_incomplete():
    """STANDING: a single NEEDS_REVIEW (kind-mapped, ungrounded) item forces
    coverage_complete = False."""
    rep = _mk(["A bid bond equal to 5% of the bid amount is required."])
    assert rep.coverage_counts[BR.NEEDS_REVIEW] >= 1
    assert rep.coverage_counts[BR.UNMAPPED] == 0
    assert rep.coverage_complete is False


def test_unmapped_form_certification_forces_coverage_incomplete():
    """An RFQ form/authority reference not mapped to a verified rule forces the
    gate False (via UNMAPPED or the possible-authority bucket)."""
    rep = _mk(["Vendors register under Environmental Conservation Law § 17-0303."])
    assert rep.possible_authorities                        # captured
    assert rep.coverage_counts[BR.UNMAPPED] >= 1
    assert rep.coverage_complete is False


def test_unmapped_authority_appears_in_gap_report():
    """An unmapped authority reference is surfaced (possible-authority bucket),
    both in the JSON and rendered output — never silently dropped."""
    rep = _mk(["Vendors register under Environmental Conservation Law § 17-0303."])
    d = rep.to_dict()
    assert d["coverage"]["possible_authorities"]["detected"] >= 1
    out = BR.render_bid_readiness(rep)
    assert "POSSIBLE AUTHORITIES REFERENCED" in out
    assert "Environmental Conservation Law" in out


def test_cueless_grounded_keyword_hit_is_not_verified_match():
    """Item C regression: a grounded rule KIND reached by an incidental keyword
    with NO obligation cue in the passage must NOT become VERIFIED_MATCH — it
    inherits nothing and stays NEEDS_REVIEW."""
    rep = _mk(["The agency deeply values the workers' compensation of its own staff."])
    wc = [r for r in rep.rows if r.kind == "insurance_workers"]
    assert wc, "the keyword still maps to a row (not dropped)"
    assert wc[0].grounding is not None                     # grounded KIND...
    assert wc[0].coverage == BR.NEEDS_REVIEW               # ...but cue-less → not verified
    assert wc[0].coverage != BR.VERIFIED_MATCH


def test_verified_match_requires_obligation_cue_in_passage():
    """VERIFIED_MATCH demands BOTH a grounded kind AND an obligation cue in this
    passage; the same grounded kind WITH a cue is VERIFIED_MATCH."""
    cued = _mk(["Contractors must maintain workers' compensation coverage."])
    wc = [r for r in cued.rows if r.kind == "insurance_workers"][0]
    assert wc.grounding is not None and BR.has_obligation_cue(wc.tender_excerpt)
    assert wc.coverage == BR.VERIFIED_MATCH


def test_passing_narrative_authority_makes_no_spurious_unmapped():
    """PRECISION: a passing narrative authority mention creates no UNMAPPED item
    and no possible-authority item."""
    rep = _mk(["Pursuant to State Finance Law, the agency issues this RFQ."])
    assert rep.other_requirements == []
    assert rep.possible_authorities == []
    assert rep.coverage_counts[BR.UNMAPPED] == 0


def test_coverage_complete_can_be_true_when_all_verified():
    """The gate is not vacuous: a tender whose only item is a grounded rule with no
    unmapped/possible items yields coverage_complete = True."""
    rep = _mk(["Bidders must certify compliance with the Iran Divestment Act "
               "under State Finance Law 165-a."],
              profile={"iran_divestment_certification_ready": True})
    assert rep.coverage_counts[BR.UNMAPPED] == 0
    assert rep.coverage_counts[BR.NEEDS_REVIEW] == 0
    assert rep.coverage_complete is True


def test_coverage_complete_is_literal_derivation_not_stored_flag():
    """coverage_complete is derived from item counts every call — mutating the
    counts (adding an unmapped item) flips it, proving it is not a cached flag."""
    rep = _mk(["Bidders must certify compliance with the Iran Divestment Act "
               "under State Finance Law 165-a."],
              profile={"iran_divestment_certification_ready": True})
    assert rep.coverage_complete is True
    rep.other_requirements.append({"text": "surprise unmapped duty", "page": 9})
    assert rep.coverage_complete is False                  # re-derived, not stored


def test_top_level_coverage_complete_field_matches_gate():
    rep = _report()
    d = rep.to_dict()
    assert d["coverage_complete"] == rep.coverage_complete
    assert d["coverage"]["coverage_complete"] == rep.coverage_complete
    assert d["coverage"]["counts"] == rep.coverage_counts


def test_no_complete_headline_renders_while_coverage_incomplete():
    """STANDING: no PASS/COMPLETE headline may render while coverage_complete is
    False. If a later change lets a COMPLETE headline print with an unmapped or
    needs-review item present, this fails."""
    rep = _report()
    assert rep.coverage_complete is False
    out = BR.render_bid_readiness(rep)
    assert BR.HEADLINE_COVERAGE_INCOMPLETE in out
    assert BR.HEADLINE_COVERAGE_COMPLETE not in out        # positive headline absent
    assert "NOT COMPLETE" in out


def test_complete_headline_renders_only_when_coverage_complete():
    rep = _mk(["Bidders must certify compliance with the Iran Divestment Act "
               "under State Finance Law 165-a."],
              profile={"iran_divestment_certification_ready": True})
    assert rep.coverage_complete is True
    out = BR.render_bid_readiness(rep)
    assert BR.HEADLINE_COVERAGE_COMPLETE in out


def test_render_separates_verified_from_needs_review_and_unmapped():
    """User-facing output visibly separates VERIFIED from NEEDS_REVIEW / UNMAPPED."""
    out = BR.render_bid_readiness(_report())
    assert "VERIFIED against golden copy" in out
    assert "NEEDS REVIEW" in out
    assert "UNMAPPED RFQ passages" in out
    # The 'found in RFQ but not verified' language is present for unmapped items.
    assert "not verified in the golden copy" in out


def test_na_rows_excluded_from_coverage_buckets():
    """A rule below its threshold (N/A) is not a requirement for this contract and
    is excluded from the coverage taxonomy counts."""
    rep = _report(_profile(contract_value_usd=30000))
    st = [r for r in rep.rows if r.kind == "sales_tax_5a"][0]
    assert st.status == BR.NA
    verified, needs_review = rep.coverage_buckets
    assert st not in verified and st not in needs_review


def test_citation_audit_still_end_to_end_yes_after_pr45():
    """Guardrail invariant (PR #44): the citation audit still prints END-TO-END
    YES, the runtime surface is unchanged, and nothing is unclassified — this PR
    added no new cite() path."""
    sys.path.insert(0, os.path.join(HERE, "scripts"))
    import golden_audit as ga
    rep = ga.run()
    assert rep["enforcement_complete"] is True
    assert rep["cite_surface_unclassified"] == []
    assert rep["unmigrated_cite_sites"] == []
    assert set(rep["cite_surface_runtime"]) == {
        "validator.py", "bid_readiness.py", "cert_renewal.py", "gap_analysis.py",
        "engine/citation.py", "engine/payment_clock.py"}
    assert "ENFORCED END-TO-END: YES" in ga.render(rep)


def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("BID-READINESS (Part A) — TEST SUITE ({} tests)".format(len(tests)))
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
