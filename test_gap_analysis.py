#!/usr/bin/env python3
"""
Tests for Capability 2 gap-analysis engine (CAPABILITY2-BUILD-SPEC §Tests).

Runnable as `python3 test_gap_analysis.py` (built-in runner, no pytest needed)
or under pytest.

Covers: MWBE ✅ HAVE and ⏰ EXPIRING, MISSING, UNKNOWN (validity_rule=unknown),
sunset-lapsed → UNKNOWN (override), free-form confirm → mapped, and free-form
no-match → attorney-pending. Plus catalog citation-integrity and the unknown-safe
invariant.
"""

import sys

import gap_analysis as G
from gap_analysis import VendorCredential


def _mwbe(issuance, **kw):
    return VendorCredential(vendor_id="v1", requirement_id="mwbe-certification",
                            status="have", issuance_date=issuance, source_path="checklist", **kw)


# --------------------------------------------------------------------------
# Catalog integrity
# --------------------------------------------------------------------------

def test_catalog_citations_are_verbatim():
    """Every catalog entry's citation must be verbatim in its golden source."""
    gc = G._GC
    for rid, entry in G.CATALOG.items():
        assert entry.citation_quote in gc.body(entry.source_file), rid


def test_catalog_only_mwbe_has_a_golden_validity_rule():
    """Unknown-where-not-golden: non-MWBE seeds must not invent a validity rule."""
    assert G.CATALOG["mwbe-certification"].validity_rule == "fixed-period:5y"
    assert G.CATALOG["vendor-responsibility"].validity_rule == "unknown"
    assert G.CATALOG["workers-comp-insurance"].validity_rule == "unknown"


# --------------------------------------------------------------------------
# MWBE ✅ / ⏰
# --------------------------------------------------------------------------

def test_mwbe_have_when_valid_through_deadline():
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [_mwbe("2022-03-01")])
    assert r["verdict"] == G.HAVE and r["icon"] == "✅"
    assert r["detail"]["computed_expiry"] == "2027-03-01"   # issuance + 5y, after deadline
    assert r["citation"]["source_file"] == "source-exec-314-mwbe-cert-validity.md"


def test_mwbe_expiring_when_expires_before_deadline():
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [_mwbe("2020-06-01")])
    assert r["verdict"] == G.EXPIRING and r["icon"] == "⏰"
    assert r["detail"]["computed_expiry"] == "2025-06-01"   # issuance + 5y, before deadline
    assert r["attorney_review_required"] is True


def test_mwbe_never_green_without_issuance_date():
    """fixed-period rule but no issuance_date → cannot confirm → UNKNOWN (never ✅)."""
    cred = VendorCredential(requirement_id="mwbe-certification", status="have",
                            source_path="checklist")
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [cred])
    assert r["verdict"] == G.UNKNOWN


# --------------------------------------------------------------------------
# Missing / Unknown
# --------------------------------------------------------------------------

def test_missing_when_no_matching_entry():
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [])
    assert r["verdict"] == G.MISSING and r["icon"] == "❌"


def test_unknown_when_validity_rule_unknown():
    cred = VendorCredential(requirement_id="vendor-responsibility", status="have",
                            source_path="checklist")
    r = G.evaluate_requirement("vendor-responsibility", "2026-09-01", [cred])
    assert r["verdict"] == G.UNKNOWN and r["icon"] == "⚠️"
    assert "no golden validity rule" in r["reason"]


def test_unknown_when_requirement_not_in_catalog():
    r = G.evaluate_requirement("some-new-requirement", "2026-09-01", [])
    assert r["verdict"] == G.UNKNOWN
    assert r["citation"] is None


# --------------------------------------------------------------------------
# Sunset override
# --------------------------------------------------------------------------

