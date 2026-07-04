#!/usr/bin/env python3
"""Tests for Step 1 Triage. Runnable as `python3 test_triage.py` or under pytest."""

import json
import sys

import step1_triage as T
from step1_triage import (BIDDABLE, NON_BIDDABLE, EDGE, HUMAN_REVIEW,
                          OUT_OF_SCOPE, J_STATE, HIGH, LOW)

AD_TYPES = json.load(open("data/nyscr_ad_types.json", encoding="utf-8"))["labels"]


# --------------------------------------------------------------------------
# Output-schema invariant
# --------------------------------------------------------------------------

REQUIRED_KEYS = {"source_type", "jurisdiction", "jurisdiction_match",
                 "triage_class", "reason", "confidence", "source_field",
                 "label_provisional"}


def _schema_ok(o):
    assert REQUIRED_KEYS.issubset(o.keys()), o.keys()
    assert isinstance(o["label_provisional"], bool)
    assert o["confidence"] in (HIGH, LOW)
    assert o["triage_class"] in (BIDDABLE, NON_BIDDABLE, EDGE, HUMAN_REVIEW, OUT_OF_SCOPE)


# --------------------------------------------------------------------------
# Step 3 — 12 NYSCR label fixtures (STATE agency confirmed)
# --------------------------------------------------------------------------

def _nyscr(ad_type, text=None):
    opp = {"issuer": "Office of General Services", "ad_type": ad_type}
    if text:
        opp["text"] = text
    return T.triage(opp)


def test_all_12_labels_classify_and_propagate_provisional():
    seen = {BIDDABLE: 0, NON_BIDDABLE: 0, EDGE: 0}
    for row in AD_TYPES:
        r = _nyscr(row["label"])
        _schema_ok(r)
        assert r["source_type"] == "nyscr"
        assert r["jurisdiction"] == J_STATE
        assert r["triage_class"] == row["class"], (row["label"], r["triage_class"])
        assert r["label_provisional"] is True          # every label is provisional
        assert r["confidence"] == HIGH                 # exact rule match ⇒ high
        seen[row["class"]] += 1
    assert seen == {BIDDABLE: 7, NON_BIDDABLE: 4, EDGE: 1}, seen


def test_sole_source_is_non_biddable_with_reason():
    r = _nyscr("Single/Sole Source Notice")
    assert r["triage_class"] == NON_BIDDABLE
    assert r["reason"] == "award/exemption notice, not open solicitation"


def test_label_alias_resolves():
    r = _nyscr("RFI")                                   # alias of Request for Information
    assert r["triage_class"] == NON_BIDDABLE
    assert r["source_field"] == "ad_type"


def test_biddable_label_is_green_despite_provisional():
    r = _nyscr("General")
    assert r["triage_class"] == BIDDABLE and r["confidence"] == HIGH
    assert r["label_provisional"] is True               # green allowed: high + exact match


# --------------------------------------------------------------------------
# Step 2 — jurisdiction gate
# --------------------------------------------------------------------------

def test_state_agency_full_engine():
    r = T.triage({"issuer": "Department of Health", "ad_type": "General"})
    assert r["jurisdiction"] == J_STATE
    assert r["jurisdiction_match"]["entity_name"] == "Department of Health"
    assert r["jurisdiction_match"]["list_capture_date"]
    assert r["triage_class"] == BIDDABLE


def test_mta_authority_human_review_2879():
    r = T.triage({"issuer": "MTA", "ad_type": "General"})
    assert r["triage_class"] == HUMAN_REVIEW
    assert "§2879" in r["reason"]
    assert r["jurisdiction"] == "AUTHORITY"
    assert r["jurisdiction_match"]["entity_name"] == "Metropolitan Transportation Authority"


def test_esd_authority_despite_no_authority_in_name():
    # ESD's name lacks the word "Authority" — it must still match via the list.
    r = T.triage({"issuer": "Empire State Development", "ad_type": "General"})
    assert r["triage_class"] == HUMAN_REVIEW and "§2879" in r["reason"]
    assert r["jurisdiction"] == "AUTHORITY"


def test_dormitory_authority_matched_by_list_not_keyword():
    r = T.triage({"issuer": "Dormitory Authority"})
    assert r["triage_class"] == HUMAN_REVIEW and "§2879" in r["reason"]
    assert r["jurisdiction_match"]["entity_name"].startswith("Dormitory Authority")


def test_suny_human_review_education_law():
    r = T.triage({"issuer": "SUNY", "ad_type": "General"})
    assert r["triage_class"] == HUMAN_REVIEW
    assert "Education Law" in r["reason"]
    assert r["jurisdiction"] == "SUNY_CUNY"


def test_municipality_human_review_gml():
    r = T.triage({"issuer": "City of Albany", "ad_type": "General"})
    assert r["triage_class"] == HUMAN_REVIEW
    assert "General Municipal Law" in r["reason"]
    assert r["jurisdiction"] == "MUNICIPAL"


def test_non_ny_out_of_scope_valid_schema():
    r = T.triage({"issuer": "Commonwealth of Massachusetts", "ad_type": "General"})
    _schema_ok(r)
    assert r["triage_class"] == OUT_OF_SCOPE
    assert "non-NY" in r["reason"]
    assert r["jurisdiction"] == "NON_NY"
    assert r["jurisdiction_match"] is None


