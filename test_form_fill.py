#!/usr/bin/env python3
"""
Tests for the Step 6 form-fill engine + AC 3237-S config.

Runnable as `python3 test_form_fill.py` or under pytest. No network, no PDF
library required. TIN/SSN use the obvious placeholder 000000000 only.
"""

import glob
import json
import os
import re
import sys

from pipeline.form_fill import (load_form_config, build_fill_values, fill_report,
                                FACTUAL, ATTESTATION)

CONFIG = load_form_config("ac3237s")
FIELDS_FIXTURE = os.path.join("tests", "fixtures", "ac3237s_fields.json")

# The 6 fields that must NEVER be auto-filled (Part V cert, exemptions, preparer,
# signature date). Field names are verbatim from the real PDF (incl. OSC's typo).
ATTESTATION_FIELDS = {
    "Subject to Backup Witholding", "Exempt Payee", "Certification Date",
    "Print Preparer's Name", "Preparer's Phone Number", "Preparer's Email Address",
}


# --------------------------------------------------------------------------
# (a) config completeness — config covers EXACTLY the real 21 AcroForm fields
# --------------------------------------------------------------------------

def test_config_covers_exactly_the_real_field_inventory():
    """Tradeoff: the PDF binary was unavailable in the build session, so the
    authoritative pikepdf field dump is committed as the fixture and the config
    is asserted against it (swap to live PDF extraction once the PDF is added)."""
    inv = json.load(open(FIELDS_FIXTURE, encoding="utf-8"))
    real_names = [f["name"] for f in inv["fields"]]
    assert len(real_names) == 21 and inv["field_count"] == 21
    assert len(real_names) == len(set(real_names)), "duplicate names in inventory"

    cfg_names = list(CONFIG["fields"].keys())
    assert len(cfg_names) == len(set(cfg_names)), "a field appears twice in the config"
    # Every real field appears exactly once; no invented fields.
    assert set(cfg_names) == set(real_names), {
        "missing_from_config": sorted(set(real_names) - set(cfg_names)),
        "extra_in_config": sorted(set(cfg_names) - set(real_names)),
    }
    assert CONFIG["field_count"] == 21


def test_config_types_match_the_real_pdf():
    inv = {f["name"]: f["type"] for f in
           json.load(open(FIELDS_FIXTURE, encoding="utf-8"))["fields"]}
    for name, spec in CONFIG["fields"].items():
        assert spec["type"] == inv[name], (name, spec["type"], inv[name])


def test_every_field_classified_factual_or_attestation():
    for name, spec in CONFIG["fields"].items():
        assert spec["class"] in (FACTUAL, ATTESTATION), (name, spec.get("class"))
    attest = {n for n, s in CONFIG["fields"].items() if s["class"] == ATTESTATION}
    assert attest == ATTESTATION_FIELDS, attest


# --------------------------------------------------------------------------
# (b) attestation fields never emitted, even when maliciously supplied
# --------------------------------------------------------------------------

def test_attestation_never_filled_even_if_profile_supplies_it():
    # Maliciously supply a value for EVERY attestation field's plausible key.
    malicious = {
        "subject_to_backup_witholding": "/1",
        "exempt_payee": "/On",
        "certification_date": "2026-07-04",
        "print_preparer_name": "Somebody",
        "preparer_phone": "518-555-0000",
        "preparer_email": "x@example.com",
        # also give a real factual value so we know the engine still runs
        "legal_business_name": "Acme Widgets LLC",
    }
    # Point the attestation specs at those keys to make the attack maximally direct.
    cfg = json.loads(json.dumps(CONFIG))
    for name in ATTESTATION_FIELDS:
        cfg["fields"][name]["profile_key"] = {
            "Subject to Backup Witholding": "subject_to_backup_witholding",
            "Exempt Payee": "exempt_payee",
            "Certification Date": "certification_date",
            "Print Preparer's Name": "print_preparer_name",
            "Preparer's Phone Number": "preparer_phone",
            "Preparer's Email Address": "preparer_email",
        }[name]
    r = build_fill_values(cfg, malicious)
    # No attestation field is in the output values.
    assert not (ATTESTATION_FIELDS & set(r["values"].keys()))
    # All are recorded as skipped, and the supplied-attempts are flagged.
    assert ATTESTATION_FIELDS.issubset(set(r["attestation_skipped"]))
    assert set(r["attestation_supplied"]) == ATTESTATION_FIELDS
    # The one legit factual field still filled.
    assert r["values"]["1. Legal Business Name"] == "Acme Widgets LLC"


