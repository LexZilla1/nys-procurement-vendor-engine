#!/usr/bin/env python3
"""
Tests for tender_extractor.py (BUILD SPEC v2 Part A support).

Runnable two ways:
    python3 test_tender_extractor.py     # built-in runner, no dependencies
    pytest test_tender_extractor.py

Covers:
  * PRIVACY (§11) — the module imports NO network/model client.
  * PDF text-layer round-trip on the committed sample tender.
  * Requirement detection: domain classification + page attribution.
  * Plain-text (.txt) paste fallback parses pages on form feeds.
  * A no-text-layer (scanned) PDF reports has_text_layer=False — never guesses.
"""

import os
import sys

import tender_extractor as TE

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = os.path.join(HERE, "sample-tender.pdf")
TXT = os.path.join(HERE, "sample-tender.txt")


def test_privacy_no_network_imports():
    """Extraction must stay on-machine: no socket/urllib/http/model imports."""
    TE._assert_no_network_imports()


def test_pdf_has_text_layer_and_pages():
    ex = TE.extract(PDF)
    assert ex["has_text_layer"] is True
    assert ex["page_count"] == 3, ex["page_count"]
    assert any("EEO" in p for p in ex["pages"])


def test_requirements_found_and_classified():
    ex = TE.extract(PDF)
    reqs = TE.find_requirements(ex)
    kinds = {r["kind"] for r in reqs}
    for expected in ("eeo", "mwbe", "sdvob", "insurance", "bonding",
                     "vendor_responsibility"):
        assert expected in kinds, "missing kind {} in {}".format(expected, kinds)


def test_requirement_excerpts_are_verbatim_from_tender():
    """Every detected requirement text must appear verbatim in some page —
    provenance is the uploaded tender, not a paraphrase."""
    ex = TE.extract(PDF)
    blob = "\n".join(ex["pages"])
    for r in TE.find_requirements(ex):
        assert r["text"] in blob or r["text"].rstrip(";.") in blob, r["text"]


def test_page_attribution_is_one_based():
    ex = TE.extract(PDF)
    reqs = TE.find_requirements(ex)
    eeo = [r for r in reqs if r["kind"] == "eeo"][0]
    assert eeo["page"] == 2, eeo["page"]
    sdvob = [r for r in reqs if r["kind"] == "sdvob"][0]
    assert sdvob["page"] == 3, sdvob["page"]


def test_txt_paste_fallback_splits_pages_on_formfeed():
    ex = TE.extract(TXT)
    assert ex["has_text_layer"] is True
    assert ex["page_count"] == 3, ex["page_count"]
    reqs = TE.find_requirements(ex)
    assert {r["kind"] for r in reqs} >= {"eeo", "mwbe", "sdvob"}


def test_scanned_pdf_reports_no_text_layer_not_guess():
    """A PDF with no extractable text operators must yield has_text_layer=False
    so the caller says 'not confirmed' rather than inventing requirements."""
    import tempfile
    fake = ("%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
            "trailer\n<< /Root 1 0 R >>\n%%EOF\n").encode("latin-1")
    path = os.path.join(tempfile.gettempdir(), "scanned-no-text.pdf")
    with open(path, "wb") as fh:
        fh.write(fake)
    try:
        ex = TE.extract(path)
        assert ex["has_text_layer"] is False
        assert TE.find_requirements(ex) == []
    finally:
        os.remove(path)


def test_dehyphenate_rejoins_words_split_across_lines():
    # Capitalized continuation → keep the hyphen (real compound).
    assert TE._dehyphenate("Minority and Women-\nOwned Business") == \
        "Minority and Women-Owned Business"
    # lowercase continuation → soft wrap hyphen dropped.
    assert TE._dehyphenate("utiliza-\ntion plan") == "utilization plan"


def test_workforce_one_word_does_not_trigger_eeo():
    # The WIOA false positive: "Workforce" (one word) must NOT classify as EEO.
    assert TE._classify("Under the Workforce Innovation and Opportunity Act") != "eeo"
    # The real §143.3(c) term "work force" (two words) still does.
    assert TE._classify("submit total work force data to the agency") == "eeo"


def test_public_work_boilerplate_does_not_trigger_220i():
    # Bare 'public work contract' in a standard clause must NOT trip §220-i.
    assert TE._classify(
        "If this is a public work contract covered by Article 8") \
        != "public_work_registration"
    # An explicit registration reference still does.
    assert TE._classify(
        "Contractor must hold a Certificate of Registration (220-i)") \
        == "public_work_registration"


def test_pdf_string_unescape_octal_and_parens():
    assert TE._unescape_pdf_string(r"a\(b\)c") == "a(b)c"
    assert TE._unescape_pdf_string(r"line\nbreak") == "line\nbreak"
    assert TE._unescape_pdf_string(r"\101") == "A"  # octal 101 = 'A'


# --------------------------------------------------------------------------
# Silent-drop fix (PR #45) — authority/form references without shall/must
# --------------------------------------------------------------------------

