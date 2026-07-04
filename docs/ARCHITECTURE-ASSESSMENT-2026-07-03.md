# Architecture Scalability Assessment — 2026-07-03 (read-only)

Can the **NYS Procurement Vendor Engine** expand to new jurisdictions (federal
FAR/SBA first, NY Public Authorities Law, other states later) as content-pack
drop-ins — or are NY assumptions baked in? Assessed against the three-layer
target: **L1** universal schema (code-enforced), **L2** swappable content packs
(citation-ID lookup, never hardcoded), **L3** jurisdiction-blind tooling.

No code or golden-copy file was modified. The two WARN link swaps authorized by
the task were **not performed** — they require live re-verification first and
the network blocks State sites (see Area 5).

## Verdict summary

| # | Area | Verdict | One-line basis |
|---|---|---|---|
| 1 | Schema | **YELLOW** | Machine-validated and highly consistent — but no jurisdiction/citation-ID fields; NY implicit; count hardcoded |
| 2 | Coupling | **YELLOW** | NY specifics are concentrated in module-top data tables, not spread through control flow — but zero of it is behind an adapter |
| 3 | Tooling portability | **YELLOW** | Parser ~portable; freshness has NY content-in-code; LLM reader + extractor have NY hardwired in prompts/patterns |
| 4 | Lookup layer | **YELLOW (worst offender)** | No citation index — rules referenced by hardcoded filename constants + verbatim quote literals inside .py |
| 5 | Verbatim sufficiency | **GREEN (internal) / UNVERIFIED (live)** | No fragments detected internally; live re-verification impossible (network blocked) — 45 URLs listed for manual check |
| 6 | Coverage map | **YELLOW** | 26/45 sources consumed by runtime checks; 19 orphans (deliberate groundwork, listed); all 5 named NY areas present as text, 2 lack runtime checks |

**Nothing is RED. Nothing blocks NY operation today.** The gap between here and
"federal is a drop-in" is a bounded refactor (~8–10 code files + one mechanical
pass over the 45 sources), detailed at the end.

---

## Area 1 — Schema: YELLOW

**Formally enforced, not convention.** `parse_golden_copy.py` machine-validates
every file and exits 1 on violation: 5 required non-empty header labels
(`Name, Date, Issued by, Link, Copied exactly on` — lines 33–36, 141–146),
non-empty `## STATE TEXT (verbatim)` (103, 158), non-empty `## CITATIONS`
(105, 163), section ordering (107), plus the 45/45/45 three-way reconciliation.

**Structural consistency across the 45: excellent.** Census: all 45 carry all
5 modal labels and both canonical sections; zero deviations. Extra sections are
additive one-offs (§314's `SUNSET / AUTHORIZATION`; agency-page subheads in
sdvob/vendrep-forms) — allowed by the parser, harmless.

**What's missing for L1:**
- **No jurisdiction field (0/45)** — "NY" is implicit in filenames and prose.
- **No citation-ID field (0/45)** — files are addressed by filename only.
- `EXPECTED_COUNT = 45` hardcoded (parse_golden_copy.py:31); single flat
  `golden-copy/sources/` tree — no pack concept. (Hygiene: docstring line 9
  still says "all three must be 37" — stale.)

**Minimal refactor:** add `Jurisdiction:` + `Citation-ID:` to REQUIRED_FIELDS;
mechanical backfill across 45 files; per-pack manifest carrying its own
expected count. *Files: parse_golden_copy.py + 45 sources (mechanical).*
**Timing: citation-ID is worth adding before Step 1 Triage** (it unlocks Area
4 cheaply); jurisdiction field can wait until pack #2.

## Area 2 — Coupling inventory: YELLOW

Every place jurisdiction-specific logic lives outside a separable adapter
(pipeline + tooling, tests excluded):

