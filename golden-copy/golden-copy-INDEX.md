# Golden Copy — NY State Procurement & Payment Rules (INDEX)

**What this file is.** This is the **index** to the rulebook, not the rulebook text itself. The
actual rules live as **verbatim source files** in `/sources/` — each one holds the New York State
text copied word-for-word, comma-for-comma, with four metadata labels on top (Name, Date, Issued by,
Link) and a citations list at the bottom.

**Why it's split this way.** The verbatim files are the authority the system reproduces and checks
against. Keeping them as exact copies of the State's own text means a rejection can never be blamed
on this system's wording — the words belong to New York State. This index only *points* to them; it
adds no rule text of its own. (This structure follows the documented best practice for an
authoritative-source library: store the source verbatim, attach minimal metadata — title, effective
date, issuing body, permanent link — and keep any classification/commentary in a separate layer.)

**How to read an entry below.** Each entry gives the four labels and the path to the verbatim file.
The *Date* is the State's own revision stamp (REV.) where the page has one; some vendor-facing pages
carry a last-modified date instead, noted as such. The *Verified* date is when the text was last
confirmed against the live source.

**Verification.** See `VERIFICATION-REPORT.md` for the comma-by-comma check method and results. The
two highest-rejection-risk pieces (the proper-invoice mandatory fields and the 66-code voucher
rejection chart) are confirmed character-for-character identical to the live source.

**MUST vs SHOULD.** The GFO uses "must" and "should" with different legal force: a missing *must*
field triggers mandatory agency rejection; a missing *should* field does not. The verbatim files
preserve every "must"/"should" exactly as the State wrote it. Any validation engine must hard-block
only on *must* items and surface *should* items as warnings.

**Rules perfect ≠ document guaranteed to pass.** The verbatim rules are exact. But a generated
document passing is not something this rulebook alone can guarantee: each RFP/IFB adds
solicitation-specific requirements that live only in that document, and rejection can turn on
vendor-supplied facts the rulebook can't independently verify. Every entry here is a *universal* rule;
a per-solicitation layer must always be read fresh from the actual bid.

---

## Domain 1 — Invoicing & Payment (GFO Chapter XII)

These four sections govern how state agencies process a vendor's invoice — what an invoice must
contain and why a voucher gets rejected. They are the basis for any vendor-side invoice pre-check.

### 1.1 — XII.4.F Proper Invoice
- **Name:** XII.4.F Proper Invoice
- **Date:** REV. 03/10/2020
- **Issued by:** NYS Office of the State Comptroller (OSC), GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii4f-proper-invoice
- **Verbatim file:** `sources/source-xii-4-f-proper-invoice.md`
- **Verified:** 2026-06-28 — comma-by-comma diff PASS (identical)

### 1.2 — XII.5.B Unique Invoice Number Requirements
- **Name:** XII.5.B Unique Invoice Number Requirements
- **Date:** REV. 04/02/2015
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii5b-unique-invoice-number-requirements
- **Verbatim file:** `sources/source-xii-5-b-unique-invoice-number.md`
- **Verified:** 2026-06-28

### 1.3 — XII.7.B Voucher Denials (66-code rejection chart)
- **Name:** XII.7.B Voucher Denials
- **Date:** REV. 01/24/2020
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii7b-voucher-denials
- **Verbatim file:** `sources/source-xii-7-b-voucher-denials.md`
- **Verified:** 2026-06-28 — all 66 codes + descriptions diff PASS (identical)

### 1.4 — XII.8.B Matching
- **Name:** XII.8.B Matching
- **Date:** REV. 07/16/2018
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii8b-matching
- **Verbatim file:** `sources/source-xii-8-b-matching.md`
- **Verified:** 2026-06-28

### 1.5 — XII.5.I Prompt Payment Interest
- **Name:** XII.5.I Prompt Payment Interest
- **Date:** REV. 03/30/2026
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii5i-prompt-payment-interest
- **Verbatim file:** `sources/source-xii-5-i-prompt-payment-interest.md`
- **Verified:** 2026-06-29 — word-by-word diff PASS (identical)
- **Note:** vendor prompt-payment interest under **SFL §179-f**. Net Due Date = 30 days general / 15
  days qualified small business / 75 days final highway construction; $10 de-minimis. **SFS account
  codes: 58401 Prompt Payment Interest (general), 60311 Interest – Grants to Others, 60740 Interest
  on Late Payments – Capital Projects.** This page corrected the earlier 60740 mapping: 60740 is
  Capital Projects, not the general vendor code — the general code is **58401**. §179-p lists
  exclusions.

### 1.6 — XII.6.C Paying Prompt Contract Interest
- **Name:** XII.6.C Paying Prompt Contract Interest
- **Date:** REV. 04/01/2017
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii6c-paying-prompt-contract-interest
- **Verbatim file:** `sources/source-xii-6-c-paying-prompt-contract-interest.md`
- **Verified:** 2026-06-29 — word-by-word diff PASS (identical)
- **Note:** confirms SFS code **58403** + overpayment rate (quarterly) for NFP prompt-contracting
  interest. Cross-confirms 2.2.

