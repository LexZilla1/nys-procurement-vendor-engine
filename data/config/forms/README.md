# Form field-mapping configs

Language-agnostic JSON configs that map a fillable NYS AcroForm's **real field
names** (extracted from the actual PDF) to a vendor-profile schema. Consumed by
the Python reference engine (`pipeline/form_fill.py`) now and by the future
pdf-lib browser client unchanged.

## Schema (`<form_id>.json`)

Top-level:
- `form_id`, `form_name`, `revision`, `source_url`, `field_count`
- `extraction` — how the field names were obtained + where the inventory lives
- `fields` — `{ <exact AcroForm field name> : <field entry> }`

Field entry:
| key | applies to | meaning |
|---|---|---|
| `class` | all | `"factual"` (auto-fillable from the vendor profile) or `"attestation"` (**never** auto-filled — a person must complete it: signatures, dates, Part V certification, preparer block, tax-status claims) |
| `type` | all | AcroForm type as extracted: `"/Tx"` (text) or `"/Btn"` (checkbox/radio) |
| `profile_key` | factual | the vendor-profile dict key this field maps from |
| `value_map` | radio `/Btn` | `{ profile value → export state }`; used ONLY when `value_map_confirmed` is true |
| `value_map_confirmed` | radio `/Btn` | `false` = export-state↔label order NOT confirmed from the real PDF widgets → engine routes the field to the **unfilled** list (never guesses a checkbox state) |
| `note` | any | free-text provenance / caveat |

## Hard rules the engine enforces (not the config)
- **Attestation fields are never emitted**, even if the vendor profile supplies a
  matching key (the attempt is recorded as a warning).
- **Missing factual data → field omitted**, returned in the `unfilled` list for
  the UI to surface — partial fill is valid.
- **Unconfirmed radios → unfilled**, never an inferred checkbox state.
- No output is submitted anywhere; it is a draft the vendor reviews and signs.

## No PII persistence
Configs contain **no** vendor data — only field names and mappings. TIN/SSN/DOB
values live only transiently in the caller's profile dict at fill time; nothing
here (or in tests/fixtures) persists them. Test data uses obvious placeholders
(`000000000`).
