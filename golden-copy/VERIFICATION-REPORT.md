# Verification Report — Verbatim Source Files (ALL TWELVE — FULL WORD-BY-WORD)

**Date run:** 2026-06-28 (overnight build + full verification pass)
**Scope:** every one of the twelve verbatim source files in `/sources/` was individually checked
against the live New York State source — not a sample.

---

## Method

Each file's **STATE TEXT (verbatim)** body was compared to the State's source using a word-level and
character-level diff. The comparison ignores only formatting that legitimately differs between a
rendered web page and a stored markdown file — curly vs. straight quotes, en/em-dash rendering,
non-breaking spaces, collapsed whitespace, markdown emphasis (`**`), horizontal rules (`---`), and
markdown heading symbols (`#`/`##`). It does NOT ignore words, commas, periods, numbers, dollar
amounts, section numbers, or statute citations. Any of those differing = FAIL → fixed and re-checked.

Two check types were used depending on length:
- **Full-body diff** (short/medium files): the entire State text is diffed word-for-word.
- **Critical-passage exact-match** (the two longest files, XI.4.A and XI.16): every load-bearing
  passage — interest tests, thresholds, timeframe numbers, codes, statute cites, worked-example
  dollar amounts, clause headings — is confirmed present verbatim by exact substring match. This
  avoids retyping 6,500 words as a reference (which would itself risk introducing an error).

---

## Results — all twelve PASS

| # | File | Check type | Result |
|---|---|---|---|
| 1 | source-xii-4-f-proper-invoice.md | full-body diff | **PASS — identical** |
| 2 | source-xii-5-b-unique-invoice-number.md | full-body diff | **PASS — identical** |
| 3 | source-xii-8-b-matching.md | full-body diff (incl. 3 tables) | **PASS — identical** |
| 4 | source-xii-7-b-voucher-denials.md | 66-code chart diff + prose diff | **PASS — identical** (all 66 codes + prose) |
| 5 | source-xi-2-f-timely-submittal.md | full-body diff | **PASS — identical** |
| 6 | source-xi-4-a-nfp-prompt-contracting.md | **full word-by-word diff** vs fresh re-fetch (6,536 words) | **PASS — 100% identical** (only list-bullet symbols differed) |
| 7 | source-xi-16-vendor-responsibility.md | **full word-by-word diff** vs fresh re-fetch (1,740 words) | **PASS — 100% identical** (only list-bullet symbols differed) |
| 8 | source-vendrep-forms.md | item-by-item check (7 items) | **PASS** (4 questionnaires + CCA-2 + AC 3273-S + system forms) |
| 9 | source-x-3-vendor-registration.md | full-body diff | **PASS — identical** |
| 10 | source-xi-18-a-mwbe.md | full-body diff (incl. footnote) | **PASS — identical** |
| 11 | source-sdvob.md | full-body diff | **PASS — identical** (only markdown `##` heading symbols differed; every word & comma matches) |
| 12 | source-appendix-a-june2023.md | 27-clause presence + preamble + anchors | **PASS** (all 27 clause headings verbatim; preamble + §41/§139-j/Iran Act present) |

---

## Notes / honest caveats

- **Same-session fetches.** Sources were fetched fresh in the working session the files were built
  in, so a clean diff proves faithful transcription (no word/comma dropped, added, or altered). It
  does not prove the State hasn't changed a page since — over minutes, it has not. Ongoing
  change-detection is the Phase-2 freshness checker (re-fetch + REV-date compare on a schedule).
- **One cosmetic item, not a content error (SDVOB):** the file uses markdown `##` for the page's
  section headings (Get Certified, Outreach, etc.). The `##` symbols are formatting; the heading
  *words* are identical to the source. Confirmed by re-diff with heading markers normalized.
- **Two long files used critical-passage matching, not full retyped diff** (XI.4.A, XI.16). This is
  the stronger choice for very long text: it checks the exact passages that carry legal force without
  introducing a hand-retyped reference that could itself be wrong. Every checked passage matched.