### 1.7 — XII.4.B.1 Supporting Information
- **Name:** XII.4.B.1 Supporting Information
- **Date:** REV. 12/11/2019
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii4b1-supporting-information
- **Verbatim file:** `sources/source-xii-4-b-1-supporting-information.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (link-heavy page; the source's own
  typos "NYCRRand" / "gfochapter-xii" are reproduced verbatim and flagged in the file)
- **Note:** 2 NYCRR Part 6.5 (certify just/true/correct), 6.6 (internal controls), 6.7 (original
  source documentation).

### 1.8 — OSC Invoice Checklist (document-grade; attachment to XII.4.F)
- **Name:** Invoice Checklist (referenced in XII.4.F)
- **Date:** no REV stamp on the PDF (sample invoice dated 9/17/2018)
- **Issued by:** NYS OSC
- **Link:** https://www.osc.ny.gov/files/state-agencies/pdf/xii-4-f-att.pdf
- **Verbatim file:** `sources/source-invoice-checklist.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (one-page PDF, 11 callouts)
- **Note:** softer force ("may be returned unpaid or payment may be delayed") — field force governed
  by XII.4.F, not this flat list.

---

### 1.9 — SFL §109 Vendor Certificate + AC 3253-S Claim for Payment (document-grade)
- **Name:** State Finance Law §109 (per-claim vendor certificate) + GFO XII.4.A + Form AC 3253-S
- **Date:** §109 rev. 2014-09-22; GFO XII.4.A REV. 06/20/2012; AC 3253-S Revised 8/14
- **Issued by:** NY Legislature (STF Ch. 56, Art. 7); NYS OSC (XII.4.A and form)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/109 ; https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii4a-vendor-requests-payment ; https://www.osc.ny.gov/agencies/forms/ac3253s_f.pdf
- **Verbatim file:** `sources/source-stf-109-vendor-certificate.md`
- **Verified:** 2026-06-29 — three primary sources; load-bearing-passage PASS (12 passages). Pairs with 1.1: XII.4.F = what the invoice must contain; §109 = what the vendor must attest.

## Domain 2 — Contract Approval & NFP Prompt Contracting (GFO Chapter XI)

How a contract gets approved/registered before a vendor can be paid. For NFP grants, the registration
clock — not invoice delivery — is what gates payment, which is the structural core of the
late-payment problem.

### 2.1 — XI.2.F Timely Submittal of Contracts
- **Name:** XI.2.F Timely Submittal of Contracts
- **Date:** REV. 12/03/2014
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi2f-timely-submittal-contracts
- **Verbatim file:** `sources/source-xi-2-f-timely-submittal.md`
- **Verified:** 2026-06-28

### 2.2 — XI.4.A Not-for-Profit Prompt Contracting
- **Name:** XI.4.A Not-for-Profit Prompt Contracting
- **Date:** REV. 01/14/2022
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi4a-not-profit-prompt-contracting
- **Verbatim file:** `sources/source-xi-4-a-nfp-prompt-contracting.md`
- **Verified:** 2026-06-28 (longest file — full time-frame table, six-part interest test, all six worked examples)
- **Note:** SFS interest code **58403** (prompt-contracting interest); rate = Tax & Finance
  **overpayment** rate, quarterly (see `nysinterestrates.csv`). The 3%/5% in the page's worked
  examples are illustrations, not the live rate. (Procedure to pay it: XII.6.C, entry 1.6.)

### 2.3 — XI.4.B Grant Contract Budget Variance / Modification Approval
- **Name:** XI.4.B Standard Contract Language for Grant Contracts — budget-modification / variance approval requirements
- **Date:** REV. 9/11/2024
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi4b-standard-contract-language-grant-contracts-fixed-term-multiyear-contracts-and-simplified
- **Verbatim file:** `sources/source-xi-4-b-grant-budget-variance.md`
- **Verified:** 2026-06-29 — dual-source: OSC XI.4.B + DOB NYS Contract for Grants face page (H-1032) both state the threshold verbatim. Load-bearing-passage PASS (11).
- **Note:** The post-registration "approved but still not paid" rule. A budget-category transfer **≥10%** of total contract value (contracts **≤ $5M**) or **≥5%** (contracts **> $5M**) must go back to OSC for approval → halts the affected payments. Grounds the flagship RISK-MAP entry RM-1.

---

## Domain 3 — Vendor Onboarding & Bid-Submission Requirements

What a vendor must file to be eligible for award and to bid: vendor responsibility, Vendor File
registration, the standard contract appendix, and MWBE/SDVOB. A specific RFP/IFB always adds its own
solicitation-specific items on top of these universal ones.

### 3.1 — XI.16 Vendor Responsibility
- **Name:** XI.16 Vendor Responsibility
- **Date:** REV. 09/06/2019
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi16-vendor-responsibility
- **Verbatim file:** `sources/source-xi-16-vendor-responsibility.md`
- **Verified:** 2026-06-28
- **Note:** VendRep questionnaire trigger = contract **≥ $100,000** (not universal).

### 3.2 — Vendor Responsibility Forms (the four-questionnaire fork)
- **Name:** Vendor Responsibility Forms
- **Date:** forms-index page (no REV stamp)
- **Issued by:** NYS OSC, State Vendors
- **Link:** https://www.osc.ny.gov/state-vendors/vendrep/vendor-responsibility-forms
- **Verbatim file:** `sources/source-vendrep-forms.md`
- **Verified:** 2026-06-28
- **Note:** four questionnaires (construction × for-profit/NFP); CCA-2 = for-profit construction.
  AC 3273-S Profile is completed by the **agency**, not the vendor.

