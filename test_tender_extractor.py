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


def test_dehyphenate_rejoins_end_of_line_hyphenation():
    """End-of-line hyphenation rejoins the split word; a capitalized continuation
    keeps the hyphen (a real compound), never dropping characters."""
    assert TE._dehyphenate("require-\nment") == "requirement"
    assert TE._dehyphenate("Service-\nDisabled") == "Service-Disabled"


def test_tj_array_bracket_glyph_not_swallowed():
    """A '[' GLYPH inside a TJ-array string must not break array parsing.

    Regression for the real IFB 23447 "witState" defect: the TJ array showing
    "h the Procurement Lobbying Law [" ended with a '[' string literal, which the
    old array regex mis-parsed — dropping that array's text and concatenating
    "wit" + "State" into "witState". The corrected text (derived from the PDF
    bytes) keeps every character."""
    raw = ("[(In accordance wit)]TJ\nET\nq\nBT\n/T 1 Tf\n10 0 0 10 259 518 Tm\n"
           "[(h the Procurement Lobbying Law )([)]TJ\n[(State Finance Law )]TJ")
    out = TE._text_from_content(raw)
    assert "witState" not in out
    assert "In accordance with the Procurement Lobbying Law [State Finance Law" in out


def test_tj_array_bracket_at_string_edges_preserved():
    """A ']' glyph at a string edge is preserved; no character is dropped."""
    assert TE._text_from_content("[(a)(])(b)]TJ") == "a]b"


def test_plain_line_break_separates_not_swallows():
    """A non-hyphenated line break (Td) separates words with a newline — both
    words survive; characters are never swallowed by concatenation."""
    out = TE._text_from_content("[(foo)]TJ\n0 -12 Td\n[(bar)]TJ")
    assert "foo" in out and "bar" in out


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


def test_procurement_lobbying_classification():
    # PR-B1 test (a): a §139-j / restricted-period / offerer-certification passage
    # classifies as procurement_lobbying — NOT the generic 'certification' kind
    # (which routes to UNMAPPED) and not 'general'.
    hit = TE._classify(
        "Offerers are advised of the restricted period under State Finance Law "
        "§139-j; the Offerer's Certification of Compliance with §139-j and "
        "§139-k and Disclosure of Prior Non-Responsibility Determinations must "
        "be submitted.")
    assert hit == "procurement_lobbying", hit
    # §139-k alone, procurement-lobbying, and prior-non-responsibility all route here.
    assert TE._classify("procurement lobbying restrictions apply (139-k)") \
        == "procurement_lobbying"
    assert TE._classify("disclose any prior non-responsibility determination") \
        == "procurement_lobbying"
    # It wins over the generic 'certification' entry (placed after it, first-match).
    assert TE._classify("the Offerer's certification is required") \
        == "procurement_lobbying"


def test_procurement_lobbying_negative_bare_terms():
    # PR-B1 test (e): bare 'contacts' / 'period' / 'restricted' in unrelated
    # boilerplate must NOT trip the §139-j/§139-k keyword.
    for seg in ("The vendor contacts the help desk for support.",
                "The warranty period is one year.",
                "Access to the site is restricted to badged personnel."):
        assert TE._classify(seg) != "procurement_lobbying", seg


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


# --------------------------------------------------------------------------
# Other-bucket precision (PR #45 review): prose wrap-stitch + fragment guard
# --------------------------------------------------------------------------

def test_is_incomplete_fragment_flags_real_wrap_leftovers():
    """The real PDF wrap leftovers are incomplete fragments; a whole obligation
    is not."""
    assert TE.is_incomplete_fragment("no later than May")            # 4 words, unterminated
    assert TE.is_incomplete_fragment("The CDRC must")                # 3 words, unterminated
    assert not TE.is_incomplete_fragment(
        "The contractor shall submit all required documentation before the deadline.")


def test_prose_wrap_stitches_lowercase_continuation():
    """A line ending mid-clause whose next line starts lowercase is a PDF wrap —
    rejoined with a single space."""
    assert TE._stitch_wraps("submit the plan\nno later than the deadline.") == \
        "submit the plan no later than the deadline."
    # a comma (mid-clause) also joins
    assert TE._stitch_wraps("Court System,\nthe bidder will provide.") == \
        "Court System, the bidder will provide."