| File:lines | What | Class |
|---|---|---|
| freshness_checker.py:55–56, 415–416, 562 | `WATCH_179_BILLS = ["S7001","A11179","S4877"]` + §179 filename regex — NY bill-watch hardcoded | NY content in code |
| freshness_checker.py:66–71, 93–95 | `SUNSET_SEED` keyed on NY source filenames with NY repeal dates | NY content in code |
| freshness_checker.py:244 | GFO `REV. MM/DD/YYYY` date convention (OSC-specific format, keyword-anchored) | NY format, isolated |
| validator.py:317–326, 328–380 | Source-file constants (XII4F, STF109, XI4B, MWBE, STF179V/F/P/E…) + §179-p exclusion tables + §179-e(8) set-off text | NY rule tables in code |
| validator.py:382–385 | VendRep form-number → source map (AC 3290-S…) | NY rule tables in code |
| bid_readiness.py:48–104, 139–160 | CHECKS table: 13 NY checks with source files + verbatim quotes (§139-d/-h/-l/-m, §165-a, Tax §5-a, §165, LAB 220-i, WKC §57…) | NY rule tables in code |
| gap_analysis.py:77–92 | CATALOG seed (MWBE §314 fixed-period:5y etc.) | NY rule tables in code |
| cert_renewal.py:40–43 | EXEC314 / SDVOB source constants + quotes | NY rule tables in code |
| llm_reader.py:35–63 | SYSTEM prompt: "New York State procurement analyst", NYS doc taxonomy (VendRep, MWBE, SDVOB, Iran, Appendix A…) | NY hardwired in tooling |
| tender_extractor.py (8 hits) | NY-flavored extraction patterns | NY hardwired in tooling |

**The good news:** the coupling is *concentrated in module-top data structures*
(dicts, constants, dataclass seeds) — not smeared through control flow. The
engines that consume them (`evaluate_requirement`, the Finding builder,
`read_sunset`, `cite()`) are already rule-agnostic. The refactor is
externalization, not rewrite. The "NB Repealed" parsing the task asked about:
freshness_checker does **not** parse NB annotations at all — sunset comes from
inline metadata fields or the seed table — so the NY Senate formatting question
collapses into "move SUNSET_SEED to pack config."

## Area 3 — Tooling portability: YELLOW

Would each tool run unmodified on a federal (eCFR/acquisition.gov) pack?

- **parse_golden_copy.py — nearly.** Labels and sections are jurisdiction-
  neutral. Breaks: `EXPECTED_COUNT=45`, fixed `golden-copy/` root, single
  INDEX/VERIFICATION pair. Fix = pack-path + per-pack count config. *Small.*
