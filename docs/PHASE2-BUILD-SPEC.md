# NYS Procurement Vendor Phase 2 — Build Spec for the Validation Engine

**Audience:** the coding agent (Claude Code) building Phase 2, and the founder reviewing its work.
**Status:** Phase 2 spec, v1.0, 2026-06-29. Written against the Phase 1 golden copy (50-file Project).
**Read first:** `METHODOLOGY-MANUAL.md` (v1.1) — it defines the verbatim standard, the MUST/SHOULD
rule, the no-reconstruction rule, the load-bearing-passage method, and the two-layer pain-point
architecture. This spec assumes that manual is the law; nothing here overrides it.

---

## 0. What you are building, in one paragraph

A validation engine that takes a vendor's or not-for-profit's document (an invoice, a utilization
plan, a budget modification, a VendRep questionnaire) and checks it against New York State's
procurement and payment rules, returning a structured pass/warn/fail result with the exact rule and
source citation behind each finding. The engine reads the **golden copy** as its authority (what the
rule says) and the **risk map** as its check-list (what to test and how to phrase it). It never
invents a rule, never paraphrases one, and never gives legal or financial advice — it reports what a
rule requires and whether the document meets it.

---

## 1. Non-negotiable principles (inherited from Phase 1 — do not relax these)

1. **The golden copy is the only source of rule truth.** Every check the engine performs must trace to
   a verbatim source file in `/golden-copy/sources/`. If a rule is not in the golden copy, the engine
   does not enforce it — it surfaces "not covered," never guesses.
2. **No reconstruction, ever.** The engine quotes rule text from the source files; it does not
   re-summarize statutes from memory or from a model's training. If a citation is needed, it comes from
   the file.
3. **MUST hard-blocks; SHOULD warns.** A missing/incorrect *must* item is a FAIL (mandatory rejection
   risk). A missing *should* item is a WARN. Never conflate the two — this distinction is already
   captured verbatim in each source file and the engine must honor it.
4. **Information, not advice.** Output states what the rule requires and whether the document conforms.
   It must not tell the user to file a claim, pursue the State, take a legal position, or arrange
   financing. This is a hard product boundary (see §7, Compliance).
5. **State-system-safe by construction.** No feature requires vendor logins, credential scraping, or automated
   submission into State systems on the vendor's behalf. The engine reads documents the user provides
   and reports on them. Nothing that creates regulatory exposure.
6. **Freshness is mandatory, not optional.** A rule verified on a date is verified as of that date. The
   engine must know each rule's capture date and must refuse to present a rule as authoritative if the
   freshness-checker has flagged it as drifted (see §4).

---

## 2. Repository structure

```
/golden-copy/
  /sources/              # the 37 verbatim source-*.md files (copied verbatim from Phase 1)
  golden-copy-INDEX.md   # the index/spine
  VERIFICATION-REPORT.md # the audit trail
/data/
  nys-interest-rates.csv          # time-series; one row per quarter; existing rows immutable
  nys-interest-rates-README.md
/risk/
  RISK-MAP.md            # the production check-list spec (RM-1..RM-5)
  PAINPOINT-REGISTER.md  # the evidence layer
/docs/
  METHODOLOGY-MANUAL.md  # v1.1 — the standard
  PHASE2-BUILD-SPEC.md   # this file
/tools/
  diffcheck.py           # the Phase 1 diff harness (seed for the freshness-checker)
  verify_codes.py, structural_check.py, extract_body.py
/engine/                 # NEW in Phase 2 — the validation engine code
/freshness/              # NEW in Phase 2 — the freshness-checker
/tests/                  # NEW in Phase 2 — fixtures and rule-coverage tests
```

The golden copy, data, risk, and docs folders are **inputs the engine reads**. They are not rewritten
by the engine. The only writable new code lives in `/engine/`, `/freshness/`, `/tests/`.

---

## 3. Build order (do these in sequence; do not skip ahead)

**The order matters because a stale or mis-parsed rulebook silently breaks every feature built on top.
Build the foundation that protects correctness before building anything user-facing.**

### Step 1 — Source-file parser + integrity check (foundation)
- Parse each `source-*.md` into a structured record: the four header labels (Name, Date, Issued by,
  Link + Copied-on), the `## STATE TEXT (verbatim)` body, and the `## CITATIONS` list.
- Assert every source file has all four labels and a non-empty verbatim body. Fail loudly on any file
  that doesn't — that's a corruption signal.
- Cross-check parsed file count against `golden-copy-INDEX.md` entry count and `VERIFICATION-REPORT.md`
  row count. All three must agree (currently 37). A mismatch halts the build.