def test_prose_stitch_never_joins_complete_sentences():
    """Two lines that each read as complete sentences (prior ends terminal, next
    starts uppercase) are NEVER joined."""
    assert TE._stitch_wraps("First sentence.\nSecond sentence.") == \
        "First sentence.\nSecond sentence."
    # prior ends terminal even if next is lowercase → not joined
    assert TE._stitch_wraps("Done.\nthen more") == "Done.\nthen more"
    # next starts uppercase (a new clause) → not joined
    assert TE._stitch_wraps("ends midclause\nThe Next") == "ends midclause\nThe Next"


def test_wrapped_obligation_consolidates_into_one_segment():
    """A genuine obligation wrapped across lines is stitched into ONE complete
    segment (consolidates, does not fragment)."""
    page = "The contractor shall maintain records\nfor the full contract term."
    reqs = TE.find_requirements({"pages": [page], "page_count": 1, "source": "x",
                                 "has_text_layer": True})
    texts = [r["text"] for r in reqs]
    assert any(t == "The contractor shall maintain records for the full contract "
               "term." for t in texts), texts


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


# ---------------------------------------------------------------------------
# PR-A finding 1 — bid-bond waiver / negation detection (extractor level)
# ---------------------------------------------------------------------------

_WAIVER = ("The Commissioner of OGS has determined that no performance, payment "
           "or Bid bond of any kind is required for this procurement.")
_POSITIVE = "A bid bond of 5% of the bid amount shall accompany each bid."
_GUARD = "A bond is required unless waived by the Commissioner."


_DEADLINE = ("No later than the bid due date, a bid bond of 5% of the bid amount "
             "is required.")


def test_is_bond_waiver_is_narrow():
    # waiver / negation constructions -> True
    assert TE.is_bond_waiver(_WAIVER)
    assert TE.is_bond_waiver("A bid bond is not required for this solicitation.")
    assert TE.is_bond_waiver("Bid bond is not required.")
    # affirmative requirement (even one mentioning waiver) -> False (not suppressed)
    assert not TE.is_bond_waiver(_POSITIVE)
    assert not TE.is_bond_waiver(_GUARD)                       # "required unless waived"
    assert not TE.is_bond_waiver("A bid bond is required unless waived by OGS.")


def test_is_bond_waiver_ignores_comparative_deadline_idioms():
    # "no <word> than" idioms are NOT bond negations — must return False so a real
    # bond requirement with deadline/comparative phrasing is not suppressed.
    assert not TE.is_bond_waiver(_DEADLINE)                     # "No later than ..."
    assert not TE.is_bond_waiver("No earlier than award, a bid bond is required.")
    assert not TE.is_bond_waiver("A bid bond of no less than 5% is required.")
    assert not TE.is_bond_waiver("A bid bond of no more than 10% is required.")
    assert not TE.is_bond_waiver("Submit no fewer than three references; a bid bond is required.")


def test_wrap_split_bond_waiver_routes_to_waiver_not_requirement():
    """CROSS-CORPUS REGRESSION: the OGS bond-waiver sentence, when PDF line-wrap
    splits it across a capitalized continuation ('...of the\\nContract is
    required'), used to lose the 'no ... required' framing on the single segment
    and score as a RED bond REQUIREMENT (false-RED, inconsistent across tenders).
    It must instead route to the WAIVER channel via the reconstructed sentence."""
    page = ("The Commissioner of OGS has determined that no performance, payment\n"
            "or Bid bond, or other form of security for the faithful performance of the\n"
            "Contract is required at any time during the term of the resulting Contract.")
    reqs = TE.find_requirements({"pages": [page], "page_count": 1, "source": "x",
                                 "has_text_layer": True})
    bond = [r for r in reqs if r["kind"] == "bonding"]
    assert bond, "the bond passage must still be captured (never silently dropped)"
    assert all(r.get("capture") == "waiver" for r in bond), bond
    # no bonding passage is left as a scored requirement (signal)
    assert not any(r["kind"] == "bonding" and r.get("capture") == "signal" for r in reqs)


def test_wrap_split_genuine_bond_requirement_is_not_suppressed():
    """SAFETY: a genuine affirmative bond REQUIREMENT that is also wrap-split must
    NOT be rerouted to the waiver channel — the fix keys on is_bond_waiver, so
    only a real 'no ... required' negation reroutes, never an affirmative duty."""
    page = ("Each bidder shall furnish a bid bond of five percent of the\n"
            "Bid amount, which is required with the bid submission.")
    reqs = TE.find_requirements({"pages": [page], "page_count": 1, "source": "x",
                                 "has_text_layer": True})
    bond = [r for r in reqs if r["kind"] == "bonding"]
    assert bond, "the genuine bond requirement must be captured"
    assert any(r.get("capture") == "signal" for r in bond), bond   # scored, not waived
    assert not any(r.get("capture") == "waiver" for r in bond), bond


