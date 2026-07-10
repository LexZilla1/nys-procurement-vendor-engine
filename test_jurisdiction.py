#!/usr/bin/env python3
"""Tests for jurisdiction.py — the jurisdiction-pack seam.

Runnable two ways:
    python3 test_jurisdiction.py
    pytest test_jurisdiction.py

Guards:
  * The default pack (ny-state) loads and every declared resource path exists.
  * The pack resolves golden-copy / entities / citations to the SAME locations
    the engine used before the seam existed (byte-identical default).
  * Unknown pack id and malformed manifests fail loudly (never silently).
  * The engine's real consumers (validator.GoldenCopy, step1_triage) actually
    read through the pack.
"""

import json
import os
import pathlib

import pytest

import jurisdiction as J
import validator as V

HERE = os.path.dirname(os.path.abspath(__file__))


def _write_valid_repo(root):
    """Create a minimal but REAL set of pack resources under `root`; return the
    resources dict (repo-root-relative paths) for a manifest. Used to build
    temp packs that actually resolve to existing files/dirs."""
    p = pathlib.Path(root)
    (p / "golden-copy" / "sources").mkdir(parents=True, exist_ok=True)
    (p / "golden-copy" / "sources" / "source-x.md").write_text(
        "## STATE TEXT (verbatim)\nbody\n", encoding="utf-8")
    (p / "data" / "entities").mkdir(parents=True, exist_ok=True)
    (p / "data" / "entities" / "entities.json").write_text('{"entities": []}', encoding="utf-8")
    (p / "data" / "nyscr_ad_types.json").write_text('{"labels": []}', encoding="utf-8")
    (p / "data" / "citations.json").write_text('{}', encoding="utf-8")
    (p / "data" / "config" / "forms").mkdir(parents=True, exist_ok=True)
    (p / "data" / "config" / "statute_capture_registry.json").write_text('{}', encoding="utf-8")
    return {
        "golden_copy_sources": "golden-copy/sources",
        "entities": "data/entities/entities.json",
        "ad_types": "data/nyscr_ad_types.json",
        "citations": "data/citations.json",
        "freshness_registry": "data/config/statute_capture_registry.json",
        "forms": "data/config/forms",
    }


def _valid_manifest(res):
    return {"id": "ny-state", "display_name": "NY",
            "jurisdiction_class": "STATE", "resources": res}


def _install_ny_state_pack(monkeypatch, root, manifest_text):
    """Write packs/ny-state/manifest.json under `root` (verbatim `manifest_text`)
    and point jurisdiction's module globals at it, so GoldenCopy() — which calls
    load_pack() with no args — loads THIS pack."""
    packs = pathlib.Path(root) / "packs" / "ny-state"
    packs.mkdir(parents=True, exist_ok=True)
    (packs / "manifest.json").write_text(manifest_text, encoding="utf-8")
    monkeypatch.setattr(J, "_HERE", str(root))
    monkeypatch.setattr(J, "PACKS_DIR", str(pathlib.Path(root) / "packs"))


# --------------------------------------------------------------------------
# Default pack loads and its resources exist
# --------------------------------------------------------------------------

def test_default_pack_is_ny_state():
    pack = J.load_pack()
    assert pack.id == "ny-state"
    assert pack.jurisdiction_class == "STATE"
    assert pack.governing_law == "State Finance Law Art. 11"
    assert pack.freshness_adapter == "open-legislation-api"
    assert pack.mwbe_regime == "article-15-a"


def test_all_declared_resources_exist_on_disk():
    pack = J.load_pack()
    assert os.path.isdir(pack.golden_copy_sources)
    assert os.path.isfile(pack.entities_path)
    assert os.path.isfile(pack.ad_types_path)
    assert os.path.isfile(pack.citations_path)
    assert os.path.isfile(pack.freshness_registry_path)
    assert os.path.isdir(pack.forms_dir)


def test_available_packs_includes_ny_state():
    assert "ny-state" in J.available_packs()


# --------------------------------------------------------------------------
# Byte-identical default: pack resolves to the historical hardcoded paths
# --------------------------------------------------------------------------

def test_golden_copy_path_matches_historical_default():
    pack = J.load_pack()
    assert pack.golden_copy_sources == os.path.join(HERE, "golden-copy", "sources")


def test_data_paths_match_historical_defaults():
    pack = J.load_pack()
    data = os.path.join(HERE, "data")
    assert pack.entities_path == os.path.join(data, "entities", "entities.json")
    assert pack.ad_types_path == os.path.join(data, "nyscr_ad_types.json")
    assert pack.citations_path == os.path.join(data, "citations.json")


# --------------------------------------------------------------------------
# The engine's real consumers read through the pack
# --------------------------------------------------------------------------

def test_validator_goldencopy_uses_pack_path():
    import validator as V
    gc = V.GoldenCopy()
    assert gc.sources_dir == J.load_pack().golden_copy_sources
    # and it actually loaded sources from there
    assert len(gc._body) > 0


