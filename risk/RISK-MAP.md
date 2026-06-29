# LEXZILLA RISK MAP (rule-to-risk / production-spec layer)

**Purpose.** This is the layer that makes the SaaS better than a human reviewer. The golden copy says
what each rule SAYS; this map says what GOES WRONG at each rule, what the product should CHECK, and which
production FEATURE that check powers. A human expert carries some of these traps in memory and forgets
others under load; this map applies every trap, every time, deterministically.

**How to read an entry.**
- PAIN-POINT — the failure in plain terms
- GROUNDS IN — the exact golden-copy source file that gives the rule its authority (+ register entry)
- PROCESS STAGE — where in the vendor lifecycle it bites
- FAILURE MODE — the precise mechanism of loss (rejection, halt, unpaid entitlement, disqualification)
- PRE-CHECK — what the product tests, stated as a rule a validator can implement
- FEATURE — the sellable product surface
- MODE — PREVENTION (don't get rejected) or RECOVERY (get what you're owed)
- CONFIDENCE — from the register

**Compliance frame (binding).** Every feature below is an INFORMATION / DOCUMENT-VALIDATION tool, not
financial or legal advice or representation. Outputs state what a rule requires and whether a document
meets it. The §179 interest-recovery feature (RM-2) in particular must be run past licensed-attorney
oversight before launch, and must not drift into arranging or advising on financing.

**Production handoff.** An engineer building the validator reads PRE-CHECK as the spec and GROUNDS IN
as the authority. Phase-2 freshness-checker keeps GROUNDS IN current; if a source file's REV date
changes, re-confirm the linked PRE-CHECK still holds.

---

## RM-1 — Budget-variance pre-check  ⟶  FLAGSHIP
- **PAIN-POINT:** Post-registration, a budget-category transfer at/above threshold forces OSC
  re-approval and halts payment; budgets bounce back repeatedly.
- **GROUNDS IN:** source-xi-4-b-grant-budget-variance.md (REG-1)
- **PROCESS STAGE:** Post-registration, pre-/mid-payment
- **FAILURE MODE:** Payment halt + re-review loop until OSC re-approves the modified budget
- **PRE-CHECK:** Given an approved budget and a proposed/actual spend, flag any transfer among program
  activities or budget cost categories where the moved amount ≥ 10% of total contract value (contracts
  ≤ $5,000,000) or ≥ 5% (contracts > $5,000,000). Flag BEFORE submission; advise that an amount/scope/
  term change is a different, amendment-track event.
- **FEATURE:** Budget-variance gate — "will this budget move trigger OSC re-approval?"
- **MODE:** PREVENTION
- **CONFIDENCE:** HIGH

## RM-2 — §179 interest entitlement calculator  ⟶  STRONGEST P&L WEDGE
- **PAIN-POINT:** Interest owed on late-executed/late-paid NFP contracts often goes unclaimed/unpaid.
- **GROUNDS IN:** source-stf-179-v.md + source-xi-4-a-nfp-prompt-contracting.md (REG-2)
- **PROCESS STAGE:** Post-execution, payment late
- **FAILURE MODE:** Vendor never receives interest it is statutorily entitled to (state ambiguity +
  no one computing it)
- **PRE-CHECK:** From contract dates (scheduled commencement / service-start / approval / payment dates)
  and the payment schedule, determine whether a §179-v interest entitlement arose and compute the
  indicative amount; produce the documentation a vendor needs to assert it. Surface the conditions that
  must hold (written directive not suspended; OSC/AG approval; no warranted waiver).
- **FEATURE:** Interest-entitlement calculator + claim-support pack
- **MODE:** RECOVERY  (run past attorney oversight before launch)
- **CONFIDENCE:** HIGH on entitlement logic; freshness-sensitive (S7001/A11179/S4877)

## RM-3 — VendRep stale-certification monitor  ⟶  RECURRING REVENUE
- **PAIN-POINT:** Certified questionnaire goes stale after a material change; stale-but-certified = risk.
- **GROUNDS IN:** VendRep source files (AC 3290-S/3291-S/3292-S/3293-S) (REG-3)
- **PROCESS STAGE:** Continuous; bites at award / OSC approval
- **FAILURE MODE:** Responsibility finding / delay because the questionnaire no longer reflects reality
- **PRE-CHECK:** Track events that constitute MATERIAL CHANGES (ownership change, new judgment/lien,
  tax-status change, bankruptcy, debarment/suspension, key-personnel integrity events). On any such
  event, prompt re-certification. For paper filings, confirm notarized owner/officer signature present.
- **FEATURE:** "Your VendRep is at risk" monitor (event-driven re-certification prompts)
- **MODE:** PREVENTION (subscription-shaped)
- **CONFIDENCE:** HIGH

## RM-4 — MWBE deadline-cascade tracker
- **PAIN-POINT:** A short chain of post-low-bid deadlines; missing one disqualifies for
  non-responsiveness.
- **GROUNDS IN:** source-mwbe-5nycrr-pass-fail.md (REG-4)
- **PROCESS STAGE:** Post-low-bid notice, pre-award
- **FAILURE MODE:** Bid disqualified on the clock (utilization plan / cure / waiver deadlines)
- **PRE-CHECK:** Start the clock at low-bid notice. Track: utilization plan due 10 business days; agency
  deficiency notice 20 days; vendor written remedy 7 business days from notice; waiver form 5 business
  days if requested. Warn before each cliff. Separately, hard-block on a missing EEO policy
  statement/staffing plan (§143.3(c) "shall result in rejection") unless the 10-employee carve-out or a
  written justification applies.
- **FEATURE:** MWBE deadline + completeness tracker
- **MODE:** PREVENTION
- **CONFIDENCE:** HIGH

## RM-5 — Invoice certification + proper-invoice pre-check  (additive)
- **PAIN-POINT:** A claim missing required fields or the §109 certificate is improper → agencies must
  reject.
- **GROUNDS IN:** source-stf-109-vendor-certificate.md + (proper-invoice fields) XII.4.F file (register
  CANDIDATE/§109)
- **PROCESS STAGE:** Each payment request
- **FAILURE MODE:** Improper-invoice rejection; restart of the clock
- **PRE-CHECK:** Confirm the invoice contains every required proper-invoice field AND carries the §109
  certificate ("just, true and correct" / not previously paid / actually due and owing), or the
  AC 3253-S certification with a valid signature/e-signature. Treat §109(1-a) (Comptroller may accept a
  normal-course invoice without separate certification) as the exception, not a license to skip.
- **FEATURE:** Invoice pre-flight (fields + certificate)
- **MODE:** PREVENTION
- **CONFIDENCE:** HIGH

---

## PRODUCT PATTERN (for planning)
Two modes cluster the portfolio:
- **PREVENTION gates** — RM-1, RM-3, RM-4, RM-5 — "don't get rejected / don't get halted." Sold as
  insurance against severe, well-defined failure events.
- **RECOVERY / entitlement** — RM-2 — "get what the State already owes you." Has a dollar figure
  attached, so pricing is concrete; this is the differentiating wedge and aligns with the founder's
  structured-finance background.

## MAINTENANCE
- Every RM entry must point at a verified golden-copy file AND a REG entry. If either is missing,
  the entry is a DRAFT and cannot drive a hard-block.
- When Phase-2 freshness-checker flags a REV-date change on a GROUNDS-IN file, re-verify the PRE-CHECK.
- §179 cluster (RM-2) carries an elevated freshness flag due to active legislation.