- **Acceptance:** parser ingests all 37 files, all integrity assertions pass, counts reconcile.

### Step 2 — The freshness-checker (build BEFORE any validator)
- For each source file, re-fetch its canonical Link, extract the source's current revision/effective
  date, and compare to the Date recorded in the file.
- Where the source is a page with a REV stamp (GFO) or a revision selector (nysenate.gov statutes),
  compare those. Where it's a PDF/form, re-run the load-bearing-passage check from the manual.
- Output a freshness report: per rule — OK / DRIFTED (date or content changed) / UNREACHABLE.
- Seed it from `/tools/diffcheck.py`; that harness already normalizes formatting noise correctly.
- **Elevated-priority targets (hard-code as a watch-list):** the §179 cluster (active legislation
  S7001 / A11179 / S4877) and the three repeal dates (§139-j/k 2028-07-31; §163 2031-06-30).
- **Acceptance:** running the freshness-checker produces a clean per-rule report; a deliberately
  altered Date in a test fixture is correctly flagged DRIFTED.
- **Guardrail:** the engine (Step 3+) must consult the latest freshness report and must not present a
  DRIFTED rule as authoritative without a human re-verification per the methodology manual.

### Step 3 — The validation core (rule-agnostic engine)
- A document + a rule set in → a structured result out. Result schema per finding:
  `{rule_id, source_file, citation_quote, severity (FAIL|WARN|INFO), check_description, passed (bool), evidence}`.
- The engine maps a document type to the applicable RISK-MAP entries (its check-list) and the
  golden-copy files those entries ground in (its authority).
- Every finding must carry the verbatim `citation_quote` pulled from the source file — never a
  paraphrase. If the engine can't cite it, it can't assert it.
- **Acceptance:** given a known-good and a known-bad fixture for one rule, the engine returns the
  correct FAIL/WARN/PASS with the right citation.

### Step 4 — First validator: RM-1 Budget-Variance (flagship, PREVENTION)
- Implement the RM-1 PRE-CHECK from the risk map: given an approved budget and a proposed/actual
  spend, flag any transfer among program activities or budget cost categories where the moved amount
  is ≥ 10% of total contract value (contracts ≤ $5,000,000) or ≥ 5% (contracts > $5,000,000).
- Authority: `source-xi-4-b-grant-budget-variance.md`. Cite it verbatim in the finding.
- Distinguish this (a budget-category transfer not changing amount/scope/term) from an
  amount/scope/term change, which is a different, amendment-track event — surface that, don't conflate.
- **Acceptance:** a budget moving 11% on a $2M contract → FAIL with the XI.4.B citation; a 4% move →
  PASS; a 6% move on a $7M contract → FAIL. Output names the threshold that applied.
- **Why first:** clean rule, dual-source verified, high confidence, pure prevention, no compliance
  complications.

### Step 5 — Second validator: RM-5 Invoice pre-flight (PREVENTION)
- Implement the proper-invoice field check (XII.4.F) + the §109 certification check
  (`source-stf-109-vendor-certificate.md`). Confirm required fields present AND the "just, true and
  correct / unpaid / due and owing" certificate (or AC 3253-S equivalent) is present.
- Honor §109(1-a) as the exception (Comptroller may accept a normal-course invoice without separate
  certification) — so a missing separate certificate is a WARN with context, not an automatic FAIL,
  unless the agency/contract requires it.
- **Acceptance:** invoice missing a required field → FAIL citing XII.4.F; invoice present but
  uncertified where required → WARN citing §109.

### Step 6 — Then RM-4 (MWBE deadline cascade) and RM-3 (VendRep stale-cert), in either order
- RM-4: deadline tracker from low-bid notice; the 10/20/7/5-business-day chain; plus the §143.3(c)
  EEO-statement hard-block. Authority: `source-mwbe-5nycrr-pass-fail.md`.
- RM-3: event-driven re-certification prompts on material-change events; notarization check for paper
  filings. Authority: the four VendRep source files.

### Step 7 — RM-2 Interest entitlement calculator (RECOVERY) — BUILD LAST, GATED
- Implement the §179-v entitlement logic and the indicative interest computation using the rate from
  `/data/nys-interest-rates.csv` (never hard-code a rate). Authority: `source-stf-179-v.md`,
  `source-stf-179-g.md`, `source-xi-4-a-nfp-prompt-contracting.md`.
- **This is the only RECOVERY feature and it is gated:** it computes and documents an *indicative*
  entitlement and must be reviewed by licensed-attorney oversight before it ships to any user. It must
  not advise the user to pursue the State or characterize the output as a legal determination. Frame:
  "based on these dates and this rule, an interest entitlement may have arisen; here is the rule and
  the computation." (See §7.)
