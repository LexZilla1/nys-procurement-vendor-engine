# Decisions & Findings — 2026-07-23

Documentation-only session close. Nothing here changes code, schema, golden copy,
config, or workflows. This is the durable record of decisions **agreed but not yet
built**, verbatim statute findings read this session, and research conclusions, so they
survive into the next session.

Base: `origin/main` = `b5dddc050fa2031b896d940acd914c2ad3af2688` (verified by
`git fetch origin` + `git rev-parse origin/main` this session — not trusted from memory).

---

## 1. Vendor Profile — design decisions (agreed, not yet built)

### Fact model (two axes, applies to ALL vendor facts)
- **provenance:** `vendor | uploaded_document | agency | third_party`
- **verification:** `verified | unverified`
- **`attested_at`** (when the vendor asserted it) and **`evidence_date`** (the as-of
  date of the underlying fact) are **SEPARATE fields**. §179-f(6)'s "at the time of
  payment" test operates on `evidence_date`. Collapsing them produces stale results that
  look fresh.
- Facts are **append-only**: `superseded_by`, never mutated.
- **`provenance:vendor` always means `verification:unverified`.** No path may let an
  attestation flip its own verification bit.

### Rule model (separate from facts — never merged)
- **definition_status:** `DEFINED_IN_GOLDEN_COPY | UNDEFINED_IN_GOLDEN_COPY | INTERPRETIVE`
- **evaluation_basis:** `OBJECTIVE_THRESHOLD | VENDOR_ATTESTATION | DOCUMENTARY_REVIEW | HUMAN_LEGAL_REVIEW`
- These two axes are **ORTHOGONAL.** Proof: `sb_primary_place_ny` is
  `DEFINED_IN_GOLDEN_COPY` but `VENDOR_ATTESTATION` — the statute names the criterion
  clearly, yet we have no independent way to test it.
- **Rejected:** `standard_undefined: true`. That asserts something about the world.
  `UNDEFINED_IN_GOLDEN_COPY` asserts something about our corpus — the only thing we can
  verify.

### Output ceiling
The maximum profile verdict is **`SATISFIED_AS_ATTESTED`. There is no `PASS`.** The verb
carries the meaning: the vendor said something consistent with the criterion; the
criterion is not proven met.

### Readiness ≠ entitlement
Profile readiness is a snapshot of **profile/program readiness only**. It never
determines that a specific invoice must be paid in 15 days. Five `scope_limits` are
**always emitted, never suppressed**.

### Product decision (ours, not the State's) — staleness horizon
A staleness horizon applies to attested facts. **If no horizon is configured, the result
is `INCOMPLETE` — the code must never select a default.** An unconfigured policy is a
missing human decision, not a value for the engine to invent.

### Permanent non-goal — no SFS write path, ever
The engine never offers to complete the vendor's SFS portal certification. That is a
State-system login, permanently out of scope (State-system boundary).

### Known accepted limit — `documentation_available_on_request`
This is a vendor attestation. If the vendor is later asked and cannot produce, the
attestation was false. **No engine-side remedy exists and none should be built.**
Documented here so it is not rediscovered later as an oversight.

---

## 2. §179-f — verbatim findings (read from golden copy this session)

- **"at the time of payment" attaches ONLY to the ≤200-employee threshold**, not to the
  other **four** criteria. (§179-f(6) names five criteria total — primary place in NY,
  significant business presence, independently owned and operated, not dominant in its
  field, ≤200 employees — so four criteria besides the employee test. An earlier draft of
  this section said "five"; corrected.) The employee test is a **payment-date** test, not
  an onboarding-date test.
- **§179-f(2)** requires the vendor to identify that it is seeking expedited payment as a
  small business. **The statute does not say HOW.**
- **OSC (GFO XII.5.I)** maps that identification to **SFS portal self-certification**.
  **THAT MAPPING IS OSC'S, NOT THE STATUTE'S** — record as an **interpretive bridge**
  (OUTCOME 2). Cite the two sources **separately**; never collapse into one rule.
- **Two statutory criteria have no definition and no numeric test in §179-f:**
  "significant business presence" and "not dominant in its field" →
  `UNDEFINED_IN_GOLDEN_COPY`.

---

## 3. §179-p — CORRECTION: captured; implemented for RM-2 with legal applicability attorney-gated (was falsely recorded as a gap)