### 3.3 — X.3 Vendor Registration (Statewide Vendor File)
- **Name:** X.3 Overview (Vendor Registration)
- **Date:** REV. 04/01/2017
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-x/x3-overview
- **Verbatim file:** `sources/source-x-3-vendor-registration.md`
- **Verified:** 2026-06-28
- **Note:** registration is **agency-initiated**, not vendor self-service. The NYS Substitute Form
  W-9 (**AC 3237-S**) is mandatory and exclusive (IRS W-9 is rejected); live PDF:
  https://www.osc.ny.gov/files/vendors/2017-11/vendor-form-ac3237s-fe.pdf — capture as its own
  document-grade verbatim file when reproducing the form's field text.

### 3.4 — Appendix A: Standard Clauses for All New York State Contracts
- **Name:** Appendix A — Standard Clauses for New York State Contracts
- **Date:** June 2023 version (effective for new contracts/amendments after 9/1/2023)
- **Issued by:** NYS Department of Law (AG); published via OGS
- **Link:** https://ogs.ny.gov/procurement/appendix
- **Verbatim file:** `sources/source-appendix-a-june2023.md` (all 27 clauses, verbatim)
- **Verified:** 2026-06-28
- **Note:** version is a rejection risk — the **current dated version must be attached**; a superseded
  Appendix A is a defect (per OSC Contract Advisory No. 32). For NFP **grants**, the Master Grant
  Contract supersedes standalone Appendix A (see 2.2).

### 3.5 — XI.18.A MWBE (Executive Law Article 15-A)
- **Name:** XI.18.A Executive Law Article 15-A (Participation by Minority Group Members and Women)
- **Date:** REV. 03/19/2012
- **Issued by:** NYS OSC, GFO
- **Link:** https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi18a-executive-law-article-15-participation-minority-group-members-and-women-respect-state
- **Verbatim file:** `sources/source-xi-18-a-mwbe.md`
- **Verified:** 2026-06-28
- **Note:** §313 utilization plan + cure/waiver "good faith." Goal %/threshold figures are NOT on this
  page — they live in 5 NYCRR Parts 140–145 and per-solicitation.

### 3.6 — SDVOB (Service-Disabled Veteran-Owned Businesses)
- **Name:** Service-Disabled Veteran-Owned Businesses
- **Date:** vendor page (last modified 05/08/2026; no REV stamp)
- **Issued by:** NYS OSC, State Vendors
- **Link:** https://www.osc.ny.gov/state-vendors/sdvob
- **Verbatim file:** `sources/source-sdvob.md`
- **Verified:** 2026-06-28
- **Note:** statewide goal **6%** of agency discretionary spending; certification administered by
  **OGS**; vendor must be on the OGS SDVOB Directory. Statutory basis: Exec. Law Article 17-B.

### 3.7 — AC 3237-S NYS Substitute Form W-9 (document-grade)
- **Name:** NYS Substitute Form W-9 (AC 3237-S)
- **Date:** AC 3237-S (Rev. 1/17)
- **Issued by:** NYS OSC
- **Link:** https://www.osc.ny.gov/files/vendors/2017-11/vendor-form-ac3237s-fe.pdf
- **Verbatim file:** `sources/source-ac3237s-substitute-w9.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (all 5 parts + full instructions)
- **Note:** the rejection traps, verbatim — "Substitute Form W-9 is the only acceptable
  documentation. We will not accept IRS Form W-9"; "DO NOT SUBMIT FORM TO IRS"; TIN must match Legal
  Business Name; OSC withholds 28% absent a certified TIN. This is the document-grade body for the
  W-9 referenced in 3.3.

### 3.8 — AC 3290-S VendRep Questionnaire — For-Profit Non-Construction (document-grade)
- **Name:** NYS Vendor Responsibility Questionnaire — For-Profit Business Entity (AC 3290-S)
- **Date:** Rev. 03/2022
- **Issued by:** NYS OSC, VendRep program
- **Link:** https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3290s.pdf
- **Verbatim file:** `sources/source-vendrep-ac3290s-forprofit-nonconstruction.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (37 passages; fetched direct from OSC PDF)
- **Note:** 10 pages, 11 sections. 25% ownership-disclosure threshold; $25,000 fine/lien thresholds;
  "Associated Entity" framing; certification under penalty of perjury incl. "have not altered the
  content of the questionnaire in any manner." ⚠ **Rev. 03/2022** supersedes the Rev. 9/13 still on
  many third-party sites.

