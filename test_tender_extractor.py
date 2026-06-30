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


def test_pdf_string_unescape_octal_and_parens():
    assert TE._unescape_pdf_string(r"a\(b\)c") == "a(b)c"
    assert TE._unescape_pdf_string(r"line\nbreak") == "line\nbreak"
    assert TE._unescape_pdf_string(r"\101") == "A"  # octal 101 = 'A'


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
