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

## Architecture — pre-Triage gates (design, not yet built)
- [ ] SOURCE-DECLARATION FLAG at upload: user declares whether the uploaded
  tender is (a) an underlying public solicitation (agency/NYSCR record) or
  (b) proprietary enrichment from a paid aggregator (GovWin/BidNet/GovSpend).
  Wire to retention: (a) process + may retain; (b) process for uploading
  vendor ONLY, no retention, never fed into internal lead-gen store.
  Rationale: the agency's actual RFQ/solicitation is a public record
  regardless of how the vendor found it; the aggregator's analyst summaries/
  enrichment are licensed content.
- [ ] JURISDICTION GATE (separate from source flag): is this NY state / NY
  municipal-authority / non-NY? Full engine applies only to NY state-level.
  Municipal/authority = flag "verify which rules apply" (golden copy may be
  partial). Non-NY = "out of scope, NY-only" rather than asserting NY rules.
  Source flag and jurisdiction gate are INDEPENDENT checks; neither substitutes
  for the other

## Next build
- Step 1 Triage: classify NYSCR ad from metadata (open IFB / sole-source /
  award-notice / RFI); flag the ~8% non-biddable. Pure rules, smallest build.

## Open verification items (golden copy)
- [x] MWBE Exec Law §314(5)(a) sunset date 2028-07-01 — DONE 2026-07-03.
  Primary-verified against NY Exec Law §314, nysenate.gov/legislation/laws/EXC/314:
  the section page carries the statutory note "* NB Repealed July 1, 2028" directly.
  Repeal applies to all of Article 15-A (§§310–318); §314's five-year validity
  terminates with it. The NB markers ("** NB Effective July 1, 2026", "* NB
  Repealed July 1, 2028") are now captured verbatim in the STATE TEXT block of
  source-exec-314-mwbe-cert-validity.md (they had been dropped from the original
  capture). File metadata updated: sunset_date_verified: 2026-07-03.

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

## Website / delivery layer — design decisions (not yet built)

- [ ] CURATED PRIMARY-SOURCE DIRECTORY: website hosts a maintained index of
  links to primary NY procurement sources (osc.ny.gov, ogs.ny.gov,
  esd.ny.gov, nyscr.ny.gov), each tagged by topic (e.g. "discretionary
  thresholds," "restricted period list," "MWBE certification," "Contractor
  Financing Program"). Solves staleness: we maintain the INDEX, not
  paraphrased content — the live source stays current on its own.

- [ ] BOUNDED QUESTION HAND-OFF (not an open chat box): from a directory
  entry, user can send a SPECIFIC, PRE-SCOPED question tied to that named
  primary source into Claude (e.g. "Ask about: NY discretionary purchase
  thresholds" -> scoped prompt against a named source). Explicitly NOT a
  general "ask me anything about NY procurement" interface.
  RATIONALE: open-ended Q&A risks UPL/scope drift (e.g. "should I structure
  my business as an MWBE," "how do I dispute a non-responsibility finding").
  Link-scoped questions keep answers bounded to a named, verifiable source.

- [ ] SPECIALIZED CLAUDE CONFIGURATION (delivery layer, not a new product):
  the bounded hand-off is served by a Claude instance/skill set scoped to
  our verified golden copy — answers ONLY from cited golden-copy entries,
  refuses/redirects questions outside that scope. This is the retrieval +
  reasoning layer over the existing golden copy (46 verified sources) and
  verification methodology (Tier 1/2, attorney-gated) — NOT a standalone
  "NYS Tenders Copilot" product. Rejected as a separate initiative because:
  (a) duplicates the golden copy instead of exposing it, (b) competes on
  the crowded generic-Q&A layer (see GovWin's "Ask Dela"), (c) open-ended
  scope increases UPL risk vs. per-tender bounded checks.

## Golden-copy-adjacent — referral content (informational only, not advice)

- [ ] NY CONTRACTOR FINANCING PROGRAM (verified, source: esd.ny.gov):
  $37M SSBCI-funded loan-loss-reserve program; participating CDFIs/community
  lenders extend lines of credit (up to $500k) to NY government contractors
  (revenue <=$5M, <100 employees) to bridge payment-timing gaps. EXCLUDES
  nonprofits. Named lenders: BOC Capital, Carver Federal Savings, Cooperative
  Federal, Greater Jamaica Development Corp, Lendistry, Ponce Bank, Pursuit,
  TruFund. Free SSBCI Technical Assistance (legal/accounting/financial
  advisory) also available.
  USE: surface as informational context at Step 8 (post-award/payment) when
  a payment-delay or prompt-pay-interest situation is flagged. Link only,
  no lending recommendation (keeps clear of FINRA/advisory exposure).
  VERIFY BEFORE USE: confirm current program status (funding remaining,
  active enrollment) at esd.ny.gov before citing as active.
  GTM NOTE: named lenders + TA providers already reach this exact ICP —
  potential co-marketing/referral partners, separate from core product build.
