#!/usr/bin/env python3
"""Jurisdiction packs — the seam that makes the engine portable across
jurisdictions (states, cities, authorities) without touching engine code.

A *pack* is a self-contained bundle of everything jurisdiction-specific:
verified golden-copy rules, the entity roster, the citation map, the freshness
source registry, and form definitions. The engine machinery (extractor,
scorer, coverage, never-green gate, triage framework, freshness harness) is
jurisdiction-agnostic and reads WHICHEVER pack it is handed.

`packs/<id>/manifest.json` is the pack's cover page: it declares the
jurisdiction's identity (governing law, MWBE regime, freshness adapter, ...)
and, in its `resources` block, WHERE each resource lives (paths relative to the
repo root). Adding a jurisdiction = author a new pack directory + manifest;
NEVER edit engine code.

v1 note (deliberate, byte-identical): the reference pack `ny-state` points its
resources at NY's EXISTING on-disk locations rather than relocating them. That
keeps this change a pure additive seam with zero behavior change. Physically
consolidating NY's files under `packs/ny-state/` is optional future cleanup —
the seam is what makes portability cheap; the file layout is cosmetic.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))  # repo root (this file lives there)
PACKS_DIR = os.path.join(_HERE, "packs")
DEFAULT_PACK = "ny-state"

# Resource keys every pack manifest must declare. Kept explicit so a malformed
# or partial pack fails loudly at load time rather than at first use.
_REQUIRED_RESOURCES = (
    "golden_copy_sources",
    "entities",
    "ad_types",
    "citations",
    "freshness_registry",
    "forms",
)
_REQUIRED_FIELDS = ("id", "display_name", "jurisdiction_class")


class UnknownJurisdiction(ValueError):
    """Raised when a pack id has no manifest under packs/."""


class InvalidPack(ValueError):
    """Raised when a manifest is missing a required field or resource key."""


class Pack:
    """Resolved view of one jurisdiction's manifest. Resource attributes are
    ABSOLUTE paths (repo_root + the manifest's relative path)."""

    def __init__(self, manifest, repo_root):
        missing = [f for f in _REQUIRED_FIELDS if f not in manifest]
        if missing:
            raise InvalidPack("manifest missing field(s): %s" % ", ".join(missing))
        res = manifest.get("resources") or {}
        missing_res = [k for k in _REQUIRED_RESOURCES if k not in res]
        if missing_res:
            raise InvalidPack("manifest 'resources' missing: %s" % ", ".join(missing_res))

        self.manifest = manifest
        self.repo_root = repo_root

        # identity / capability metadata
        self.id = manifest["id"]
        self.display_name = manifest["display_name"]
        self.jurisdiction_class = manifest["jurisdiction_class"]
        self.governing_law = manifest.get("governing_law")
        self.citation_family = manifest.get("citation_family")
        self.freshness_adapter = manifest.get("freshness_adapter")
        self.mwbe_regime = manifest.get("mwbe_regime")
        self.entity_source = manifest.get("entity_source")

        # resolved resource locations (absolute)
        self._res = {k: os.path.join(repo_root, v) for k, v in res.items()}

    def resource(self, key):
        """Absolute path for a declared resource key (raises KeyError if absent)."""
        return self._res[key]

    # Convenience accessors for the well-known resources.
    @property
    def golden_copy_sources(self):
        return self._res["golden_copy_sources"]

    @property
    def entities_path(self):
        return self._res["entities"]

    @property
    def ad_types_path(self):
        return self._res["ad_types"]

    @property
    def citations_path(self):
        return self._res["citations"]

    @property
    def freshness_registry_path(self):
        return self._res["freshness_registry"]

    @property
    def forms_dir(self):
        return self._res["forms"]

    def __repr__(self):
        return "Pack(id=%r, class=%r)" % (self.id, self.jurisdiction_class)


def available_packs(packs_dir=None):
    """Sorted list of pack ids that have a manifest.json under packs/."""
    base = packs_dir or PACKS_DIR
    if not os.path.isdir(base):
        return []
    ids = []
    for name in os.listdir(base):
        if os.path.isfile(os.path.join(base, name, "manifest.json")):
            ids.append(name)
    return sorted(ids)


def load_pack(pack_id=DEFAULT_PACK, repo_root=None, packs_dir=None):
    """Load and resolve a jurisdiction pack by id.

    repo_root defaults to this file's directory (the repo root), so resource
    paths in the manifest resolve exactly like the engine's historical
    hardcoded paths — keeping the default pack byte-identical.
    """
    base = packs_dir or PACKS_DIR
    root = repo_root or _HERE
    manifest_path = os.path.join(base, pack_id, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise UnknownJurisdiction(
            "no pack %r (available: %s)" % (pack_id, ", ".join(available_packs(base)) or "none")
        )
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    return Pack(manifest, root)