> **This section was originally recorded as "§179-p is NOT in golden copy / BLOCKING." That
> was FALSE** — a chat-session inference from GFO XII.5.I's paraphrase, never checked against
> the filesystem. Corrected 2026-07-23 against the repo. See the "Prompt claims are unverified
> by default" rule in CLAUDE.md and the corrected BACKLOG entry.

**Keep three states distinct — do not conflate capture with legal applicability.**

- **(1) Capture — RESOLVED.** `golden-copy/sources/source-stf-179-p.md` — full-section
  verbatim capture, copied 2026-07-01, API activeDate 2014-09-22, `openleg-api-v3`, all six
  inapplicability clauses word-for-word. Freshness: `FULL-MATCH`, checked 2026-07-12.
  Implemented + tested: `validator.py` (~398–444, ~1031–1112) runs all six clauses as the
  interest-exclusion pre-screen, cited to the source (not the paraphrase);
  `test_validator.py` covers it — which proves the code matches its fixture, not that the
  legal question below is answered.
- **(2) Article 11-A → Article 11-B applicability — ATTORNEY-GATED (open).** §179-p is an
  Article 11-A prompt-**payment** provision; RM-2 is Article 11-B prompt-**contracting**.
  `validator.py`'s own `scope_note` (~1106) plus `attorney_review_required: True` state that
  whether the 11-A exclusions bind an 11-B (§179-v) entitlement is a licensed-review
  question. The engine applies them conservatively (exclusion → not entitled) but does not
  assert the cross-article legal conclusion.
- **(3) OSC guidance freshness (GFO XII.5.I) — UNVERIFIED (open).**
  `source-xii-5-i-prompt-payment-interest.md` is **REV. 03/30/2026** (copied 2026-06-29).
  OSC guidance pages are **not** in the OpenLeg monthly freshness net (statute-class only),
  so guidance drift is not auto-caught; a newer OSC revision may exist and needs a manual
  recheck/recapture (egress-blocked in-sandbox).
- **Content (category summary — NOT verbatim; cite the golden source for exact wording):**
  §179-p enumerates **six** numbered categories of payments to which Article 11-A
  prompt-payment interest does not apply — (1) eminent domain; (2) court-judgment interest
  under other law; (3) federal government / state agencies / any unit of local government /
  public authorities / state-agency employees; (4) third-party payment-agreement contractors
  (e.g. §367-b social-services fiscal agents); (5) entities receiving state funds through a
  non-state-agency intermediary (pass-through); (6) comptroller-authorized set-offs. **The
  exact six clauses live verbatim in `golden-copy/sources/source-stf-179-p.md` — cite that
  source; this doc does not restate statutory text.** *(Two earlier drafts mis-stated this:
  first the "local governments receiving state aid" paraphrase; then a partial list labeled
  "verbatim" that dropped clauses 2/4/5. Both are corrected by citing the source rather than
  restating — do not call a partial summary "verbatim.")*
- **Also open (design, not a gap):** whether `engine/invoice_clock.py` needs its own
  §179-p exclusion awareness or should delegate to the entitlement layer (`validator.py`).
- **Not blocking on grounds of absence, and Vendor Profile / Onboarding Readiness (Layer-B)
  is unaffected either way.**

---

## 4. Sourcing — conclusion (verified, closes the question)

**No automated channel exists for NYS bid opportunities.** Verified independently by four
sources this session (this analysis, Gemini, Copilot, Perplexity) converging on five
points:

- No NYSCR API, RSS, XML feed, bulk download, or developer interface. Registration +
  e-Alert email only.
- No `data.ny.gov` dataset of currently open NYS solicitations (historical/award only).
- No published NYSCR commercial licensing program.
- No data-sharing / partnership mechanism for third parties.
- No agency-level open-data portal with open solicitations.

NYSCR is administered under Empire State Development (ESD). FOIL does not help: it reaches
existing static records, not prospective real-time feeds.

### Operating model (decided)
**The vendor brings the documents.** Client clicks a plain deep-link to NYSCR (new tab,
own account), downloads with their own credentials, and uploads to their page in our
system. We **never** scrape, **never** proxy, **never** iframe, **never** handle client
credentials, **never** re-host documents.

**Rejected this session, with reasons:**
- NYSCR scraper — contractual / CFAA risk under the click-wrap we accepted.
- Using client credentials — account sharing.
- iframe / embed — framing + implied affiliation.
- Document repository served to clients — re-hosting.

### Market fact
NYSCR ads are already republished free by third-party aggregators (LightRFP, GovDash).
**The opportunity list itself has no commercial value.** Value is the **JUDGMENT** on the
list — triage, eligibility, checklist — not the list.

