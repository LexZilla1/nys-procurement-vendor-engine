"""Freshness state — the runtime tripwire that makes audit verdicts effective.

The monthly freshness audit (scripts/freshness_check.py) re-fetches the statute
sources from the NY Senate Open Legislation API and classifies each stored
golden-copy source. Historically those verdicts were report-only: a source could
be flagged DIVERGENT and the engine would still emit confident citations from it.

This module is the bridge. A checked-in JSON state file records, per source
filename, the latest audit verdict. `GoldenCopy` READS it at load (no network,
ever) and feeds it through the EXISTING citation-eligibility gate
(golden_status.derive_status -> is_citable), so:

  * DIVERGENT  -> not citable. The existing fail-soft in bid_readiness._build_rules
                 drops grounding to None, so affected rows fall to NEEDS_REVIEW.
                 This makes fail-closed HARDER, never easier (never-green).
  * FRAGMENT / EMPTY-STORED / UNREACHABLE -> still citable, but the deterministic
                 report shows a per-source freshness warning.
  * FULL-MATCH / absent -> citable, exactly today's behavior.

The primary verification remains the human-read verbatim STATE TEXT headers; this
is an added tripwire, not a replacement for it. Verdict strings are the audit's
own vocabulary (scripts/freshness_check.py classify()), not invented here.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
SOURCES_DIR = os.path.join(REPO_ROOT, "golden-copy", "sources")
DEFAULT_STATE_PATH = os.path.join(REPO_ROOT, "data", "config", "freshness-state.json")

# Verdict vocabulary — exactly scripts/freshness_check.py classify() plus
# UNREACHABLE (a source that could not be fetched during a run). Not invented.
FULL_MATCH = "FULL-MATCH"
FRAGMENT = "FRAGMENT"
DIVERGENT = "DIVERGENT"
EMPTY_STORED = "EMPTY-STORED"
UNREACHABLE = "UNREACHABLE"

# Only DIVERGENT drives not-citable (this is exactly the verdict string
# golden_status.derive_status already keys on). The suspect verdicts stay
# citable and surface a warning — the sunset/STALE_CHECK_REQUIRED axis is
# deliberately NOT used here, because it maps to NOT_CITABLE and would over-block.
NOT_CITABLE_VERDICTS = frozenset({DIVERGENT})
WARN_VERDICTS = frozenset({FRAGMENT, EMPTY_STORED, UNREACHABLE})


def load_state(path=None):
    """Read the freshness state file.

    Returns (overlay, rich, available):
      * overlay: {source_file: (verdict, sunset_stale=False)} — the shape
        GoldenCopy(freshness=...) expects; feeds derive_status. sunset_stale is
        always False here (only DIVERGENT blocks; see module docstring).
      * rich: {source_file: {"verdict","checked_date","detail"}} — for rendering.
      * available: False if the file is missing OR malformed. A missing/malformed
        file NEVER raises and NEVER blocks a citation — the caller treats it as
        "absent, with a warning". A present-but-empty file is available=True.
    """
    path = path or DEFAULT_STATE_PATH
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        sources = data.get("sources")
        if not isinstance(sources, dict):
            return {}, {}, False
        overlay, rich = {}, {}
        for fn, rec in sources.items():
            if not isinstance(rec, dict):
                continue
            verdict = rec.get("verdict")
            overlay[fn] = (verdict, False)
            rich[fn] = {
                "verdict": verdict,
                "checked_date": rec.get("checked_date"),
                "detail": rec.get("detail"),
            }
        return overlay, rich, True
    except Exception:
        # Missing file, bad JSON, unreadable — fail open on citation, warn on render.
        return {}, {}, False


def seed_all_ok(checked_date, sources_dir=None, note=None):
    """Build an all-OK (FULL-MATCH) seed state by enumerating the golden sources.
    Offline; used when a live audit run is not possible in this environment."""
    sources_dir = sources_dir or SOURCES_DIR
    files = sorted(n for n in os.listdir(sources_dir)
                   if n.startswith("source-") and n.endswith(".md"))
    return {
        "generated": checked_date,
        "note": note or ("SEED — all-OK placeholder, NOT a real freshness run. "
                         "Regenerate from a live audit via "
                         "scripts/freshness_check.py --write-state."),
        "sources": {fn: {"verdict": FULL_MATCH, "checked_date": checked_date,
                         "detail": "seed"} for fn in files},
    }


def write_state(path, state):
    """Persist a state dict as pretty JSON (audit --write-state / --seed-all-ok)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
