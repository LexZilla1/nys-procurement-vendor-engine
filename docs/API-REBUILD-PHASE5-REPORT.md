# Golden-Copy Full-Text Rebuild — Phase 5 Report (2026-07-03)

Applied the user-supplied authoritative Open Legislation API texts
(fetched 2026-07-03) to the 22 statute-class sources. Source of live text:
uploaded `openlegfulltext20260703.zip` (22 files + MANIFEST). The API was
NOT reached from this environment; no scraping. Validation gate PASSED
(LAB/220-I returned the full 10-subdivision section, activeDate 2025-01-03,
vs the stored subd-6-only fragment).

## Verdicts + actions (22 statute-class)

| source_id | class | verdict | API activeDate | action taken |
|---|---|---|---|---|
| exc-314 | STATUTE | DIVERGENT (dual-version) | 2026-02-20 | REBUILT full section; both subd-5 versions kept; operative-version annotation |
| lab-220-i | STATUTE | FRAGMENT | 2025-01-03 | REBUILT full section; WARN link relinked to nysenate.gov |
| stf-109 | STATUTE | DIVERGENT (mixed capture) | 2014-09-22 | REBUILT statute layer A to full §109; guidance (B) + form (C) layers preserved |
| stf-112 | STATUTE | FULL-MATCH | 2023-03-10 | Covers + API activeDate added; text untouched |
| stf-139-d | STATUTE | FRAGMENT | 2014-09-22 | REBUILT full section |
| stf-139-h | STATUTE | FRAGMENT | 2014-09-22 | REBUILT full section; WARN link relinked to nysenate.gov |
| stf-139-j | STATUTE | FULL-MATCH | 2026-05-29 | Covers + API activeDate added; text untouched |
| stf-139-k | STATUTE | FULL-MATCH | 2026-05-29 | Covers + API activeDate added; text untouched |
| stf-139-l | STATUTE | FRAGMENT | 2019-01-18 | REBUILT full section |
| stf-139-m | STATUTE | FRAGMENT | 2025-11-07 | REBUILT full section |
| stf-163 | STATUTE | FULL-MATCH | 2026-06-19 | Covers + API activeDate added; text untouched |
| stf-179-d | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-e | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-f | STATUTE | FULL-MATCH | 2017-04-14 | Covers + API activeDate added; text untouched |
| stf-179-g | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-p | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-q | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-s | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-t | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-u | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| stf-179-v | STATUTE | FULL-MATCH | 2014-09-22 | Covers + API activeDate added; text untouched |
| wkc-57 | STATUTE | FRAGMENT | 2014-09-22 | REBUILT full section |

**Tally:** 14 FULL-MATCH (text untouched, metadata added) · 6 FRAGMENT (rebuilt to full section) · 2 DIVERGENT special-cases (exc-314 dual-version, stf-109 mixed).

## Sunset cross-check (API repealed/repealedDate vs our records — flagged, not reconciled)

| statute | API `repealed` | NB-Repealed in live text | our sunset record | status |
|---|---|---|---|---|
| EXC/314 | None (not yet repealed) | July 1, 2028 | 2028-07-01 | ✅ text matches record; API boolean correctly not-yet-repealed |
| STF/139-J | None | July 31, 2028 | 2028-07-31 | ✅ match |
| STF/139-K | None | July 31, 2028 | 2028-07-31 | ✅ match |
| STF/163 | None | June 30, 2031 | 2031-06-30 | ✅ match |

The API `repealed` boolean is None/false for all four because the repeals
are FUTURE-DATED scheduled repeals; the dates live in the section's `* NB
Repealed ...` text annotation (now captured verbatim in every full-text
rebuild) and match our records exactly. No mismatch; nothing reconciled.

## Non-statute sources (23) — NOT in the Open Legislation API; stay on the manual capture standard

- mwbe-5nycrr-pass-fail (5 NYCRR regulation)
- appendix-a-june2023 (OGS boilerplate)
- ac3237s-substitute-w9 (OSC form)
- vendrep-ac3290s / ac3291s / ac3292s / ac3293s (OSC forms)
- vendrep-forms (OSC forms index)
- sdvob (OSC program page)
- invoice-checklist (OSC attachment)
- x-3-vendor-registration (GFO)
- xi-2-f / xi-4-a / xi-4-b / xi-16 / xi-18-a (GFO chapters)
- xii-4-b-1 / xii-4-f / xii-5-b / xii-5-i / xii-6-c / xii-7-b / xii-8-b (GFO chapters)

Each received a one-line `Covers:` metadata label (required by the Phase-4
parser change) describing its capture; **their captured text was not altered.**

## Phase 4 — parser enforcement (parse_golden_copy.py)

- `Covers` is now a REQUIRED header field (all 45 files carry it).
- Records declaring `Covers: full section` must have STATE TEXT beginning at
  the section heading `§` (leading annotation markers like `* §` allowed) —
  a structural sanity check. Non-statute files use other `Covers` values and
  are exempt from the § check.

## Phase 5 — verification

- Parser + reconciliation: **PASS 45/45/45** (with the new required field + § check).
- Test suites: **147 passed, 0 failed** — validator 39, bid_readiness 43,
  clarification 24, gap_analysis 19, cert_renewal 11, tender_extractor 11
  (llm_reader regression env-skipped: no `anthropic` package offline).
- freshness_checker `--selftest`: ALL PASS; sunset watch OK=4 / APPROACHING=0 / LAPSED=0.
- Citation integrity preserved: every pipeline `cite()` quote remains a
  verbatim substring of its (now fuller) STATE TEXT body — enforced by the
  passing validator/gap_analysis/cert_renewal/bid_readiness suites.

## Note on capture formatting

The API delivers hard-wrapped plain text; each section was reflowed to the
golden-copy one-line-per-subdivision style (words untouched) so that the
`cite()` raw-substring choke-point keeps matching. NB/repeal annotation
lines are preserved as their own lines, first word to last annotation.