def test_sunset_lapsed_forces_unknown_over_a_green():
    """A credential that would be ✅ HAVE on dates becomes ⚠️ UNKNOWN when the
    rule's authorization is LAPSED — no false green on an expired program."""
    lapsed = lambda rid: "LAPSED"
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [_mwbe("2022-03-01")],
                               sunset_status_fn=lapsed)
    assert r["verdict"] == G.UNKNOWN and r["icon"] == "⚠️"
    assert "authorization may have lapsed" in r["reason"]


def test_sunset_ok_does_not_disturb_a_valid_have():
    ok = lambda rid: "OK"
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [_mwbe("2022-03-01")],
                               sunset_status_fn=ok)
    assert r["verdict"] == G.HAVE


def test_default_sunset_status_reads_freshness_checker():
    """§314's real sunset (2028-07-01) classifies OK today — not lapsed."""
    assert G.default_sunset_status("mwbe-certification") == "OK"


# --------------------------------------------------------------------------
# Free-form auto-match (Option 2)
# --------------------------------------------------------------------------

def test_freeform_confirm_maps_to_requirement():
    cred = VendorCredential(vendor_id="v1", label="M/WBE cert", source_path="freeform")
    updated, suggestion = G.resolve_freeform(cred, vendor_confirms=True)
    assert updated.requirement_id == "mwbe-certification"
    assert updated.candidate_state == G.CONFIRMED
    assert "Did you mean" in suggestion and "source-exec-314" in suggestion


def test_freeform_confirmed_then_evaluates_like_checklist():
    cred = VendorCredential(vendor_id="v1", label="M/WBE cert", source_path="freeform",
                            issuance_date="2022-03-01")
    G.resolve_freeform(cred, vendor_confirms=True)
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [cred])
    assert r["verdict"] == G.HAVE


def test_freeform_no_match_is_attorney_pending():
    cred = VendorCredential(vendor_id="v1", label="Acme Gizmo License", source_path="freeform")
    updated, suggestion = G.resolve_freeform(cred, vendor_confirms=None)
    assert updated.candidate_state == G.ATTORNEY_PENDING
    assert updated.requirement_id is None
    assert suggestion is None


def test_freeform_no_when_declined_is_attorney_pending():
    cred = VendorCredential(vendor_id="v1", label="M/WBE cert", source_path="freeform")
    updated, _ = G.resolve_freeform(cred, vendor_confirms=False)   # vendor said NO
    assert updated.candidate_state == G.ATTORNEY_PENDING
    assert updated.requirement_id is None


def test_auto_match_only_hits_golden_catalog_entries():
    entry, _ = G.auto_match("minority and women-owned business enterprise")
    assert entry is not None and entry.requirement_id == "mwbe-certification"
    assert G.auto_match("completely unrelated widget permit") == (None, None)


# --------------------------------------------------------------------------
# End-to-end analyze(): counts, UPL framing, attorney-pending surfaced
# --------------------------------------------------------------------------

def test_analyze_bundle_counts_and_upl_and_pending_row():
    profile = [
        _mwbe("2022-03-01"),                                               # ✅
        VendorCredential(requirement_id="vendor-responsibility", status="have",
                         source_path="checklist"),                         # ⚠️ unknown rule
        VendorCredential(label="Acme Gizmo License", source_path="freeform"),  # ⚠️ pending
    ]
    bundle = G.analyze(["mwbe-certification", "vendor-responsibility", "workers-comp-insurance"],
                       "2026-09-01", profile)
    s = bundle["summary"]
    assert s["have"] == 1                       # mwbe
    assert s["missing"] == 1                    # workers-comp not in profile
    assert s["unknown"] == 2                    # vendor-responsibility + the pending free-form row
    assert bundle["upl_framing"].startswith("This is information to help you prepare your bid")
    # The unmatched free-form credential is surfaced as its own ⚠️ row, never dropped.
    pending = [r for r in bundle["results"] if r["candidate_state"] == G.ATTORNEY_PENDING]
    assert pending and pending[0]["verdict"] == G.UNKNOWN


