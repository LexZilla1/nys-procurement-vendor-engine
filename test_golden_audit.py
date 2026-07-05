#!/usr/bin/env python3
"""
Tests for the Golden Copy Reliability Audit:
engine/golden_status.py, the GoldenCopy.cite() eligibility guardrail, and
scripts/golden_audit.py.

Runnable as `python3 test_golden_audit.py` or under pytest. No live network.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from engine import golden_status as gs  # noqa: E402
from validator import GoldenCopy, GoldenEligibilityError, CitationError  # noqa: E402
import validator as V  # noqa: E402
import golden_audit as ga  # noqa: E402

# Sources under an interim VERIFY gate (mixed/PARTIAL captures, gated-only).
INTERIM_SOURCES = {V.STF109, V.MWBE}


def _interim_citations_by_method():
    """Mechanically collect every validator Finding that cites an interim-gated
    source, by RUNNING the FULL validator surface over the repo fixtures (NOT
    narrated). Each record is tagged with the CHECK METHOD that produced it, so
    the RM-rule -> source attribution is derived, not hand-labelled. Returns
    [{method, rule_id, source, quote}, ...]."""
    val = V.Validator(golden=GoldenCopy())

    def _load(name):
        with open(name, encoding="utf-8") as fh:
            return json.load(fh)

    inv_missing = _load("sample-invoice-fail-missing-cert.json")
    inv_exc = dict(inv_missing)                     # missing cert + invokes §109(1-a)
    inv_exc["normal_course_invoice"] = True
    inv_exc["certification_required"] = False

    # The full public check surface — so interim-source citations can be
    # attributed to EXACTLY one method/rule, and any miswire (e.g. mwbe routed
    # through check_invoice) shows up as a new (method, source) pair.
    battery = [
        ("check_invoice", val.check_invoice, [_load("sample-invoice-pass.json"),
                                              inv_missing, inv_exc]),
        ("check_budget", val.check_budget, [_load("sample-budget-pass.json"),
                                            _load("sample-budget-fail.json")]),
        ("check_vendrep", val.check_vendrep, [_load("sample-vendrep-pass.json"),
                                              _load("sample-vendrep-fail-material-change.json")]),
        ("check_bid", val.check_bid, [_load("sample-bid-pass.json"),
                                      _load("sample-bid-fail-missing-eeo.json"),
                                      _load("sample-bid-fail-overdue.json")]),
        ("validate_rm2_interest", val.validate_rm2_interest, [
            _load("sample-contract-entitled-to-interest.json"),
            _load("sample-contract-no-interest-directive-suspended.json"),
            _load("sample-contract-no-interest-no-directive.json"),
            _load("sample-contract-excluded-local-government.json"),
            _load("sample-contract-below-de-minimis.json"),
            _load("sample-contract-excluded-court-judgment.json"),
            _load("sample-contract-excluded-nonstate-intermediary.json")]),
    ]
    out = []
    for method_name, fn, inputs in battery:
        for payload in inputs:
            res = fn(payload)
            for f in res.findings:
                if f.source_file in INTERIM_SOURCES:
                    out.append({"method": method_name, "rule_id": f.rule_id,
                                "source": f.source_file, "quote": f.citation_quote})
    return out

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
    L-grade source — the guardrail stays opt-in for any direct caller that does
    not pass a context. (The three engine/validator sites now DO pass one; see the
    bare-cite scan tests.)"""
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


