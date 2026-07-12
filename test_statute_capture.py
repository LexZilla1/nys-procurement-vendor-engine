#!/usr/bin/env python3
"""
Tests for the manual statute-capture tool (scripts/statute_capture.py) and its
freshness-registration hook (scripts/freshness_check.py).

Runnable as `python3 test_statute_capture.py` (built-in runner, no pytest
needed) or under pytest.

NO LIVE NETWORK: every case injects a fetcher backed by a recorded fixture
(tests/fixtures/statute_capture/*.json) or by the committed EXC/314 golden fed
back as the "live" response (the same offline technique freshness_check uses).
Covers: NEW-section formatting, EXISTING FULL-MATCH (no write), DIVERGENT
(human-review + no overwrite), fail-closed on empty/truncated/API-error/
unreadable-NB/missing-expected-NB, input validation, whitelist enforcement,
atomicity (no partial capture), PR-body content, key-never-leaks, and the
freshness existence-guarded registry merge.
"""

import contextlib
import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
import statute_capture as sc  # noqa: E402
import freshness_check as fc  # noqa: E402
import parse_golden_copy as pg  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "tests", "fixtures", "statute_capture")
EXC_FILE = "source-exec-314-mwbe-cert-validity.md"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


def _fetcher_from(name):
    payload = _fixture(name)
    return lambda law, loc: payload["result"]


def _spec(mode="new", file="source-gcn-24-public-holidays.md", **kw):
    d = {"mode": mode, "file": file, "min_subdivisions": 1}
    d.update(kw)
    return d


def _golden_echo_fetcher(mutate=None):
    text = fc.stored_state_text(EXC_FILE)
    if mutate:
        text = mutate(text)
    return lambda law, loc: {"text": text, "activeDate": "2026-02-20",
                             "repealed": False, "repealedDate": None}


@contextlib.contextmanager
def _temp_golden_tree():
    """Redirect the capture module's write targets into a throwaway tree so
    write tests never touch the real golden-copy/."""
    orig = (sc.SOURCES_DIR, sc.REPORT_DIR, sc.REPO_ROOT)
    tmp = tempfile.mkdtemp()
    try:
        sc.REPO_ROOT = tmp
        sc.SOURCES_DIR = os.path.join(tmp, "golden-copy", "sources")
        sc.REPORT_DIR = os.path.join(tmp, "docs", "statute-capture")
        os.makedirs(sc.SOURCES_DIR)
        yield tmp
    finally:
        sc.SOURCES_DIR, sc.REPORT_DIR, sc.REPO_ROOT = orig


def _expect_capture_error(fn):
    try:
        fn()
    except sc.CaptureError:
        return True
    raise AssertionError("expected CaptureError, none raised")


def _new_reg():
    """Synthetic mode:new registry for exercising NEW-mode capture() end-to-end.
    The real registry now marks GCN/24 & GCN/25-A mode:existing (verified golden,
    diff-only), so NEW orchestration is driven through capture()'s injectable
    `targets` seam instead of the on-disk registry."""
    return {"GCN/24": _spec(),
            "GCN/25-A": _spec(file="source-gcn-25-a-deadline-extension.md")}


# --------------------------------------------------------------------------
# Fixtures sanity
# --------------------------------------------------------------------------

def test_fixtures_carry_literal_escaped_newlines():
    """The recorded NEW fixture must mirror the live quirk (literal \\n runs
    surviving json.loads), so the tests exercise the real reflow path."""
    txt = _fixture("gcn-24_new.json")["result"]["text"]
    assert "\\n" in txt and "\n" not in txt, \
        "fixture should carry LITERAL escaped newlines, like the live API"


def test_registered_targets_present():
    reg = json.load(open(sc.REGISTRY_PATH, encoding="utf-8"))["targets"]
    for coord in ("GCN/24", "GCN/25-A", "EXC/314"):
        assert coord in reg, "missing registry target %s" % coord
    # GCN/24 & GCN/25-A were promoted to verified-golden (2026-07-05); their
    # registry mode is now 'existing' (diff-only), which closes the path where a
    # mode:new run could overwrite a verified golden with a PENDING candidate.
    assert reg["GCN/24"]["mode"] == "existing"
    assert reg["GCN/25-A"]["mode"] == "existing"
    assert reg["EXC/314"]["mode"] == "existing"


