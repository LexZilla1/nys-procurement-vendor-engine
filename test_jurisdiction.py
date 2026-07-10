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

import pytest

import jurisdiction as J

HERE = os.path.dirname(os.path.abspath(__file__))


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
    pack_dir = tmp_path / "packs" / "demo"
    pack_dir.mkdir(parents=True)
    manifest = {
        "id": "demo", "display_name": "Demo", "jurisdiction_class": "CITY",
        "resources": {k: k for k in (
            "golden_copy_sources", "entities", "ad_types",
            "citations", "freshness_registry", "forms")},
    }
    (pack_dir / "manifest.json").write_text(json.dumps(manifest))
    pack = J.load_pack("demo", repo_root=str(tmp_path),
                       packs_dir=str(tmp_path / "packs"))
    assert pack.id == "demo"
    assert pack.jurisdiction_class == "CITY"
    assert pack.entities_path == os.path.join(str(tmp_path), "entities")


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