def test_cite_partial_with_no_marker_not_citable_in_any_context():
    # A PARTIAL capture with NO provision-eligibility marker is not citable in any
    # context. (The real stf-109 / mwbe files now carry an INTERIM_VERIFY marker;
    # this invariant is proven on a synthetic marker-free PARTIAL source.)
    with tempfile.TemporaryDirectory() as tmp:
        _write_source(tmp, "source-part.md", body_marker="This is a MIXED capture with form layers.")
        g = GoldenCopy(sources_dir=tmp)
        assert g.status_of("source-part.md") == gs.PARTIAL_CAPTURE
        q = "§ 1. Synthetic body."
        for ctx in (gs.OUTPUT_CONFIDENT, gs.OUTPUT_VERIFY, gs.OUTPUT_ATTORNEY_GATED):
            try:
                g.cite("source-part.md", q, output_context=ctx)
            except GoldenEligibilityError as e:
                assert e.status == gs.PARTIAL_CAPTURE
            else:
                raise AssertionError("marker-free PARTIAL must not be citable in %s" % ctx)


def test_exc314_5a_confident_but_presumption_gated():
    """Per-provision markers: the mechanical § 314(5)(a) five-year sentence is
    confident-eligible; the (5)(b)-(c) presumption stays gated (VERIFY/attorney
    only). The confident marker must not bleed to the presumption."""
    g = GoldenCopy()
    exc = "source-exec-314-mwbe-cert-validity.md"
    five = ("all minority and women-owned business enterprise certifications "
            "shall be valid for a period of five years")
    pres = "there shall be a rebuttable presumption"
    # 5(a): confident OK
    assert g.cite(exc, five, output_context=gs.OUTPUT_CONFIDENT) == five
    # 5(b)-(c): confident BLOCKED, but VERIFY / attorney-gated OK
    try:
        g.cite(exc, pres, output_context=gs.OUTPUT_CONFIDENT)
        raise AssertionError("presumption must not be confident-eligible")
    except GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
    assert g.cite(exc, pres, output_context=gs.OUTPUT_VERIFY) == pres


def test_make_cert_expiry_quote_is_confident_eligible():
    """The exact quote engine.dated_objects.make_cert_expiry cites must resolve to
    a confident-eligible provision (so the future migration doesn't break it)."""
    from engine.dated_objects import EXC314_SOURCE, EXC314_QUOTE
    g = GoldenCopy()
    assert g.cite(EXC314_SOURCE, EXC314_QUOTE,
                  output_context=gs.OUTPUT_CONFIDENT) == EXC314_QUOTE


def test_stf109_and_mwbe_are_interim_verify_gated():
    """stf-109 and mwbe-5nycrr are downgraded to interim VERIFY: citable ONLY into
    VERIFY / attorney-gated, never confident (they are still PARTIAL captures)."""
    g = GoldenCopy()
    for fn in ("source-stf-109-vendor-certificate.md", "source-mwbe-5nycrr-pass-fail.md"):
        q = g.body(fn).strip().split("\n", 1)[0][:30]
        try:
            g.cite(fn, q, output_context=gs.OUTPUT_CONFIDENT)
            raise AssertionError("%s must not be confident-eligible (interim)" % fn)
        except GoldenEligibilityError as e:
            assert e.status == gs.INTERIM_VERIFY
        assert g.cite(fn, q, output_context=gs.OUTPUT_VERIFY) == q
        assert g.cite(fn, q, output_context=gs.OUTPUT_ATTORNEY_GATED) == q


def test_audit_blocking_cleared_and_end_to_end_yes():
    """After the per-provision markers + interim gates AND the call-site migration,
    no engine cite is a hard blocker (the four findings stay cleared/downgraded)
    AND every runtime cite() site passes an output_context, so end-to-end
    enforcement is now YES."""
    rep = ga.run()
    assert rep["blocking_to_enforcement"] == [], rep["blocking_to_enforcement"]
    files = lambda k: {e["file"] for e in rep[k]}
    assert "source-exec-314-mwbe-cert-validity.md" in files("cleared_by_provision")
    assert {"source-stf-109-vendor-certificate.md",
            "source-mwbe-5nycrr-pass-fail.md"} <= files("interim_verify_gate")
    assert "source-gcn-24-public-holidays.md" in files("gated_lgrade")
    # migration done -> no bare cite() sites remain -> end-to-end YES
    assert rep["unmigrated_cite_sites"] == [], rep["unmigrated_cite_sites"]
    assert rep["enforcement_complete"] is True


