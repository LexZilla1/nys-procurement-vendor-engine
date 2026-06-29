# NYS Interest Rate History — companion to `nysinterestrates.csv`

**What this is.** A quarter-by-quarter record of the New York State Department of Taxation
and Finance interest rates, captured from primary source (tax.ny.gov). It is a time-series
**dataset**, not a rule — it grows by one row each quarter and existing rows never change.
It is deliberately kept SEPARATE from the golden copy (which holds rules, each re-verified
against a source revision date). The golden copy *points to* this dataset; it does not embed
rate numbers, because a frozen rate is wrong within 90 days.

**Why it exists.** Interest on a *past* late payment must be calculated using the rate in
effect *during that period*, not today's rate. A late payment spanning several quarters is
computed quarter-by-quarter (see the worked examples in GFO XI.4.A). A stored history makes
any past calculation instant and removes the need to re-fetch archived quarters one at a time.

## Which rate feeds which interest regime (DO NOT confuse these)

| Regime | Statute / GFO | SFS code | Rate column to use |
|---|---|---|---|
| **NFP Prompt-Contracting interest** | SFL Article XI-B / GFO XI.4.A | 58403 | **`overpayment_rate_pct`** |
| **Vendor Prompt-Payment interest** | SFL §179-f, §179-g / GFO XII.5.I | **58401** (primary) | **`overpayment_rate_pct`** ✓ |

\* **CORRECTED 2026-06-29 against full-text-verified GFO XII.5.I (REV. 03/30/2026) and SFL §179-g.**
Three fixes vs. the earlier draft:
1. **SFS code.** XII.5.I lists three prompt-payment account codes, not one: **58401 – Prompt Payment
   Interest** (the general code), **60311 – Interest – Grants to Others**, and **60740 – Interest on
   Late Payments – Capital Projects**. The earlier README listed 60740 as *the* vendor code; in fact
   60740 is the **Capital Projects** code. Use **58401** as the general/default vendor prompt-payment
   code; 60311 and 60740 are situational (grants-to-others and capital-projects respectively).
2. **Statute.** The governing statute for prompt *payment* is **SFL §179-f** (with §179-p listing
   exclusions); "Article XI-A" was the brief's shorthand. The verbatim source cites §179-f / §179-p.
3. **Rate column — NOW CLOSED, verbatim.** The earlier draft mapped the vendor side to
   `underpayment_697j_rate_pct` and flagged it "indicative." That was WRONG. **SFL §179-g** (Computation
   of interest payment) states verbatim that prompt-payment interest "shall be computed at the rate
   equal to the **overpayment rate** set by the commissioner of taxation and finance pursuant to
   **subsection (e) of section one thousand ninety-six of the tax law**" — i.e. **Tax Law §1096(e),
   the OVERPAYMENT rate.** So vendor prompt-payment interest uses the **`overpayment_rate_pct`**
   column — the SAME overpayment rate as NFP prompt-contracting interest, NOT an underpayment rate.
   The two interest regimes differ in trigger, statute, and SFS code, but both compute on the
   overpayment rate.

## Column meanings
- `overpayment_rate_pct` — the **overpayment** rate set by the Commissioner of Taxation and Finance.
  **This is the operative column for BOTH procurement interest regimes:** NFP prompt-contracting
  interest (per GFO XI.4.A) AND vendor prompt-payment interest (per SFL §179-g, which cites Tax Law
  **§1096(e)** by name). Record the §1096(e) overpayment figure here each quarter.
- `underpayment_697j_rate_pct` — Tax Law §697(j) (income tax) underpayment rate. Recorded for
  reference; **NOT** used for procurement interest (the earlier draft's vendor-side guess — corrected).
- `underpayment_1096e_rate_pct` — Tax Law §1096(e) (corporation tax) underpayment rate. Recorded
  for completeness; the UNDERpayment direction is not the one used for procurement interest. (Note:
  §179-g points to the §1096(e) OVERpayment rate, captured in `overpayment_rate_pct` above.)

## Maintenance (Phase 2)
- A scheduled quarterly job appends one new row from the then-current tax.ny.gov rate page.
  This is the natural sibling of the golden-copy freshness checker — one quarterly run can both
  re-verify OSC pages AND append the new rate row.
- Each row must carry its own `source_url` and `verified_on`. Never append a rate that wasn't
  read from the primary tax.ny.gov page for that quarter.
- Existing rows are immutable. Corrections happen by replacing a row only if it's found to have
  been recorded wrong against its own source.

## Current coverage
- 2026-Q1 and 2026-Q2 only (both full-text verified 2026-06-28).
- **Back-history not yet collected.** Extending earlier requires one verified fetch per quarter
  from that quarter's archived tax.ny.gov page. Decide how many years of coverage are needed.