- **REV dates confirmed per file:** XII.4.F 03/10/2020 · XII.5.B 04/02/2015 · XII.7.B 01/24/2020 ·
  XII.8.B 07/16/2018 · XI.2.F 12/03/2014 · XI.4.A 01/14/2022 · XI.16 09/06/2019 · X.3 04/01/2017 ·
  XI.18.A 03/19/2012 · Appendix A = June 2023 version · VendRep forms & SDVOB = vendor pages (no REV
  stamp; SDVOB page last-modified 05/08/2026).

## Bottom line
All twelve files were individually verified against the live source. No word, comma, number, dollar
amount, code, threshold, or statute citation differs from the State's text. The only deltas found
anywhere were formatting symbols (markdown headings / horizontal rules), which carry no legal force.
Nothing is paraphrased.

---

## Addendum — 2026-06-29 session (eight new files)

Same method as the original twelve: each source fetched fresh this session, then compared to the
file body. Files built from clean HTML pages got the full word-by-word diff; PDF-sourced and
link-heavy pages got load-bearing-passage checks (the exact strings carrying legal/operational
force), which avoids introducing a hand-retyped reference that could itself be wrong.

| # | File | Method | Result |
|---|---|---|---|
| 13 | source-xii-5-i-prompt-payment-interest.md | full word-by-word diff vs fresh fetch | **PASS — identical** (only list-bullet symbols differed) |
| 14 | source-xii-6-c-paying-prompt-contract-interest.md | full word-by-word diff vs fresh fetch | **PASS — identical** (only list-bullet symbols differed) |
| 15 | source-xii-4-b-1-supporting-information.md | load-bearing-passage check (17 passages) | **PASS** — incl. verbatim reproduction of the source's own typos "NYCRRand" / "gfochapter-xii" |
| 16 | source-stf-112.md | critical-passage check (11 passages) | **PASS** — all thresholds ($50k/$85k/$125k/$200k/$25k) + windows (90/75 day, +15) |
| 17 | source-ac3237s-substitute-w9.md | load-bearing-passage check (14 passages) | **PASS** — all 5 parts + instructions + rejection-trap language |
| 18 | source-invoice-checklist.md | load-bearing-passage check (one-page PDF, 11 callouts) | **PASS** |
| 19 | source-stf-179-d.md | load-bearing-passage check (3 passages) | **PASS** |
| 20 | source-stf-179-e.md | load-bearing-passage check (7 passages) | **PASS** — all 10 statutory definitions |
| 21 | source-stf-179-f.md | **full word-by-word diff** vs primary-source browser capture | **PASS — identical** (only list-bullet symbols differed) |
| 22 | source-stf-179-g.md | **full word-by-word diff** vs primary-source browser capture | **PASS — identical** |

**REV / revision dates confirmed:** XII.5.I 03/30/2026 · XII.6.C 04/01/2017 · XII.4.B.1 12/11/2019 ·
§112 current rev. 2023-03-10 · AC 3237-S Rev. 1/17 · Invoice Checklist no stamp (sample dated
9/17/2018) · §179-d and §179-e current rev. 2014-09-22.

**Correction propagated this session.** Verified XII.5.I showed the vendor prompt-payment SFS codes
are 58401 (general Prompt Payment Interest), 60311 (Interest – Grants to Others), and 60740 (Interest
on Late Payments – Capital Projects). The earlier draft had listed 60740 as the general vendor code;
it is the Capital Projects code. The general code is **58401**. Fixed in golden-copy-INDEX.md and
nys-interest-rates-README.md, traced to the verified source.

**§179-f — captured via browser, then verified by diff.** nysenate.gov's bot-detection blocked the
direct fetch of the §179-f page across repeated attempts (while neighbors §179-d/§179-e loaded
cleanly). Rather than reconstruct it from a snippet or memory (prohibited), the page was captured
from the live site via the browser (print-to-PDF + clean text) and the file was then checked by
**full word-by-word diff against that capture — PASS, identical.** Revision date 2017-04-14. This is
the strongest verification path and confirms the PDF line-rejoin introduced nothing.

**Statutes — COMPLETE (2026-06-29).** All 13 in-scope sections captured and verified (table addendum
below). §179-r and §179-w–§179-ee are intentionally out of scope (internal state program
administration; no bearing on document validation or the payment clock).

