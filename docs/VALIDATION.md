# Validation methodology — the lean pass

A repeatable, expert-free confidence check: run a corpus of **real** NY State
solicitations through the engine end-to-end and assert the safety invariants
hold on every document. This is **not** a substitute for a human NY tender
expert — it is a regression net that catches invariant breaks and crashes.

Run it as a **read-only** session: report findings only; no commit / push / PR.
Keyless (no live Anthropic calls).

## Corpus sourcing rules

- **Public agency pages only.** Download each PDF directly from the issuing
  agency's own public website (see `docs/tender-sources.md` §A — the
  `DIRECT_PDF` sources). No logins, no gated portals.
- **NYSCR is discovery-only.** Use it (with a free human account) to find *what*
  exists; **never scrape it, never redistribute it, never fetch documents
  through it.** The engine only ever ingests a document obtained from the
  agency's own site.
- **Keep PDFs out of the repo.** Store downloads in a scratch dir outside the
  working tree; never commit tender PDFs. Record each document's source URL and
  download date.
- **Diversify.** Span multiple agencies and obligation profiles
  (construction / prevailing-wage, services, commodities, MWBE-heavy) so
  different rule paths are exercised. Note: the two `rfp25003*` test-tenders are
  the **same** procurement — count them as one document.

## Invariants (every document must hold — any breach is severity-1: stop)

1. **NEVER-GREEN** — no confident COMPLETE / PASS headline without verbatim
   golden-copy grounding.
2. **VERIFIED_MATCH gate** — no `VERIFIED_MATCH` without grounding **and** an
   obligation cue in the excerpt.
3. **GOLDEN GATE** — a `DIVERGENT_FROM_API` freshness verdict makes a source
   not citable.
4. **ZERO-EVIDENCE FAIL-CLOSED (vacuous-COMPLETE)** — a zero-requirement,
   empty, non-PDF, non-tender, or no-text-layer input must render the distinct
   `NO REQUIREMENTS EXTRACTED` state with `coverage_complete == False` and
   `analyzable == False`. Any `COVERAGE STATUS: COMPLETE` headline on such input
   is a failed fix. (Locked by unit tests in `test_bid_readiness.py`.)
5. **FRESHNESS** — the checked-in freshness seed loads; **no** "freshness state
   unavailable" warning appears (that warning means the state file was not read —
   a wiring regression, not a data condition).

> **Scope note on invariant 3.** `DIVERGENT → not-citable` is **not** exercised
> by a corpus run under the all-OK seed: the checked-in
> `data/config/freshness-state.json` seeds every source FULL-MATCH, so no source
> is DIVERGENT during a normal pass. That path is covered by **injected-state
> unit tests** (an explicit freshness overlay), not by a corpus run. Do not
> claim a corpus pass validated the DIVERGENT path — it cannot.

## Per-document record

For each document, capture:

- **exception y/n + traceback** — the pipeline (`extract → score_bid → render`)
  must not crash.
- **page count + approximate flag** — `pages_read`, `page_count_exact`,
  `page_numbers_approximate`.
- **requirements found vs scored rows** — `requirements_found` vs `len(rows)`.
- **coverage buckets** — `VERIFIED_MATCH` / `NEEDS_REVIEW` / `UNMAPPED` counts.
- **bond-routing spot-check** — bid-bond waiver / negation language
  ("no … bond … required") must land in the waiver review bucket, never as a
  scored row.
- **mojibake byte-scan** — scan excerpts for control / cp1252 bytes
  (0x80–0x9f, stray replacement chars). Log occurrences; this is the known
  Finding-2 mojibake, expected and non-blocking.
- **freshness note state** — `freshness_state_available == True`; note any
  per-source `withheld` / `warning` freshness notes.

## Fail-safe inputs (include in every run)

Exercise the four degenerate inputs and assert each fails closed:

- an **empty** file,
- **non-PDF bytes** renamed `.pdf`,
- a **non-tender PDF** (has a text layer, no obligations),
- a **synthesized no-text-layer PDF** (a page object with no text stream).

Each must: not crash; render **no** `COVERAGE STATUS: COMPLETE`; render
`NO REQUIREMENTS EXTRACTED`; `coverage_complete == False`;
`analyzable == False`. These are also locked by unit tests, so a corpus run is a
belt-and-suspenders check, not the only guard.

## Output

A table (one row per document) plus a short prose summary: which invariants held
everywhere, any severity-1 breach, and the mojibake tally. Because the session is
read-only, the deliverable is the report — nothing is committed.
