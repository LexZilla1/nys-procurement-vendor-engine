# Vendor Profile — schema & persist classification (agreed 2026-07-23, not yet built)

Status: **DESIGN, APPROVED. Not built.** This document is the **contract** the build
session implements. Design discovery is done — see `docs/DECISIONS-2026-07-23.md` §1–§2
(fact/rule model, §179-f findings) and `golden-copy/sources/source-stf-179-f.md` (the only
statutory basis). The build implements this schema; it does not re-derive or re-research.

Scope of the build this contract feeds: **Vendor Profile model + Onboarding Readiness
Check + fixture-based tests. Nothing else.** §179-p is a separate task and does not block.

---

## 1. Two models, never merged

The engine holds two orthogonal object families. A vendor **fact** is data about the
vendor. A criterion **rule** is metadata about how we can (or cannot) evaluate a criterion
against our corpus. They are stored separately and never collapsed into one shape.

### 1.1 Fact envelope (every vendor fact carries this)

| Field | Meaning | persist |
| --- | --- | --- |
| `value` | the asserted value (bool / int / enum, per fact) | ✅ PERSIST |
| `provenance` | `vendor \| uploaded_document \| agency \| third_party` | ✅ PERSIST |
| `verification` | `verified \| unverified` | ✅ PERSIST |
| `attested_at` | timestamp the vendor **asserted** the fact | ✅ PERSIST |
| `evidence_date` | as-of date of the **underlying fact** (SEPARATE from `attested_at`) | ✅ PERSIST |
| `superseded_by` | pointer to the fact that replaces this one (append-only; never mutate) | ✅ PERSIST |

Hard rules (test-enforced in the build):
- **`provenance:vendor` ALWAYS forces `verification:unverified`.** No code path lets an
  attestation flip its own verification bit.
- **Facts are append-only.** A change writes a new fact and sets `superseded_by` on the
  old one; values are never mutated in place.
- **`attested_at` and `evidence_date` are distinct fields.** §179-f(6)'s "at the time of
  payment" test reads **`evidence_date`**, never `attested_at`. Collapsing them makes a
  stale fact look fresh.

### 1.2 Criterion rule (separate object)

| Field | Domain |
| --- | --- |
| `definition_status` | `DEFINED_IN_GOLDEN_COPY \| UNDEFINED_IN_GOLDEN_COPY \| INTERPRETIVE` |
| `evaluation_basis` | `OBJECTIVE_THRESHOLD \| VENDOR_ATTESTATION \| DOCUMENTARY_REVIEW \| HUMAN_LEGAL_REVIEW` |

The two axes are **orthogonal** — proof: `sb_primary_place_ny` is
`DEFINED_IN_GOLDEN_COPY` yet `VENDOR_ATTESTATION` (the statute names the criterion
clearly, but we have no independent way to test it).

`UNDEFINED_IN_GOLDEN_COPY` asserts something about **our corpus** (we have no captured
definition/threshold), which is the only thing we can verify. The rejected alternative
`standard_undefined: true` asserted something about **the world** and was dropped.

---

## 2. Field inventory & persist classification

Statutory basis is **§179-f(6)** (small-business definition) and **§179-f(2)** (expedited-
payment preconditions), read verbatim from golden copy this session:

> *"small business" shall mean a business whose primary place of business is in New York
> state, has a significant business presence in the state, is independently owned and
> operated, not dominant in its field, and employs no more than two hundred employees at
> the time of payment. The small business shall, upon request, provide the contracting
> entity with sufficient documentation to reflect and confirm its status as a small
> business.* — §179-f(6)

**Temporal note (corrected):** "at the time of payment" attaches **only** to the
≤200-employee threshold, **not** to the other **four** criteria. (§179-f(6) names five
criteria total; `DECISIONS-2026-07-23.md` §2 says "the other five criteria" — that is a
miscount; the correct number of *other* criteria is four. Recorded here so the build uses
the right count; the DECISIONS wording should be corrected in a follow-up.)

### A. §179-f(6) small-business criteria

| Fact | `definition_status` | `evaluation_basis` | persist | SHIELD (GBL §899-aa/-bb) reasoning |
| --- | --- | --- | --- | --- |
| `sb_primary_place_ny` | DEFINED_IN_GOLDEN_COPY | VENDOR_ATTESTATION | ✅ PERSIST | Business locus, not a natural-person identifier → not §899-aa "private information" |
| `sb_significant_presence` | UNDEFINED_IN_GOLDEN_COPY | VENDOR_ATTESTATION | ✅ PERSIST | Business attribute → not private information |
| `sb_independently_owned` | DEFINED_IN_GOLDEN_COPY | VENDOR_ATTESTATION | ✅ PERSIST | Ownership structure of a *business* → not private information |
| `sb_not_dominant` | UNDEFINED_IN_GOLDEN_COPY | VENDOR_ATTESTATION | ✅ PERSIST | Market-position attribute → not private information |
| `sb_employee_count` (≤200 @ time of payment) | DEFINED_IN_GOLDEN_COPY | OBJECTIVE_THRESHOLD | ✅ PERSIST | Aggregate workforce count, not a personal identifier. `evidence_date` is the load-bearing "at the time of payment" anchor |
| `documentation_available_on_request` | DEFINED_IN_GOLDEN_COPY | VENDOR_ATTESTATION | ✅ PERSIST | Attestation (known accepted limit) → not private information |

### B. §179-f(2) expedited-payment onboarding preconditions