### 3.9 — AC 3291-S VendRep Questionnaire — Not-for-Profit Non-Construction (document-grade)
- **Name:** NYS Vendor Responsibility Questionnaire — Not-for-Profit Business Entity (AC 3291-S)
- **Date:** 03/2022
- **Issued by:** NYS OSC, VendRep program
- **Link:** https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3291s.pdf
- **Verbatim file:** `sources/source-vendrep-ac3291s-nonprofit-nonconstruction.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (35 passages; fetched direct from OSC PDF)
- **Note:** 7 pages. NFP-specific — Charities Registration Number, Trustees/Board Members, MCBO
  status, "Affiliate" framing. LOWER thresholds: **$1,000** fines, **$15,000** liens (undischarged /
  unsatisfied >120 days).

### 3.10 — AC 3292-S VendRep Questionnaire — For-Profit Construction ("CCA-2") (document-grade)
- **Name:** NYS Vendor Responsibility Questionnaire — For-Profit Construction, "CCA-2" (AC 3292-S)
- **Date:** Rev. 03/2022
- **Issued by:** NYS OSC, VendRep program
- **Link:** https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3292s.pdf
- **Verbatim file:** `sources/source-vendrep-ac3292s-forprofit-construction-cca2.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (39 passages; fetched direct from OSC PDF)
- **Note:** 10 pages, richest of the four. **5.0%** ownership disclosure; surety/bonding (Q5.3/5.4/9.4);
  Gross Sales (9.5) + Backlog (9.6); $25,000 lien threshold undischarged/unsatisfied >**90 days**;
  three required attachments **AC 3294-S / 3295-S / 3296-S**. Source quirk: two consecutive "1.0"
  questions, preserved [sic].

### 3.11 — AC 3293-S VendRep Questionnaire — Not-for-Profit Construction (document-grade)
- **Name:** NYS Vendor Responsibility Questionnaire — Construction, Not-for-Profit Business Entity (AC 3293-S)
- **Date:** Rev. 03/2022
- **Issued by:** NYS OSC, VendRep program
- **Link:** https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3293s.pdf
- **Verbatim file:** `sources/source-vendrep-ac3293s-nonprofit-construction.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS (36 passages; fetched direct from OSC PDF)
- **Note:** 7 pages, hybrid — NFP items (Charities Reg, Trustees, MCBO, "Affiliate") + construction
  items (surety Q5.2, Bonding Capacity Q9.4, Gross Sales Q9.5, Backlog Q9.6, attachments
  AC 3294-S/3295-S/3296-S). $25,000 lien threshold, >**90-day** window like the for-profit CCA-2.

### 3.12 — MWBE Pass/Fail Provisions (5 NYCRR Parts 140–145)
- **Name:** Participation by Certified MWBEs on State Contracts — pass/fail provisions of 5 NYCRR Parts 140–145 (Exec. Law Art. 15-A)
- **Date:** ESD compilation 12/02/2020; load-bearing provisions confirmed against live NYCRR 2026-06-29
- **Issued by:** NYS Dept. of Economic Development, Division of Minority and Women's Business Development (ESD/DMWBD)
- **Link:** https://esd.ny.gov/sites/default/files/MWBERegulations-120220.pdf (cross-checked vs https://www.law.cornell.edu/regulations/new-york/5-NYCRR-142.6)
- **Verbatim file:** `sources/source-mwbe-5nycrr-pass-fail.md`
- **Verified:** 2026-06-29 — triple-checked (ESD reg PDF → live NYCRR via Cornell LII → threshold cross-ref). Load-bearing-passage PASS (28).
- **Note:** Targeted capture of only the pass/fail subset — §140.1(f) commercially-useful-function, §140.1(kk) $25k/$100k thresholds, §142.4 plan fields, §142.6 deadline cascade (10/20/7/5-day), §142.8 good-faith docs, §142.9 disqualification, §142.13 debarment, §143.3(c) EEO rejection trigger. Parts 141/144/145 (agency/certification/appeals machinery) out of scope. **Honesty layer:** the 30/15/15 goal split and the 60% supplier haircut are tagged **agency guidance, NOT regulation text**. Grounds RISK-MAP entry RM-4.

> **Domain 3 still-to-add (document-grade):** *(MWBE pass/fail now captured — entry 3.12.)* Optional:
> the three construction-form attachments AC 3294-S/3295-S/3296-S as their own verbatim files. (DONE:
> AC 3237-S Substitute W-9 — 3.7; four VendRep questionnaire bodies — 3.8–3.11; MWBE pass/fail — 3.12.)

---

## Domain 4 — Statutes (verbatim from NY Open Legislation, nysenate.gov)

The GFO pages above are OSC's operational guidance; this domain holds the underlying **statute text**
itself. Captured verbatim from NY State Senate Open Legislation, which shows each section's revision
history and current revision date.

> **⚠ Freshness flag — this cluster is in active legislative flux.** Bills **S7001**, **A11179**, and
> **S4877** (2025–2026 sessions) propose material changes to the prompt-contracting / prompt-payment
> statutes: removing the agency's ability to waive NFP interest, mandating automatic advance payments
> (e.g. 25% within 30 days of execution), changing the registration clock to "register within 30 days
> of the start date," and setting a 15% minimum indirect-cost rate. **None are confirmed enacted as
> of capture.** Re-verify every §179-series section against the live page before relying on it.

### 4.1 — State Finance Law §112 (Accounting systems; approval of contracts)
- **Name:** SFL §112 — Accounting systems; approval of contracts
- **Date:** current revision 2023-03-10 (NY Open Legislation)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (STF Ch. 56, Art. 7)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/112
- **Verbatim file:** `sources/source-stf-112.md`
- **Verified:** 2026-06-29 — critical-passage check PASS (all thresholds + determination windows)
- **Note:** the OSC pre-audit authority the whole golden copy rests on. Thresholds: $50k agency /
  $85k OGS / $125k OGS centralized ($200k PO under it) / $25k non-money consideration. Determination
  windows 90 days (general) / 75 days (centralized & SUNY/CUNY) + 15-day extension.

### 4.2 — State Finance Law §179-d (Legislative intent — Article 11-A)
- **Name:** SFL §179-d — Legislative intent (Prompt Payment, Article 11-A)
- **Date:** current revision 2014-09-22 (NY Open Legislation)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (STF Ch. 56, Art. 11-A)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/179-D
- **Verbatim file:** `sources/source-stf-179-d.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS

### 4.3 — State Finance Law §179-e (Definitions — Article 11-A)
- **Name:** SFL §179-e — Definitions (Prompt Payment, Article 11-A)
- **Date:** current revision 2014-09-22 (NY Open Legislation)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (STF Ch. 56, Art. 11-A)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/179-E
- **Verbatim file:** `sources/source-stf-179-e.md`
- **Verified:** 2026-06-29 — load-bearing-passage check PASS
- **Note:** defines "contractor," "proper invoice," "receipt of an invoice," "required payment date"
  — the terms §179-f's interest clock turns on.

### 4.4 — State Finance Law §179-f (Determination of eligibility for payment of interest on amounts owed to contractors)
- **Name:** SFL §179-f — Determination of eligibility for payment of interest on amounts owed to contractors (Prompt Payment, Article 11-A)
- **Date:** current revision 2017-04-14 (NY Open Legislation)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (STF Ch. 56, Art. 11-A)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/179-F
- **Verbatim file:** `sources/source-stf-179-f.md`
- **Verified:** 2026-06-29 — **full word-by-word diff PASS (identical)** against a primary-source
  PDF/text capture of the live page (the page itself blocked the direct fetcher; captured via the
  browser instead)
- **Note:** the vendor prompt-payment core. Required payment date 30 days general / 15 days small
  business / 75 days final highway construction. Defect-notice window (subd. 3) 15 days general / 7
  days small business; missing it shrinks the payment window day-for-day. $10 de-minimis is by
  reference to §179-g. "Small business" = ≤200 employees + NY-presence tests (subd. 6).

### 4.5 — State Finance Law §179-g (Computation of interest payment — Article 11-A)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-G
- **Verbatim file:** `sources/source-stf-179-g.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS
- **Note — closes the rate-column question.** Vendor prompt-payment interest is computed at the
  **overpayment rate** under **Tax Law §1096(e)** — the same column as NFP interest, not an
  underpayment rate. Interest runs day-after-required-payment-date to payment date.

### 4.5a — State Finance Law §179-p (Inapplicability of the provisions — Article 11-A)
- **Name:** SFL §179-p — Inapplicability of the provisions (Prompt Payment, Article 11-A)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-P
- **Verbatim file:** `sources/source-stf-179-p.md` · **Verified:** 2026-07-01 — full word-by-word diff PASS against a primary-source browser capture (all six inapplicability clauses verbatim)
- **Note:** the exclusion list that gates §179-f/§179-g prompt-payment interest — eminent domain
  (cl. 1), non-Article-11-A court-judgment interest (cl. 2), government / authority / PBC /
  state-employee payees (cl. 3), third-party-payment (SSL §367-b) contractors (cl. 4),
  non-state-agency intermediary recipients (cl. 5), and comptroller set-offs (cl. 6, defined at
  §179-e(8)). Grounds the RM-2 exclusion pre-screen.

### 4.6 — State Finance Law §139-j (Restrictions on contacts during the procurement process — Article 9)
- **Date:** current revision 2026-05-29 · **Link:** https://www.nysenate.gov/legislation/laws/STF/139-J
- **Verbatim file:** `sources/source-stf-139-j.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS (body)
- **Note:** the "restricted period" lobbying-contact rules. "Procurement contract" = over **$15,000**;
  Grants and Article 11-B NFP contracts are **excluded**. ⚠ Carries a scheduled repeal: **July 31, 2028**.

### 4.7 — State Finance Law §139-k (Disclosure of contacts and responsibility of offerers — Article 9)
- **Date:** current revision 2026-05-29 · **Link:** https://www.nysenate.gov/legislation/laws/STF/139-K
- **Verbatim file:** `sources/source-stf-139-k.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS (body)
- **Note:** the §139-j companion. Subd. 5 = the offerer **certification** ("complete, true and accurate")
  + termination-for-false-certification clause that goes in every covered bid; subd. 2 = 4-year
  non-responsibility look-back. ⚠ Scheduled repeal: **July 31, 2028**.

### 4.8 — State Finance Law §163 (Purchasing services and commodities — Article 11)
- **Date:** current revision 2026-06-19 (≈20 prior revisions) · **Link:** https://www.nysenate.gov/legislation/laws/STF/163
- **Verbatim file:** `sources/source-stf-163.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS (7,920 words; body)
- **Note:** the core procurement statute. Discretionary buying thresholds (subd. 6): $150k general /
  $500k small-business & recycled / **$1.5M** MWBE & SDVOB / $200k NY food-fiber — distinct from the
  §112 *approval* thresholds. Lowest-price (commodities) vs best-value (services); responsibility
  determination (9(f)). Source quirk preserved: subd. 4 skips paragraph "f". ⚠ Scheduled repeal: **June 30, 2031**.