- **freshness_checker.py — mostly.** Header parsing, link handling, drift
  logic, and the inline sunset axis (`sunset_watch`/`authorization_expires`/
  `sunset_date_verified`) are generic — a federal file using those fields
  works today. Breaks: `SUNSET_SEED` and `WATCH_179_*` are NY content in
  code; the `REV.` date branch is OSC-specific (harmless elsewhere — it just
  won't match; eCFR dates parse via the ISO/month-name branches). *Small.*
- **Reconciliation/audit — yes** aside from the same path/count constants.
- **llm_reader.py / tender_extractor.py — no.** NY persona, NY document
  taxonomy, NY patterns are hardwired (llm_reader.py:35–63). A federal RFP fed
  to this reader would be read through NY glasses (asks for VendRep/MWBE/SDVOB,
  not SAM registration/reps-and-certs). Fix = per-jurisdiction prompt/pattern
  packs. *Moderate but mechanical.*

## Area 4 — Lookup layer: YELLOW (the load-bearing gap)

**Today:** pipeline references rules via (a) hardcoded filename constants
(`validator.py:317–326`, `cert_renewal.py:40–43`), (b) inline filename+quote
tuples (`bid_readiness.py:48–104`), (c) a seeded catalog (`gap_analysis.py:
77–92`) — all *inside .py files*. The single choke-point `GoldenCopy.cite()`
(validator.py:166–215) is genuinely jurisdiction-blind: verbatim-substring
gating over any source dir. There is **no citation-ID index anywhere**.

**Can a second pack mount without touching pipeline logic? No.** Adding
federal rules today means editing four Python modules.

**Minimal refactor:** per-pack manifest (`packs/<jur>/catalog.json`:
`citation_id → {source_file, quote, rule_params}`), plus thin loaders
replacing the module-top tables in bid_readiness / gap_analysis / validator /
cert_renewal. `cite()` stays exactly as is. *Files: 4 pipeline modules + 1 new
manifest + tests.* **Timing: must precede pack #2; not required for Step 1
Triage** (Triage consumes NYSCR ad metadata, not golden-copy rules) — but do
the citation-ID field (Area 1) at Triage time so new code stops deepening
filename coupling.

## Area 5 — Verbatim sufficiency: GREEN internally; live check BLOCKED

**Internal completeness (all 45):** section-boundary scan for fragments —
bodies ending mid-sentence, truncation markers, ellipses. After correcting for
the trailing `---` separator, 3 heuristic flags remained and all cleared on
manual read (Appendix A ends with its transcription note; the two VendRep
non-construction forms end at the signature-block line — the natural end of a
form capture). All four sunset-class statutes carry their closing `* NB
Repealed …` markers as the last line of STATE TEXT (§314, §139-j, §139-k,
§163) — captures span first word to last annotation. **No fragment findings.**

**Live re-verification: NOT POSSIBLE from this environment.** Direct fetch,
WebFetch, and headless-browser all return 403 at the egress proxy for State
sites (re-tested this session against nysenate.gov). Consequently the **two
WARN link swaps (lab-220-i → nysenate.gov LAB/220-I; stf-139-h → nysenate.gov
STF/139-H) were NOT performed** — swapping a citation link to a page that
could not be re-verified would violate the golden-copy methodology. They stay
WARN. The full 45-URL manual-check list is Appendix B; the two swap targets
are marked.

## Area 6 — Coverage map: YELLOW

**Runtime checks → sources (26/45 consumed):**

| Check (module) | Golden-copy source(s) |
|---|---|
| RM-1 budget variance (validator) | xi-4-b-grant-budget-variance |
| RM-2 gated §179 interest (validator) | stf-179-v, -f, -p, -e; xi-4-a; xii-5-i |
| RM-3 material change / VendRep (validator) | vendrep-ac3290s/3291s/3292s/3293s |
| RM-5 invoice pre-flight (validator) | xii-4-f-proper-invoice, stf-109-vendor-certificate |
| MWBE bid pass/fail (validator) | mwbe-5nycrr-pass-fail |
| Bid-readiness: EEO / MWBE / SDVOB | mwbe-5nycrr, xi-18-a-mwbe, sdvob |
| Bid-readiness: VendRep / non-collusion / WC | xi-16-vendor-responsibility, stf-139-d, wkc-57 |
| Bid-readiness: §139-l / §139-m / §139-h / 220-i | stf-139-l, stf-139-m, stf-139-h, lab-220-i |
| Bid-readiness: Iran §165-a / Tax §5-a / §165 hardwoods | appendix-a-june2023 (clauses) |
| Cert renewal: MWBE 5-yr / SDVOB | exec-314-mwbe-cert-validity, sdvob |
| Gap analysis catalog | exec-314, xi-16, wkc-57 |
| Freshness sunset axis | exec-314 (inline), stf-139-j/-k, stf-163 (seed) |

**Orphan sources — no runtime consumer (19):** ac3237s-substitute-w9,
invoice-checklist, stf-112, stf-139-j, stf-139-k, stf-179-d/-g/-q/-s/-t/-u,
vendrep-forms, x-3-vendor-registration, xi-2-f-timely-submittal,
xii-4-b-1-supporting-information, xii-5-b-unique-invoice-number,
xii-6-c-paying-prompt-contract-interest, xii-7-b-voucher-denials,
xii-8-b-matching. Pattern: the §179 siblings and GFO XII invoice cluster are
Step-8 (post-award/payment) groundwork; 139-j/-k feed the freshness seed only;
179-g grounds the RM-2 rate-column decision **by comment only**
(validator.py:89) — worth promoting to a real `cite()` when RM-2 is next
touched. Orphaned-but-captured is consistent with the build order; none look
like dead weight. **Checks with no source: none** — every runtime check cites
a golden source (the citation-integrity tests enforce this).

**Named NY coverage areas:**

| Area | Text in golden copy? | Runtime check? |
|---|---|---|
| Tax Law §5-a certification | ✅ appendix-a clause | ✅ bid_readiness `sales_tax_5a` |
| Iran Divestment (SFL §165-a) | ✅ appendix-a clause | ✅ bid_readiness `iran_divestment` |
| Consultant disclosure (§163(4)(g)) | ✅ appendix-a clause 23 | ❌ no dedicated check |
| Prevailing wage beyond §220-i | ✅ appendix-a §220/§220-e clauses | ❌ no dedicated check (only 220-i registration) |
| OGS centralized-contract rules | ⚠️ partial — §163/§112 text captured; no OGS guidance-document source | ❌ no dedicated check |

---

## Total cost of making federal a content-pack drop-in

**Bounded refactor, no rewrite.** The engines are already rule-agnostic; the
work is externalizing NY data from code and parameterizing paths/prompts:

1. Pack layout + manifest (`packs/<jur>/` with sources, INDEX, verification,
   catalog.json, expected count) — parse_golden_copy.py, freshness_checker.py.
2. Schema fields `Jurisdiction:` + `Citation-ID:` — parse_golden_copy.py + one
   mechanical pass over 45 sources.
3. Catalog externalization (the Area-4 refactor) — bid_readiness.py,
   gap_analysis.py, validator.py, cert_renewal.py + manifest + tests.
4. Freshness config: SUNSET_SEED + watch-bills → pack config — freshness_checker.py.
5. Reader prompt/pattern packs — llm_reader.py, tender_extractor.py.

**Scope: ~8–10 code files + 45 mechanical source-file edits + test updates.**
Sequencing: **none of this blocks Step 1 Triage** (metadata-only, no golden-copy
dependency). Do item 2's citation-ID at Triage time cheaply; items 1/3/4/5 when
pack #2 actually starts. The federal pack itself (capturing FAR/SBA sources) is
content work on top, unchanged by architecture.

## Appendix A — Ghost references (benign)

`freshness_checker.py` self-test builds two in-memory fixture records named
`source-fixture-sunset.md` / `source-stf-163-fixture.md`; no such files exist
on disk and none are needed. Noted so a future file-vs-code sweep doesn't
mistake them for missing sources.

## Appendix B — 45 source URLs for manual browser re-verification

Network-blocked in this environment (State sites 403 at the egress proxy).
The two rows marked **← WARN swap target** are the pending re-links.

| source_id | URL |
|---|---|
| ac3237s-substitute-w9 | https://www.osc.ny.gov/files/vendors/2017-11/vendor-form-ac3237s-fe.pdf |
| appendix-a-june2023 | https://ogs.ny.gov/procurement/appendix |
| exec-314-mwbe-cert-validity | https://www.nysenate.gov/legislation/laws/EXC/314 |
| invoice-checklist | https://www.osc.ny.gov/files/state-agencies/pdf/xii-4-f-att.pdf |
| lab-220-i-public-work-registration | https://law.justia.com/codes/new-york/lab/article-8/220-i/ | **← WARN swap target (relink to nysenate.gov LAB/220-I)**
| mwbe-5nycrr-pass-fail | https://esd.ny.gov/sites/default/files/MWBERegulations-120220.pdf |
| sdvob | https://www.osc.ny.gov/state-vendors/sdvob |
| stf-109-vendor-certificate | https://www.nysenate.gov/legislation/laws/STF/109 |
| stf-112 | https://www.nysenate.gov/legislation/laws/STF/112 |
| stf-139-d-noncollusion | https://www.nysenate.gov/legislation/laws/STF/139-D |
| stf-139-h-international-boycott | https://codes.findlaw.com/ny/state-finance-law/stf-sect-139-h/ | **← WARN swap target (relink to nysenate.gov STF/139-H)**
| stf-139-j | https://www.nysenate.gov/legislation/laws/STF/139-J |
| stf-139-k | https://www.nysenate.gov/legislation/laws/STF/139-K |
| stf-139-l-sexual-harassment | https://www.nysenate.gov/legislation/laws/STF/139-L |
| stf-139-m-gender-based-violence | https://www.nysenate.gov/legislation/laws/STF/139-M |
| stf-163 | https://www.nysenate.gov/legislation/laws/STF/163 |
| stf-179-d | https://www.nysenate.gov/legislation/laws/STF/179-D |
| stf-179-e | https://www.nysenate.gov/legislation/laws/STF/179-E |
| stf-179-f | https://www.nysenate.gov/legislation/laws/STF/179-F |
| stf-179-g | https://www.nysenate.gov/legislation/laws/STF/179-G |
| stf-179-p | https://www.nysenate.gov/legislation/laws/STF/179-P |
| stf-179-q | https://www.nysenate.gov/legislation/laws/STF/179-Q |
| stf-179-s | https://www.nysenate.gov/legislation/laws/STF/179-S |
| stf-179-t | https://www.nysenate.gov/legislation/laws/STF/179-T |
| stf-179-u | https://www.nysenate.gov/legislation/laws/STF/179-U |
| stf-179-v | https://www.nysenate.gov/legislation/laws/STF/179-V |
| vendrep-ac3290s-forprofit-nonconstruction | https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3290s.pdf |
| vendrep-ac3291s-nonprofit-nonconstruction | https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3291s.pdf |
| vendrep-ac3292s-forprofit-construction-cca2 | https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3292s.pdf |
| vendrep-ac3293s-nonprofit-construction | https://www.osc.ny.gov/files/state-vendors/vendrep/pdf/ac3293s.pdf |
| vendrep-forms | https://www.osc.ny.gov/state-vendors/vendrep/vendor-responsibility-forms |
| wkc-57-workers-comp | https://www.nysenate.gov/legislation/laws/WKC/57 |
| x-3-vendor-registration | https://www.osc.ny.gov/state-agencies/gfo/chapter-x/x3-overview |
| xi-16-vendor-responsibility | https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi16-vendor-responsibility |
| xi-18-a-mwbe | https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi18a-executive-law-article-15-participation-minority-group-members-and-women-respect-state |
| xi-2-f-timely-submittal | https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi2f-timely-submittal-contracts |
| xi-4-a-nfp-prompt-contracting | https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi4a-not-profit-prompt-contracting |
| xi-4-b-grant-budget-variance | https://www.osc.ny.gov/state-agencies/gfo/chapter-xi/xi4b-standard-contract-language-grant-contracts-fixed-term-multiyear-contracts-and-simplified |
| xii-4-b-1-supporting-information | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii4b1-supporting-information |
| xii-4-f-proper-invoice | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii4f-proper-invoice |
| xii-5-b-unique-invoice-number | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii5b-unique-invoice-number-requirements |
| xii-5-i-prompt-payment-interest | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii5i-prompt-payment-interest |
| xii-6-c-paying-prompt-contract-interest | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii6c-paying-prompt-contract-interest |
| xii-7-b-voucher-denials | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii7b-voucher-denials |
| xii-8-b-matching | https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii8b-matching |