| Fact | `definition_status` | `evaluation_basis` | persist | SHIELD reasoning |
| --- | --- | --- | --- | --- |
| `submits_invoice_electronically` (eInvoicing) | DEFINED_IN_GOLDEN_COPY | VENDOR_ATTESTATION | ✅ PERSIST | Enrollment state → not private information |
| `sb_self_identification` (SFS self-cert; OSC GFO XII.5.I) | **INTERPRETIVE** (OSC bridge, NOT statute) | VENDOR_ATTESTATION | ✅ PERSIST | Attestation → not private information |

`sb_self_identification` is `INTERPRETIVE` because §179-f(2) requires the vendor to
"identif[y] that it is seeking expedited payment as a small business" but does **not** say
how; OSC (GFO XII.5.I) maps that to SFS portal self-certification. **That mapping is
OSC's, not the statute's** — cite the two sources separately; never collapse into one rule.

### C. Vendor identity

| Fact | persist | SHIELD reasoning |
| --- | --- | --- |
| `legal_name` | ✅ PERSIST | A name **alone** is "personal information," not "private information" under §899-aa (which requires a paired data element) |
| `nys_vendor_id` | ✅ PERSIST | State-assigned, procurement-public identifier; not a personal identifier |
| `entity_type` (corp / LLC / sole-prop / nonprofit) | ✅ PERSIST | Non-sensitive — **and** the discriminator that determines whether a future TIN is an EIN or an SSN |

### D. FORWARD RULE — sets the pattern now, before form-fill brings sensitive data (NOT a current field)

| Fact | persist | SHIELD reasoning |
| --- | --- | --- |
| `tin_ein` | ❌ **DO_NOT_PERSIST** | An EIN of a corp/LLC is not §899-aa data — **but** a sole-proprietor / single-member TIN is frequently the owner's **SSN**, which **is** §899-aa "private information," and the engine cannot reliably distinguish the two at input. **Fail-closed applied to data classification:** treat the whole field as SSN-bearing → tier-3 → never at rest. Form-fill consumes it transiently into the vendor-downloaded PDF, then discards. Non-retention keeps us out of §899-bb safeguard obligations. Consistent with the existing invariant "no tier-3 (TIN/SSN/DOB) fields anywhere" (`data/schemas/README.md`, `engine/citation.py`). **Do NOT add this field in the Vendor Profile build.** |
| any SSN / DOB / driver's-license / financial-account number | ❌ **DO_NOT_PERSIST** | §899-aa "private information" → do not model, do not persist |

---

## 3. Persist policy — binary, no middle tier

Two values only:
- **PERSIST** — stored at rest in the profile record.
- **DO_NOT_PERSIST** — never at rest; consumed transiently (form-fill only), then
  discarded.

**No tokenized / last-4 display tier.** Storing a derivative of a sensitive value still
pulls us into §899-bb safeguard obligations, for a display convenience nobody has asked
for. Non-retention is simpler and matches the existing "no tier-3 fields anywhere"
invariant. Revisit only with a stated reason.

### SHIELD caveats (both retained)
1. The SHIELD reasoning here is a **classification rationale** (an engineering/architecture
   decision, like the staleness horizon) — **not** a compliance claim.
2. **Asserting SHIELD compliance to vendors is attorney-gated territory.** GBL §899-aa and
   §899-bb are not in golden copy; any vendor-facing claim of compliance requires primary
   source + licensed review.

---

## 4. Onboarding Readiness Check — output model

- **Output ceiling: `SATISFIED_AS_ATTESTED`. There is no `PASS`.** The verb carries the
  meaning: the vendor said something consistent with the criterion; the criterion is not
  proven met. A criterion whose rule is `UNDEFINED_IN_GOLDEN_COPY` can never reach
  `SATISFIED_AS_ATTESTED`.
- **Staleness horizon (our product decision, not the State's):** applies to attested
  facts. **If no horizon is configured, the result is `INCOMPLETE` — the code must never
  select a default.** An unconfigured policy is a missing human decision.
- **Readiness ≠ entitlement.** Readiness is a snapshot of profile/program readiness only.
  It **never** determines that a specific invoice must be paid in 15 days. **Five
  `scope_limits` are always emitted, never suppressed.**
- **Permanent non-goal: no SFS write path, ever.** The engine never offers to complete the
  vendor's SFS portal certification — that is a State-system login, permanently out of
  scope (State-system boundary).
- **Known accepted limit:** `documentation_available_on_request` is a vendor attestation.
  If the vendor is later asked and cannot produce, the attestation was false. No
  engine-side remedy exists and none should be built — documented so it is not
  rediscovered as an oversight.

---

## 5. Invariants the build must honor (test-enforced)

- No tier-3 fields anywhere (no TIN/SSN/DOB); `tin_ein` is DO_NOT_PERSIST and not added.
- Never-green: no numeric confidence / risk / score field in any shape.
- `attested_at` and `evidence_date` are separate; the "at the time of payment" test reads
  `evidence_date`.
- `provenance:vendor` ⇒ `verification:unverified` (no self-flip).
- Facts append-only (`superseded_by`); no in-place mutation.
- Output ceiling `SATISFIED_AS_ATTESTED`; no `PASS` anywhere.
- Unconfigured staleness horizon ⇒ `INCOMPLETE`; never a default.
- Five `scope_limits` always emitted.
- Add JSON Schema(s) under `data/schemas/` mirroring the Python primitives, per the
  `data/schemas/README.md` conventions.