def test_never_green_when_unknown_invariant():
    """The core invariant: no result is ✅ HAVE unless validity was confirmed."""
    profile = [VendorCredential(requirement_id="vendor-responsibility", status="have",
                                source_path="checklist")]
    bundle = G.analyze(["vendor-responsibility"], "2026-09-01", profile)
    assert all(r["verdict"] != G.HAVE for r in bundle["results"])


def test_analyze_summary_have_is_zero_when_authorization_lapsed():
    """Aggregate never-green: the ONLY would-be-✅-HAVE credential (MWBE, valid
    dates: issuance 2022-03-01 → expiry 2027-03-01, after the 2026-09-01 deadline)
    must drop out of the vendor-facing summary counts when its authorization is
    LAPSED — proving the invariant holds in the aggregate, not just per-row."""
    lapsed = lambda rid: "LAPSED"
    profile = [_mwbe("2022-03-01")]                     # on dates alone this is HAVE
    bundle = G.analyze(["mwbe-certification"], "2026-09-01", profile, sunset_status_fn=lapsed)
    assert bundle["summary"]["have"] == 0               # no false green in the counts
    assert bundle["summary"]["unknown"] == 1
    assert all(r["verdict"] != G.HAVE for r in bundle["results"])
    # And with the authorization OK, the same profile DOES count as one HAVE —
    # confirming the LAPSED status is what zeroes it out, not the dates.
    ok = G.analyze(["mwbe-certification"], "2026-09-01", profile, sunset_status_fn=lambda rid: "OK")
    assert ok["summary"]["have"] == 1


def test_gap_catalog_is_confident_gated_both_directions():
    """The migrated gap_analysis validates its catalog at import with
    output_context=CONFIDENT. Forward: the real catalog builds and is non-empty
    (every seed is confident-eligible). Reverse: the CONFIDENT gate is load-bearing
    — a gated source (mwbe-5nycrr, INTERIM_VERIFY) is BLOCKED at CONFIDENT, so a
    gated seed would fail the build rather than reach a vendor as a confident
    citation; it is allowed only into VERIFY / attorney-gated."""
    import engine.golden_status as gs
    from validator import GoldenEligibilityError
    assert G.CATALOG and G._build_catalog()                       # forward: builds, non-empty
    mwbe = "source-mwbe-5nycrr-pass-fail.md"
    q = G._GC.body(mwbe).strip().split("\n", 1)[0][:30]
    try:
        G._GC.cite(mwbe, q, output_context=gs.OUTPUT_CONFIDENT)   # reverse: gated seed blocked
        raise AssertionError("a gated source must fail the CONFIDENT catalog gate")
    except GoldenEligibilityError as e:
        assert e.status == gs.INTERIM_VERIFY
    assert G._GC.cite(mwbe, q, output_context=gs.OUTPUT_VERIFY) == q


def test_gap_citation_uses_canonical_validation_family_shape():
    """Seam fix: gap_analysis emits the validation-family golden-citation shape
    {source_file, citation_quote} (matching validator.py / cert_renewal.py), NOT the
    old {source_file, quote}; and its own renderer reads that same key. There is no
    cross-module consumer — clarification_questions deliberately ignores golden
    citation dicts (RFP-location vs STATE-law) — so this is internal-consistency +
    family-alignment, not a round-trip."""
    r = G.evaluate_requirement("mwbe-certification", "2026-09-01", [_mwbe("2022-03-01")])
    assert r["citation"] is not None
    assert set(r["citation"]) == {"source_file", "citation_quote"}   # canonical shape
    assert "quote" not in r["citation"]                              # old key gone
    assert r["citation"]["citation_quote"]                           # non-empty
    # internal consistency: the renderer reads the same key, no KeyError
    bundle = G.analyze(["mwbe-certification"], "2026-09-01", [_mwbe("2022-03-01")])
    out = G.render(bundle)
    assert r["citation"]["citation_quote"] in out


# --------------------------------------------------------------------------
# Built-in runner
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("GAP ANALYSIS — TEST SUITE ({} tests)".format(len(tests)))
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
