# NYS Procurement Vendor — Golden Copy — Package Manifest

**Packaged:** 2026-06-29 (UTC) — rev 2 (naming cleanup)
**Phase:** Phase 1 complete; Phase 2 spec included.
**Reconciliation at packaging:** 37 source files = 37 INDEX entries = 37 verification rows. ✓
**Methodology manual:** v1.1.

## rev 2 change note
Removed stray references to a separate project ("LexZilla") and a meaningless placeholder
phrase ("stuck-at-82") from the four wrapper docs (PROJECT_BRIEF, METHODOLOGY-MANUAL,
PHASE2-BUILD-SPEC, README). The product name in document body text now reads "NYS Procurement
Vendor." The 37 verbatim rule files, INDEX, VERIFICATION-REPORT, RISK-MAP, and PAINPOINT-REGISTER
were not affected by the cleanup.

## Contents
- 37 verbatim rule files: source-*.md (Domains 1–4)
- Spine & audit: golden-copy-INDEX.md, VERIFICATION-REPORT.md
- Pain-point layer: RISK-MAP.md, PAINPOINT-REGISTER.md
- Method: METHODOLOGY-MANUAL.md (v1.1)
- Phase 2: PHASE2-BUILD-SPEC.md
- Data (time-series, not rules): nys-interest-rates.csv, nys-interest-rates-README.md, nysinterestrates.csv
- Project context: PROJECT_BRIEF.md, README.md
- Tooling/source data: nys_contract_puller.py, nys_contracts_04012024_to_03312025.csv, promptcontractingreport2025.pdf

## Provenance note
Rule files and data from the confirmed Project set; golden-copy-INDEX.md and VERIFICATION-REPORT.md
are the current session-updated versions (Addendum 3 / 37-file state). Frozen snapshot suitable as
the Phase 2 repo's read-only /golden-copy/ input.