def test_find_requirements_routes_waiver_to_waiver_capture():
    ex = {"source": "fx", "page_count": 1, "pages": [_WAIVER], "has_text_layer": True}
    reqs = TE.find_requirements(ex)
    assert len(reqs) == 1 and reqs[0]["capture"] == "waiver"
    assert reqs[0]["kind"] == "bonding" and reqs[0]["text"] == _WAIVER


def test_find_requirements_keeps_positive_bond_as_signal():
    ex = {"source": "fx", "page_count": 1, "pages": [_POSITIVE], "has_text_layer": True}
    reqs = TE.find_requirements(ex)
    assert any(r["kind"] == "bonding" and r["capture"] == "signal" for r in reqs)
    assert not any(r.get("capture") == "waiver" for r in reqs)


# The EXACT sentence tender_extractor produces from IFB 23447 (OGS Group 05602,
# revised 2026-06-23; PDF SHA-256 e1f26e19cd5e71db4d6303875648a2548b4e2d1ddc4fb8
# fff2def45e1d86e246), captured verbatim from a real extraction run — NOT a
# hand-typed approximation. It enumerates multiple security instruments between
# "bond" and "required" (~116 chars), which the prior fixed-span waiver regex
# ({0,80}) missed, so the waiver rendered as a RED "Bid bond" blocker in pilot #2.
_IFB23447_BOND_WAIVER = (
    "The Commissioner of OGS has determined that no performance, payment or Bid "
    "bond, or negotiable irrevocable letter of credit or other form of security "
    "for the faithful performance of the Contract is required at any time during "
    "the term of the resulting Contract.")


def test_is_bond_waiver_true_on_exact_ifb23447_sentence():
    # Regression: the real IFB 23447 clause MUST be detected as a waiver. This is
    # the exact extractor output (long multi-instrument enumeration), the string
    # that defeated the {0,80}-span regex live in pilot #2.
    assert TE.is_bond_waiver(_IFB23447_BOND_WAIVER)


def test_ifb23447_bond_clause_routes_to_waiver_not_bonding_signal():
    ex = {"source": "fx", "page_count": 1, "pages": [_IFB23447_BOND_WAIVER],
          "has_text_layer": True}
    reqs = TE.find_requirements(ex)
    assert len(reqs) == 1 and reqs[0]["capture"] == "waiver"
    assert reqs[0]["kind"] == "bonding"
    assert reqs[0]["text"] == _IFB23447_BOND_WAIVER
    # It is NOT captured as a scored bonding signal.
    assert not any(r.get("capture") == "signal" for r in reqs)


def test_bond_waiver_is_sentence_scoped_not_cross_clause():
    # Sentence-scoping guard: a stray leading negation in a DIFFERENT clause (joined
    # by a comma/'and', or split by a colon/semicolon) must NOT read as a bond
    # waiver — the tempered no->bond run stops at a verb, and [.;:] bound the match.
    assert not TE.is_bond_waiver(
        "No bid may be withdrawn after opening, and a bid bond is required.")
    assert not TE.is_bond_waiver(
        "No proposal shall be withdrawn, and a bid bond is required.")
    assert not TE.is_bond_waiver("No exceptions: a bid bond is required.")
    # ...but a genuine negated instrument list, long or short, still matches.
    assert TE.is_bond_waiver("no bid bond will be required for this procurement.")
    assert TE.is_bond_waiver(
        "no performance, payment or Bid bond of any kind is required.")


# ---------------------------------------------------------------------------
# PR-A finding 2 — page count from /Type /Page objects; best-effort page numbers
# ---------------------------------------------------------------------------

