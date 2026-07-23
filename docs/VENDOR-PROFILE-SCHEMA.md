# Vendor Profile — schema & persist classification (agreed 2026-07-23, not yet built)

Status: **DESIGN — persist classification approved; schema model has OPEN decisions (see
§6). NOT YET an implementable contract; not built.** The two-axis fact/rule model, the
per-field PERSIST/DO_NOT_PERSIST classification, and the output ceiling are approved. But
the fact-record identity, supersession mechanics, the exact `scope_limits` strings, and the
readiness result-state enum + aggregation are **not yet settled** — the items in §6 must be
decided before a build can implement this without inventing product/legal shape. See
`docs/DECISIONS-2026-07-23.md` §1–§2 (fact/rule model, §179-f findings) and
`golden-copy/sources/source-stf-179-f.md` (the only statutory basis).

Scope of the build this contract feeds: **Vendor Profile model + Onboarding Readiness
Check + fixture-based tests. Nothing else.** §179-p is a separate task and does not block
this; note §179-p is already captured and implemented (see `docs/DECISIONS-2026-07-23.md`
§3), so "separate task" here means the invoice/entitlement layer, not a missing source.

---

## 1. Two models, never merged

The engine holds two orthogonal object families. A vendor **fact** is data about the
vendor. A criterion **rule** is metadata about how we can (or cannot) evaluate a criterion
against our corpus. They are stored separately and never collapsed into one shape.

### 1.1 Fact envelope (every vendor fact carries this)

| Field | Meaning | persist |
| --- | --- | --- |
| `fact_id` | stable unique id of THIS immutable fact record | ✅ PERSIST |
| `subject` | the profile/vendor this fact belongs to (`vendor_id` / `profile_id`) | ✅ PERSIST |
| `fact_key` | which criterion/attribute this is (e.g. `sb_primary_place_ny`) | ✅ PERSIST |
| `value` | the asserted value (bool / int / enum, per fact) | ✅ PERSIST |
| `provenance` | `vendor \| uploaded_document \| agency \| third_party` | ✅ PERSIST |
| `verification` | `verified \| unverified` | ✅ PERSIST |
| `asserted_at` | ISO-8601 timestamp this fact record was asserted **by its source** (the vendor for `vendor` provenance; the document date/ingest for `uploaded_document`; the agency/third-party for those) | ✅ PERSIST |
| `evidence_date` | ISO-8601 as-of date of the **underlying fact** (SEPARATE from `asserted_at`); **nullable** — unknown ⇒ contributes `INCOMPLETE`, never a guessed default | ✅ PERSIST |
| `supersedes` | `fact_id` of the prior fact this record replaces, on the NEW record (`null` if original) | ✅ PERSIST |

Hard rules (test-enforced in the build):
- **`provenance:vendor` ALWAYS forces `verification:unverified`.** No code path lets an
  attestation flip its own verification bit.
- **Facts are immutable and append-only — supersession is recorded FORWARD.** A change
  writes a NEW fact record whose `supersedes` points at the prior record's `fact_id`. **The
  prior record is never written again** — nothing on the old fact is mutated (this is the
  fix for the earlier "sets `superseded_by` on the old one" wording, which would have
  mutated an immutable record). "Current" = the fact for a `(subject, fact_key)` with no
  successor pointing at it.
- **`asserted_at` and `evidence_date` are distinct fields.** §179-f(6)'s "at the time of
  payment" test reads **`evidence_date`**, never `asserted_at`. Collapsing them makes a
  stale fact look fresh. `asserted_at` is provenance-appropriate (it is not "the vendor"
  for non-vendor provenance).

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
| `legal_name` | ✅ PERSIST | Low-risk identifier recorded for the profile. (We do not assert its §899-aa status categorically; the persist call is a product risk judgment, not a legal conclusion.) |
| `nys_vendor_id` | ✅ PERSIST | State-assigned vendor identifier, public-facing on procurements → low-risk, PERSIST. (Not asserted categorically as "not a personal identifier" — for a sole proprietor a state-assigned number could identify a natural person; this is a risk judgment, not a statutory conclusion.) |
| `entity_type` (corp / LLC / sole-prop / nonprofit) | ✅ PERSIST | Non-sensitive. It *signals* whether a future TIN is more likely an EIN or an SSN, but does **not** reliably determine it (a sole-prop may hold an EIN; a single-member LLC is ambiguous; the field itself is vendor-asserted) — which is exactly why `tin_ein` is treated fail-closed below rather than branched on this value |