# --------------------------------------------------------------------------
# NEW-section capture formatting
# --------------------------------------------------------------------------

def test_new_section_capture_formatting():
    raw = _fixture("gcn-24_new.json")["result"]
    sec = sc.process_section("GCN/24", _spec(), raw, "2099-01-01")
    assert sec["verdict"] == "NEW"
    md = sec["content"]
    for label in ("# SOURCE TEXT", "- **Name:**", "- **Date:**",
                  "- **Issued by:**", "- **Link (permanent identifier):**",
                  "- **Copied exactly on:** 2099-01-01", "- **API activeDate:**",
                  "- **Capture method:** openleg-api-v3", "- **Covers:** full section",
                  "## STATE TEXT (verbatim)", "## CITATIONS"):
        assert label in md, "missing %r in NEW candidate" % label
    # PENDING HUMAN READ tier + freshness-registration marker
    assert "PENDING HUMAN READ" in md
    assert "Freshness-registered" in md
    # NB flag preserved verbatim inside the STATE TEXT body
    body = sc._state_text_from_md(md)
    assert "* NB Effective January 1, 2099" in body
    assert body.lstrip().startswith("§")
    # subdivision counts agree (API vs saved)
    assert sec["api_subdiv_count"] == 2
    assert sec["saved_subdiv_count"] == 2


def test_new_candidate_is_parser_compatible():
    """A NEW candidate must satisfy the golden-copy parser (so a future capture
    PR passes parse_golden_copy)."""
    raw = _fixture("gcn-24_new.json")["result"]
    sec = sc.process_section("GCN/24", _spec(), raw, "2099-01-01")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as fh:
        fh.write(sec["content"])
        path = fh.name
    try:
        rec = pg.parse_source_file(path)  # raises ParseFailure if malformed
        assert rec["name"]
    finally:
        os.unlink(path)


def test_new_single_paragraph_section_counts_one_subdivision():
    raw = _fixture("gcn-25-a_new.json")["result"]
    sec = sc.process_section("GCN/25-A", _spec(file="source-gcn-25-a-deadline-extension.md"),
                             raw, "2099-01-01")
    assert sec["verdict"] == "NEW"
    assert sec["api_subdiv_count"] == 1  # implicit single subdivision
    assert sec["saved_subdiv_count"] == 1


def test_subdivision_count_reflow_case_heading_line_marker():
    """Regression: subdivision 1 reflowed onto the '§' heading line must still
    be counted (the GCN/25-A '1 subdivision' artifact). Reads 2, not 1."""
    raw = _fixture("gcn-25-a_reflow.json")["result"]
    reflowed = fc.reflow(raw["text"])
    # subdivision 1 shares the heading line; subdivision 2 is on its own line
    assert reflowed.splitlines()[0].lstrip().startswith("§")
    assert " 1. " in reflowed.splitlines()[0]  # inline on the heading line
    assert sc.ordered_subdivisions(reflowed) == ["1", "2"]
    sec = sc.process_section("GCN/25-A", _spec(file="source-gcn-25-a-deadline-extension.md"),
                             raw, "2099-01-01")
    assert sec["api_subdiv_count"] == 2
    assert sec["saved_subdiv_count"] == 2


def test_real_gcn_25a_golden_reads_two_subdivisions():
    """The promoted GCN/25-A golden on disk must count 2/2 with the fix."""
    body = fc.stored_state_text("source-gcn-25-a-deadline-extension.md")
    assert sc.ordered_subdivisions(body) == ["1", "2"]


def test_inline_marker_scan_ignores_section_number_and_dates():
    """The heading-line inline scan must not miscount the section number
    ('§ 25-a.') or in-text dates ('July 1, 2028') as subdivisions."""
    # A single-subdivision-free heading with a date and the section number only.
    txt = "§ 24. Public holidays. Effective July 1, 2028 and each general day."
    assert sc.ordered_subdivisions(txt) == []  # no false subdivision markers


# --------------------------------------------------------------------------
# EXISTING mode
# --------------------------------------------------------------------------

def test_existing_full_match_does_not_write():
    sec = sc.process_section("EXC/314", _spec(mode="existing", file=EXC_FILE),
                             _golden_echo_fetcher()("EXC", "314"), "2099-01-01")
    assert sec["verdict"] == "FULL-MATCH"
    assert sec["content"] is None          # never builds a candidate
    assert sec["write_path"] is None       # never writes