# --------------------------------------------------------------------------
# (c) partial profile -> correct unfilled list
# --------------------------------------------------------------------------

def test_partial_profile_produces_correct_unfilled_list():
    profile = {"legal_business_name": "Acme Widgets LLC", "tin": "000000000"}
    r = build_fill_values(CONFIG, profile)
    # filled: only the two supplied factual text fields
    assert r["values"] == {"1. Legal Business Name": "Acme Widgets LLC",
                           "TIN": "000000000"}
    unfilled = {u["field"] for u in r["unfilled"]}
    # every other factual field is unfilled, incl. the two unconfirmed radios
    assert "2. DBA" in unfilled and "Email Address" in unfilled
    assert "Entity Type" in unfilled and "Taxpayer ID Type" in unfilled
    # attestation fields are NOT in unfilled (they're skipped, not "to fill by data")
    assert not (ATTESTATION_FIELDS & unfilled)
    # radios carry the "select by hand" reason
    ent = next(u for u in r["unfilled"] if u["field"] == "Entity Type")
    assert "by hand" in ent["reason"]


def test_unconfirmed_radio_is_unfilled_even_when_value_present():
    profile = {"entity_type": "Corporation", "tin_type": "EIN"}
    r = build_fill_values(CONFIG, profile)
    assert "Entity Type" not in r["values"]        # never a guessed checkbox state
    assert "Taxpayer ID Type" not in r["values"]
    unfilled = {u["field"] for u in r["unfilled"]}
    assert {"Entity Type", "Taxpayer ID Type"} <= unfilled


def test_confirmed_radio_fills_from_value_map():
    # Prove the engine WILL fill a radio once the mapping is confirmed.
    cfg = json.loads(json.dumps(CONFIG))
    cfg["fields"]["Taxpayer ID Type"]["value_map"] = {"EIN": "/0", "SSN": "/1"}
    cfg["fields"]["Taxpayer ID Type"]["value_map_confirmed"] = True
    r = build_fill_values(cfg, {"tin_type": "EIN"})
    assert r["values"]["Taxpayer ID Type"] == "/0"


def test_fill_report_shape():
    r = build_fill_values(CONFIG, {"legal_business_name": "X"})
    rep = fill_report(r)
    assert rep["filled"] == ["1. Legal Business Name"]
    assert set(ATTESTATION_FIELDS).issubset(rep["attestation_skipped"])


# --------------------------------------------------------------------------
# (d) no test/fixture/script contains a realistic SSN pattern
# --------------------------------------------------------------------------

def test_no_realistic_ssn_anywhere_in_this_feature():
    dashed_ssn = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    # a 9-digit run that is NOT an obvious placeholder (all same digit)
    nine = re.compile(r"\b\d{9}\b")
    targets = ["test_form_fill.py", "scripts/fill_ac3237s.py",
               "data/config/forms/ac3237s.json", FIELDS_FIXTURE] + \
        glob.glob("tests/fixtures/*.json")
    for path in sorted(set(targets)):
        text = open(path, encoding="utf-8").read()
        assert not dashed_ssn.search(text), "dashed SSN pattern in %s" % path
        for m in nine.finditer(text):
            digits = m.group(0)
            assert len(set(digits)) == 1, \
                "non-placeholder 9-digit run %r in %s" % (digits, path)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 74)
    print("FORM FILL — TEST SUITE ({} tests)".format(len(tests)))
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
