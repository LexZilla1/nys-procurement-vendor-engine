# Golden-Copy Full-Text Rebuild via Open Legislation API — Phase 1 Report

**UPDATE 2026-07-03: Phases 2–5 are now COMPLETE** using authoritative live
API texts the user supplied as an upload (`openlegfulltext20260703.zip`). See
`API-REBUILD-PHASE5-REPORT.md` for verdicts, actions, and verification. The
original Phase-1 blocker note is retained below for provenance.

---

**Status (original run): Phase 1 (classify) COMPLETE — Phases 2–4 BLOCKED in this
environment.** Two independent blockers, verified at run time:

1. `NYSLEG_API_KEY` is not set in this session's environment.
2. The egress proxy refuses the CONNECT tunnel to
   `legislation.nysenate.gov` (HTTP 403 before the request reaches the API).

Per the task's stop rule ("if the API rejects requests or returns errors,
stop and report — do not fall back to scraping"), no fetch was attempted
beyond the connectivity probe and no source file was touched. `.env` was
already in `.gitignore` (lines 12–13); no key material exists anywhere in
the repo or this branch.

**What this branch delivers instead:** the complete Phase-1 classification
(below), the exact `lawId/locationId` fetch map, and `openleg_fetch_diff.py`
— a ready-to-run, stdlib-only Phase-2 fetch+diff tool (reads the key from
env, never writes to golden-copy/, stops hard on API errors, and enforces
the LAB/220-I validation gate before any bulk run). In a networked session
with the key exported, Phase 2 is:

    NYSLEG_API_KEY=... python3 openleg_fetch_diff.py --json phase2-report.json

## Phase 1 — Classification: 22 STATUTE-CLASS / 23 NON-STATUTE (= 45)

### STATUTE-CLASS (fetchable via `/api/3/laws/{lawId}/{locationId}`)

| source_id | lawId/locationId | notes |
|---|---|---|
| exec-314-mwbe-cert-validity | EXC/314 | ⚠️ **design-partial**: capture is DELIBERATELY the single current 5.(a) clause + NB markers (per its VERSION NOTE). The diff will call it FRAGMENT by construction. **Do not auto-rebuild to full section without an explicit decision** — that reverses a documented capture design. Sunset cross-check target (expect repealedDate 2028-07-01). |
| lab-220-i-public-work-registration | LAB/220-I | **Validation gate.** Stored capture is a confirmed one-subdivision fragment. Premise correction: the stored text is labeled **"6."** (it begins "6. No contractor shall bid…"), not mislabeled "1." as the task stated. Fragment status stands; the label does not need the "1." fix. Gate: API must return a multi-subdivision section (subds. 1–10, rev. ~2025-01-03) or the run stops. Also carries the justia.com WARN link → rebuild should relink to nysenate.gov. |
| stf-109-vendor-certificate | STF/109 | ⚠️ **MIXED capture**: statute §109 + OSC XII.4.A guidance + AC 3253-S form text in one file. Only the §109 portion is API-diffable; rebuild must not blow away the two non-statute layers. Treat as special case in Phase 3. |
| stf-112 | STF/112 | |
| stf-139-d-noncollusion | STF/139-D | |
| stf-139-h-international-boycott | STF/139-H | Carries the findlaw.com WARN link → rebuild should relink to nysenate.gov. |
| stf-139-j | STF/139-J | Sunset cross-check (expect repealedDate 2028-07-31). |
| stf-139-k | STF/139-K | Sunset cross-check (expect repealedDate 2028-07-31). |
| stf-139-l-sexual-harassment | STF/139-L | |
| stf-139-m-gender-based-violence | STF/139-M | |
| stf-163 | STF/163 | Sunset cross-check (expect repealedDate 2031-06-30). |
| stf-179-d | STF/179-D | |
| stf-179-e | STF/179-E | |
| stf-179-f | STF/179-F | |
| stf-179-g | STF/179-G | |
| stf-179-p | STF/179-P | |
| stf-179-q | STF/179-Q | |
| stf-179-s | STF/179-S | |
| stf-179-t | STF/179-T | |
| stf-179-u | STF/179-U | |
| stf-179-v | STF/179-V | Pending-amendment watch (S7001) noted in file; API activeDate will show if anything was enacted. |
| wkc-57-workers-comp | WKC/57 | |

### NON-STATUTE (23) — not in the Open Legislation API; stay on the manual capture standard

| source_id | type |
|---|---|
| mwbe-5nycrr-pass-fail | **Regulation (5 NYCRR Parts 140–145)** — NYCRR is not in Open Legislation; would need the DOS/NYCRR source, out of scope here |
| appendix-a-june2023 | OGS contract boilerplate document |
| ac3237s-substitute-w9 | OSC form |
| vendrep-ac3290s / ac3291s / ac3292s / ac3293s | OSC VendRep questionnaires (forms) |
| vendrep-forms | OSC forms-index page |
| sdvob | OSC program page |
| invoice-checklist | OSC attachment (XII.4.F) |
| x-3-vendor-registration | OSC GFO chapter |
| xi-2-f-timely-submittal, xi-4-a-nfp-prompt-contracting, xi-4-b-grant-budget-variance, xi-16-vendor-responsibility, xi-18-a-mwbe | OSC GFO chapters |
| xii-4-b-1-supporting-information, xii-4-f-proper-invoice, xii-5-b-unique-invoice-number, xii-5-i-prompt-payment-interest, xii-6-c-paying-prompt-contract-interest, xii-7-b-voucher-denials, xii-8-b-matching | OSC GFO chapters |

## Phases 2–3 — BLOCKED (not attempted)

No fetch, no diff, no rebuild, no verdicts, no activeDates. The verdict
column for all 22 statute-class sources is **PENDING (blocked: no key + no
network)**. The sunset cross-check (§314 / §139-j / §139-k / §163
repealed/repealedDate vs our records) is wired into the script
(`SUNSET_EXPECT`) and will flag mismatches without silently reconciling.

## Phase 4 — parser change DEFERRED (deliberately)

Making `Covers:` a required field now would fail all 45 files (none carry it
yet) and break the 45/45/45 reconciliation. The correct sequencing is:
rebuild adds `Covers:` to files in Phase 3 → then flip the parser
requirement in the same PR. Enforcing it before any file has the field would
turn the gate red on purpose — not done.

## Phase 5 — current state verification (nothing changed)

- Parser/reconciliation: **PASS 45/45/45** (run on this branch).
- Test suites: see PR body for per-suite pass counts (all green; no code
  paths touched by this branch except the new standalone script).

## Resume checklist (networked session)

1. Export `NYSLEG_API_KEY` (never commit it).
2. `python3 openleg_fetch_diff.py --json phase2-report.json`
   — gate on LAB/220-I, then 22 fetch+diffs, sunset cross-checks included.
3. Phase 3 rebuild from the report (human-reviewed; EXC/314 and STF/109
   need explicit decisions per the notes above; relink lab-220-i +
   stf-139-h to nysenate.gov as part of their rebuild).
4. Phase 4 parser change (`Covers:` required + "full section" begins with
   "§") in the same PR as the rebuilt files.