def test_existing_divergent_flags_review_and_does_not_overwrite():
    golden_path = os.path.join(fc.SOURCES_DIR, EXC_FILE)
    before = hashlib.sha256(open(golden_path, "rb").read()).hexdigest()

    def mutate(_):
        return ("* § 314. COMPLETELY REWRITTEN placeholder text that no longer "
                "matches the stored capture in any way. 1. one. 2. two. 3. three.")
    sec = sc.process_section("EXC/314", _spec(mode="existing", file=EXC_FILE),
                             _golden_echo_fetcher(mutate)("EXC", "314"), "2099-01-01")
    assert sec["verdict"] == "DIVERGENT"
    assert sec["diff"], "DIVERGENT must carry a diff for human review"
    assert sec["content"] is None
    after = hashlib.sha256(open(golden_path, "rb").read()).hexdigest()
    assert before == after, "DIVERGENT must NOT overwrite the golden file"


# --------------------------------------------------------------------------
# Fail-closed
# --------------------------------------------------------------------------

def test_fail_closed_empty_response():
    _expect_capture_error(lambda: sc.capture(
        ["GCN/24"], _fetcher_from("empty.json"), "2099-01-01", write=False))


def test_fail_closed_truncated_response():
    _expect_capture_error(lambda: sc.capture(
        ["GCN/24"], _fetcher_from("truncated.json"), "2099-01-01", write=False))


def test_fail_closed_api_error_no_fallback():
    def boom(law, loc):
        raise RuntimeError("simulated network failure")
    _expect_capture_error(lambda: sc.capture(["GCN/24"], boom, "2099-01-01",
                                             write=False))


def test_fail_closed_api_success_false():
    # The real http_fetcher raises CaptureError when the API returns
    # success=false; a fetcher that does the same must abort the run.
    def sf(law, loc):
        raise sc.CaptureError("API success=false for %s/%s: nope" % (law, loc))
    _expect_capture_error(lambda: sc.capture(["GCN/24"], sf, "2099-01-01",
                                             write=False))


def test_fail_closed_unreadable_nb_flag():
    def fetch(law, loc):
        return {"text": "§ 24. Placeholder body long enough to clear the "
                        "truncation length floor for this test. 1. one.\\n** NB\\n",
                "activeDate": "2099-01-01"}
    _expect_capture_error(lambda: sc.capture(["GCN/24"], fetch, "2099-01-01",
                                             write=False))


def test_fail_closed_missing_nb_when_expected():
    raw = _fixture("gcn-25-a_new.json")["result"]  # no NB flags
    _expect_capture_error(lambda: sc.process_section(
        "GCN/25-A",
        _spec(file="source-gcn-25-a-deadline-extension.md", expect_nb_flags=True),
        raw, "2099-01-01"))


def test_fail_closed_missing_subdivision_when_expected():
    raw = _fixture("gcn-25-a_new.json")["result"]  # single paragraph => 1
    _expect_capture_error(lambda: sc.process_section(
        "GCN/25-A",
        _spec(file="source-gcn-25-a-deadline-extension.md", min_subdivisions=5),
        raw, "2099-01-01"))


# --------------------------------------------------------------------------
# Input validation / whitelist
# --------------------------------------------------------------------------

def test_law_id_validation_rejects_suspicious():
    for bad in ("gcn/24", "GCN 24", "GCN/24; rm -rf /", "../etc/passwd",
                "GCN/24 OR 1=1", "", "GCN//24", "https://x/GCN/24"):
        _expect_capture_error(lambda b=bad: sc.parse_law_ids(b))


def test_law_id_validation_accepts_and_dedupes():
    assert sc.parse_law_ids("GCN/24, GCN/25-A ,EXC/314") == \
        ["GCN/24", "GCN/25-A", "EXC/314"]
    assert sc.parse_law_ids("GCN/24,GCN/24") == ["GCN/24"]


def test_unknown_target_rejected():
    _expect_capture_error(lambda: sc.capture(
        ["STF/999"], _fetcher_from("gcn-24_new.json"), "2099-01-01", write=False))


# --------------------------------------------------------------------------
# Atomicity (no partial capture) + real write path
# --------------------------------------------------------------------------