- **Why last:** highest value (the P&L wedge, aligned to the founder's structured-finance edge) but
  the only one with a compliance gate and the most freshness-sensitive rule cluster.

---

## 4. The freshness contract (how the engine stays honest over time)

- Interest rates live ONLY in `/data/nys-interest-rates.csv`, one immutable row per quarter, each with
  its own source URL and verified-on date. The engine reads the row for the relevant period; it never
  embeds a rate in code. A frozen rate is wrong within 90 days.
- The freshness-checker runs on a schedule (and on demand). Its latest report is an input to the
  engine. A rule flagged DRIFTED is quarantined: the engine still shows the rule but labels it
  "pending re-verification — captured [date], source may have changed," and a human re-verifies per the
  manual before it returns to authoritative status.
- New quarterly rate rows are appended, never edited. New legislation that amends a captured statute
  triggers a fresh verbatim capture of the new text and a diff against the pre-amendment version we
  deliberately preserved.

---

## 5. Output contract (what a vendor sees)

For each document checked, the engine returns:
- An overall status: PASS / PASS-WITH-WARNINGS / FAIL.
- A list of findings, each with: the plain-language check, the severity, PASS/FAIL, the **verbatim rule
  quote**, the **source citation** (file + canonical URL + the rule's capture date), and what the user
  would do to conform (stated as "the rule requires X," not "you should do X to win").
- A clear separation between **universal-rule findings** (what the golden copy covers) and **per-
  solicitation gaps** the engine cannot verify (every RFP/IFB adds requirements that live only in that
  document; the engine surfaces these as "read your solicitation for X," never silently resolves them).
  This mirrors the manual's "rules are perfect ≠ document guaranteed to pass" boundary.

---

## 6. Testing requirements

- **Rule-coverage test:** every RISK-MAP entry that's implemented must have at least one known-good and
  one known-bad fixture, and the engine must return the expected result with the correct citation.
- **Citation-integrity test:** every `citation_quote` the engine emits must be found verbatim in the
  named source file (string-present check). If a quote isn't in its source file, that's a build-failing
  bug — it means the engine paraphrased.
- **Count-reconciliation test:** sources parsed == INDEX entries == verification rows. Fails the build
  on mismatch.
- **Freshness-fixture test:** an altered Date and an altered body in test fixtures are both correctly
  flagged.
- **MUST/SHOULD test:** a fixture missing a *must* field FAILs; a fixture missing a *should* field
  WARNs. Never inverted.

---

## 7. Compliance guardrails (read this before writing the RM-2 feature)

- **Product framing:** NYS Procurement Vendor is an information and document-validation service with licensed-attorney
  oversight. Engine output describes what a rule requires and whether a document conforms. It is not
  legal advice, not financial advice, and not representation.
- **Forbidden output behaviors:** telling a user to sue or pursue the State; asserting a legal
  conclusion ("you are legally entitled to $X"); recommending or arranging financing; auto-submitting
  anything into a State system; anything requiring the vendor's State-system credentials.
- **RM-2 gate:** the interest-entitlement feature computes an *indicative* figure tied to the verbatim
  rule and the published rate, and must pass licensed-attorney review before launch. Its output is
  framed as information about the rule, with a clear note that whether interest is actually due and
  payable depends on facts and a determination the tool cannot make.
- **Financial-advice boundary:** nothing in the engine may create securities/financial-services
  exposure. The recovery feature stays strictly on the
  rule-information side of the line; if a future version would touch financing of receivables or
  similar, that is a separate product with its own compliance review, not an extension of this engine.

---

## 8. Definition of done for Phase 2 (minimum viable engine)

- Steps 1–3 complete (parser, freshness-checker, validation core) with all §6 tests green.
- At least RM-1 and RM-5 validators live and passing their fixtures (the two clean prevention
  features).
- Freshness-checker runnable on demand, producing a per-rule report, with the §179 + repeal-date
  watch-list wired in.
- RM-2 implemented behind the compliance gate (built, tested, NOT user-exposed until attorney sign-off).
- Citation-integrity test passing across every implemented rule (proves no paraphrase crept in).

---

## 9. What to hand back to the founder at each step

Because the founder is not a developer, each step should end with a plain-language status the founder
can verify without reading code:
- Step 1: "Engine reads all 37 rules; counts reconcile."
- Step 2: "Freshness-checker runs; here's the per-rule OK/DRIFTED/UNREACHABLE report."
- Step 4: "Budget-variance check works — here are three worked examples with the rule quoted."
- Step 7: "Interest calculator built; holding for attorney review before turning it on."

Keep the founder's verification anchored to outcomes and citations, not implementation.
