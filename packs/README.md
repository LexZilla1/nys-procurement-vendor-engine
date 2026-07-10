# Jurisdiction packs

A **pack** is a self-contained bundle of everything specific to one
jurisdiction (a state, city, or authority). The engine machinery — extractor,
scorer, coverage, never-green gate, triage framework, freshness harness — is
jurisdiction-agnostic and reads *whichever pack it is handed*. Adding a new
jurisdiction means **authoring a pack**, never editing engine code.

## What's in a pack

Each pack is a directory under `packs/<id>/` with a `manifest.json` cover page:

```
packs/
  ny-state/
    manifest.json      # identity + a resources map (see below)
```

The manifest declares the jurisdiction's identity and, in its `resources`
block, where each resource lives (paths relative to the repo root):

| resource key          | what it points at                                  |
|-----------------------|----------------------------------------------------|
| `golden_copy_sources` | the verified verbatim rule/law text                |
| `entities`            | the issuer roster used by the jurisdiction gate    |
| `ad_types`            | the ad-type classification table                   |
| `citations`           | the citation-ID → description map                  |
| `freshness_registry`  | which sources to re-fetch for freshness monitoring |
| `forms`               | form definitions                                   |

Identity fields (`governing_law`, `citation_family`, `freshness_adapter`,
`mwbe_regime`, `entity_source`, `jurisdiction_class`) declare *what varies*
between jurisdictions so the engine can adapt without hardcoding.

## Loading a pack

```python
import jurisdiction
pack = jurisdiction.load_pack("ny-state")   # default id is "ny-state"
gc = validator.GoldenCopy(sources_dir=pack.golden_copy_sources)
```

`load_pack()` resolves every resource to an absolute path and validates that
the manifest declares all required fields and resource keys — a malformed or
partial pack fails loudly at load, never silently at first use.

## Adding a jurisdiction (the runbook)

1. `mkdir packs/<id>` and write `manifest.json` (copy `ny-state`'s as a template).
2. Drop in the jurisdiction's **verified** golden copy, entity roster, citation
   map, ad-type table, freshness registry, and forms.
3. If its freshness source is a new type, register a matching freshness adapter.
4. `load_pack("<id>")` — done. **No engine code changes.**

The software is never the bottleneck; the **verified rulebook** is. A pack is
only as trustworthy as the primary-source verification behind its golden copy.

## v1 note (ny-state)

The reference pack `ny-state` currently points its resources at NY's existing
on-disk locations (`golden-copy/sources`, `data/...`) rather than relocating
them under `packs/ny-state/`. This kept the seam a pure additive change with
zero behavior change. Physically consolidating NY's files under this directory
is optional future cleanup — the seam is what makes portability cheap; the file
layout is cosmetic.
