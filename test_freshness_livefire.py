#!/usr/bin/env python3
"""Freshness live-fire wiring (PR B).

Covers the NEW material-change gate that decides whether the monthly Action opens
a HUMAN-REVIEWED state-update PR, plus the DIVERGENT -> not-citable path from a
live result through results_to_state() to the runtime gate. Offline / keyless.

Runnable two ways:
    python3 test_freshness_livefire.py
    pytest test_freshness_livefire.py
"""

import importlib.util
import os

from engine import freshness_state as fs

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "freshness_check", os.path.join(_HERE, "scripts", "freshness_check.py"))
fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fc)


def _state(note, sources):
    return {"note": note, "sources": sources}


def _not_citable(overlay):
    return {k for k, (v, _) in overlay.items() if v in fs.NOT_CITABLE_VERDICTS}


# --------------------------------------------------------------------------
# material_state_change: verdict-class change -> PR-worthy; text-only -> no-op
# --------------------------------------------------------------------------

def test_seed_replacement_is_material():
    seed = _state("SEED — all-OK placeholder, NOT a real freshness run.",
                  {"a.md": {"verdict": "FULL-MATCH"}})
    real = _state("Live freshness run", {"a.md": {"verdict": "FULL-MATCH"}})
    assert fc.material_state_change(seed, real) is True


def test_text_only_diff_same_verdicts_is_no_op():
    old = _state("Live", {"a.md": {"verdict": "FULL-MATCH",
                                   "checked_date": "2026-08-01", "detail": "x"}})
    new = _state("Live", {"a.md": {"verdict": "FULL-MATCH",
                                   "checked_date": "2026-09-01", "detail": "y"}})
    assert fc.material_state_change(old, new) is False


def test_verdict_class_change_is_material_both_directions():
    ok = _state("Live", {"a.md": {"verdict": "FULL-MATCH"}})
    bad = _state("Live", {"a.md": {"verdict": "DIVERGENT"}})
    assert fc.material_state_change(ok, bad) is True     # OK -> DIVERGENT
    assert fc.material_state_change(bad, ok) is True     # DIVERGENT -> cleared


def test_warn_class_transition_is_material():
    ok = _state("Live", {"a.md": {"verdict": "FULL-MATCH"}})
    warn = _state("Live", {"a.md": {"verdict": "FRAGMENT"}})
    assert fc.material_state_change(ok, warn) is True


def test_source_added_or_removed_is_material():
    one = _state("Live", {"a.md": {"verdict": "FULL-MATCH"}})
    two = _state("Live", {"a.md": {"verdict": "FULL-MATCH"},
                          "b.md": {"verdict": "FULL-MATCH"}})
    assert fc.material_state_change(one, two) is True    # added
    assert fc.material_state_change(two, one) is True    # removed


def test_missing_old_state_is_material():
    new = _state("Live", {"a.md": {"verdict": "FULL-MATCH"}})
    assert fc.material_state_change({}, new) is True     # first write ever


# --------------------------------------------------------------------------
# results_to_state -> runtime gate: DIVERGENT not-citable; FULL-MATCH citable
# --------------------------------------------------------------------------

def test_divergent_result_becomes_not_citable_end_to_end(tmp_path):
    results = [{"file": "source-x.md", "verdict": "DIVERGENT", "sunset_flags": []}]
    state = fc.results_to_state(results, "2026-08-01")
    assert state["sources"]["source-x.md"]["verdict"] == "DIVERGENT"
    p = tmp_path / "freshness-state.json"
    fs.write_state(str(p), state)
    overlay, rich, available = fs.load_state(str(p))
    assert available is True
    assert overlay["source-x.md"] == ("DIVERGENT", False)
    assert "source-x.md" in _not_citable(overlay)          # runtime gate blocks it


def test_full_match_result_round_trips_and_stays_citable(tmp_path):
    results = [{"file": "source-y.md", "verdict": "FULL-MATCH", "sunset_flags": []}]
    state = fc.results_to_state(results, "2026-08-01")
    p = tmp_path / "s.json"
    fs.write_state(str(p), state)
    overlay, rich, available = fs.load_state(str(p))
    assert overlay["source-y.md"][0] == "FULL-MATCH"
    assert "source-y.md" not in _not_citable(overlay)      # citable, not blocked


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