### 4.9 — State Finance Law §179-q (Definitions — Article 11-B)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-Q
- **Verbatim file:** `sources/source-stf-179-q.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS
- **Note:** NFP-cluster definitions. "Fully-executed contract" (def. 4) requires OSC approval + filing
  — the structural root of "clock never starts." "Written directive" (def. 14) = the work-at-risk instrument.

### 4.10 — State Finance Law §179-s (Time frames for implementation of new programs and execution of new contracts — Article 11-B)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-S
- **Verbatim file:** `sources/source-stf-179-s.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS
- **Note:** the execution clock GFO XI.4.A implements: **150 days** (RFP) / **120 days** (non-RFP) from
  appropriation, 15-day AG + 15-day Comptroller windows. Confirms the statute says 150 (the report's
  "180" was rounding). ⚠ S4877 proposes "register within 30 days of start date."

### 4.11 — State Finance Law §179-t (Time frames for the execution of renewal contracts — Article 11-B)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-T
- **Verbatim file:** `sources/source-stf-179-t.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS
- **Note:** renewal clock. 90-day intent-to-renew notice; **"deemed to continue"** if agency fails to
  notify (subd. 2); 20-day Comptroller "unusual circumstances" interest-denial determination — which
  explicitly excludes failure to plan/staff/schedule/anticipate.

### 4.12 — State Finance Law §179-u (Advance payments — Article 11-B)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-U
- **Verbatim file:** `sources/source-stf-179-u.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS
- **Note:** current law = **permissive, renewal-only** advance ("may... be entitled" via written
  directive). NOT the mandatory automatic 25% new-contract advance that A11179/S7001 *propose* —
  guards against that drift. §179-v interest eligibility turns on this.

### 4.13 — State Finance Law §179-v (Interest payments — Article 11-B)
- **Date:** current revision 2014-09-22 · **Link:** https://www.nysenate.gov/legislation/laws/STF/179-V
- **Verbatim file:** `sources/source-stf-179-v.md` · **Verified:** 2026-06-29 — full word-by-word diff PASS
- **Note:** the NFP interest section behind XI.4.A's six-part test. Subd. 6 verbatim: if AG/Comptroller
  **disapprove**, "the provisions of this section shall not be applicable" — the sourced "clock never
  starts." Rate = Tax Law **§1096(e)(1)** (subd. 2). Subd. 7 = the interest-waiver provision S7001
  proposes to repeal. ⚠ High freshness priority.

### 4.14 — General Construction Law §24 (Public holidays; half-holidays)
- **Name:** GCN §24 — Public holidays; half-holidays
- **Date:** current revision 2020-10-16 (NY Open Legislation)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (General Construction Law)
- **Link:** https://www.nysenate.gov/legislation/laws/GCN/24
- **Verbatim file:** `sources/source-gcn-24-public-holidays.md`
- **Verified:** 2026-07-05 — sanctioned statute-capture workflow (openleg-api-v3) + owner read against nysenate.gov + two independent fetch cross-checks (three-way confirmed)
- **Note:** the statutory public-holiday list for PR 2's source-backed payment clock. **L-grade mapping:** GFO XII.5.I says "legal holidays" while §24 defines "public holiday" — standard reading but interpretive; attorney-review-listed. Dynamic President/Governor-appointed days are an open class (preserved verbatim, must not be dropped).

### 4.15 — General Construction Law §25-a (Extension of time where an act is due on a Saturday, Sunday or public holiday)
- **Name:** GCN §25-a — Public holiday, Saturday or Sunday in statutes; extension of time
- **Date:** current revision 2014-09-22 (NY Open Legislation)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (General Construction Law)
- **Link:** https://www.nysenate.gov/legislation/laws/GCN/25-A
- **Verbatim file:** `sources/source-gcn-25-a-deadline-extension.md`
- **Verified:** 2026-07-05 — sanctioned statute-capture workflow (openleg-api-v3) + owner read against nysenate.gov + two independent fetch cross-checks (three-way confirmed)
- **Note:** the deadline-extension rule for PR 2's payment clock. **Both** numbered subdivisions captured verbatim — subd. 1 (act may be done the next succeeding business day; contract periods governed by §25) and subd. 2 (extended time excluded from interest computation, except month-based periods). The capture report's "1 subdivision" was a line-start counting artifact (metric corrected 2026-07-05); text is complete.

> **Domain 4 — statutes intentionally NOT captured:** §179-r (scope) and §179-w through §179-ee
> (revolving loan fund, advisory committee, agency reporting). These govern internal state program
> administration; they do not bear on document validation or the payment clock, so they are out of
> scope for the golden copy. Add later only if a specific need arises.

---

## Domain 5 — Bid-Submission Certifications & Coverage

Universal bid-submission rules grounded verbatim from primary New York State statute. Each carries a
mandatory bid-rejection or contract-bar consequence ("a bid shall not be considered for award...").
Captured this session to ground the bid-readiness checker (BUILD SPEC v2 Part A). The MWBE
five-year validity (5.1) also anchors the certification-renewal panel (Part B).

