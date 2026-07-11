#!/usr/bin/env python3
"""Tests for freshness_checker.find_golden_copy_root — the freshness live-fire
GATE (PR A). The drift checker must resolve the golden copy that sits next to
its own code and NEVER fall back to a foreign path (e.g. /mnt/project), or it
could write freshness verdicts about a different golden copy than the engine
cites from.

Runnable two ways:
    python3 test_freshness_checker.py
    pytest test_freshness_checker.py
"""

import os

import pytest

import freshness_checker as FC

_ADJACENT = os.path.join(
    os.path.dirname(os.path.abspath(FC.__file__)), "golden-copy", "sources")


def test_resolves_adjacent_golden_copy_in_real_repo():
    root = FC.find_golden_copy_root()
    base = os.path.dirname(os.path.abspath(FC.__file__))
    assert root == os.path.join(base, "golden-copy")
    assert "/mnt/project" not in (root or "")


def test_uses_only_the_adjacent_directory(monkeypatch):
    # isdir True ONLY for the adjacent sources dir → returned.
    monkeypatch.setattr(FC.os.path, "isdir", lambda p: p == _ADJACENT)
    base = os.path.dirname(os.path.abspath(FC.__file__))
    assert FC.find_golden_copy_root() == os.path.join(base, "golden-copy")


def test_fails_closed_no_mnt_project_fallback(monkeypatch):
    # Simulate an environment where ONLY /mnt/project/golden-copy/sources exists
    # and the adjacent copy does NOT. The removed fallback must not be consulted:
    # find_golden_copy_root must fail closed (None), never return the foreign path.
    monkeypatch.setattr(FC.os.path, "isdir",
                        lambda p: p == "/mnt/project/golden-copy/sources")
    assert FC.find_golden_copy_root() is None


def test_fails_closed_when_nothing_present(monkeypatch):
    monkeypatch.setattr(FC.os.path, "isdir", lambda p: False)
    assert FC.find_golden_copy_root() is None


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