# 3 /Type /Page LEAF objects, /Type /Pages Count 3, but only 2 text-bearing
# content streams (page 5 has no /Contents). Leaf count (3) != stream count (2).
_PDF_3PAGES_2STREAMS = (
    b"%PDF-1.7\n"
    b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
    b"2 0 obj << /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >> endobj\n"
    b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 6 0 R >> endobj\n"
    b"4 0 obj << /Type /Page /Parent 2 0 R /Contents 7 0 R >> endobj\n"
    b"5 0 obj << /Type /Page /Parent 2 0 R >> endobj\n"
    b"6 0 obj << /Length 40 >>\nstream\n"
    b"(The vendor shall submit an EEO policy statement.) Tj\nendstream endobj\n"
    b"7 0 obj << /Length 40 >>\nstream\n"
    b"(Workers compensation coverage shall be maintained.) Tj\nendstream endobj\n"
    b"trailer << /Root 1 0 R >>\n%%EOF")


def _write_bytes(data, suffix=".pdf"):
    import tempfile
    fh = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    fh.write(data)
    fh.close()
    return fh.name


def test_page_count_from_page_objects_not_streams():
    path = _write_bytes(_PDF_3PAGES_2STREAMS)
    try:
        ex = TE.extract_pdf(path)
    finally:
        os.unlink(path)
    assert ex["page_count"] == 3, ex["page_count"]                 # /Type /Page objects
    assert ex["page_count_exact"] is True
    assert ex["page_count_source"].startswith("/Type /Page")
    assert ex["text_bearing_stream_count"] == 2                    # not the vendor count
    assert ex["page_count"] != ex["text_bearing_stream_count"]


def test_page_count_counts_objects_in_compressed_object_streams():
    import zlib
    inner = b"<< /Type /Page >> << /Type /Page >>"                 # two page objs, compressed
    comp = zlib.compress(inner)
    data = (b"1 0 obj << /Type /Page >> endobj\n"                  # one uncompressed page
            b"2 0 obj << /Type /ObjStm /Filter /FlateDecode /Length %d >>\nstream\n"
            % len(comp) + comp + b"\nendstream endobj\n")
    assert TE._count_page_objects(data) == 3                       # 1 raw + 2 compressed


def test_page_numbers_flagged_approximate_when_order_unverified():
    path = _write_bytes(_PDF_3PAGES_2STREAMS)
    try:
        ex = TE.extract_pdf(path)
    finally:
        os.unlink(path)
    assert ex["page_numbers_approximate"] is True
    assert "approximate" in ex["page_number_note"].lower()
    # the mismatch is called out explicitly (stream ordinals are not page numbers)
    assert "stream" in ex["page_number_note"].lower()


def test_page_count_fallback_when_no_page_objects():
    """When /Type /Page objects cannot be found (unsupported compression/object-
    stream layout), the extractor must NOT present the text-stream count as an
    exact page count: page_count_exact is False and the note says best-effort."""
    # A PDF with a text-bearing content stream but NO /Type /Page objects anywhere.
    data = (b"%PDF-1.7\n"
            b"1 0 obj << /Length 30 >>\nstream\n"
            b"(A bid bond shall be provided.) Tj\nendstream endobj\n"
            b"trailer << >>\n%%EOF")
    assert TE._count_page_objects(data) is None                # no page objects found
    path = _write_bytes(data)
    try:
        ex = TE.extract_pdf(path)
    finally:
        os.unlink(path)
    assert ex["page_count_exact"] is False
    assert ex["page_numbers_approximate"] is True
    assert ex["text_bearing_stream_count"] == 1
    assert ex["page_count"] == 1                                # best-effort, not exact
    assert "not exact" in ex["page_count_source"].lower() or "not found" in ex["page_count_source"].lower()
    assert "best-effort" in ex["page_number_note"].lower()


def test_txt_page_numbers_are_exact():
    path = _write_bytes(b"Page one text.\fPage two text.", suffix=".txt")
    try:
        ex = TE.extract_txt(path)
    finally:
        os.unlink(path)
    assert ex["page_count"] == 2 and ex["page_numbers_approximate"] is False
    assert ex["page_count_exact"] is True


def test_extraction_recall_unchanged_by_page_numbering():
    """The page-count change must NOT drop any extracted requirement text: the
    text-bearing pages and the requirements found are exactly the stream-extractor
    output (both requirement strings survive)."""
    path = _write_bytes(_PDF_3PAGES_2STREAMS)
    try:
        ex = TE.extract_pdf(path)
    finally:
        os.unlink(path)
    assert ex["pages"] == ["The vendor shall submit an EEO policy statement.",
                           "Workers compensation coverage shall be maintained."]
    reqs = TE.find_requirements(ex)
    texts = " ".join(r["text"] for r in reqs)
    assert "EEO policy statement" in texts and "Workers compensation" in texts


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