def test_triage_loaded_entities_and_citations_from_pack():
    import step1_triage as TR
    pack = J.load_pack()
    with open(pack.entities_path, encoding="utf-8") as fh:
        entities = json.load(fh)
    with open(pack.citations_path, encoding="utf-8") as fh:
        citations = json.load(fh)
    assert TR._ENTITIES == entities
    assert TR._CITATIONS == citations


# --------------------------------------------------------------------------
# Failure modes are loud, never silent
# --------------------------------------------------------------------------

def test_unknown_pack_raises():
    with pytest.raises(J.UnknownJurisdiction):
        J.load_pack("atlantis")


def test_manifest_missing_required_field_raises():
    with pytest.raises(J.InvalidPack):
        J.Pack({"display_name": "X", "jurisdiction_class": "STATE",
                "resources": {}}, HERE)  # no id


def test_manifest_missing_resource_raises():
    manifest = {
        "id": "x", "display_name": "X", "jurisdiction_class": "STATE",
        "resources": {"golden_copy_sources": "gc"},  # missing the rest
    }
    with pytest.raises(J.InvalidPack):
        J.Pack(manifest, HERE)


def test_load_pack_reads_from_custom_packs_dir(tmp_path):
    res = _write_valid_repo(tmp_path)
    pack_dir = tmp_path / "packs" / "demo"
    pack_dir.mkdir(parents=True)
    manifest = {"id": "demo", "display_name": "Demo",
                "jurisdiction_class": "CITY", "resources": res}
    (pack_dir / "manifest.json").write_text(json.dumps(manifest))
    pack = J.load_pack("demo", repo_root=str(tmp_path),
                       packs_dir=str(tmp_path / "packs"))
    assert pack.id == "demo"
    assert pack.jurisdiction_class == "CITY"
    assert pack.entities_path == os.path.join(
        str(tmp_path), "data", "entities", "entities.json")


def test_load_pack_raises_on_nonexistent_resource_path(tmp_path):
    res = _write_valid_repo(tmp_path)
    res["citations"] = "data/NOPE.json"  # declared key, path does not exist
    pack_dir = tmp_path / "packs" / "demo"
    pack_dir.mkdir(parents=True)
    manifest = {"id": "demo", "display_name": "Demo",
                "jurisdiction_class": "CITY", "resources": res}
    (pack_dir / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(J.InvalidPack):
        J.load_pack("demo", repo_root=str(tmp_path),
                    packs_dir=str(tmp_path / "packs"))


# --------------------------------------------------------------------------
# GoldenCopy() fails closed on a bad/missing pack (the real consumer, not just
# jurisdiction.py in isolation). And the removed /mnt/project fallback must NOT
# fire on a pack-resolved path.
# --------------------------------------------------------------------------

def test_goldencopy_raises_on_missing_manifest(monkeypatch, tmp_path):
    _write_valid_repo(tmp_path)
    (tmp_path / "packs").mkdir(exist_ok=True)  # packs dir exists, no ny-state manifest
    monkeypatch.setattr(J, "_HERE", str(tmp_path))
    monkeypatch.setattr(J, "PACKS_DIR", str(tmp_path / "packs"))
    with pytest.raises(J.UnknownJurisdiction):
        V.GoldenCopy()


def test_goldencopy_raises_on_bad_json(monkeypatch, tmp_path):
    _write_valid_repo(tmp_path)
    _install_ny_state_pack(monkeypatch, tmp_path, "{ not valid json ")
    with pytest.raises(json.JSONDecodeError):
        V.GoldenCopy()


def test_goldencopy_raises_on_missing_required_key(monkeypatch, tmp_path):
    res = _write_valid_repo(tmp_path)
    del res["golden_copy_sources"]
    _install_ny_state_pack(monkeypatch, tmp_path, json.dumps(_valid_manifest(res)))
    with pytest.raises(J.InvalidPack):
        V.GoldenCopy()


def test_goldencopy_raises_on_nonexistent_golden_sources(monkeypatch, tmp_path):
    res = _write_valid_repo(tmp_path)
    res["golden_copy_sources"] = "golden-copy/DOES_NOT_EXIST"
    _install_ny_state_pack(monkeypatch, tmp_path, json.dumps(_valid_manifest(res)))
    with pytest.raises(J.InvalidPack):
        V.GoldenCopy()


def test_goldencopy_no_fallback_on_pack_resolved_path(monkeypatch, tmp_path):
    res = _write_valid_repo(tmp_path)
    _install_ny_state_pack(monkeypatch, tmp_path, json.dumps(_valid_manifest(res)))
    gc = V.GoldenCopy()
    # Uses exactly the pack-resolved path; never substituted to /mnt/project.
    assert gc.sources_dir == os.path.join(str(tmp_path), "golden-copy", "sources")
    assert "/mnt/project" not in gc.sources_dir
    assert len(gc._body) == 1  # loaded from the pack path, not a fallback


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
