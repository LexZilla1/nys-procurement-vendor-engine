# NYS PROCUREMENT VENDOR ENGINE — PAIN-POINT REGISTER (evidence layer)

**Purpose.** This is the EVIDENCE layer. Every practitioner pain-point that informs a product feature
is recorded here first, with its sources, before it is allowed into RISK-MAP.md. Same discipline as the
verification report: nothing enters the risk map without a register entry. This file is NOT verbatim
State law (that is the golden copy); it records lived-experience failure modes and the sources that
attest to them.

**Verification standard for entries.** A pain-point is marked VERIFIED only when (a) it is attested by
a primary/authoritative source (an OSC audit, a government comptroller report, a statute/GFO provision
that creates the trap) OR by multiple independent practitioner sources that agree, AND (b) the
underlying RULE it attaches to exists as a verified golden-copy source file (or is captured at the same
time). Single-blog-only claims are marked INDICATIVE and may not drive a hard-block feature until
upgraded.

**Scope guard.** NY State-track only. NYC procurement (PASSPort, PPB rules, City Comptroller
registration) is a DIFFERENT regime and is explicitly excluded; where a NYC source corroborates a
pattern, it is noted as context only, never as the rule.

---

## REG-1 — Post-registration budget-variance halt ("approved but still not paid")
- **Status:** VERIFIED (rule = primary; pattern = multiple independent sources)
- **Failure mode:** After a grant contract is registered/approved, payment stalls because the budget
  must be approved and then kept within tolerance. A transfer of funds among program activities or
  budget cost categories at/above a size-based threshold must go back to OSC for approval, halting the
  affected payments until re-approved. Budgets are returned multiple times for revision.
- **Rule grounding (golden copy):** source-xi-4-b-grant-budget-variance.md — verbatim threshold:
  ≥10% of total contract value for contracts ≤ $5M; ≥5% for contracts > $5M (OSC XI.4.B, REV.
  9/11/2024), independently confirmed verbatim by the DOB NYS Contract for Grants face page (H-1032).
- **Evidence (pattern):** OSC NFP prompt-contracting audit (78% of contracts late; start precedes
  approval) — web.osc.state.ny.us/audits/allaudits/093009/2008bse16003.pdf; nonprofit-sector field
  report describing budgets/workplans "returned multiple times … before being finalized" largely in
  the Grants Gateway portal — cnycf.org/payment-pending-cny-nonprofit-funding-delays-from-the-state-level/.
  NYC City Comptroller "Nonprofit, Nonpayment" (10% budget-overage re-review halts payment) — context
  only, different regime — comptroller.nyc.gov/reports/nonprofit-nonpayment/.
- **Confidence:** HIGH (rule dual-source verified; pattern corroborated across NY-track sources)

## REG-2 — §179-v interest owed but not paid (statutory ambiguity)
- **Status:** VERIFIED (primary audit source)
- **Failure mode:** When a contract is executed late and the NFP has been providing services, interest
  is owed under SFL §179-v from the later of the scheduled commencement date or service-start date
  until payment. In practice interest frequently is NOT paid, attributed by OSC's own audit to
  ambiguities in §179-v. Vendors leave owed money on the table.
- **Rule grounding (golden copy):** source-stf-179-v.md (interest entitlement) + source-xi-4-a-nfp-prompt-contracting.md.
- **Evidence:** OSC audit 2008-S-16003 — "no interest was paid … the result of ambiguities in Section
  179-v" (web.osc.state.ny.us/audits/allaudits/093009/2008bse16003.pdf). Active legislation
  (S7001 / A11179 / S4877) targets this cluster → elevated freshness priority.
- **Confidence:** HIGH

## REG-3 — VendRep stale-certification / material-change duty
- **Status:** VERIFIED (primary OSC guidance)
- **Failure mode:** A certified VendRep questionnaire goes stale. Even with a current certified online
  questionnaire, the vendor must ensure it reflects any MATERIAL CHANGES since last certification; a
  stale-but-certified questionnaire is a responsibility/rejection risk at award or OSC approval. Paper
  questionnaires additionally require a notarized owner/officer signature — easy to miss.
- **Rule grounding (golden copy):** the four VendRep source files (AC 3290-S/3291-S/3292-S/3293-S) +
  source-vendrep (system/process). Material-change duty stated by OSC.
- **Evidence:** OSC "The VendRep System" — vendor's responsibility to reflect material changes since
  last certification (osc.ny.gov/state-vendors/vendrep/vendrep-system); questionnaire instructions —
  owner/officer must certify and signature must be notarized.
- **Confidence:** HIGH

## REG-4 — MWBE deadline cascade (non-responsiveness disqualification)
- **Status:** VERIFIED (primary regulation)
- **Failure mode:** After low-bid notice, a chain of short deadlines (utilization plan 10 business days;
  agency deficiency notice 20 days; vendor cure 7 business days; waiver form 5 business days). Missing
  any one can disqualify the bid for non-responsiveness. Easy to lose on the clock, not the merits.
- **Rule grounding (golden copy):** source-mwbe-5nycrr-pass-fail.md — §142.6 deadline cascade,
  §143.3(c) EEO rejection trigger.
- **Evidence:** 5 NYCRR §142.6(a)-(g), §142.9 (verified verbatim against live NYCRR via Cornell LII).
- **Confidence:** HIGH

---

## CANDIDATES (not yet upgraded — do not drive hard-block features yet)
- **150-vs-180-day execution clock discrepancy** — secondary guidance floats "180 days"; statute (§179-s)
  and GFO XI.4.A say 150/120. RESOLVED in golden copy by anchoring to statute; logged so the discrepancy
  isn't re-introduced. Status: RESOLVED, no feature.
- **§109 per-claim certification** — every claim needs the "just, true and correct / unpaid / due and
  owing" certificate; an uncertified claim (where required) is improper. Rule grounding:
  source-stf-109-vendor-certificate.md. Status: VERIFIED rule; feature = invoice-certification pre-check
  (additive to REG-set). 