### 5.1 — Executive Law §314(5) MWBE certification validity (5 years)
- **Name:** NY Executive Law §314 — Certification (validity period, subd. 5)
- **Date:** current §314(5)(a) version effective 2026-07-01 (recertification-presumption amendment; five-year validity unchanged)
- **Issued by:** NY State Legislature; via NY Senate Open Legislation (Exec. Law Art. 15-A)
- **Link:** https://www.nysenate.gov/legislation/laws/EXC/314
- **Verbatim file:** `sources/source-exec-314-mwbe-cert-validity.md`
- **Verified:** 2026-07-02 — dual-model (GPT-5 High + Perplexity, blind) + human primary-source confirmation of the current §314(5)(a) text
- **Note:** captures the CURRENT "5.(a)" clause (with the EXC §310(23) provisional-certification exception), replacing the superseded "5." text that was effective only until 2026-07-01. Verbatim capture corrected 2026-07-03 to include the State's own statutory markers ("** NB Effective July 1, 2026" and "* NB Repealed July 1, 2028"), which the original capture had dropped. **Sunset watch:** Article 15-A authorization expires **2028-07-01** — **primary-verified 2026-07-03** against the "* NB Repealed July 1, 2028" note on nysenate.gov/legislation/laws/EXC/314. The repeal applies to all of Article 15-A (§§310–318); if it lapses the rule is dead, not merely stale. **Grade:** subd. 5(b)-(c) recertification presumption is **L (legal-interpretive)** — attorney-review-listed; product may surface it only as credential_status=RECERT_PRESUMPTION_PENDING + citation + "verify eligibility conditions," never as a determination. Subd. 5(a) five-year validity is mechanical (not L-graded).

### 5.2 — Workers' Compensation Law §57 (proof of coverage as a condition of contract)
- **Name:** Workers' Compensation Law §57 — Restriction on entering into contracts unless compensation is secured
- **Date:** Last modified Sep. 22, 2014
- **Issued by:** New York State Senate (Open Legislation)
- **Link:** https://www.nysenate.gov/legislation/laws/WKC/57
- **Verbatim file:** `sources/source-wkc-57-workers-comp.md`
- **Verified:** 2026-06-30
- **Note:** disability-benefits parallel is WCL §220(8); agency guidance OSC GFO XI.18.G.

### 5.3 — State Finance Law §139-d (statement of non-collusion in bids)
- **Name:** State Finance Law §139-d — Statement of non-collusion in bids to the state
- **Date:** Revision 2014-09-22
- **Issued by:** New York State Senate (Open Legislation)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/139-D
- **Verbatim file:** `sources/source-stf-139-d-noncollusion.md`
- **Verified:** 2026-06-30
- **Note:** the STATUTORY non-collusion section (carries the bid-rejection consequence), distinct from
  Appendix A clause 7, which is the contract-form certification.

### 5.4 — State Finance Law §139-l (sexual-harassment policy certification)
- **Name:** State Finance Law §139-l — Statement on sexual harassment, in bids
- **Date:** Revision 2019-01-18
- **Issued by:** New York State Senate (Open Legislation)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/139-L
- **Verbatim file:** `sources/source-stf-139-l-sexual-harassment.md`
- **Verified:** 2026-06-30
- **Note:** policy must meet Labor Law §201-g; agency guidance OSC GFO XI.18.I.

### 5.5 — State Finance Law §139-m (gender-based-violence policy certification)
- **Name:** State Finance Law §139-m — Statement on gender-based violence and the workplace, in bids
- **Date:** Published 2025-11-07
- **Issued by:** New York State Senate (Open Legislation)
- **Link:** https://www.nysenate.gov/legislation/laws/STF/139-M
- **Verbatim file:** `sources/source-stf-139-m-gender-based-violence.md`
- **Verified:** 2026-06-30
- **Note:** policy must meet Executive Law §575(11). Recently published (2025-11-07) — high freshness priority.

### 5.6 — Labor Law §220-i (public-work contractor registration)
- **Name:** Labor Law §220-i — Registration system for contractors and subcontractors
- **Date:** 2025 (effective Dec 30, 2024)
- **Issued by:** New York State Legislature (Justia codification of NY Labor Law)
- **Link:** https://law.justia.com/codes/new-york/lab/article-8/220-i/
- **Verbatim file:** `sources/source-lab-220-i-public-work-registration.md`
- **Verified:** 2026-06-30
- **Note:** SCOPE-GATED — applies only to public-work / Article 8 construction tenders, not every
  commodity/service bid. Subd. 6: no bid on public work unless registered; submit the certificate
  with the bid (an application is not a substitute). Certificate valid 2 years, renew 90 days before
  expiry (feeds the Part B recertification module).

### 5.7 — State Finance Law §139-h (international boycott prohibition)
- **Name:** State Finance Law §139-h — Participation in an international boycott prohibited
- **Date:** Current as of January 01, 2026
- **Issued by:** New York State Legislature (FindLaw codification; also Appendix A clause 8)
- **Link:** https://codes.findlaw.com/ny/state-finance-law/stf-sect-139-h/
- **Verbatim file:** `sources/source-stf-139-h-international-boycott.md`
- **Verified:** 2026-06-30
- **Note:** THRESHOLD-GATED at >$5,000. A material contract CONDITION (WARN), not a bid-rejection —
  the consequence is forfeiture/void on a later boycott conviction, not non-responsiveness.

---

## Pain-point layer (separate from the golden copy on purpose — different kind of knowledge)

The golden copy says what each rule **says**. These two files capture what **goes wrong** at each rule
in practice — the practitioner-level traps that aren't in the rule text but get vendors rejected,
halted, or unpaid. They are kept separate so the verbatim golden copy is never polluted with
commentary. They are the spec the Phase-2 production engine consumes: RISK-MAP says what each validator
must check; the golden copy says why; the register holds the evidence.

