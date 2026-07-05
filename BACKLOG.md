# NYS Procurement Vendor Engine — Backlog & Open State

## Build state (as of this entry)
- Step 4.5 Clarification-Question Generator: BUILT (PR #9). Reader schema
  extended with optional question_submission object; pure-Python generator in
  clarification_questions.py; three deadline states (no window / passed /
  deadline_unverified) + force=True on-demand path; questions weave gap["gap"]
  verbatim, citation-tagged, factual-only enforced by denylist test.
  Status: OPEN, ready to merge (draft PR #9, head 4420a58; mergeable_state clean).

## Statute capture — sanctioned egress-blocked path (BUILT)
The **manual statute-capture GitHub Actions workflow** is the sanctioned way to
pull statutes when interactive Claude Code sessions are egress-blocked. Cloud
sessions cannot reach legislation.nysenate.gov and do not inherit
`NYSLEG_API_KEY`; Actions holds the key as a secret and can reach OpenLeg (same
proof as the monthly freshness automation).
- **Workflow:** `.github/workflows/statute-capture.yml` — `workflow_dispatch`
  only, input `law_ids` (default `GCN/24,GCN/25-A,EXC/314`). Least-privilege
  (`contents: write`, `pull-requests: write`). Never pushes to main: it branches
  and opens a **draft** PR via the existing peter-evans convention. Uploads the
  candidates + report as artifacts if PR creation fails.
- **Script:** `scripts/statute_capture.py` — reuses the freshness checker's
  verbatim-safe reflow/classify. NEW mode (GCN/24, GCN/25-a) writes a
  full-section candidate marked `Tier: PENDING HUMAN READ — not golden until
  human-verified`, all NB flags preserved verbatim. EXISTING mode (EXC/314) is
  diff-only: FULL-MATCH is report-only (golden never rewritten); DIVERGENT opens
  a review-flagged PR and never auto-reconciles. Fail-closed on missing key /
  API error / empty / truncated / parse failure / missing subdivision structure
  / missing-or-unreadable NB flags, with atomic all-or-nothing writes. The key
  is never logged, written, or placed in any endpoint/PR body/report.
- **Registry:** `data/config/statute_capture_registry.json` is the target
  whitelist; `freshness_check.py` merges any target whose golden file EXISTS into
  the monthly check (existence-guarded), so a capture becomes freshness-registered
  once merged.
- **Tests:** `test_statute_capture.py` (22) + `scripts/statute_capture.py
  --selftest`, fixtures-only (no live network).
- **NOT golden:** GCN/24 and GCN/25-a remain unverified until a human reviews the
  workflow-produced candidates against the primary source. See the PR 2 block and
  follow-up B above.

## Backlog — non-blocking
- [ ] Clarification questions: multi-shape templates. Current = one fixed
  question shape per gap (safe, correct for launch). Future = 2-3 shapes
  selected by gap TYPE (missing-criteria / contradiction / undefined-term).
  PREREQUISITE: gap-type taxonomy must be verified in gap_analysis.py /
  bid_readiness.py FIRST — shape-selection depends on how gaps are actually
  typed. Do not build shape-selection before confirming the taxonomy exists.
  Must preserve factual-only boundary + denylist test when added.

## Daily-habit backend — roadmap & gates
PR 1 (state primitives) is BUILT: engine/{citation,dated_objects,state_machine,
outcome_log}.py + data/schemas/ + test_daily_habit_backend.py. Never-green,
verify-first, golden-cited, no tier-3 data — all test-enforced.
- [x] **§314(5)(b)-(c) golden refresh — DONE.** source-exec-314-mwbe-cert-validity.md
  already carries the full section verbatim including subd. 5 (a)/(b)/(c) and all
  three NB flags ("** NB Effective until July 1, 2026" / "** NB Effective July 1,
  2026" / "* NB Repealed July 1, 2028"), captured openleg-api-v3 (activeDate
  2026-02-20) on 2026-07-03 and primary-source verified (INDEX §314 entry,
  2026-07-02/03). This PR adds: an **Operative version (as of 2026-07-01)**
  metadata note that subd. 5(a)-(c) is the current text; and an **L-grade**
  (legal-interpretive) annotation on the (5)(b)-(c) presumption (conditions —
  no ownership/capital change, no material change in nature/management, prior
  cert approved within 6 yrs 6 mos, 5 NYCRR 144 compliant — are attorney
  judgment, not product logic). Cert/presumption semantics are **no longer
  blocked by a stale §314 capture**, and the payment-clock PR (PR 2) may proceed
  without relying on unverified §314 assumptions. Presumption is rebuttable and
  is NEVER rendered as credential_status OK.
- [x] **B: re-pull EXC/314 for the audit trail — CLOSED 2026-07-05.** The
  sanctioned statute-capture workflow run (2026-07-05) re-pulled EXC/314 via the
  OpenLeg API from Actions (`existing`/diff-only target) and diffed it against the
  stored 2026-07-03 capture: result **FULL-MATCH** (subdivs 8/8, all three NB flags
  present — `** NB Effective until July 1, 2026`, `** NB Effective July 1, 2026`,
  `* NB Repealed July 1, 2028`). Golden body was **not** rewritten (report-only per
  convention); the audit verdict is recorded in `docs/statute-capture/2026-07-05.md`
  and VERIFICATION-REPORT row 38 context. This was impossible in interactive
  sessions (key unset + egress 403); the workflow was the fix. No further action.

## Attorney-review list (legal-interpretive — needs licensed-attorney judgment before product logic asserts it)
- [ ] **EXC §314(5)(b)-(c) recertification presumption (L-grade).** Product may
  surface ONLY as credential_status=RECERT_PRESUMPTION_PENDING + citation +
  "verify eligibility conditions"; never as a determination and never as OK. The
  presumption expires on final determination of the application (5)(c). Source:
  golden-copy/sources/source-exec-314-mwbe-cert-validity.md.
- [ ] **GCN §24 "public holiday" ↔ GFO XII.5.I "legal holidays" mapping (L-grade).**
  The payment clock treats the GCN §24 public-holiday list as the set of "legal
  holidays" GFO XII.5.I uses to pause/suspend the clock. Standard reading, but an
  interpretive mapping between differently-worded sources, not a mechanical
  identity — needs attorney sign-off before the clock asserts it. Practical risk
  is bounded by PR 2's fail-closed, source-backed, VERIFY-gated design. Also note
  the dynamic President/Governor-appointed holidays (an open class) must be
  handled, not omitted. Sources: golden-copy/sources/source-gcn-24-public-holidays.md,
  golden-copy/sources/source-xii-5-i-prompt-payment-interest.md.
- [ ] **PR 2 = payment clock.** HolidayCalendarProvider MUST be source-backed
  and fail closed — no embedded/hardcoded holiday lists; if the calendar source
  is unavailable, the clock refuses to compute rather than guessing. RM-5 §109
  semantic-concept check -> PREFLIGHT_FLAG (categorical, never a numeric score).
  Fills the Invoice shell (data/schemas/invoice.schema.json) with clock logic.
  **HOLIDAY SOURCE NOW UNBLOCKED (2026-07-05).** GCN/24 (public holidays) and
  GCN/25-a (deadline extension to the next succeeding business day; interest-
  computation rule) were captured via the sanctioned statute-capture workflow and
  **promoted to verified golden 2026-07-05** (owner read + two independent fetch
  cross-checks; INDEX 4.14/4.15; VERIFICATION-REPORT rows 46–47). The source-backed
  HolidayCalendarProvider now has its golden holiday + deadline sources. Remaining
  gate before the clock asserts the mapping: the **L-grade attorney item** above
  (GCN §24 "public holiday" ↔ GFO XII.5.I "legal holidays"). Design invariants
  unchanged: no hardcoded holiday lists; fail-closed if a source is unavailable.
- [ ] **PR 3 = morning-brief generator.** Locked section hierarchy +
  generated_at + data_quality counts (operational counts, not scores) +
  prompt_payment_note wording. Consumes the outcome_log records; no analytics
  scoring.
- [ ] WCB C-105.2 / DB-120.1 workers'-comp & disability coverage capture —
  BLOCKED on the .ny.gov allowlist (forms not yet fetchable this environment).
- [ ] Fit-and-friction categorical rubric (categorical only — never a score).
- [ ] Readiness-assessment funnel.
- [ ] Collaboration layer (multi-user on a tender/contract).
- [ ] Defects-prevented metric (operational count from outcome_log; not a score).

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
- [ ] NYSCR ToS / IP CONSTRAINT — GATE before any feature retains NYSCR content.
  Source (verified 2026-07-03): nyscr.ny.gov/policies.cfm — "All Content on any
  ESD Site is Proprietary... The Department expressly prohibits the copying of
  any protected materials on this site without written permission," granted
  case-by-case at ESD's sole discretion.
  - Cleared for build: (a) public list metadata — title, agency, ad type, dates
    — are facts, usable as Triage classification vocabulary; (b) vendor downloads
    own solicitation and uploads to engine for processing FOR THAT VENDOR
    (own-use, transient).
  - GATED pending attorney sign-off: any feature that RETAINS NYSCR solicitation
    body text server-side beyond the uploading vendor's session, feeds it into a
    shared corpus, or reuses it for lead-gen/other users. Mirrors the existing
    aggregator-content rule (SOURCE-DECLARATION FLAG above) — now applies to
    NYSCR-sourced content too.
  - Open legal question (not to be self-resolved): whether transient per-vendor
    processing-then-discard counts as prohibited "copying." Low-risk read =
    permitted own-use; confirm with counsel before productionizing retention.
  - 12 ad-type labels + list metadata: NOT protected (facts) — safe to use.

## Next build
- Step 1 Triage: classify NYSCR ad from metadata (open IFB / sole-source /
  award-notice / RFI); flag the ~8% non-biddable. Pure rules, smallest build.

## Step 1 Triage — follow-ups
- [ ] Consider adding `citations_to_ad_text` to the LLM fallback (Step 4) output
  for auditability. Requires a deliberate prompt revision + test update. Not
  urgent — the current contract is `{triage_class, confidence, reason}`.

## Step 6 form-fill — follow-ups
- [ ] Browser port (pdf-lib) with the UI: consume data/config/forms/*.json
  unchanged; same attestation-exclusion + unfilled-list semantics as
  pipeline/form_fill.py.
- [x] Confirm the two AC 3237-S radio value maps against the real PDF widgets
  (Entity Type /0-/9 — note 10 export states vs 11 visual labels; Taxpayer ID
  Type /0-/3). Populate value_map + set value_map_confirmed:true so the engine
  fills them instead of routing to unfilled. Commit the blank PDF to
  tests/fixtures/ and upgrade the completeness test to live-extract from it
  (currently asserts against the committed pikepdf field dump). — DONE: the
  canonical OSC PDF is committed at tests/fixtures/ac3237s.pdf; both radios are
  confirmed (value_map_confirmed:true) with export states bound to labels from
  widget /Rect reading order cross-checked against the golden-copy label
  sequence (Entity Type /0-/9, Taxpayer ID Type /0-/3 = EIN/SSN/ITIN/N-A);
  scripts/extract_acroform_fields.py regenerates the inventory from the PDF
  (pure-Python pdfrw, no native crypto); the completeness test now live-extracts
  from the committed PDF with the committed inventory as the offline fallback.
- [ ] VendRep forms AC 3290-S..3293-S mapping configs (same schema).
- [ ] Flatten-on-export decision (lock filled draft vs keep editable).

## Freshness automation — follow-ups
- [ ] Extend the monthly freshness Action to form fixtures: re-download each
  committed form PDF from its canonical OSC URL, diff the AcroForm field
  inventory against tests/fixtures/, open a freshness-drift PR on mismatch —
  same pattern as statute drift.

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

## Data connectors — verified BUILD-NOW set (API + reuse checked 2026-07-03)

Verification method note: dataset IDs + API existence confirmed via Socrata
catalog / official docs; live HTTP GETs and verbatim license text NOT yet run
(research env blocks outbound). Two license reads still gate a fully clean
build (flagged below). Grades: BUILD-NOW = API + procurement-useful + acceptable
reuse; REVIEW-LATER = useful but reuse/API unread; NOT-USEFUL = API exists, wrong
domain; DOC-WARNING = metadata open but actual RFP/bid docs not API-accessible.

SCOPE TRUTH (state before building): the BUILD-NOW set gives federal live
tenders+documents (SAM), federal award intel (USAspending), and NY/NYC HISTORY +
vendor + notice-metadata (Socrata x2, Checkbook) + statute monitoring (Open Leg).
It does NOT provide NY/NYC LIVE RFP DOCUMENTS — those exist only in NYSCR (locked,
no API, ESD-proprietary) and PASSPort Public (viewer/manual-export, no clean API).
State this gap in product scope; do not imply NY live-document coverage.

### BUILD-NOW connectors
- [ ] SAM.gov Opportunities — `https://api.sam.gov/opportunities/v2/search`
  (api_key, free SAM.gov account). FEDERAL ONLY. Live solicitations + actual
  documents via the `resourceLinks` field (public domain). The one confirmed
  API with real RFP-document access. Store metadata AND raw docs (PD).
- [ ] USAspending — `https://api.usaspending.gov/api/v2/search/spending_by_award/`
  (no key, CC0). Federal awards/spending only — no solicitations, no docs.
  Use for incumbent/competitor intelligence, not tender discovery.
- [ ] NYC Open Data (Socrata) — `https://data.cityofnewyork.us/resource/{4x4}.json`.
  Reuse VERIFIED OPEN: "Open Data belongs to all New Yorkers. There are no
  restrictions on the use of Open Data" (NYC Open Data FAQ; attribution of
  source/version/modifications + AS-IS per Admin Code §23-504). Core datasets:
  City Record Online `dg92-zbpx` (HIGH — live+historical citywide notices, all
  agencies; verify 37-col schema for a notice-URL/body field); Recent Contract
  Awards `qyyg-4tf5` (weekly recent-award signal); Bid Tabulations `9k82-ys7w`
  (historical pricing, FROZEN post-PASSPort); M/WBE-LBE-EBE Certified list
  `ci93-uc8s` (vendor directory). AVOID `3khw-qi8f` (Current Solicitations —
  private/deprecated). Documents live in PASSPort, not here.
- [ ] Open Data NY (Socrata) — `https://data.ny.gov/resource/{4x4}.json`;
  discovery `https://api.us.socrata.com/api/catalog/v1?domains=data.ny.gov&q=procurement`.
  Reuse = Open NY license — **READ / RESOLVED 2026-07-03**: public data.ny.gov
  datasets are usable for commercial/reuse through the official Open Data NY /
  Socrata channel, subject to conditions — license is revocable; State gives no
  warranty on accuracy/completeness; use at own risk; user indemnifies/holds the
  State harmless; downstream product pages must carry a data-accuracy disclaimer +
  source/date attribution. Procurement reports (historical
  transactions >=$5,000, 8 FY, ABO/PARIS; no live RFPs, no docs): State Auth
  `ehig-g5x3`, Local Auth `8w5p-k45m`, IDA `p3p6-xqr5`, LDC `d84c-dk28`, MTA
  procurement `gpsc-qqsz`. Forward-lead to inspect: "Eye On The Future — MTA
  Contract Solicitations" `e3e7-qwer`. Vendor enrichment: DOS Corporations
  `63wc-4exh` (+ `ekwr-p59j`, `2tms-hftb`), Certified DBEs `pfeu-dsx6`.
- [ ] NY Senate Open Legislation — `https://legislation.nysenate.gov/api/3/laws/EXC?key=`
  (free key). Statutory/compliance monitoring only — no tenders, no docs. This
  is the golden-copy FRESHNESS pipe (pull statute text/versions, e.g. the §314
  sunset watch, instead of manual capture). Data-payload license unverified
  (open-source posture is worded around code); statutory text not copyrightable.
- [ ] Checkbook NYC — `https://www.checkbooknyc.com/contract-api` (NYC Comptroller).
  XML over HTTP POST; up to 20,000 records/call; rate limit "1 concurrent
  session per IP and at a rate of 1 per second." Deep NYC contract/spend/vendor-
  payment history — no solicitations, no docs. CAVEAT: redistribution terms
  REVIEW PENDING. Build a batched ingestion/cache layer (not live per-request).

### REVIEW-LATER
- [ ] Open Book NY (osc.ny.gov) — no clean API (web viewer + manual spreadsheet
  export); historical state contracts/authority financials. Pull the same class
  of data through the data.ny.gov Socrata APIs instead. Reuse terms unverified.

### NOT-USEFUL (API exists, wrong domain — drop from procurement roadmap)
- [ ] MTA developer feeds (mta.info/developers) — GTFS/GTFS-RT transit data, not
  procurement. For MTA procurement use data.ny.gov `gpsc-qqsz` / `e3e7-qwer`.
- [ ] 511NY (511ny.org/developers) — traffic/transit ops; requires key + signed
  NYSDOT Developers Access Agreement; redistribution restricted. Not procurement.

### DOC-WARNING (metadata open, actual RFP/bid docs NOT API-accessible)
- [ ] NYSCR — holds NY-state live solicitations >=$50,000 + documents, but NO API
  and ESD-proprietary ("expressly prohibits the copying of any protected
  materials on the site without written permission... case-by-case at the sole
  discretion of the Department"). BD/licensing path only; never scrape.
- [ ] PASSPort Public (a0333-passportpublic.nyc.gov) — authoritative NYC live RFx
  + documents, viewable without account, but NO documented stable public API
  (browse + manual export). Drive discovery from CROL `dg92-zbpx`, deep-link into
  PASSPort for the document; ask MOCS about any sanctioned bulk feed before
  depending on an undocumented endpoint.

### Open reads to promote REVIEW -> BUILD (one live GET each)
- [x] Open NY license — RESOLVED 2026-07-03. Public data.ny.gov datasets are
  usable for commercial/reuse through the official Open Data NY / Socrata access
  path, subject to the license conditions: (1) no State warranty on accuracy or
  completeness; (2) use at own risk; (3) user indemnifies / holds the State
  harmless; (4) downstream product pages should include a data-accuracy
  disclaimer + source/date attribution. License is revocable.
- [ ] Read NYC Terms of Use + Admin Code §23-504 verbatim; read Checkbook NYC
  redistribution terms verbatim.
- [ ] Live-GET each 4x4 for HTTP 200 + schema (esp. CROL `dg92-zbpx` notice-URL/
  body column; SAM `resourceLinks`; data.ny.gov vendor/award-amount fields).

Remaining open questions (golden-copy/connectors legal):
1. Checkbook NYC redistribution terms.
2. Whether PASSPort has a sanctioned bulk feed / API from MOCS.
3. Whether NYSCR licensing / data access is possible through ESD.

### Document-storage rule (rights-driven)
- Store raw documents ONLY where a doc link AND reuse rights both hold -> SAM.gov
  (`resourceLinks`, public domain): retain + index.
- Metadata + deep-link ONLY, no server-side retention of document bodies ->
  NYSCR and PASSPort docs (proprietary/unverified; retention trips the NYSCR/
  aggregator ToS gates above). Per-vendor transient processing only.
- Metadata rows, retain freely -> all NYC/NYS Socrata datasets and Checkbook
  (open reuse; contain no documents anyway).

## Payment-clock features (RM-2 reframe, 2026-07-04)

- [ ] PROPER-INVOICE PRE-FLIGHT is the flagship payment feature. Already BUILT
  as RM-5 (proper-invoice required-field check, grounded in GFO XII.4.F +
  §109 vendor certificate). Promote it in product framing — this is the
  headline payment capability, not a secondary check.
- [ ] VOUCHER-REJECTION TRIAGE using the XII.7.B 66 denial codes (the golden
  copy already holds them). Map each denial code -> plain-language fix so a
  vendor whose voucher was denied knows exactly what to correct.
- [ ] 15-DAY SMALL BUSINESS CERTIFICATION CHECK at vendor onboarding (SFL
  §179-f). Vendor self-certifies in the SFS portal; criteria: NY-based,
  independently owned, <=200 employees, e-invoice required. Surface the check
  and the 15-day window at onboarding.
- [ ] MIR-DATE + QUARTER-RATE AUDIT of auto-paid prompt-payment interest — audit
  whether the interest the State auto-paid matches the correct quarter's rate
  from the MIR (Merchandise/Invoice Received) date. Uses nysinterestrates.csv.
- [ ] DELAY-COST QUANTIFICATION — information only; NO financing advice
  (FINRA-safe boundary per PHASE2 spec §1.5). Quantify the cost of a payment
  delay for the vendor's awareness; never recommend a financing product.
- NOTE: RM-2 recovery framing is DEPRECATED — vendor-side interest is auto-paid
  by SFS (GFO XIV.13.A); NFP Article 11-B interest averages ~$883/contract. The
  attorney gate on RM-2 output wording remains in force.
- [ ] STEP 6 FILL: all 5 forms verified AcroForm (212 / 193 / 217 / 176 / 21
  fields). Client-side fill; no TIN/DOB persistence. AC 3237-S is the first
  module (brief to follow separately).