def test_exc314_confident_marker_does_not_bleed_to_other_sentences():
    """Negative anchor-bleed: an EXC/314 quote OUTSIDE the § 314(5)(a) five-year
    sentence must NOT inherit the confident marker. It stays governed by the
    file's L_GRADE status — blocked in confident, allowed only in VERIFY/gated."""
    g = GoldenCopy()
    exc = "source-exec-314-mwbe-cert-validity.md"
    other = "The director shall prepare a directory of certified businesses"  # subd. 2
    assert other in g.body(exc)                     # verbatim, and NOT within the 5(a) anchor
    raw = g._raw[exc]
    assert gs.effective_status(raw, other, g.status_of(exc)) == gs.L_GRADE_INTERPRETIVE
    try:
        g.cite(exc, other, output_context=gs.OUTPUT_CONFIDENT)
        raise AssertionError("non-5(a) EXC/314 text must not be confident-eligible")
    except GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
    assert g.cite(exc, other, output_context=gs.OUTPUT_VERIFY) == other


def test_interim_marker_is_additive_gating_not_a_file_trust_upgrade():
    """The interim marker must NOT change the derived whole-file status: stf-109
    and mwbe stay PARTIAL_CAPTURE (never VERIFIED_GOLDEN)."""
    for fn in ("source-mwbe-5nycrr-pass-fail.md", "source-stf-109-vendor-certificate.md"):
        raw = open(os.path.join("golden-copy", "sources", fn), encoding="utf-8").read()
        assert gs.derive_status(raw)[0] == gs.PARTIAL_CAPTURE
        assert gs.derive_status(raw)[0] != gs.VERIFIED_GOLDEN


def test_rm_outputs_citing_interim_sources_flip_confident_to_verify():
    """Every validator output that cites an interim-gated source (stf-109 / mwbe)
    is BLOCKED in a confident context and ALLOWED in VERIFY / attorney-gated —
    i.e. it flips confident -> VERIFY. Exercises the REAL guardrail (g.cite) in
    both directions per cited quote; mechanically derived (not narrated)."""
    g = GoldenCopy()
    cited = _interim_citations_by_method()
    assert cited, "expected validator findings citing stf-109/mwbe"
    seen = set()
    for rec in cited:
        src, quote = rec["source"], rec["quote"]
        seen.add(src)
        # fails in confident context...
        try:
            g.cite(src, quote, output_context=gs.OUTPUT_CONFIDENT)
            raise AssertionError("%s must be non-citable in CONFIDENT: %r" % (src, rec))
        except GoldenEligibilityError as e:
            assert e.status == gs.INTERIM_VERIFY, rec
        # ...and passes in VERIFY / attorney-gated context.
        assert g.cite(src, quote, output_context=gs.OUTPUT_VERIFY) == quote
        assert g.cite(src, quote, output_context=gs.OUTPUT_ATTORNEY_GATED) == quote
    assert seen == INTERIM_SOURCES, ("both interim sources must be exercised", seen)


def test_rm_attribution_is_a_mechanically_asserted_invariant():
    """The RM-rule -> source attribution is an ASSERTED invariant, derived from
    running the checks — not a hand-written label. It fails loudly on any miswire:
      * stf-109 is cited ONLY by RM-5 / check_invoice;
      * mwbe-5nycrr is cited ONLY by RM-4 / check_bid.
    If mwbe were ever routed back through check_invoice (or emitted as RM-5), the
    (source -> methods) / (source -> rule_ids) sets below would change and break."""
    cited = _interim_citations_by_method()
    rules_by_source, methods_by_source = {}, {}
    for rec in cited:
        rules_by_source.setdefault(rec["source"], set()).add(rec["rule_id"])
        methods_by_source.setdefault(rec["source"], set()).add(rec["method"])

    assert rules_by_source == {V.STF109: {"RM-5"}, V.MWBE: {"RM-4"}}, rules_by_source
    assert methods_by_source == {V.STF109: {"check_invoice"},
                                 V.MWBE: {"check_bid"}}, methods_by_source


