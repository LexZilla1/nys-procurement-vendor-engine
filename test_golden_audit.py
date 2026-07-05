#!/usr/bin/env python3
"""
Tests for the Golden Copy Reliability Audit:
engine/golden_status.py, the GoldenCopy.cite() eligibility guardrail, and
scripts/golden_audit.py.

Runnable as `python3 test_golden_audit.py` or under pytest. No live network.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from engine import golden_status as gs  # noqa: E402
from validator import GoldenCopy, GoldenEligibilityError, CitationError  # noqa: E402
import golden_audit as ga  # noqa: E402

# A minimal, parseable synthetic source body for temp-GoldenCopy tests.
_HEADER = (
    "# SOURCE TEXT — synthetic\n\n"
    "- **Name:** synthetic\n- **Date:** x\n- **Issued by:** x\n"
    "- **Link (permanent identifier):** https://example/x\n"
    "- **Copied exactly on:** 2026-07-05\n- **Covers:** full section\n%s\n"
    "---\n\n## STATE TEXT (verbatim)\n\n§ 1. Synthetic body long enough to parse.\n\n"
    "---\n\n## CITATIONS THIS TEXT POINTS TO\n\n- none\n")


def _write_source(dirpath, name, extra_meta="", body_marker=""):
    text = _HEADER % extra_meta
    if body_marker:
        text = text.replace("§ 1. Synthetic body long enough to parse.",
                            "§ 1. Synthetic body. " + body_marker)
    with open(os.path.join(dirpath, name), "w", encoding="utf-8") as fh:
        fh.write(text)


# ======================= status derivation (pure) =========================

def test_derive_status_verified_golden():
    raw = _HEADER % ""
    assert gs.derive_status(raw)[0] == gs.VERIFIED_GOLDEN


def test_derive_status_pending_human_read():
    raw = (_HEADER % "- **Tier:** PENDING HUMAN READ — not golden until human-verified")
    assert gs.derive_status(raw)[0] == gs.PENDING_HUMAN_READ


def test_derive_status_l_grade():
    raw = _HEADER % "" + "\n> GRADE — mapping = L (legal-interpretive).\n"
    assert gs.derive_status(raw)[0] == gs.L_GRADE_INTERPRETIVE


def test_derive_status_partial_capture():
    raw = _HEADER % "" + "\nThis is a MIXED capture with form layers.\n"
    assert gs.derive_status(raw)[0] == gs.PARTIAL_CAPTURE


def test_derive_status_superseded():
    raw = _HEADER % "" + "\n** NB Effective until July 1, 2026\n"
    assert gs.derive_status(raw)[0] == gs.SUPERSEDED_VERSION_PRESENT


def test_derive_status_divergent_from_freshness():
    raw = _HEADER % ""
    assert gs.derive_status(raw, freshness_verdict="DIVERGENT")[0] == gs.DIVERGENT_FROM_API


def test_derive_status_stale_from_freshness():
    raw = _HEADER % ""
    assert gs.derive_status(raw, sunset_stale=True)[0] == gs.STALE_CHECK_REQUIRED


def test_derive_status_insufficient_metadata_is_a_finding():
    status, reasons = gs.derive_status("no header, no state text at all")
    assert status is None and reasons


def test_pending_precedes_lgrade():
    raw = (_HEADER % "- **Tier:** PENDING HUMAN READ") + "\n> GRADE — = L (legal-interpretive)\n"
    assert gs.derive_status(raw)[0] == gs.PENDING_HUMAN_READ


# ======================= cite() eligibility guardrail =====================

def test_cite_bare_is_backward_compatible():
    """A bare cite() (no output_context) keeps verbatim-only behavior even for an
    L-grade source — existing callers / verify_golden are unchanged."""
    g = GoldenCopy()
    q = "The term public holiday includes the following days in each year"
    assert g.cite("source-gcn-24-public-holidays.md", q) == q   # no raise


def test_cite_confident_blocks_l_grade():
    g = GoldenCopy()
    q = "The term public holiday includes the following days in each year"
    try:
        g.cite("source-gcn-24-public-holidays.md", q,
               output_context=gs.OUTPUT_CONFIDENT)
    except GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
        return
    raise AssertionError("confident cite of an L-grade source must be blocked")


def test_cite_l_grade_allowed_in_verify_and_attorney_gated():
    g = GoldenCopy()
    q = "The term public holiday includes the following days in each year"
    assert g.cite("source-gcn-24-public-holidays.md", q, output_context=gs.OUTPUT_VERIFY) == q
    assert g.cite("source-gcn-24-public-holidays.md", q,
                  output_context=gs.OUTPUT_ATTORNEY_GATED) == q


def test_cite_verified_allowed_in_confident():
    g = GoldenCopy()
    q = "shall be computed at the rate equal to the overpayment rate"
    assert g.cite("source-stf-179-g.md", q, output_context=gs.OUTPUT_CONFIDENT) == q


def test_cite_partial_not_citable_in_any_context():
    g = GoldenCopy()
    # a verbatim quote from the §109 statute layer of the (PARTIAL) mixed file
    body = g.body("source-stf-109-vendor-certificate.md")
    q = body.split("\n", 1)[0][:40]   # a real verbatim prefix
    for ctx in (gs.OUTPUT_CONFIDENT, gs.OUTPUT_VERIFY, gs.OUTPUT_ATTORNEY_GATED):
        try:
            g.cite("source-stf-109-vendor-certificate.md", q, output_context=ctx)
        except GoldenEligibilityError as e:
            assert e.status == gs.PARTIAL_CAPTURE
        else:
            raise AssertionError("PARTIAL source must not be citable in %s" % ctx)


def test_cite_raises_on_pending_human_read():
    with tempfile.TemporaryDirectory() as tmp:
        _write_source(tmp, "source-syn.md",
                      extra_meta="- **Tier:** PENDING HUMAN READ")
        g = GoldenCopy(sources_dir=tmp)
        assert g.status_of("source-syn.md") == gs.PENDING_HUMAN_READ
        try:
            g.cite("source-syn.md", "§ 1. Synthetic body",
                   output_context=gs.OUTPUT_VERIFY)
        except GoldenEligibilityError as e:
            assert e.status == gs.PENDING_HUMAN_READ
            return
        raise AssertionError("PENDING_HUMAN_READ must never be citable")


def test_cite_raises_on_divergent_via_overlay():
    g = GoldenCopy(freshness={"source-stf-179-g.md": ("DIVERGENT", False)})
    assert g.status_of("source-stf-179-g.md") == gs.DIVERGENT_FROM_API
    q = "shall be computed at the rate equal to the overpayment rate"
    try:
        g.cite("source-stf-179-g.md", q, output_context=gs.OUTPUT_VERIFY)
    except GoldenEligibilityError as e:
        assert e.status == gs.DIVERGENT_FROM_API
        return
    raise AssertionError("DIVERGENT source must not be citable")


def test_eligibility_error_is_a_citation_error():
    """Subclassing keeps existing `except CitationError` handlers working."""
    assert issubclass(GoldenEligibilityError, CitationError)


def test_bad_quote_still_raises_before_eligibility():
    g = GoldenCopy()
    try:
        g.cite("source-stf-179-g.md", "NOT A VERBATIM QUOTE",
               output_context=gs.OUTPUT_CONFIDENT)
    except CitationError:
        return
    raise AssertionError("a non-verbatim quote must still be rejected")


# ======================= audit script =====================================

def test_audit_discovers_all_sources():
    rep = ga.run()
    n = len([p for p in os.listdir(ga.SOURCES_DIR)
             if p.startswith("source-") and p.endswith(".md")])
    assert rep["discovered_count"] == n
    import parse_golden_copy as pg
    assert rep["discovered_count"] == pg.EXPECTED_COUNT   # 47


def test_audit_full_run_has_no_hard_failures():
    rep = ga.run()
    hard = [r for r in rep["results"] if r["hard_fail"]]
    assert hard == [], "hard failures: %s" % [r["file"] for r in hard]


def test_audit_fails_on_missing_index_entry():
    raw = _HEADER % ""
    r = ga.audit_source("source-x.md", raw, in_index=False, in_report=True,
                        freshness={})
    assert r["hard_fail"] is True
    assert any("INDEX" in f for f in r["findings"])


def test_audit_fails_on_missing_verification_row():
    raw = _HEADER % ""
    r = ga.audit_source("source-x.md", raw, in_index=True, in_report=False,
                        freshness={})
    assert r["hard_fail"] is True
    assert any("VERIFICATION-REPORT" in f for f in r["findings"])


def test_audit_catches_nb_flag_loss():
    # a sunset statute (sunset_watch) whose STATE TEXT has NO NB flag -> finding
    raw = (_HEADER % "- **API activeDate:** 2020-01-01") + \
        "\nsunset_watch: true\n(capture method openleg-api-v3, but NB flag dropped)\n"
    r = ga.audit_source("source-x.md", raw, in_index=True, in_report=True,
                        freshness={})
    assert any("NB" in f for f in r["findings"]), r["findings"]


def test_audit_status_tally_matches_survey():
    by = {r["file"]: r["status"] for r in ga.run()["results"]}
    assert by["source-gcn-24-public-holidays.md"] == gs.L_GRADE_INTERPRETIVE
    assert by["source-exec-314-mwbe-cert-validity.md"] == gs.L_GRADE_INTERPRETIVE
    assert by["source-stf-109-vendor-certificate.md"] == gs.PARTIAL_CAPTURE
    assert by["source-mwbe-5nycrr-pass-fail.md"] == gs.PARTIAL_CAPTURE
    assert by["source-appendix-a-june2023.md"] == gs.SUPERSEDED_VERSION_PRESENT
    assert by["source-stf-179-g.md"] == gs.VERIFIED_GOLDEN


def test_audit_reports_engine_reach_to_gated_sources():
    reach = {e["file"] for e in ga.run()["engine_citation_reach"]}
    # the known engine references to L-grade / partial sources are surfaced
    assert "source-exec-314-mwbe-cert-validity.md" in reach
    assert "source-gcn-24-public-holidays.md" in reach
    assert "source-stf-109-vendor-certificate.md" in reach


def test_audit_consumes_dated_freshness_report_not_readme():
    _, used = ga.load_latest_freshness()
    assert used is None or used.endswith(".md")
    assert used != "README.md"


def test_audit_reports_three_finding_classes():
    rep = ga.run()
    for key in ("hard_failures", "blocking_to_enforcement", "advisory",
                "enforcement_complete"):
        assert key in rep


def test_engine_reach_is_blocking_to_enforcement_not_advisory():
    """Engine citations to non-eligible sources must be labeled blocking-to-
    enforcement (a distinct class), not folded into plain advisory findings."""
    rep = ga.run()
    blocking = {e["file"] for e in rep["blocking_to_enforcement"]}
    assert "source-stf-109-vendor-certificate.md" in blocking
    assert "source-exec-314-mwbe-cert-validity.md" in blocking
    assert rep["blocking_to_enforcement"], "expected blocking-to-enforcement findings"


def test_enforcement_not_complete_while_engine_bypasses():
    """Honest status: enforcement is NOT complete while any engine call site can
    reach a non-eligible source via bare cite()."""
    rep = ga.run()
    assert rep["enforcement_complete"] is False


def test_render_states_enforcement_not_complete():
    out = ga.render(ga.run())
    assert "ENFORCED END-TO-END: NO" in out
    assert "BLOCKING-TO-ENFORCEMENT" in out


# ======================= item 1: EXC/314 per-provision markers ============

_EXC = "source-exec-314-mwbe-cert-validity.md"
_FIVE_YEAR = ("all minority and women-owned business enterprise certifications "
              "shall be valid for a period of five years")
_RECERT = "there shall be a rebuttable presumption"
_OTHER_EXC = ("The director shall promulgate rules and regulations providing for "
              "the establishment of a statewide certification program")


def test_provision_marker_allows_confident_cite_of_5a_mechanical_sentence():
    g = GoldenCopy()
    assert g.cite(_EXC, _FIVE_YEAR, output_context=gs.OUTPUT_CONFIDENT) == _FIVE_YEAR


def test_provision_l_grade_recert_blocked_from_confident_allowed_gated():
    g = GoldenCopy()
    try:
        g.cite(_EXC, _RECERT, output_context=gs.OUTPUT_CONFIDENT)
    except GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
    else:
        raise AssertionError("recertification presumption must be confident-blocked")
    assert g.cite(_EXC, _RECERT, output_context=gs.OUTPUT_VERIFY) == _RECERT
    assert g.cite(_EXC, _RECERT, output_context=gs.OUTPUT_ATTORNEY_GATED) == _RECERT


def test_provision_marker_does_not_bless_file_wide():
    """A non-marked EXC/314 quote falls back to the file-level L_GRADE status —
    the F marker for 5(a) must not make the whole file confident-citable."""
    g = GoldenCopy()
    try:
        g.cite(_EXC, _OTHER_EXC, output_context=gs.OUTPUT_CONFIDENT)
    except GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
        return
    raise AssertionError("non-provision quote must inherit file-level L_GRADE")


def test_file_level_status_of_exc314_unchanged():
    assert GoldenCopy().status_of(_EXC) == gs.L_GRADE_INTERPRETIVE


def test_parse_provision_markers_format():
    raw = open(os.path.join(ga.SOURCES_DIR, _EXC), encoding="utf-8").read()
    markers = gs.parse_provision_markers(raw)
    by_status = {m["status"] for m in markers}
    assert gs.VERIFIED_GOLDEN in by_status and gs.L_GRADE_INTERPRETIVE in by_status
    assert all(m["anchor"] for m in markers)


# ======================= item 3: GCN/24 gated call site ===================

def test_gcn24_cite_passes_attorney_gated_and_verify():
    g = GoldenCopy()
    q = "The term public holiday includes the following days in each year"
    assert g.cite("source-gcn-24-public-holidays.md", q, output_context=gs.OUTPUT_ATTORNEY_GATED)
    assert g.cite("source-gcn-24-public-holidays.md", q, output_context=gs.OUTPUT_VERIFY)


def test_gcn24_cite_blocked_in_confident():
    g = GoldenCopy()
    q = "The term public holiday includes the following days in each year"
    try:
        g.cite("source-gcn-24-public-holidays.md", q, output_context=gs.OUTPUT_CONFIDENT)
    except GoldenEligibilityError:
        return
    raise AssertionError("GCN/24 must be confident-blocked")


def test_payment_clock_provider_builds_with_gated_anchor_check():
    """The payment_clock call-site now cites the GCN anchors with ATTORNEY_GATED
    context; the provider must still construct (GCN/24 L-grade passes gated)."""
    from engine.payment_clock import PaymentClock
    clk = PaymentClock(approved=True)
    assert clk.calendar is not None
    assert clk.net_due_adjusted("2026-06-15", 30).status == "KNOWN"


# ======================= runner ===========================================

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("GOLDEN COPY RELIABILITY AUDIT — TEST SUITE ({} tests)".format(len(tests)))
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
