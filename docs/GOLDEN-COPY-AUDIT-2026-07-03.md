# Golden-Copy Audit — 2026-07-03 (read-only)

Audit of all 45 verified golden-copy sources for the **NYS Procurement Vendor
Engine**. No source file was modified. Checks per source: (1) verbatim text
present, (2) primary-source URL, (3) capture date parseable, (4) verification
flag uses a token the freshness checker actually recognizes, (5) capture
completeness (structural annotations / NB notes), (6) counted in the 45/45/45
reconciliation.

## Summary

| Total | PASS | BLOCKER | WARN |
|---|---|---|---|
| 45 | 43 | **0** | 2 |

- **Reconciliation (check 6): PASS — all 45 files parsed; source files = INDEX
  entries = VERIFICATION-REPORT rows = 45.** Re-run after the audit; unchanged.
- **No BLOCKER findings.** Every source has a non-empty `## STATE TEXT
  (verbatim)` block containing captured source text (statute text or the
  declared agency page's own words) — no summary-only / "silent model A"
  records were found. Every verification flag in use parses to a recognized
  token.
- **2 WARN findings** — secondary-host URLs (details below).

## Known-prior-failure regression checks (both clean)

- **Bare-date verification flag** (the §314 silent failure): the freshness
  checker accepts only `confirmed|verified|yes|true` (case-insensitive) —
  confirmed from `freshness_checker.py:76,89`, not assumed. Scanned all 45
  files for every `*_verified` field: the only inline flag is
  `source-exec-314-mwbe-cert-validity.md` → `sunset_date_verified: verified`
  (valid token). Companion fields (`_on`, `_source`) are not read by the
  checker (by design). Live run: `read_sunset(§314) → (2028-07-01,
  verified=True, Part KK FY2025-26 budget)`. **No bare-date pattern exists
  anywhere in the 45.**
- **Dropped NB annotations** (the §314 capture-fidelity failure): every source
  in the sunset/scheduled-repeal class was checked for its statutory markers
  in STATE TEXT — §314 (`** NB Effective July 1, 2026` + `* NB Repealed July
  1, 2028`), STF §139-j (`* NB Repealed July 31, 2028`), STF §139-k (`* NB
  Repealed July 31, 2028`), STF §163 (`* NB Repealed June 30, 2031`). **All
  four carry the State's own markers verbatim in the captured text.**

## WARN details (2)

1. **`source-lab-220-i-public-work-registration.md`** — check 2: Link is
   `law.justia.com` (Justia codification), not an official State domain. The
   file is transparent about this ("copied word-for-word from the Justia
   codification") and the capture is genuine statute text, but per audit
   policy a secondary host is a WARN. Remediation (not applied): re-verify
   against `nysenate.gov/legislation/laws/LAB/220-I` and swap the link.
   Note: the file itself flags "recently effective (Dec 30, 2024) — re-open
   and confirm before production reliance."
2. **`source-stf-139-h-international-boycott.md`** — check 2: Link is
   `codes.findlaw.com` (FindLaw codification). Same class: verbatim statute
   text on a secondary host. Remediation (not applied): re-verify against
   `nysenate.gov/legislation/laws/STF/139-H` and swap the link.

## Advisory notes (not failures)

- `source-stf-179-v.md` — mentions a REPEAL, but it is pending bill S7001
  (unenacted at capture), correctly labeled as such; no statutory NB note
  exists to capture. Not a completeness gap. Already on the §179 watch list
  (`WATCH_179_BILLS` includes S7001).
- `source-sdvob.md`, `source-vendrep-forms.md`, `source-x-3-vendor-registration.md`
  and similar OSC/OGS records — the "verbatim text" is the official agency
  page's own words (guidance/forms-index pages, not statutes). This matches
  each record's declared source type; noted so nobody mistakes agency-page
  prose for statutory text.
- `source-exec-314-mwbe-cert-validity.md` has the shortest STATE TEXT (323
  chars) — correct: it deliberately captures only the single current
  §314(5)(a) validity clause plus its two NB markers, per its VERSION NOTE.

## Audit limits (honest scope)

- The environment cannot reach State websites, so check 5 could not diff
  captures against the **live** pages. Completeness was verified by internal
  consistency (metadata claims vs captured text) plus targeted checks of the
  known failure class (sunset/repeal statutes). A networked re-verification
  pass against live pages remains the stronger guarantee.
- Check 1 "verbatim vs paraphrase" combined automated markers with manual
  reading of the shortest/highest-risk captures; all 45 hold captured source
  text.

## Per-source results (45)

| source_id | checks passed | specific failures | severity |
|---|---|---|---|
| ac3237s-substitute-w9 | 1,2,3,4,5,6 | — | PASS |
| appendix-a-june2023 | 1,2,3,4,5,6 | — | PASS |
| exec-314-mwbe-cert-validity | 1,2,3,4,5,6 | — | PASS |
| invoice-checklist | 1,2,3,4,5,6 | — | PASS |
| lab-220-i-public-work-registration | 1,3,4,5,6 | non-official domain(s): ['law.justia.com'] | WARN |
| mwbe-5nycrr-pass-fail | 1,2,3,4,5,6 | — | PASS |
| sdvob | 1,2,3,4,5,6 | — | PASS |
| stf-109-vendor-certificate | 1,2,3,4,5,6 | — | PASS |
| stf-112 | 1,2,3,4,5,6 | — | PASS |
| stf-139-d-noncollusion | 1,2,3,4,5,6 | — | PASS |
| stf-139-h-international-boycott | 1,3,4,5,6 | non-official domain(s): ['codes.findlaw.com'] | WARN |
| stf-139-j | 1,2,3,4,5,6 | — | PASS |
| stf-139-k | 1,2,3,4,5,6 | — | PASS |
| stf-139-l-sexual-harassment | 1,2,3,4,5,6 | — | PASS |
| stf-139-m-gender-based-violence | 1,2,3,4,5,6 | — | PASS |
| stf-163 | 1,2,3,4,5,6 | — | PASS |
| stf-179-d | 1,2,3,4,5,6 | — | PASS |
| stf-179-e | 1,2,3,4,5,6 | — | PASS |
| stf-179-f | 1,2,3,4,5,6 | — | PASS |
| stf-179-g | 1,2,3,4,5,6 | — | PASS |
| stf-179-p | 1,2,3,4,5,6 | — | PASS |
| stf-179-q | 1,2,3,4,5,6 | — | PASS |
| stf-179-s | 1,2,3,4,5,6 | — | PASS |
| stf-179-t | 1,2,3,4,5,6 | — | PASS |
| stf-179-u | 1,2,3,4,5,6 | — | PASS |
| stf-179-v | 1,2,3,4,5,6 | — | PASS |
| vendrep-ac3290s-forprofit-nonconstruction | 1,2,3,4,5,6 | — | PASS |
| vendrep-ac3291s-nonprofit-nonconstruction | 1,2,3,4,5,6 | — | PASS |
| vendrep-ac3292s-forprofit-construction-cca2 | 1,2,3,4,5,6 | — | PASS |
| vendrep-ac3293s-nonprofit-construction | 1,2,3,4,5,6 | — | PASS |
| vendrep-forms | 1,2,3,4,5,6 | — | PASS |
| wkc-57-workers-comp | 1,2,3,4,5,6 | — | PASS |
| x-3-vendor-registration | 1,2,3,4,5,6 | — | PASS |
| xi-16-vendor-responsibility | 1,2,3,4,5,6 | — | PASS |
| xi-18-a-mwbe | 1,2,3,4,5,6 | — | PASS |
| xi-2-f-timely-submittal | 1,2,3,4,5,6 | — | PASS |
| xi-4-a-nfp-prompt-contracting | 1,2,3,4,5,6 | — | PASS |
| xi-4-b-grant-budget-variance | 1,2,3,4,5,6 | — | PASS |
| xii-4-b-1-supporting-information | 1,2,3,4,5,6 | — | PASS |
| xii-4-f-proper-invoice | 1,2,3,4,5,6 | — | PASS |
| xii-5-b-unique-invoice-number | 1,2,3,4,5,6 | — | PASS |
| xii-5-i-prompt-payment-interest | 1,2,3,4,5,6 | — | PASS |
| xii-6-c-paying-prompt-contract-interest | 1,2,3,4,5,6 | — | PASS |
| xii-7-b-voucher-denials | 1,2,3,4,5,6 | — | PASS |
| xii-8-b-matching | 1,2,3,4,5,6 | — | PASS |
