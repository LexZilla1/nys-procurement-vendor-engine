# SOURCE TEXT — NY State Finance Law § 179-g (Computation of interest payment)

- **Name:** State Finance Law § 179-g — Computation of interest payment (Article 11-A, Interest Payments On Certain Amounts Owed By State)
- **Date:** Current revision per NY Open Legislation (Article 11-A; confirm exact revision date on the live page — see note)
- **Issued by:** New York State Legislature; published via NY State Senate Open Legislation (STF Chapter 56, Article 11-A)
- **Link (permanent identifier):** https://www.nysenate.gov/legislation/laws/STF/179-G
- **Copied exactly on:** 2026-06-29

> Source captured from the live NY Open Legislation page via the browser (nysenate.gov's
> bot-detection blocks the direct fetcher on these statute pages). Nothing here is reworded. The
> revision-date line was not included in this capture — re-open the link to record the exact "Viewing
> most recent revision (from YYYY-MM-DD)" date before production reliance, and note the
> active-legislation freshness flag on the §179 cluster (S7001 / A11179 / S4877).

---

## STATE TEXT (verbatim)

§ 179-g. Computation of interest payment. Interest payments on amounts due to a contractor pursuant to this article shall be paid to the contractor for the period beginning on the day after the required payment date and ending on the payment date for those payments required according to this article and shall be paid at the rate of interest in effect on the date when the interest payment is made. Notwithstanding any other provision of law to the contrary, interest shall be computed at the rate equal to the overpayment rate set by the commissioner of taxation and finance pursuant to subsection (e) of section one thousand ninety-six of the tax law.

---

## CITATIONS THIS TEXT POINTS TO (tagged for traceability — not part of the rule)

- NY Tax Law § 1096(e) — the overpayment rate set by the Commissioner of Taxation and Finance (this
  is the rate that feeds vendor prompt-payment interest; it is the SAME "overpayment" rate that feeds
  NFP prompt-contracting interest per GFO XI.4.A / XII.6.C)
- NY State Finance Law § 179-f — required payment date (the period start: "day after the required
  payment date")
- Interest accrues from the day after the required payment date to the payment date, at the rate in
  effect on the date the interest payment is made

---

## RATE-COLUMN DETERMINATION (verified — feeds RM-2)

**Determination:** Vendor prompt-payment interest is computed on the **OVERPAYMENT rate**
(`overpayment_rate_pct` column), NOT any underpayment rate.

**Primary-source basis (re-verified 2026-07-01 against nysenate.gov):** § 179-g states verbatim
that interest "shall be computed at the rate equal to the **overpayment rate** set by the
commissioner of taxation and finance pursuant to subsection (e) of section one thousand ninety-six
of the tax law." Tax Law § 1096(e)(2): overpayment rate = federal short-term rate + 2 points;
underpayment rate = federal short-term rate + 7 points. The +2/+7 spread confirms the two columns
in nysinterestrates.csv are correctly labeled.

**Deviation note:** The Phase 2 build brief instructed "underpayment rate." That instruction is
INCORRECT against § 179-g. The engine correctly follows verified statute over the brief. This
resolves the RM-2 open decision: `RATE_COLUMN = overpayment_rate_pct` is CONFIRMED CORRECT.

Reference values (from nysinterestrates.csv, full-text verified 2026-06-28):
2026-Q1 overpayment = 6.0% · 2026-Q2 overpayment = 5.0%.
