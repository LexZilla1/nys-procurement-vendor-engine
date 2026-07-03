# LexZilla / NYS Procurement Vendor Engine — Backlog & Open State

## Build state (as of this entry)
- Step 4.5 Clarification-Question Generator: BUILT (PR #9). Reader schema
  extended with optional question_submission object; pure-Python generator in
  clarification_questions.py; three deadline states (no window / passed /
  deadline_unverified) + force=True on-demand path; questions weave gap["gap"]
  verbatim, citation-tagged, factual-only enforced by denylist test.
  Status: OPEN, ready to merge (draft PR #9, head 4420a58; mergeable_state clean).

## Backlog — non-blocking
- [ ] Clarification questions: multi-shape templates. Current = one fixed
  question shape per gap (safe, correct for launch). Future = 2-3 shapes
  selected by gap TYPE (missing-criteria / contradiction / undefined-term).
  PREREQUISITE: gap-type taxonomy must be verified in gap_analysis.py /
  bid_readiness.py FIRST — shape-selection depends on how gaps are actually
  typed. Do not build shape-selection before confirming the taxonomy exists.
  Must preserve factual-only boundary + denylist test when added.

## Next build
- Step 1 Triage: classify NYSCR ad from metadata (open IFB / sole-source /
  award-notice / RFI); flag the ~8% non-biddable. Pure rules, smallest build.

## Open verification items (golden copy)
- [ ] MWBE Exec Law §314(5)(a) sunset date 2028-07-01 — verify against PRIMARY
  source: Part KK, FY2025-26 enacted budget. Currently unconfirmed.

## Golden copy — verified entries (source: OGS/ESD "Doing Business With New York State" guide, primary source)

- [x] PURCHASING PRIORITY ORDER (verified): agencies must purchase in order:
  (1) Preferred Sources (Corcraft, NYS Preferred Source for the Blind, NYS
  Industries for the Disabled) — statutorily exempt from competitive bid;
  (2) OGS Centralized Contracts; (3) agency/multi-agency established
  contracts; (4) agency's own procurement (competitive or discretionary).
  TRIAGE IMPLICATION: add a "structurally non-competable" state — if a
  vendor's commodity/service category is covered by a Preferred Source,
  flag before any bid-fit analysis, since Preferred Source displaces open
  competition entirely.

- [x] DISCRETIONARY PURCHASE THRESHOLDS (verified): general $50,000; NY-grown
  food (incl. milk/milk products) $200,000; purchases from NYS-certified
  MWBE / Small Business / SDVOB, or recycled/remanufactured commodities/
  technology, $500,000. Below threshold, agency may skip formal competitive
  bid (still must document price reasonableness + vendor responsibility).
  ELIGIBILITY IMPLICATION: a vendor's own certification status can change
  whether a given-size purchase is competitively bid at all.

- [x] RESTRICTED PERIOD LIST (verified, OGS-specific): public list of OGS
  solicitations currently in restricted period:
  ogs.ny.gov/procurement/restricted-period-lists. Usable as a live
  cross-check for §139-j restricted-period status on OGS procurements.

- [x] JURISDICTION / GOVERNING LAW SPLIT (verified — CONFIRMS prior
  assumption, resolves it from "unverified" to "confirmed"): different NY
  procuring-entity types operate under DIFFERENT statutes:
    - State agencies -> State Finance Law (this is what our golden copy is
      built on)
    - Municipalities (counties, cities, towns) -> General Municipal Law
    - Authorities -> Public Authority Law
    - School districts -> General Municipal Law + State Education Law
  GOLDEN COPY SCOPE: confirmed accurate for STATE AGENCY procurements only.
  NOT directly applicable to municipal/authority/school district
  procurements without separate statute verification. The jurisdiction gate
  (already logged) must route non-state-agency uploads to a
  "verify applicable statute" flag rather than applying State Finance Law
  rules.

Source citation for all four: OGS/Empire State Development, "Doing Business
With New York State: A Guide to Understanding the State's Procurement
Practices" (joint OGS/ESD publication).

## Internal-feature backlog (not vendor-facing)
- [ ] Competitor/incumbent lookup on every tender processed → internal
  client-acquisition pipeline (not shown to vendors). Public data only
  (OpenBook NY / NYSCR / data.ny.gov). PREREQUISITE: verify programmatic
  access terms — data.ny.gov Socrata API (clean) vs OpenBook UI (terms
  unverified). No credentials/scraping/auto-send.