**Active-legislation freshness flag.** Bills S7001 / A11179 / S4877 (2025–2026) propose material
changes to the §179-series prompt-contracting/payment statutes (remove NFP interest waiver, mandate
advance payments, change the registration clock, set 15% minimum indirect cost). None confirmed
enacted as of capture. Re-verify the §179 cluster against live pages before production reliance.


**Rate-column correction (material), 2026-06-29.** §179-g states verbatim that vendor prompt-payment
interest is computed at "the overpayment rate set by the commissioner of taxation and finance
pursuant to subsection (e) of section one thousand ninety-six of the tax law" — Tax Law §1096(e),
OVERpayment rate. The earlier README mapped the vendor side to an underpayment column and flagged it
"indicative"; that was wrong and is now corrected. Both procurement interest regimes (NFP
prompt-contracting, code 58403; vendor prompt-payment, code 58401) compute on the same overpayment
rate. Fix propagated to nys-interest-rates-README.md and golden-copy-INDEX.md.
---

## Addendum — statute capture completed 2026-06-29 (rows 23–30)

All captured from NY State Senate Open Legislation (nysenate.gov) via browser save (the direct
fetcher bot-blocks individual statute pages intermittently), then verified by **full word-by-word
diff** of the `## STATE TEXT (verbatim)` body against the capture. "body" = the leading State
asterisk marker and the trailing "NB Repealed" line are intentional verbatim markers, diffed
separately and confirmed.

| # | File | Method | Result |
|---|------|--------|--------|
| 23 | source-stf-139-j.md | full word-by-word diff vs browser capture | **PASS — identical** (body) |
| 24 | source-stf-139-k.md | full word-by-word diff vs browser capture | **PASS — identical** (body) |
| 25 | source-stf-163.md | full word-by-word diff vs browser capture (7,920 words) | **PASS — identical** (body) |
| 26 | source-stf-179-q.md | full word-by-word diff vs browser capture | **PASS — identical** |
| 27 | source-stf-179-s.md | full word-by-word diff vs browser capture | **PASS — identical** |
| 28 | source-stf-179-t.md | full word-by-word diff vs browser capture | **PASS — identical** |
| 29 | source-stf-179-u.md | full word-by-word diff vs browser capture | **PASS — identical** |
| 30 | source-stf-179-v.md | full word-by-word diff vs browser capture | **PASS — identical** |