def test_unknown_issuer_human_review():
    r = T.triage({"issuer": "Acme Widgets Procurement Office", "ad_type": "General"})
    assert r["triage_class"] == HUMAN_REVIEW
    assert "not on verified entity lists" in r["reason"]


def test_bare_authority_keyword_does_not_match():
    # A random name containing "Authority" must NOT match the entity list.
    r = T.triage({"issuer": "Global Widget Authority", "ad_type": "General"})
    assert r["jurisdiction"] == "UNDETERMINED"
    assert r["triage_class"] == HUMAN_REVIEW
    assert r["jurisdiction_match"] is None


def test_ogs_alias_resolves():
    assert T.lookup_entity("OGS")["name"] == "Office of General Services"
    assert T.lookup_entity("NYSDOT")["name"] == "Department of Transportation"
    assert T.lookup_entity("Global Widget Authority") is None


# --------------------------------------------------------------------------
# Step 4 — LLM path + escalation
# --------------------------------------------------------------------------

class _SpyLLM:
    def __init__(self, verdict):
        self.verdict = verdict
        self.calls = 0

    def __call__(self, text):
        self.calls += 1
        return self.verdict


def test_general_plus_sole_source_language_routes_to_step4():
    spy = _SpyLLM({"triage_class": NON_BIDDABLE, "confidence": HIGH,
                   "reason": "text describes a sole-source award"})
    r = T.triage({"issuer": "Office of General Services", "ad_type": "General",
                  "text": "This is a notice of intent to award on a sole source basis."},
                 llm=spy)
    assert spy.calls == 1                                # escalated to Step 4
    assert r["source_field"] == "llm"
    assert r["triage_class"] == NON_BIDDABLE and r["confidence"] == HIGH


def test_non_nyscr_pasted_text_skips_step3_uses_step4():
    spy = _SpyLLM({"triage_class": BIDDABLE, "confidence": HIGH,
                   "reason": "open solicitation"})
    r = T.triage({"issuer": "Department of Labor",
                  "text": "Sealed bids are invited for janitorial services."}, llm=spy)
    assert r["source_type"] == "other"
    assert spy.calls == 1
    assert r["triage_class"] == BIDDABLE and r["confidence"] == HIGH


def test_unrecognized_ad_type_uses_step4():
    spy = _SpyLLM({"triage_class": HUMAN_REVIEW, "confidence": LOW, "reason": "unclear"})
    r = T.triage({"issuer": "Office of General Services", "ad_type": "Mystery Category",
                  "text": "..."}, llm=spy)
    assert r["source_type"] == "unknown"
    assert spy.calls == 1


def test_low_confidence_llm_becomes_human_review():
    spy = _SpyLLM({"triage_class": BIDDABLE, "confidence": LOW,
                   "reason": "might be biddable"})
    r = T.triage({"issuer": "Department of Health",
                  "text": "ambiguous opportunity text"}, llm=spy)
    assert r["triage_class"] == HUMAN_REVIEW            # never silently green
    assert r["confidence"] == LOW


def test_llm_never_runs_for_a_confirmed_rule_match():
    spy = _SpyLLM({"triage_class": BIDDABLE, "confidence": HIGH, "reason": "x"})
    r = T.triage({"issuer": "Office of General Services", "ad_type": "General"}, llm=spy)
    assert spy.calls == 0                               # rule match wins; LLM untouched
    assert r["triage_class"] == BIDDABLE


# --------------------------------------------------------------------------
# EDGE / grant — tag only, no downstream call
# --------------------------------------------------------------------------

def test_grant_edge_tagged_grant_flow_no_downstream_call():
    spy = _SpyLLM({"triage_class": BIDDABLE, "confidence": HIGH, "reason": "x"})
    r = T.triage({"issuer": "Office of General Services",
                  "ad_type": "Grant / Notice of Funds Availability"}, llm=spy)
    assert r["triage_class"] == EDGE
    assert r["route"] == "grant_flow"
    assert spy.calls == 0                               # NO downstream call


# --------------------------------------------------------------------------
# Never-green backstop + citation convention
# --------------------------------------------------------------------------

def test_finalize_backstop_blocks_green_off_state():
    # Directly exercise the backstop: a BIDDABLE with non-STATE jurisdiction
    # must be forced to HUMAN_REVIEW even if it somehow reached _out.
    o = T._out("nyscr", "AUTHORITY", None, BIDDABLE, "x", HIGH, "ad_type", True)
    T._finalize(o)
    assert o["triage_class"] == HUMAN_REVIEW


def test_citations_are_ids_not_filenames():
    # Golden-copy references are citation IDs, never source-*.md filenames.
    r = _nyscr("General")
    assert r.get("citation_id") == "SFL-ART-11"
    assert T.resolve_citation("SFL-ART-11").startswith("State Finance Law Article 11")
    for c in json.load(open("data/citations.json"))["citations"].values():
        assert "source-" not in c and ".md" not in c


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 74)
    print("STEP 1 TRIAGE — TEST SUITE ({} tests)".format(len(tests)))
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
    sys.exit(_run())
