# data/schemas — daily-habit backend (PR 1: state primitives)

JSON Schemas (draft 2020-12) for the domain objects in `engine/`. They are the
language-agnostic contract mirrored by the Python primitives, so a future
browser/UI client can consume the same shapes.

| Schema | Backs | Notes |
| --- | --- | --- |
| `citation.schema.json` | `engine/citation.py` | No bare strings; `source_type` is a closed set. |
| `dated_obligation.schema.json` | `engine/dated_objects.py` | Categorical `state` only; `date_status` verify-first. |
| `credential_status.schema.json` | future credential object | **Separate axis** from obligation `state`; includes `RECERT_PRESUMPTION_PENDING`. |
| `transition_log_entry.schema.json` | `engine/state_machine.py` | Actor + timestamp + from/to + optional citation. |
| `tender.schema.json` | Tender | `entity_id` nullable (future multi-entity). |
| `contract.schema.json` | Contract | Spawned on AWARDED; `entity_id` nullable. |
| `invoice.schema.json` | Invoice | **Shell for PR 2** — fields only, no clock logic. |

## Invariants baked into these schemas
- **Never-green:** no numeric confidence / risk / score field exists in any
  schema. Operational integers (`net_terms_days`, `lead_times` entries) are
  counts, not scores. `test_daily_habit_backend.py` scans for this.
- **Verify-first:** `date_status` carries `VERIFY_AT_SOURCE`; `due_date` is
  nullable so an unknown date is explicit, never a guessed default.
- **Two axes:** obligation `state` and `credential_status` are separate enums.
  `RECERT_PRESUMPTION_PENDING` appears only in `credential_status`.
- **No tier-3 data:** no TIN/SSN/DOB fields anywhere.

`$ref`s are relative sibling filenames resolved against each schema's `$id`
base URI.