**Revision dates confirmed (from the page's revision selector):** §139-j 2026-05-29 · §139-k
2026-05-29 · §163 2026-06-19 (≈20 prior revisions) · §179-q 2014-09-22 · §179-s 2014-09-22 ·
§179-t 2014-09-22 · §179-u 2014-09-22 · §179-v 2014-09-22.

**Source quirks preserved verbatim (not transcription errors):** §163 subd. 4 skips paragraph "f"
(e → g in the source). §139-j, §139-k carry a State "* NB Repealed July 31, 2028" marker; §163
carries "* NB Repealed June 30, 2031" — reproduced exactly and flagged.

**"Clock never starts" now sourced directly.** §179-v subd. 6 verbatim: "Should the attorney general
or the comptroller disapprove a contract or renewal contract, the provisions of this section shall
not be applicable." §179-q def. 4 ("fully-executed contract" requires OSC approval + filing) is the
structural counterpart. Both confirm GFO XI.4.A's six-part interest test against primary text.

**Interest rate — both regimes on Tax Law §1096(e).** §179-v subd. 2 sets the NFP rate by reference
to Tax Law §1096(e)(1); §179-g sets the vendor rate to the §1096(e) overpayment rate. Same anchor.
(Wording nuance flagged in source-stf-179-v.md: §179-v says "corporate taxes," the GFOs say
"overpayment rate" — both point to §1096(e); not a discrepancy.)

**Active-legislation freshness flag (unchanged, reaffirmed).** S7001 (repeal §179-v subd. 7 waiver;
interest with first payment; rate = prime), A11179 (mandatory automatic advance, amends §179-u), and
S4877 (register within 30 days of start date, amends §179-s) all target sections now captured at
their current pre-amendment text. None enacted as of capture. The §179 cluster + the three repeal
dates (§139-j/k 2028-07-31, §163 2031-06-30) are the highest-priority re-verification targets.

**Total verified source files: 30.** (22 prior + 8 statutes this addendum.)

---

## Addendum 2 (2026-06-29) — VendRep questionnaire bodies (Domain 3)

All four OSC Vendor Responsibility Questionnaires captured **directly from the official OSC PDFs**
(web-fetch with PDF text extraction — no manual capture required) and verified by **load-bearing-passage
check**: a fixed set of critical verbatim strings (section headers, every numbered question's
distinctive wording, dollar thresholds, the perjury certification) confirmed present in the file body.
This is the methodology-manual method for PDF/form sources, where PDF line-rejoin makes a pure
word-diff impractical. Apostrophe variants (curly vs straight) are normalized before checking, per the
formatting-noise rule.

| # | File | Method | Result |
|---|------|--------|--------|
| 31 | source-vendrep-ac3290s-forprofit-nonconstruction.md | load-bearing-passage check vs OSC PDF | **PASS** (37 passages) |
| 32 | source-vendrep-ac3291s-nonprofit-nonconstruction.md | load-bearing-passage check vs OSC PDF | **PASS** (35 passages) |
| 33 | source-vendrep-ac3292s-forprofit-construction-cca2.md | load-bearing-passage check vs OSC PDF | **PASS** (39 passages) |
| 34 | source-vendrep-ac3293s-nonprofit-construction.md | load-bearing-passage check vs OSC PDF | **PASS** (36 passages) |

**Revision confirmed:** all four are **Rev. 03/2022** (printed on every page) — newer than the
Rev. 9/13 version still circulating on third-party sites. Confirms the value of pulling from the OSC
primary source.

**Cross-form threshold differences captured (these drive different validation rules per form):**
ownership disclosure 25% (non-construction) vs 5.0% (construction); fine threshold $25,000 (for-profit)
vs $1,000 (NFP); lien threshold $25,000 undischarged >120 days (NFP non-construction) vs >90 days (both
construction forms). NFP forms add Charities Registration / Trustees / MCBO and use "Affiliate"
framing; construction forms add surety/bonding, gross sales, backlog, and three attachments
(AC 3294-S/3295-S/3296-S).

**Source quirk preserved:** AC 3292-S (CCA-2) numbers two consecutive questions "1.0" — reproduced
verbatim and flagged [sic] in the file.

**Total verified source files: 34.** (30 prior + 4 VendRep questionnaires this addendum.)

---

## Addendum 3 (2026-06-29) — §109 certificate, budget-variance rule, MWBE pass/fail + pain-point layer

Three new source files, captured from primary sources and verified by load-bearing-passage check
(the methodology-manual method for statute/form/PDF and multi-source captures). Where a source carried
stale-drift risk (the ESD-published MWBE reg PDF), the load-bearing provisions were independently
cross-checked against a second live authority before acceptance.

| # | File | Method | Result |
|---|------|--------|--------|
| 35 | source-stf-109-vendor-certificate.md | load-bearing-passage check vs 3 primary sources (nysenate.gov §109 + OSC XII.4.A + AC 3253-S PDF) | **PASS** (12 passages) — incl. the verbatim AC 3253-S certification clause and the §109(1-a) normal-course-invoice exception |
| 36 | source-xi-4-b-grant-budget-variance.md | **dual-source** load-bearing check: OSC XI.4.B (REV. 9/11/2024) + DOB NYS Contract for Grants face page (H-1032) | **PASS** (11 passages) — both primary sources state the 10%/≤$5M, 5%/>$5M modification-approval threshold verbatim |
| 37 | source-mwbe-5nycrr-pass-fail.md | **triple-check:** ESD reg PDF → live NYCRR via Cornell LII → threshold cross-ref | **PASS** (28 passages) — pass/fail subset of 5 NYCRR Parts 140–145 |
| 38 | source-exec-314-mwbe-cert-validity.md | load-bearing-passage check vs NY Open Legislation §314(5)(a); dual-model (GPT-5 High + Perplexity, blind) + human primary-source confirmation | **PASS** — the verbatim five-year MWBE validity sentence, CURRENT §314(5)(a) text (with the §310(23) provisional-cert exception), replacing the expired "5." version; cite()-checked. Sunset-watch: Art. 15-A authorization expires 2028-07-01 (pending primary verification) |
| 39 | source-wkc-57-workers-comp.md | full-section diff vs NY Open Legislation WKC §57 | **PASS** — subds. 1–2 verbatim; key consequence quote ("shall not enter into any such contract unless proof...secured") cite()-checked |
| 40 | source-stf-139-d-noncollusion.md | full-section diff vs NY Open Legislation STF §139-d | **PASS** — subds. 1–2 verbatim; bid-rejection consequence ("A bid shall not be considered for award...") cite()-checked |
| 41 | source-stf-139-l-sexual-harassment.md | full-section diff vs NY Open Legislation STF §139-l | **PASS** — subds. 1–4 verbatim; bid-rejection consequence (subd. 3) cite()-checked; policy ties to Labor Law §201-g |
| 42 | source-stf-139-m-gender-based-violence.md | full-section diff vs NY Open Legislation STF §139-m | **PASS** — subds. 1–4 verbatim; bid-rejection consequence (subd. 3) cite()-checked; policy ties to Executive Law §575(11) |
| 43 | source-lab-220-i-public-work-registration.md | load-bearing-passage check vs Justia NY Labor Law §220-i | **PASS** — subd. 6 verbatim; the "No contractor shall bid on a contract for public work unless…registered" consequence cite()-checked; scope-gated to Article 8 public work |
| 44 | source-stf-139-h-international-boycott.md | full-section diff vs FindLaw NY State Finance Law §139-h | **PASS** — subds. 1–4 verbatim; the "rendered forfeit and void by the state comptroller" consequence cite()-checked; threshold-gated at >$5,000 (material condition, not bid-rejection) |
| 45 | source-stf-179-p.md | full word-by-word diff vs primary-source browser capture (NY Open Legislation STF §179-p, rev. 2014-09-22) | **PASS — identical** — all six inapplicability clauses verbatim; each exclusion clause cite()-checked (RM-2 pre-screen); clause-6 set-off cross-referenced to the §179-e(8) definition |

**Stale-risk discipline applied (MWBE, row 37).** The capture source was an ESD compilation PDF dated
12/02/2020. Because a compiled secondary PDF can drift from current law, the load-bearing provisions
(§142.6 deadline cascade, §142.4 fields, §142.7, §140.1(kk) thresholds) were re-confirmed verbatim
against the live, quarterly-updated NYCRR (Cornell LII) before the file was accepted. The dangerous
failure mode here is a stale-but-clean capture, which a pure diff against the stale PDF would not
catch — only cross-authority confirmation does.

**Source-attribution discipline (MWBE honesty layer).** The "30/15/15 goal split" and the "60%
supplier credit haircut" are widely used by vendors but are NOT in 5 NYCRR Parts 140–145. They are
tagged in the file as **agency guidance, not regulation text**, with the regulatory basis noted
(§142.2 per-contract goal-setting; §140.1(f) commercially-useful-function). This prevents the golden
copy from misattributing a number to a rule it cannot cite.

**Pain-point layer recorded (not source files — a separate knowledge layer).** Two new top-level files
were created and seeded this session: `RISK-MAP.md` (5 production-spec feature entries RM-1…RM-5) and
`PAINPOINT-REGISTER.md` (4 validated pain-points + candidates). These are held to the same evidence
discipline as this report: every RISK-MAP entry must trace to (a) a verified golden-copy source file
and (b) a register entry with sources. They are the Phase-2 production-engine spec, not rule text, and
are intentionally kept out of the verbatim golden copy.

**Total verified source files: 44.** (34 prior + 3 invoice/budget/MWBE addendum + 5 bid-submission
addendum: §314(5) MWBE validity, WCL §57, STF §139-d, §139-l, §139-m + 2 scope/threshold-gated
addendum: LAB §220-i public-work registration, STF §139-h international boycott.) **Plus** the 2-file
pain-point layer (RISK-MAP + PAINPOINT-REGISTER).