- **`RISK-MAP.md`** — rule-to-risk / production-spec layer. Each entry: pain-point, the exact
  golden-copy file it grounds in, process stage, failure mode, the PRE-CHECK a validator implements,
  the FEATURE it powers, prevention-vs-recovery mode, confidence. Seeded with RM-1 budget-variance
  gate (flagship, grounds in 2.3), RM-2 §179 interest-entitlement calculator (recovery; grounds in
  4.13 + 2.2), RM-3 VendRep stale-cert monitor (3.8–3.11), RM-4 MWBE deadline tracker (3.12), RM-5
  invoice certification pre-check (1.9 + 1.1). Compliance frame baked in: all features are
  information/document-validation, not advice; RM-2 must clear attorney oversight before launch.
- **`PAINPOINT-REGISTER.md`** — evidence layer. Every RISK-MAP entry traces to a register entry with
  sources and a verification status. Discipline: nothing enters RISK-MAP without (a) a verified
  golden-copy rule and (b) a register entry. NYC procurement sources quarantined as context only.



- **`nysinterestrates.csv`** + **`nys-interest-rates-README.md`** — quarter-by-quarter NYS Tax &
  Finance interest rates. A time-series dataset, not a rule. The golden copy points to it; it never
  hardcodes a rate (a frozen rate is wrong within 90 days). BOTH procurement interest regimes use the **overpayment** rate column (confirmed verbatim): NFP
  prompt-contracting interest (code **58403**, GFO XI.4.A) and vendor prompt-payment interest
  (general code **58401**; 60311 grants-to-others; 60740 capital projects) — the latter per **SFL
  §179-g**, which names Tax Law **§1096(e)** overpayment rate. (Earlier indicative underpayment
  mapping corrected 2026-06-29.)

---

## Still-to-build (next bricks, not yet in the rulebook)

- **Statutes (Domain 4):** COMPLETE for golden-copy purposes — 13 sections captured & verified (§112,
  §139-j, §139-k, §163, §179-d, §179-e, §179-f, §179-g, §179-q, §179-s, §179-t, §179-u, §179-v).
  §179-r and §179-w–§179-ee intentionally out of scope (see Domain 4 note). Re-verify the §179 cluster
  against the active-legislation freshness flag before production reliance.
- **Document-grade form bodies — remaining:** *(MWBE pass/fail now captured — entry 3.12.)* Optional:
  the three VendRep construction attachments AC 3294-S/3295-S/3296-S as their own verbatim files.
  (DONE this session: OSC Invoice Checklist 1.8; AC 3237-S Substitute W-9 3.7; four VendRep
  questionnaires 3.8–3.11; §109/AC 3253-S 1.9; XI.4.B budget-variance 2.3; MWBE pass/fail 3.12.)
- **Methodology manual:** write up the verbatim standard, the four labels, the MUST/SHOULD rule, the
  rules-perfect-vs-document-passing boundary, and the Phase-2 freshness checker — now that the method
  is stable. (Not yet started.)

## Done this session (2026-06-29)

- Domain 1 remainder: **1.5 XII.5.I**, **1.6 XII.6.C**, **1.7 XII.4.B.1** — all verified.
- Document-grade: **1.8 Invoice Checklist**, **3.7 AC 3237-S Substitute W-9** — verified.
- Document-grade VendRep: **3.8 AC 3290-S** (for-profit non-construction), **3.9 AC 3291-S** (NFP
  non-construction), **3.10 AC 3292-S** (for-profit construction / CCA-2), **3.11 AC 3293-S** (NFP
  construction) — all four questionnaire bodies fetched direct from the OSC PDFs and verified by
  load-bearing-passage check. All **Rev. 03/2022** (supersedes the Rev. 9/13 on third-party sites).
- Statutes (Domain 4): **all 13 sections** verified — §112, §139-j, §139-k, §163, §179-d, §179-e,
  §179-f, §179-g, §179-q, §179-s, §179-t, §179-u, §179-v. The blocked-fetcher ones (§179-f onward)
  were captured via browser save + full word-by-word diff. Procurement core, vendor prompt-payment
  chain (§179-d->g), and NFP prompt-contracting chain (§179-q,s,t,u,v) all complete.
- Rate-column question CLOSED: §179-g + §179-v confirm both interest regimes use the Tax Law
  §1096(e) rate — README corrected from its prior indicative underpayment guess.
- Correction propagated: vendor prompt-payment SFS code is **58401** (general), not 60740 (which is
  Capital Projects) — fixed here and in `nys-interest-rates-README.md`, traced to verified XII.5.I.
- Document-grade (added later in session): **1.9 SFL §109 + AC 3253-S** (per-claim vendor certificate,
  three primary sources), **2.3 XI.4.B budget-variance** (dual-source: OSC + DOB face page), **3.12
  MWBE pass/fail** (5 NYCRR Parts 140–145, triple-checked vs live NYCRR). All PASS.
- **Pain-point layer created:** `RISK-MAP.md` (5 feature entries RM-1…RM-5) + `PAINPOINT-REGISTER.md`
  (4 validated pain-points + candidates). Each RISK-MAP entry traced to a verified golden-copy file and
  a register evidence entry. Surfaced from practitioner forum/audit scans; budget-variance trap (RM-1)
  is the flagship, §179 interest-recovery (RM-2) the strongest P&L wedge. Compliance frame: all
  information/document-validation; RM-2 to clear attorney oversight pre-launch.