### D. FORWARD RULE — sets the pattern now, before form-fill brings sensitive data (NOT a current field)

| Fact | persist | SHIELD reasoning |
| --- | --- | --- |
| `tin_ein` | ❌ **DO_NOT_PERSIST** | An EIN of a corp/LLC is not §899-aa data — **but** a sole-proprietor / single-member TIN is frequently the owner's **SSN**, which **is** §899-aa "private information," and the engine cannot reliably distinguish the two at input. **Fail-closed applied to data classification:** treat the whole field as SSN-bearing → tier-3 → never at rest. Form-fill consumes it transiently into the vendor-downloaded PDF, then discards. Non-retention **reduces sensitive-data exposure**; it does **not** establish that §899-bb is inapplicable to transient processing (the statute contemplates collection, transport, and destruction/disposal — legal applicability is attorney-gated). Consistent with the existing invariant "no tier-3 (TIN/SSN/DOB) fields anywhere" (`data/schemas/README.md`, `engine/citation.py`). **Do NOT add this field in the Vendor Profile build.** |
| any SSN / DOB / driver's-license / financial-account number | ❌ **DO_NOT_PERSIST** | Fields that are, or may be, sensitive personal identifiers — SSN; financial-account numbers (whose §899-aa status is conditional on accompanying access/security info); driver's-license numbers; and, by our own tier-3 policy, DOB (note: DOB **alone** is not §899-aa "private information"). DO_NOT_PERSIST as a **product risk-classification** choice. Whether any specific field is "private information" under GBL §899-aa is a legal question we do **not** decide here. |

---

## 3. Persist policy — binary, no middle tier

Two values only:
- **PERSIST** — stored at rest in the profile record.
- **DO_NOT_PERSIST** — never at rest; consumed transiently (form-fill only), then
  discarded.

**No tokenized / last-4 display tier.** Storing a derivative of a sensitive value keeps
sensitive data at rest and increases exposure, for a display convenience nobody has asked
for; it does not let us assume §899-bb is inapplicable (that is attorney-gated). Non-
retention is simpler, reduces exposure, and matches the existing "no tier-3 fields
anywhere" invariant. Revisit only with a stated reason.

### SHIELD caveats (all retained)
1. Everything in the "SHIELD reasoning" columns above is **product risk classification** —
   an engineering/architecture judgment (like the staleness horizon), **not** a statutory
   determination of what is or is not "private information," and **not** a compliance claim.
   Where a cell references §899-aa, it names a *risk signal*, not a legal conclusion.
2. The specific §899-aa contours are deliberately left to counsel: a name alone, DOB alone,
   a financial-account number without accompanying access info, and a state-assigned vendor
   ID for an individual/sole proprietor are all context-dependent under the statute. This
   doc does not resolve them; it errs toward non-retention.
3. **Asserting SHIELD compliance to vendors is attorney-gated territory.** GBL §899-aa and
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

