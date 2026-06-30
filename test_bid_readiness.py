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


def test_insurance_limit_shortfall_is_yellow_with_gap():
    rep = _report()
    ins = [r for r in rep.rows if r.kind == "insurance"][0]
    assert ins.status == BR.YELLOW
    assert "1,000,000" in (ins.gap or "") and "2,000,000" in (ins.gap or "")


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
    rep = _report()
    nc = [r for r in rep.rows if r.kind == "non_collusion"][0]
    assert nc.vendor_has is True and nc.grounding is not None
    assert nc.status == BR.GREEN


def test_iran_unsatisfied_mandatory_is_red_blocker_with_confirmed_cite():
    rep = _report()
    iran = [r for r in rep.rows if r.kind == "iran_divestment"][0]
    assert iran.must is True and iran.vendor_has is False
    assert iran.status == BR.RED and iran in rep.blocking
    assert iran.grounding is not None  # RED, yet citation-grounded (Track 1)


def test_action_list_targets_gaps():
    rep = _report()
    actions = rep.actions
    labels = {a["for"] for a in actions}
    assert "MWBE utilization plan" in labels
    assert "Bid bond" in labels


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
