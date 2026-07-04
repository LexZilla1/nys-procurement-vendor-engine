# NYS PROCUREMENT VENDOR ENGINE — SESSION HANDOFF 2026-07-04

Independent project. NOT LexZilla — do not use that name anywhere. LexZilla1 is only the GitHub org handle. Not a developer; Claude Code implements, strategy chat handles architecture/verification.

## WHAT CLOSED THIS SESSION

### Golden-Copy Full-Text Rebuild (PRs #18–#20, #24, #25)
- **Audit** (PR #18): 45 audited — 43 PASS / 0 BLOCKER / 2 WARN (Justia/FindLaw secondary links).
- **Architecture assessment** (PR #19): 6 areas, no RED. Federal = bounded refactor (~8–10 files). Load-bearing gap: citation-ID externalization (YELLOW, fix at pack #2 time).
- **Full-text rebuild** (PR #20): discovered 6/22 statute sources were fragments (LAB §220-i held only subd. 6 of 10). All 22 statute-class sources re-captured via NY Open Legislation API v3 as full sections. 2 WARN links swapped to nysenate.gov. Provenance cleaned. Parser now enforces `Covers:` field. 45/45/45 green.
- **Key architectural decision**: every source file = full section verbatim as the untouchable base layer + Claude commentary clearly separated below, never replacing text. Machine-enforced via `Covers:` parser check.
- **Open Legislation API** (legislation.nysenate.gov): free, key-authenticated, serves full Consolidated Laws text as JSON with point-in-time versioning + repealed/repealedDate fields. NYSLEG_API_KEY stored as GitHub Actions secret. Key also registered for breaking-changes email alerts.

### Freshness Automation (PRs #21, #24, #25)
- **GitHub Actions** monthly cron (1st of month, 06:00 UTC) + manual dispatch.
- Fetches all 22 statute-class sources via API, diffs against golden copy.
- All FULL-MATCH → non-draft PR labeled `freshness-clean` with report.
- Any DIVERGENT or sunset mismatch → draft PR labeled `freshness-drift`.
- Never auto-merges, never rewrites golden-copy files.
- **Normalization bug fixed** (PR #24): API JSON text carries literal `\n` escapes; raw-response fixture added for permanent regression coverage.
- **Branch protection fix** (PR #25): clean runs open PRs instead of pushing directly to main.
- **First live run**: 22/22 FULL-MATCH, green, report merged. Automation proven.

### Step 1 Triage (PR #23)
- **Entity lookup table**: authoritative issuer classification from ABO State/Local Authorities datasets + state agency roster. Exact + alias matching only (no fuzzy/keyword). Each row carries source URL + capture date.
- **Jurisdiction gate** (Step 2, always first):
  - STATE_AGENCY → full engine (SFL Art. 11 golden copy applies)
  - AUTHORITY → HUMAN_REVIEW (PAL §2879 — not in golden copy)
  - SUNY/CUNY → HUMAN_REVIEW (Education Law — unverified)
  - Municipal → HUMAN_REVIEW (GML — not in golden copy)
  - Non-NY → OUT_OF_SCOPE
  - No match → HUMAN_REVIEW ("jurisdiction undetermined")
- **Ad-type classification** (Step 3): 12 NYSCR labels as config table, all `provisional: true`. 7 BIDDABLE, 4 NON_BIDDABLE, 1 EDGE (grant_flow tag-only).
- **LLM fallback** (Step 4): currently a stub returning low-confidence → HUMAN_REVIEW. Injectable interface for tests. **Wiring to live Sonnet call is the next build item.**
- **Never-green invariant**: no confident BIDDABLE/NON_BIDDABLE unless jurisdiction confirmed STATE via entity lookup AND (not provisional+low-confidence).
- 22 tests green including: ESD without "Authority" in name, bare "Authority" non-match, alias resolution, sole-source language override.

### Claude Code Environment Setup
- **Network egress allowlist** (Settings → Capabilities): legislation.nysenate.gov, nysenate.gov, data.ny.gov, data.cityofnewyork.us, api.usaspending.gov, api.sam.gov added.
- **Repo branch protection**: Rulesets (not classic). `github-actions[bot]` cannot be added to bypass list in the Rulesets UI — workaround: all automated commits go through PRs.
- **Preferences updated**: properly scoped across LexZilla and NYS Procurement Vendor Engine. No more cross-contamination.

## IMMEDIATE NEXT ACTIONS

1. **Merge PR #23** (Triage core) — ready, 22 tests green.
2. **Wire Step 4 live Sonnet call** — prompt ready. Opus 4.8. Last build item before pilot.
3. **Get a pilot NY vendor user** — gates all expansion decisions.

## BACKLOG (prioritized)

1. NYSCR 12 ad-type labels dual-model cross-check — still provisional.
2. Entity refresh script → wire into monthly GitHub Action alongside freshness.
3. 23 non-statute sources completeness verification — manual, not API-coverable, same fragment risk as statutes had.
4. Coverage gaps from architecture assessment: §163(4)(g) consultant disclosure, §220 general prevailing wage, OGS centralized-contract rules — golden-copy text exists, no runtime checks yet.
5. Citation-ID externalization (~8–10 files) — required before federal pack #2, not before.
6. Federal expansion: FAR, 13 CFR (SBA regs), SAM.gov/USAspending APIs all tested and mapped. eCFR has versioned API (capture-date architecture nearly native). Only after NY pilot validates.
7. §2879 Public Authorities Law — alternative first expansion, unlocks MTA/Thruway/ESD volume inside existing NY market. Decide ranking with pilot data.

## PARKED (do not build)

- NJ data sourcing — revisit after NY pilot validates.
- NYSCR scraping/redistribution — copyright-gated per NYSCR's own policies. Lawyer-review gate logged.
- Open Book NY — access-only, no reuse grant found. Query-only, never redistributed.
- CarRadar agentic rebuild — separate project, parked.
- Federal golden copy — real build cost, explicit decision to avoid splitting focus pre-revenue.

## CONSTRAINTS (always apply)

- FINRA/securities registration: NOT relevant to this product — do not raise. Compliance concerns that DO apply: unauthorized practice of law (UPL), data privacy, accuracy/reliability liability.
- London relocation: off the table. Do not reference.
- LexZilla framing: never apply to this project. LexZilla1 = GitHub org handle only.
- Model guidance: Fable 5 for investigative/architectural tasks; Opus 4.8 for scoped build/mechanical work.
- Standing precision rule: no assumption-based analysis. Verify before asserting. "I don't know" preferred over inference.

## KEY REPO FACTS

- GitHub: LexZilla1/nys-procurement-vendor-engine
- Golden copy: 45 verified sources (22 statute-class via API, 23 non-statute manual), reconciled 45/45/45
- Parser: parse_golden_copy.py enforces `Covers:` field, exits 1 on structural violations
- Freshness checker: scripts/freshness_check.py, .github/workflows/freshness-check.yml
- Entity table: data/entities/entities.json (ABO sourced, exact+alias matching)
- Ad-type config: data/config/nyscr_ad_types.json (12 labels, all provisional)
- Citation map: data/config/citations.json (citation-ID → description, no filename coupling)
- Triage: pipeline/step1_triage.py (4-step: source detect → jurisdiction gate → ad-type → LLM fallback)
- Test suite: 147 existing + 22 triage = 169 total, all green
- NYSLEG_API_KEY: GitHub Actions secret (legislation.nysenate.gov, free, read-only)
- ANTHROPIC_API_KEY: needed for Step 4 live Sonnet call (not yet wired)
