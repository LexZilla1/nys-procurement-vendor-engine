# BUILD SPEC v2 — NYS Bid-Readiness Checker (testable across all vendor types)

**Status:** Build brief for Claude Code (Opus 4.8). Strategy settled in RESEARCH-LEDGER §13.
**Date:** 2026-06-30 (v2 — reframed from a cert-only tracker to an upload-a-real-tender
bid-readiness checker that works for ANY NYS vendor; certification tracking becomes a module
that lights up only for certified firms. Reason: founder wants something testable with a
VARIETY of vendors, certified and not. A cert-only tool can't be tested on non-certified vendors.)

**One-line:** A NYS vendor uploads a real tender (RFP/IFB/bid package). The tool reads it, lists
what it requires, flags what the vendor is missing, and scores whether they're ready to bid — and
if the vendor is certified, also shows their MWBE/SDVOB renewal status. Works for every NYS vendor.

---

## 0. THE GOAL OF THIS BUILD (read first)

This is a TEST artifact, built to put in front of a variety of real NYS vendors (certified MWBE,
certified SDVOB, and non-certified small businesses) to learn which part they react to most — and,
ultimately, whether they'd pay. It is the thing that answers the one open question in the ledger
(willingness to pay), which no further research can answer. Build it to be SHOWN.

**The wow effect is the point — but engineered honestly.** The wow is NOT "the AI is magically
perfect at reading any PDF" (it can't honestly promise that). The wow is: "it did the tedious
paperwork review I dread, in 30 seconds, and caught a gap that would have disqualified me." Wow
through VISIBLE THOROUGHNESS, not false perfection. A demo that misfires silently is worse than no
demo — so the tool shows its work and tells the truth about its confidence.

---

## 1. WHO IT'S FOR (and why it's not cert-only)

- **The core flow works for ALL NYS vendors.** Tender requirements — deadlines, mandatory forms,
  VendRep (required >$100k), insurance, bid bonds, MWBE/SDVOB utilization asks, disqualification
  triggers — apply to every bidder, certified or not. This is the universal value.
- **Certification tracking is ONE module** that appears only for certified MWBE/SDVOB firms (they
  have a certificate to renew; non-certified firms don't). It's the reliability anchor (see §4),
  not the whole product.
- Why certified firms still matter as the first audience: their pain is the only one we could
  QUANTIFY (SDVOB 19.6% recert-lapse, RESEARCH-LEDGER §13), and they're a findable, listable group
  (~9,745 MWBE + ~1,401 SDVOB). But the product is NOT limited to them — it's the entry wedge into
  a tool that serves everyone.

---

## 2. THE TWO-PART EXPERIENCE

### Part A — Tender Bid-Readiness Check (THE CENTERPIECE — works for everyone)
The vendor uploads a real NYS tender (PDF — likely 30-80+ pages with attachments). The tool:
1. **Reads the document** and extracts requirements:
   - Submission deadline + method
   - Mandatory forms (VendRep questionnaire, EEO, MWBE/SDVOB utilization plan, etc.)
   - Insurance / bonding requirements
   - Vendor responsibility threshold (>$100k triggers VendRep)
   - Required attachments, certifications, signatures
   - Disqualification / non-responsiveness triggers
   - Post-award reporting obligations
2. **Compares against the vendor's quick profile** (a short intake, NOT a full passport — see §5).
3. **Produces the readiness output** (the "aha" screen):
   - Bid-readiness score /100, with every point explained
   - GREEN / YELLOW / RED per requirement
   - The specific gaps that would make the bid non-responsive
   - A plain-English action list: "Do these 3 things before you submit"

### Part B — Certification Renewal Panel (lights up ONLY for certified firms)
If the vendor says they're MWBE/SDVOB certified, an extra panel shows:
- Certification type + expiration date
- Renewal window status (MWBE: opens 90 days before expiry — CONFIRMED, ESD)
- Days until expiration / lapse risk
- Grounded warning: "NYS reports 19.6% of SDVOBs lapse by failing to recertify on time."
This panel is the RELIABILITY ANCHOR — it's grounded in statute and works perfectly every time
(see §4), so even if the tender-reading (Part A) is imperfect on a given document, the vendor still
sees something undeniably sharp and accurate.

---

## 3. GROUNDING — what's confirmed vs not (fact-checked against PRIMARY sources 2026-06-30)

Every rule/date/consequence shown to the user carries one of three states:
1. **CONFIRMED** — primary source, cited verbatim.
2. **NOT CONFIRMED / CLAIM** — flagged "verify with certifying body."
3. **USER-PROVIDED** — vendor entered it (e.g., their own cert expiration date).

Confirmed facts (safe to state with citation):
- **MWBE certifications valid 5 years.** PRIMARY: NY Executive Law § 314(5) — "all minority and
  women-owned business enterprise certifications shall be valid for a period of five years."
  (nysenate.gov/legislation/laws/EXC/314; Justia 2025 codification.) NOTE: earlier secondary blogs
  said "2 years" — they were WRONG (confused NYS with NYC). Statute is unambiguous: FIVE years.
- **MWBE recertification window opens 90 days before expiry.** PRIMARY: ESD (esd.ny.gov/mwbe-new-certification).
- **MWBE rebuttable presumption** if no ownership/management change since prior cert (§ 314).
- **SDVOB lapse stats: 398 (19.6%) lapsed; 62 of 188 eligible lapsed in 2025; 1,401 certified.**
  PRIMARY: OGS 2025 SDVOB Annual Report.
- **VendRep required on contracts >$100k.** In golden copy (existing).

Still to verify before relying:
- **SDVOB cycle length** (ChatGPT says OGS report states "5 years" — NOT independently confirmed).
  Until confirmed: SDVOB expiration is USER-PROVIDED (vendor enters their date). MWBE can auto-compute
  (issue date + 5 years) and cite § 314.
- **Tender-extraction accuracy** is inherently per-document; never claim 100%. Always end Part A with
  "Verify these against the original tender — I flag what I found, you confirm."

---

## 4. THE RELIABILITY-ANCHOR DESIGN (how we protect the wow)

Real-PDF extraction (Part A) will sometimes miss or misread on an unseen document. To make sure the
first impression still lands:
- **Part B (cert renewal) is statute-grounded and exact** — for a certified vendor it's always right.
- **Part A shows its work**: "I read 52 pages, found 14 mandatory requirements, checked them against
  your profile, here are 3 gaps." The wow is watching the machine do the dreaded tedious task — not a
  claim of magic. Honesty about confidence BUILDS trust; it doesn't kill wow.
- The tool never silently pretends completeness. Misses are framed as "verify against original,"
  which is credible, not embarrassing.

---

## 5. QUICK PROFILE (intake — deliberately minimal, NOT the full passport)

Collect only what the readiness check needs:
- Business legal name, NYS Vendor ID (optional)
- Certified? (MWBE / SDVOB / none) + cert type + expiration date (if certified)
- Which standard docs they HAVE: insurance certificate (+ expiry), tax returns (year), W-9,
  capability statement, required licenses
- That's it. The full reusable document vault / Vendor Compliance Passport is EXPANSION (§8),
  not v1 — pulling it in turns a demo into a multi-month build.

---

## 6. TECHNICAL SHAPE

- **Part A (tender reading)** is where the AI does real work: PDF text extraction + an AI agent that
  identifies requirements. Expect to ITERATE — it won't be perfect on document one. Build it to
  degrade gracefully (flag uncertainty, never assert false completeness).
- **Part B + the readiness scoring** are DETERMINISTIC — reuse the existing `validator.py` engine and
  the golden copy. RM-3 (VendRep stale-cert monitor) is the prototype for the cert panel; extend it to
  the MWBE/SDVOB certificate. Citation-by-construction: any rule/consequence shown must be a
  verbatim-grounded citation (GoldenCopy.cite()) or it renders as "not confirmed."
- **Readiness score** (transparent, 0-100, every point explainable — no hidden AI scoring):
  cert-not-expired, required-forms-identified, docs-present, docs-not-stale, material-change-answered,
  profile-complete. Weights visible to the user.
- **One clean screen** a non-technical vendor understands. Polish matters here because it's a demo —
  but substance (the caught gap) matters more than gloss.

---

## 7. DEFINITION OF DONE (testable v2)

- Vendor completes the quick profile.
- Vendor uploads a real NYS tender PDF; tool extracts and lists its key requirements.
- Tool compares requirements to the profile and shows readiness score + per-requirement GREEN/YELLOW/RED.
- Tool lists the specific gaps + a plain-English action list.
- For a certified vendor, the cert-renewal panel shows accurate, statute-grounded status.
- Every rule shown is CONFIRMED-with-citation, CLAIM-flagged, or USER-PROVIDED.
- Part A always ends with "verify against the original" — no false completeness.
- One legible screen, demo-ready, that makes a vendor say "it caught something I'd have missed."

---

## 8. AFTER THIS SLICE (not now)

Once it demos: this is the artifact for testing with a VARIETY of vendors and for the one
willingness-to-pay conversation (APEX / Finn Kreidler / SBDC / a certified MWBE-SDVOB). Watch which
part they react to — the tender check, the gap-catch, or the cert panel — and that reaction tells you
the real wedge with evidence.

Expansion order (from product paper, RESEARCH-LEDGER §13 / product paper §9.2):
Vendor Compliance Passport (full doc vault) → richer tender extraction → bid/no-bid recommendation →
historical award / price intelligence → prime/sub utilization workspace → other jurisdictions → federal.

---

## 9. WHAT NOT TO BUILD NOW
Full document vault/passport, award/price intelligence, bid/no-bid auto-recommendation, portal
auto-submission, proposal writing, prime/sub utilization, multi-state, federal modules. Those are
later. v2 proves the upload→readiness loop across vendor types first.

## 10. COMPLIANCE FRAME (binding)
Information / document-validation tool only. Not legal or financial advice. The tool states what a
rule requires and whether a document meets it; the vendor approves everything. No auto-submission to
State portals. (Per RISK-MAP compliance frame.)

## 11. DATA SENSITIVITY & TRUST (build in from day one — not an afterthought)
The vendor uploads sensitive material to use this tool: tax returns, ownership/financial documents,
the tender itself. GovCon practitioners explicitly say they will NOT run sensitive content through
LLMs and keep it in private environments with no third-party retention (confirmed signal,
r/GovernmentContracting AI-tools thread, 2026-06-30). For a compliance product, trust IS the product —
a vendor who doesn't trust where their financials go won't upload them, and the demo dies at the
upload step.

Requirements:
- **Clear, upfront data-handling statement** the vendor sees before uploading: what's stored, where,
  for how long, and that it is NOT used to train third-party models or shared.
- **No third-party data retention** of uploaded sensitive documents; private handling.
- **Minimize what's sent to any LLM** — extract/process the tender text for requirements, but do not
  ship the vendor's proprietary financials/ownership docs to a third-party model unnecessarily.
  Where document content must be processed, prefer handling that doesn't retain or train on it.
- **Be explicit in the demo** about this — it's a trust-builder, not fine print. For these vendors,
  "your documents stay private and aren't used to train anything" is itself part of the wow.
- This is consistent with the §10 compliance frame and the information-only posture: the product is a
  private document-validation tool, not a data pipeline.

---

## 12. ACTIVE-LEARNING LOOP (PHASE 2 — not in the first demo slice)

**Founder's design.** Turns the golden copy's inevitable incompleteness into a self-improving
loop instead of a static gap. When the tool hits a tender requirement with no golden-copy rule, an
AI does targeted deep research; if it finds a probable basis, it shows the vendor a clearly-marked
UNVERIFIED finding ("this could be the rule — verify yourself") AND emails the manager so a human
can verify against primary source and, if confirmed, promote it into the golden copy.

**Why this matters (the completeness problem, honestly):** there is NO way to guarantee the golden
copy contains every vendor pass/fail rule in NY law — they're scattered across State Finance Law,
Labor Law, WCL, Executive Law, Tax Law, GML, NYCRR, and agency-specific tender terms. §139-d was
missed even though it sat next to rules we already had. So completeness is a DIRECTION, not a state
you certify. This loop makes gaps (a) safe (flagged, never a false pass) and (b) self-closing (each
real tender surfaces the next rule to ground, in priority order of what vendors actually hit).

### The three-track separation (NON-NEGOTIABLE — this protects the product's entire trust model)
The golden copy's value is that everything in it is verbatim-from-primary-source. Introducing live
AI research risks contaminating that. So output MUST keep three visually distinct tracks, never blended:
- **Track 1 — CONFIRMED.** Golden-copy rule, verbatim citation. Authoritative. "This is the law."
  Visual: green/check, source cited (e.g. "✓ NY Exec Law §314(5)").
- **Track 2 — TENDER-DERIVED.** Requirement read from the uploaded tender. "This RFP asks for X."
  Visual: neutral, provenance = "this tender, page N."
- **Track 3 — UNVERIFIED (AI-assisted research, NEW).** Deep research on an ungrounded requirement.
  Visual: clearly different (amber/warning), heavily caveated: "⚠️ Unverified — AI-assisted
  research, NOT a confirmed rule, NOT legal advice. Verify independently before relying."
  NEVER styled like Track 1. The vendor must never confuse "found on the web" with "verified
  against law." This separation is structural, not a footnote.

### The disciplined research prompt (or it pollutes the review queue)
The AI gap-research must enforce the SAME discipline we apply by hand, or the manager's inbox fills
with junk and the loop dies from neglect:
- PRIMARY sources only (the statute, NYCRR, official ny.gov/ogs/osc/esd pages). 
- Secondary sources (consultant blogs, FAQs) → flagged low-confidence, never presented as the rule.
- If no primary source found → say "no primary source found," do NOT guess. (This is exactly the
  discipline that caught the false "2-year MWBE" claim — bake it into the prompt.)
- Output to manager: the requirement, the AI's candidate source + URL + verbatim quote, and a
  confidence label. Manager verifies → promotes to Track 1 (golden copy) only if it holds.

### Manager review queue (the human-in-the-loop)
- Each Track 3 event fires an email to the engine manager: requirement text, tender it came from,
  AI candidate source/quote/URL, confidence.
- Manager verifies against primary source (same process used all session). If confirmed → a new
  verbatim source-*.md is added to the golden copy → next time it's Track 1 for everyone.
- Net effect: every real tender either confirms coverage or hands the manager a prioritized,
  pre-researched candidate rule to verify. Completeness becomes evidence-driven and continuous.

### Guardrails (compliance / liability — load-bearing, not fine print)
- Showing AI "here's what the rule might be" is closer to advice than showing a verbatim statute.
  The "unverified / not legal advice / verify yourself" framing must be airtight and PROMINENT on
  every Track 3 item — it's what keeps this feature behind the advice line.
- Privacy (§11): the gap-research query must send only the REQUIREMENT description to any research
  model — never the vendor's uploaded financials/ownership documents. Decide the research-model
  data posture explicitly (no-retention) before building, same standard as §11.

### Sequencing
PHASE 2, after the core demo works. The first slice ships with honest "not confirmed" flags only
(Track 1 + Track 2). This loop adds the LLM-research + email infrastructure the first slice
deliberately avoids — build it once the upload→readiness core is validated with real vendors.

---

## 13. PRODUCT ROADMAP — THREE CAPABILITIES (the real product shape)

Clarified after the first real-tender test. The product is a two-phase, three-capability
progression. Capability 1 is built and proven on real NYS tenders; 2 and 3 are the forward path.
Each capability is independently valuable and demoable — you do NOT need 3 to have a product worth
paying for.

### Capability 1 — Requirements checklist (RFP → what's needed)  ✅ BUILT & TESTED
Vendor uploads an identified RFP; the tool reads it and returns the complete list of documents,
forms, certifications, and requirements needed to participate — in plain English, RFP-specific.
- Status: working on real 68/54-page ACCES-VR tenders (extractor reads them, grounds the real NYS
  clauses, surfaces real numbers: MWBE 30%, SDVOB 6%, insurance $1M).
- **Output reframe (next small task):** present the result as a REQUIREMENTS CHECKLIST, not a
  readiness score. The 0-100 score is meaningless on large real docs (only a handful of rows are
  checkable). The checklist ("here are the 14 things this RFP demands, each with what it requires
  and the deadline") is the actual value. Reframe output; don't rebuild.
- Value on its own: knowing the complete required-items list buried across 68 pages is the single
  hardest, most error-prone part of NYS bidding. This alone is worth paying for.
- (Future front-end: one day the engine PROPOSES the matched RFP/RFQ to the vendor. Not now.)

### Capability 2 — Gap analysis (checklist × client profile)  ← NEXT BUILD
If the tool holds an updated client profile (documents on hand + their expiry dates), it produces a
four-state answer per required item:
- **Required by this RFP** →
  - ✓ You already have it, and it's current
  - ✗ You're missing it
  - ⏰ You have it but it EXPIRES BEFORE the RFP due date — renew it before you bid
The expiry-vs-deadline check is the sharpest feature — connecting a document's expiration to THIS
RFP's specific due date and saying "renew before bidding" catches the exact failure a vendor loses a
contract over.
- Difficulty: mostly a DATA + DATE-MATCH problem (profile of held docs/expiries × checklist × RFP
  due date), NOT hard document-parsing. Close to reach; this is where the "wow" lives.
- This is the natural home of the existing cert-renewal logic (§314 MWBE 5-yr, §220-i 2-yr, etc.) —
  the recertification tracking becomes the expiry engine behind the ⏰ state.

### Capability 3 — Compliance review (do the documents actually satisfy the RFP)  ← LATER BUILD
Not just "you have a non-collusion form" but "your form is signed, dated, and matches what THIS RFP
demands." Reads the vendor's ACTUAL submitted documents and checks them for apparent compliance
against each requirement — presence AND apparent match, not just presence.
- Difficulty: HARDEST — requires parsing the vendor's own (messy) submission documents, a second
  document-reading job on top of the RFP reading. This is the deepest verification and strongest moat.
- **REGULATORY BOUNDARY (build in from the start, non-negotiable):** "reviewing compliance" edges
  toward legal judgment. Safe framing, consistent with the information-tool posture: the
  tool states "here is what this RFP requires this document to contain; here is whether yours appears
  to contain it; verify with counsel." It checks presence and apparent match against the stated
  requirement — it does NOT render a legal compliance opinion. Bake this boundary in, don't bolt on.

### Build sequence
1 (done) → reframe 1's output as a checklist → 2 (gap analysis: have / missing / renew-before-deadline)
→ 3 (compliance review, with the counsel-verification boundary).
Capability 2 yields a genuinely impressive, demoable product for the cost of profile-data + date
logic — no hard document-parsing required. Ship through Capability 2 before attempting 3.

### How this relates to earlier sections
- The "vendor profile" in §5 is the seed of Capability 2's client profile — extend it with held-doc
  expiry dates.
- The Active-Learning Loop (§12) still applies: novel mandatory requirements with no golden-copy rule
  surface in the "other requirements detected" bucket (safe, ungraded) and feed the loop that
  eventually promotes them into graded Capability-1 checklist items.
- Real-tender test (2026-06-30) confirmed Capability 1's extractor works and defined the refinement
  backlog: contract-value safety (done), flood suppression (done), de-hyphenation + number-surfacing
  (done). Remaining: run a 3rd unseen tender to confirm fixes generalize; decide whether the coarse
  score is dropped entirely in favor of the checklist framing.

---

## 14. READING-ENGINE ARCHITECTURE DECISION (locked 2026-06-30)

The real-tender test exposed that Phase 1's failures ($50-per-hour misread as contract value,
"workforce" tripping EEO, hyphenation splits, missed RFP-specific requirements) are artifacts of the
**stdlib-only, pattern-matching extractor** — NOT limitations of AI. That extractor was chosen for
privacy (§11: nothing leaves the machine, no LLM). The decision below resolves the reading engine.

### The key insight: match the reader to the data's sensitivity
The two document types have very different privacy needs, so they get different reading engines:

- **The RFP is a PUBLIC government document** (published on the NYS Contract Reporter, downloadable by
  anyone). Reading it with a full commercial LLM carries ZERO privacy risk — there is nothing
  confidential to protect. This is also the most reading-intensive, highest-value task (extract every
  requirement, incl. the RFP-specific ones the pattern-matcher misses).
  → **Phase 1 reading = full LLM. No privacy constraint. Do this.**

- **The vendor's own documents** (financials, ownership, certs) ARE private. These need either a
  local/self-hosted model or a no-retention enterprise LLM arrangement on infrastructure the company
  controls — never passed to a third-party AI provider.
  → **Phase 3 reading = LLM on controlled infra (no-retention / self-hosted).**

### "Your machine" = the company's controlled infrastructure, not the vendor's device
Privacy is protected by the COMPANY processing uploads on infrastructure IT controls and
NOT forwarding them to any third-party AI service — not by requiring the model to run on the vendor's
laptop (impractical for capable models). Trust story to vendors: "Your documents are processed on our
secured systems and are never sent to any outside AI service or used to train anyone's model." This
mirrors how regulated industries (e.g. banks) already use LLMs. Founder has direct knowledge of a
bank-approved setup — start next session from "what did the bank's compliance review approve" rather
than researching from scratch.

### Privacy options (most-private → most-convenient), for the PRIVATE documents only
1. Self-hosted open-weight model on company hardware/cloud tenant — data never leaves company perimeter.
2. Enterprise API with contractual zero-data-retention (no storage, no training) — the common
   regulated-industry pattern (Anthropic/OpenAI enterprise, AWS Bedrock, Azure OpenAI).
3. Model running inside the company's own cloud account (Bedrock / Azure OpenAI) — enterprise models,
   data stays in the controlled environment.

### Migration scope (Phase 1: stdlib → LLM)
Swapping the RFP reader from the stdlib pattern-matcher to an LLM is a REAL rebuild of the extractor,
not a tweak — but well-scoped, and it fixes the entire class of today's failures in one move (an LLM
understands "$50/hour is a rate, not a contract total," catches RFP-specific requirements, never
splits hyphens). CRITICAL: everything built ON TOP of the extractor stays — the golden copy, the
citation-by-construction discipline (GoldenCopy.cite), the issue/fix output, the tri-state provenance
(confirmed / tender-derived / not-confirmed), threshold + scope gating, the gap-analysis design. Only
the READING layer underneath changes. The LLM extracts requirements; the golden copy still grounds
consequences verbatim; the LLM's output is never treated as citable rule truth (it reads the RFP, it
does not invent law).

### Sequence implication
Phase 1's near-term path is: (a) move RFP reading to an LLM, (b) reframe output as a requirements
CHECKLIST (not a score), (c) run a 3rd unseen tender to confirm generality. Then Capability 2 (gap
analysis) and Capability 3 (compliance review on private docs, controlled-infra LLM).