def _reqs(*lines):
    ex = {"pages": ["\n".join(lines)], "page_count": 1, "source": "x",
          "has_text_layer": True}
    return TE.find_requirements(ex)


def test_authority_reference_with_cue_but_no_mandatory_language_is_captured():
    """An authority reference with an obligation cue but no shall/must and no
    mapped domain used to be silently dropped; it is now captured."""
    reqs = _reqs("Vendors register under Environmental Conservation Law § 17-0303.")
    auth = [r for r in reqs if r.get("capture") == "authority_reference"]
    assert auth, "cued authority reference should be captured, not dropped"
    assert "Environmental Conservation Law" in auth[0]["text"]


def test_form_attachment_reference_with_cue_is_captured():
    reqs = _reqs("All submissions are governed by Appendix B.")     # 'governed by' cue
    auth = [r for r in reqs if r.get("capture") == "authority_reference"]
    assert auth and "Appendix B" in auth[0]["text"]


def test_bare_authority_or_form_reference_without_cue_is_dropped():
    """Refinement 3 — a bare authority/form reference with NO obligation cue is
    not a duty and must not be captured (kills 'Article 15', '(See Attachment A)')."""
    for line in ("Article 15", "Article 3", "(See Attachment A).",
                 "The program operates under Executive Law generally."):
        reqs = _reqs(line)
        assert [r for r in reqs if r.get("capture") == "authority_reference"] == [], \
            line


def test_real_pdf_wrap_fragments_are_dropped():
    """Refinement 1+2 — the actual PDF line-wrap fragments found in
    rfp25003mediation must NOT each become a possible-authority."""
    fragments = ["Education Law § 2-", "d and § 121.6 of",
                 "Pursuant to Education Law § 2-",
                 "A of the New York State Executive Law"]
    for frag in fragments:
        reqs = _reqs(frag)
        assert [r for r in reqs if r.get("capture") == "authority_reference"] == [], \
            frag


def test_form_code_pattern_does_not_match_lowercase_word():
    """'Form is completed' is not a form CODE — the code must be uppercase/digit."""
    assert not TE._AUTHORITY_REF_RE.search("the form is completed by the vendor")
    assert TE._AUTHORITY_REF_RE.search("submit Form ST-220 with the bid")


def test_wrapped_citation_is_stitched_before_capture():
    """Refinement 1 — a citation split across a line break is rejoined so it is
    captured once as a whole reference rather than as two fragments."""
    page = "The contractor certifies compliance with Education Law § 2-\nd and § 121.6."
    reqs = TE.find_requirements({"pages": [page], "page_count": 1, "source": "x",
                                 "has_text_layer": True})
    auth = [r for r in reqs if r.get("capture") == "authority_reference"]
    assert auth, "stitched citation should be captured"
    assert "§ 2-d" in auth[0]["text"]                  # hyphen-split id rejoined


def test_repeated_authority_is_deduped_by_normalized_reference():
    """Refinement 4 — the same citation repeated across the document collapses to
    a single possible-authority capture."""
    page = "\n".join(
        ["Contractor certifies compliance with Education Law § 2-d for record %d." % i
         for i in range(5)])
    reqs = TE.find_requirements({"pages": [page], "page_count": 1, "source": "x",
                                 "has_text_layer": True})
    auth = [r for r in reqs if r.get("capture") == "authority_reference"]
    assert len(auth) == 1, [r["text"] for r in auth]


def test_passing_narrative_authority_mention_is_not_captured():
    """PRECISION: an authority cited only in passing narrative (the issuer's
    action, no bidder duty) must NOT generate a spurious requirement."""
    seg = "Pursuant to State Finance Law, the agency issues this RFQ."
    reqs = _reqs(seg)
    assert reqs == [], reqs                          # no requirement at all
    assert TE._is_passing_narrative(seg)             # classified as narrative
    assert TE._AUTHORITY_REF_RE.search(seg)          # (the authority IS present)


def test_authority_reference_with_vendor_cue_is_not_treated_as_narrative():
    """A bidder-directed cue defeats the narrative guard even with a 'pursuant to'
    frame — the reference plausibly imposes an obligation and is captured."""
    seg = "Pursuant to Labor Law § 220, the contractor must register."
    # This one has 'must' → captured via the normal signal path (not dropped).
    reqs = _reqs(seg)
    assert reqs, "a bidder-directed authority obligation must not be dropped"
    assert not TE._is_passing_narrative(seg)


def test_existing_signal_captures_still_tagged_signal():
    ex = TE.extract(PDF)
    reqs = TE.find_requirements(ex)
    assert reqs and all(r.get("capture") in ("signal", "authority_reference")
                        for r in reqs)
    # The real sample has no residual possible-authority captures.
    assert all(r.get("capture") == "signal" for r in reqs)


def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("TENDER EXTRACTOR — TEST SUITE ({} tests)".format(len(tests)))
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