def test_mwbe_both_directions_through_the_actual_check_bid_path():
    """mwbe both-directions, tied to the REAL RM-4 / check_bid citation (not an
    assumed RM-5 path): a quote check_bid actually cites is non-citable confident
    and citable in VERIFY / attorney-gated."""
    g = GoldenCopy()
    mwbe_via_bid = [r for r in _interim_citations_by_method()
                    if r["source"] == V.MWBE and r["method"] == "check_bid"]
    assert mwbe_via_bid, "check_bid must produce mwbe-5nycrr citations"
    for rec in mwbe_via_bid:
        assert rec["rule_id"] == "RM-4", rec
        q = rec["quote"]
        try:
            g.cite(V.MWBE, q, output_context=gs.OUTPUT_CONFIDENT)
            raise AssertionError("mwbe via check_bid must be non-citable confident")
        except GoldenEligibilityError as e:
            assert e.status == gs.INTERIM_VERIFY
        assert g.cite(V.MWBE, q, output_context=gs.OUTPUT_VERIFY) == q
        assert g.cite(V.MWBE, q, output_context=gs.OUTPUT_ATTORNEY_GATED) == q


# ============ both-directions tests per migrated gated cite site ==========
# One test per migrated runtime site, each exercising the REAL migrated code
# path in BOTH directions: the legitimate citation is admitted at the site's
# chosen context, and an ineligible source is fail-closed there.

def test_migrated_site_verify_golden_both_directions():
    """Site engine/citation.py::Citation.verify_golden (CONFIDENT default).
    Forward: a confident-eligible obligation citation (make_cert_expiry, EXC
    §314(5)(a)) verifies through the default confident gate. Reverse: a citation on
    a gated-only source (stf-109, interim) is REJECTED at the confident default and
    ACCEPTED once the caller passes a VERIFY context."""
    from engine.dated_objects import make_cert_expiry
    from engine.citation import Citation, GOLDEN_RULE
    from engine.citation import CitationError as EngineCitationError
    g = GoldenCopy()
    # forward: confident obligation verifies via the default output_context=CONFIDENT
    assert make_cert_expiry("c", "cred", "2027-01-01").citation.verify_golden(g) is True
    # reverse: an interim (stf-109) citation is blocked at the confident default...
    q = g.body(V.STF109).strip().split("\n", 1)[0][:30]
    gated = Citation(source_id=V.STF109, source_type=GOLDEN_RULE, locator="§ 109",
                     quote=q, captured_at="2026-07-05")
    try:
        gated.verify_golden(g)                       # default CONFIDENT -> rejected
        raise AssertionError("interim source must not verify at the confident default")
    except EngineCitationError:
        pass
    # ...and admitted when the caller declares a VERIFY / attorney-gated output.
    assert gated.verify_golden(g, output_context=gs.OUTPUT_VERIFY) is True
    assert gated.verify_golden(g, output_context=gs.OUTPUT_ATTORNEY_GATED) is True