### Still gated
The discovery-directory / source-resolver build remains **gated on an IP-attorney
opinion. Unchanged. Do not build.**

---

## 5. Payment-delay research findings

> **PROVENANCE:** figures in this section come from web research conducted in the
> 2026-07-23 session (OSC prompt-payment interest reports, SFY 2020-21 and 2021-22).
> They are NOT golden copy and have NOT been verified against primary source by tooling.
> They are recorded as session findings, not as citable rules. Verify against osc.ny.gov
> before using any figure in vendor-facing output.

**The paradox:** late payment is vendors' #1 financial issue, yet NYS paid only **$1.45M**
in prompt-payment interest (SFY 2020-21), falling to **$1.0M** (SFY 2021-22). Five
structural filters explain it — all recorded:

1. **$10 de-minimis.** Interest below $10 per invoice is not paid (in §179-f and in the
   standard purchase-order terms the vendor signs). 96.6% of interest payments in SFY
   2020-21 were under $500; ~11,890 of 12,312 payments, averaging ~$61.
2. **The clock runs from the MIR date** (Merchandise/Invoice Receipt), not from vendor
   submission. Time between sending and MIR registration does not count. GFO XII.5.F
   governs adjusting the MIR date; OSC rejection code **14** is "Incorrect MIR date".
3. **An improper invoice never starts the clock.** Rejection + correction cycles generate
   no interest. Vendor notification of defects is best practice, not a hard obligation.
4. **Suppression flags the vendor cannot see.** The Prompt Payment Interest Eligibility
   Indicator in the Statewide Vendor File, and the Late Charge Option on the voucher, can
   suppress interest regardless of delay. The vendor cannot see either.
5. **§179-p category exclusions** (captured and implemented — see corrected §3 above; not a gap).

**OSC-stated causes of delay (SFY 2020-21):** Agency Backlog/Processing Delay $558,314
(302 payments); Delay in Encumbrance Processing $163,556 (119); System Processing $503
(1); under-$500 miscellaneous $728,845 (11,890).

**Proper invoice = 6 mandatory fields (GFO XII.4.F):** vendor name; NYS agency that
ordered; description of goods/services; quantity delivered; amount claimed; PO number if
applicable. **Plus 4 recommended:** NYS Vendor ID, invoice date, unique invoice number,
payment terms.

**OSC XII.7.B** lists 60+ voucher rejection codes; ~14 have vendor-side root causes: 30
(Improper Invoice field), 14 (Incorrect MIR date), 26 / 8D (documentation), 03 / 5H
(vendor identity), 6G / 3M (contract reference), 22 (terms), 5C (scope), 5D (duplicate),
27 (expired contract), 5G (amount), 6A (receipt).

**Vendor visibility:** the SFS Vendor Self-Service Portal **DOES** show invoice / PO /
payment status and interest amounts paid (data back to April 2012). It does **NOT** show
MIR date, voucher rejection codes, or the interest-eligibility indicator. OSC instructs
agencies to direct vendors to the portal rather than call — so the portal is the intended
channel.

**Product implication:** an interest calculator is **not a product** (median ~$61). The
value is:
- **(a) Onboarding** — SFS self-certification + eInvoicing + ePayment enrollment, or the
  vendor loses the 15-day lane on every invoice forever.
- **(b) Proper-invoice pre-flight** — so the clock starts on first submission.
- **(c) Knowing which questions to ask when payment stalls** — MIR date, voucher status /
  rejection code.

---

## 6. Operational lesson (also added to CLAUDE.md this session)

**ALWAYS `git fetch origin` and confirm the real remote HEAD before analyzing the repo.**
A prior session lost hours to a stale local branch 26 commits behind `origin/main`, which
produced a confident and completely wrong "none of this work exists" conclusion. A stale
local checkout is as unreliable as a stale summary. Verifying "against git" only counts if
git has been fetched.

---

## 7. Standing state (snapshot)

- **Base:** `origin/main` = `b5dddc050fa2031b896d940acd914c2ad3af2688` (verified this
  session).
- §314 closed end-to-end; write-guard #82 merged; state-model redesign recorded (#83).
- **Next build:** Vendor Profile + Onboarding Readiness Check (schema agreed above, not
  built).
- **Open:** 5 NYCRR 144 (human paste + attorney); pilot vendor; attorney hour. (§179-p
  capture was falsely listed here — it is already captured, freshness-clean, and
  implemented in `validator.py`; see corrected §3.)
- **Gated:** NYSCR discovery-directory (IP-attorney opinion).