### Per-criterion result state (PROPOSED — pending sign-off, see §6)
Proposed enum per criterion: `SATISFIED_AS_ATTESTED` (ceiling) | `NOT_ATTESTED` (vendor
hasn't asserted) | `CONTRADICTED` (attestation conflicts with an uploaded/agency fact) |
`UNDEFINED_REQUIRES_REVIEW` (rule is `UNDEFINED_IN_GOLDEN_COPY` — cannot be self-assessed;
never reaches SATISFIED) | `STALE` (evidence past the configured horizon) | `INCOMPLETE`
(no horizon configured, or `evidence_date` unknown).

### Overall readiness aggregation (PROPOSED — this is a product decision, see §6)
Because two required §179-f(6) criteria (`sb_significant_presence`, `sb_not_dominant`) are
`UNDEFINED_IN_GOLDEN_COPY` and can **never** reach `SATISFIED_AS_ATTESTED`, an overall
"ready / all criteria satisfied" verdict is **not reachable** and must not be faked.
Proposed: **no single clean "ready" verdict.** Emit per-criterion states plus a roll-up
that surfaces the UNDEFINED criteria as `UNDEFINED_REQUIRES_REVIEW` (documentary/legal
review), never as blocking-fail and never as pass. This keeps never-green and
readiness≠entitlement intact. *(Alternative considered: an overall ceiling of
`ATTESTED_WITH_OPEN_ITEMS`. Either is acceptable; the choice is the founder's — §6.)*

### The five `scope_limits` (PROPOSED strings — vendor-facing → UPL review required, §6)
These are always emitted, never suppressed. Draft wording, **not yet approved**; each must
pass the compliance-wording (UPL) check before use:
1. "This is a readiness snapshot of your profile, not a determination that any invoice must
   be paid within 15 days."
2. "Criteria marked as attested reflect what you stated; they are not independently
   verified or proven met."
3. "Two small-business criteria ('significant business presence', 'not dominant in its
   field') have no definition in our source corpus and cannot be self-assessed here."
4. "Eligibility for expedited payment is determined by the State, not by this tool."
5. "This tool never certifies you in, or submits anything to, the SFS portal or any State
   system."

*(Strings above are placeholders for review — do not ship as-is.)*

---

## 5. Invariants the build must honor (test-enforced)

- No tier-3 fields anywhere (no TIN/SSN/DOB); `tin_ein` is DO_NOT_PERSIST and not added.
- Never-green: no numeric confidence / risk / score field in any shape.
- `asserted_at` and `evidence_date` are separate; the "at the time of payment" test reads
  `evidence_date`.
- `provenance:vendor` ⇒ `verification:unverified` (no self-flip).
- Facts immutable + append-only; supersession recorded FORWARD via `supersedes` on the new
  record; no in-place mutation of a prior record.
- Output ceiling `SATISFIED_AS_ATTESTED`; no `PASS` anywhere.
- Unconfigured staleness horizon ⇒ `INCOMPLETE`; never a default.
- Five `scope_limits` always emitted.
- Add JSON Schema(s) under `data/schemas/` mirroring the Python primitives, per the
  `data/schemas/README.md` conventions.

---

## 6. Open decisions — required before this is an implementable contract

The persist classification and the two-axis model are approved. These items are **not yet
settled** and a build must not invent them:

1. **Supersession mechanics** — confirm `supersedes`-forward on the new immutable record
   (proposed §1.1) vs. a separate supersession-event log. Pick one; both keep the prior
   record immutable.
2. **Overall readiness aggregation** — no single "ready" verdict vs. an
   `ATTESTED_WITH_OPEN_ITEMS` ceiling (proposed §4). This is a product decision because two
   required criteria are permanently `UNDEFINED_IN_GOLDEN_COPY`.
3. **The five `scope_limits` strings** — the §4 drafts are placeholders; final wording must
   pass the compliance-wording (UPL) check before shipping.
4. **Result-state enum** — confirm the per-criterion enum (proposed §4) and how `STALE` /
   `INCOMPLETE` interact with the staleness horizon.
5. **Field specifics for the JSON schema** — `fact_id`/`subject` id formats, timestamp
   format (ISO-8601), `evidence_date` nullability semantics (unknown ⇒ `INCOMPLETE`),
   and the closed set of `fact_key` values.

Until 1–4 are decided, treat this document as an approved *design direction*, not a
turn-key build spec.
