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