def test_write_path_creates_candidate_and_report():
    with _temp_golden_tree() as tmp:
        sc.capture(["GCN/24"], _fetcher_from("gcn-24_new.json"),
                   "2099-01-01", write=True, targets=_new_reg())
        assert os.path.exists(os.path.join(
            sc.SOURCES_DIR, "source-gcn-24-public-holidays.md"))
        assert os.path.exists(os.path.join(
            tmp, "docs", "statute-capture", "2099-01-01.md"))


def test_atomic_no_partial_capture_on_failure():
    with _temp_golden_tree():
        before = set(os.listdir(sc.SOURCES_DIR))

        def one_ok_one_bad(law, loc):
            if loc == "24":
                return _fixture("gcn-24_new.json")["result"]
            return {"text": ""}  # GCN/25-A empty -> fail-closed
        _expect_capture_error(lambda: sc.capture(
            ["GCN/24", "GCN/25-A"], one_ok_one_bad, "2099-01-02", write=True,
            targets=_new_reg()))
        after = set(os.listdir(sc.SOURCES_DIR))
        assert before == after, "a fail-closed run wrote a partial capture"


# --------------------------------------------------------------------------
# PR body / report content + key protection
# --------------------------------------------------------------------------

def test_report_contains_all_required_fields():
    new = sc.process_section("GCN/24", _spec(), _fixture("gcn-24_new.json")["result"],
                             "2099-01-01")

    def mutate(_):
        return "* § 314. rewritten placeholder. 1. one. 2. two."
    div = sc.process_section("EXC/314", _spec(mode="existing", file=EXC_FILE),
                             _golden_echo_fetcher(mutate)("EXC", "314"), "2099-01-01")
    rep = sc.render_report([new, div], "2099-01-01")
    for needle in ("GCN/24", "EXC/314",              # law IDs
                   sc.API_BASE + "/GCN/24",          # endpoint (no key)
                   "Capture mode", "NEW", "EXISTING",
                   "Subdivision count (from API)", "Subdivision count (saved in file)",
                   "NB flags found", "Diff result",
                   "PENDING HUMAN READ",              # pending notice
                   "not verified golden"):           # explicit not-golden note
        assert needle in rep, "report missing %r" % needle
    assert "DIVERGENT" in rep and "```diff" in rep


def test_key_never_leaks_into_endpoint_or_report():
    sentinel = "SECRET_KEY_SHOULD_NOT_APPEAR"
    os.environ["NYSLEG_API_KEY"] = sentinel
    try:
        new = sc.process_section("GCN/24", _spec(),
                                 _fixture("gcn-24_new.json")["result"], "2099-01-01")
        rep = sc.render_report([new], "2099-01-01")
        assert sentinel not in rep
        assert "key=" not in rep
        assert sentinel not in new["endpoint"] and "key=" not in new["endpoint"]
    finally:
        del os.environ["NYSLEG_API_KEY"]


# --------------------------------------------------------------------------
# Freshness registration (existence-guarded merge)
# --------------------------------------------------------------------------

def test_freshness_registry_merge_existence_guarded():
    merged = fc.all_sources()
    # base 22 preserved
    assert set(fc.STATUTE_SOURCES).issubset(merged)
    # only registered targets whose golden file exists are merged
    for fn in fc.load_registry_sources():
        assert os.path.exists(os.path.join(fc.SOURCES_DIR, fn))
    # EXC/314 exists -> merged (and dedupes with the base map)
    assert EXC_FILE in merged
    # POST-CAPTURE reality: the GCN goldens now exist on disk, so they are
    # freshness-registered and correctly join the merged monthly-check map.
    assert "source-gcn-24-public-holidays.md" in merged
    assert "source-gcn-25-a-deadline-extension.md" in merged
    # The existence guard still holds: a registry pointed at a directory where
    # the golden files are absent merges nothing (pending captures never join).
    pending = fc.load_registry_sources(
        sources_dir=os.path.join(fc.REPO_ROOT, "does-not-exist"))
    assert pending == {}


# --------------------------------------------------------------------------
# Built-in runner
# --------------------------------------------------------------------------

def _run():
    tests = [(n, g) for n, g in sorted(globals().items())
             if n.startswith("test_") and callable(g)]
    passed = failed = 0
    print("=" * 78)
    print("STATUTE CAPTURE — TEST SUITE ({} tests)".format(len(tests)))
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