def test_migrated_site_payment_clock_anchor_both_directions():
    """Site engine/payment_clock.py HolidayCalendarProvider anchor cite (VERIFY,
    gated). Forward: the provider builds — the L-grade GCN §24 anchor is citable
    into the gated (VERIFY) context it uses. Reverse: that migrated context is
    load-bearing (the same anchor is NOT confident-eligible), and a holiday source
    non-citable even at VERIFY fails the provider closed."""
    import engine.payment_clock as pcmod
    # forward: real provider construction succeeds through the migrated cite
    assert pcmod.HolidayCalendarProvider(golden=GoldenCopy()) is not None
    # reverse (a): the migrated gate matters — confident is blocked (L_GRADE)
    g = GoldenCopy()
    try:
        g.cite(pcmod.GCN24_SOURCE, pcmod.GCN24_ANCHOR_QUOTE,
               output_context=gs.OUTPUT_CONFIDENT)
        raise AssertionError("GCN §24 (L-grade) anchor must not be confident-eligible")
    except GoldenEligibilityError as e:
        assert e.status == gs.L_GRADE_INTERPRETIVE
    # reverse (b): a source non-citable even at VERIFY fails the provider closed
    diverged = GoldenCopy(freshness={pcmod.GCN24_SOURCE: ("DIVERGENT", False)})
    try:
        pcmod.HolidayCalendarProvider(golden=diverged)
        raise AssertionError("DIVERGENT holiday source must fail the provider closed")
    except pcmod.HolidaySourceUnavailable:
        pass


def test_migrated_site_validator_f_both_directions():
    """Site validator.py::Validator._f (VERIFY floor). Forward: a finding citing an
    interim-gated source (stf-109) is built — the VERIFY floor admits it — and the
    full check surface still emits interim-source citations. Reverse: a finding
    whose source is non-citable at VERIFY (DIVERGENT overlay) fails the builder
    closed."""
    # forward: _f admits an interim (stf-109) citation at the VERIFY floor
    val = V.Validator(golden=GoldenCopy())
    q = val.gc.body(V.STF109).strip().split("\n", 1)[0][:30]
    f = val._f("RM-5", V.STF109, q, V.FAIL, "interim cite admitted at VERIFY", True)
    assert f.source_file == V.STF109 and f.citation_quote == q
    assert _interim_citations_by_method(), "checks must still cite interim sources"
    # reverse: a DIVERGENT-overlaid source is non-citable at VERIFY -> _f raises
    diverged = V.Validator(golden=GoldenCopy(freshness={V.XII4F: ("DIVERGENT", False)}))
    dq = diverged.gc.body(V.XII4F).strip().split("\n", 1)[0][:20]
    try:
        diverged._f("RM-5", V.XII4F, dq, V.FAIL, "divergent must fail closed", True)
        raise AssertionError("DIVERGENT source must not be citable at the VERIFY floor")
    except GoldenEligibilityError as e:
        assert e.status == gs.DIVERGENT_FROM_API


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


def test_engine_reach_is_classified_by_disposition_not_folded_into_advisory():
    """Engine citations to gated/non-citable sources are classified by enforcement
    disposition — CLEARED_BY_PROVISION / INTERIM_VERIFY_GATE / GATED_LGRADE /
    BLOCKING — a distinct axis from plain advisory metadata findings. After
    Micro-PR A's markers, the four former blockers are cleared/downgraded (not
    folded into advisory, and no longer hard blockers)."""
    rep = ga.run()
    for e in rep["engine_citation_reach"]:
        assert e["disposition"] in ("CLEARED_BY_PROVISION", "INTERIM_VERIFY_GATE",
                                    "GATED_LGRADE", "BLOCKING"), e
    reached = {e["file"] for e in rep["engine_citation_reach"]}
    # the four historically-flagged sources are all still tracked (reached)...
    assert {"source-stf-109-vendor-certificate.md",
            "source-exec-314-mwbe-cert-validity.md",
            "source-mwbe-5nycrr-pass-fail.md",
            "source-gcn-24-public-holidays.md"} <= reached
    # ...but none remains a hard blocker after the markers/gates.
    assert rep["blocking_to_enforcement"] == []


def test_enforcement_complete_after_migration():
    """Honest status: enforcement is complete now that every engine/validator call
    site cites through an output_context — no bare cite() bypass remains."""
    rep = ga.run()
    assert rep["unmigrated_cite_sites"] == []
    assert rep["enforcement_complete"] is True


def test_render_states_enforcement_complete():
    out = ga.render(ga.run())
    assert "ENFORCED END-TO-END: YES" in out
    assert "BLOCKING-TO-ENFORCEMENT" in out


def test_cite_surface_classification_is_complete_and_runtime_is_migrated():
    """The runtime scan surface is CLASSIFICATION-DERIVED, not handpicked: every
    repo .py that invokes cite() is classified, the RUNTIME/product surface is
    exactly the six vendor-facing paths, all cite-invoking test suites are excluded
    WITH a reason, nothing is unclassified, and no runtime cite is bare."""
    surface = ga.classify_cite_surface()
    assert surface["unclassified"] == [], surface["unclassified"]
    assert set(surface["runtime"]) == {
        "validator.py", "bid_readiness.py", "cert_renewal.py", "gap_analysis.py",
        "engine/citation.py", "engine/payment_clock.py"}, sorted(surface["runtime"])
    assert all(reason for reason in surface["runtime"].values())      # every runtime path justified
    assert all(reason for reason in surface["excluded"].values())     # every exclusion justified
    assert ga.BARE_CITE_ALLOWLIST == frozenset()
    assert ga.unmigrated_cite_sites() == []


def test_excluded_test_paths_with_bare_cites_are_not_flagged():
    """A cite-invoking file is excluded ONLY with a reason, and its bare cites are
    then not flagged: e.g. test_payment_clock.py carries bare verbatim-assert cites
    (lines 197-200) yet is an EXCLUDED path, so no test_* site appears as
    unmigrated."""
    surface = ga.classify_cite_surface()
    assert "test_payment_clock.py" in surface["excluded"]
    assert surface["excluded"]["test_payment_clock.py"]              # reason present
    assert all(not s["file"].startswith("test_") for s in ga.unmigrated_cite_sites())


def test_unclassified_cite_invoking_file_fails_closed():
    """STANDING fail-closed guard: a cite-invoking file absent from BOTH
    classification tables must (a) surface as UNCLASSIFIED (count > 0), (b) set
    enforcement_complete False, and (c) render END-TO-END: NO listing the file.
    This breaks CI if someone later drops the unclassified term from the YES gate.
    (Simulated by dropping a known runtime entry; the FILE is unchanged, only the
    in-memory classification table — restored in finally.)"""
    orig = dict(ga.RUNTIME_CITE_FILES)
    try:
        del ga.RUNTIME_CITE_FILES["bid_readiness.py"]               # now unclassified
        surface = ga.classify_cite_surface()
        assert "bid_readiness.py" in surface["unclassified"], surface   # (a) count > 0
        rep = ga.run()
        assert len(rep["cite_surface_unclassified"]) > 0
        assert rep["enforcement_complete"] is False                     # (b) YES gate closed
        out = ga.render(rep)                                            # (c) audit finding surfaced
        assert "ENFORCED END-TO-END: NO" in out
        assert "bid_readiness.py" in out
    finally:
        ga.RUNTIME_CITE_FILES.clear()
        ga.RUNTIME_CITE_FILES.update(orig)


def test_cite_call_detection_is_ast_based_and_robust():
    """Detection is AST-based (point 3): a `.cite(` split across lines / reformatted
    onto its own line is found and its `output_context` recognized; a docstring
    mention `GoldenCopy.cite()` and a `def cite(` definition are NOT calls. So the
    ban is not defeated by ordinary reformatting, and not tripped by prose."""
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "m.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(
                '"""A doc mention of GoldenCopy.cite() must be ignored."""\n'
                "def cite(self, a, b):\n    return a\n"          # a def, not a call
                "golden \\\n    .cite(\n        src,\n        quote,\n    )\n"  # bare, multi-line, own line
                "self.gc.cite(s, q, output_context=X)\n")        # migrated, attribute-chained
        calls = ga._cite_calls(p)
        # exactly two CALLS detected: one bare, then one migrated (doc/def ignored)
        assert [oc for _, oc in calls] == [False, True], calls


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
