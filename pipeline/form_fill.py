#!/usr/bin/env python3
"""
Generic form-fill engine — NYS Procurement Vendor Engine (Step 6).

Pure functions that turn a form's field-mapping config + a vendor profile into a
`{field_name: value}` fill map. Client-side-portable by design: no I/O beyond
loading the committed config, no network, no persistence. The browser port
(pdf-lib) consumes the SAME JSON config, so this is the reference semantics.

Hard invariants (enforced HERE, not in the prompt/config):
  * Attestation fields are NEVER emitted — even if the vendor profile supplies a
    matching key. Such an attempt is recorded in `attestation_supplied` (logged)
    and the field is still skipped. Signatures, dates, Part V certification, the
    preparer block, and tax-status claims must be completed by an authorized
    person, never the engine.
  * Missing factual data → the field is omitted and listed in `unfilled` (partial
    fill is valid; the UI shows the vendor what to finish by hand).
  * A radio /Btn with value_map_confirmed=false is routed to `unfilled`, never an
    inferred checkbox state.
  * Nothing here submits anything. The output is a draft for vendor review.

No TIN/SSN/DOB is persisted anywhere: values live only in the caller's profile
dict and the returned in-memory map.
"""

import json
import os
import sys

CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "config", "forms")

FACTUAL = "factual"
ATTESTATION = "attestation"


def load_form_config(form_id):
    """Load data/config/forms/<form_id>.json. Raises FileNotFoundError if absent."""
    path = os.path.join(CONFIG_DIR, "%s.json" % form_id)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _is_empty(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def build_fill_values(config, vendor_profile):
    """Return a fill result:

        {"values": {field_name: value},         # factual, present, fillable
         "unfilled": [{"field","reason"}...],    # factual but missing/unconfirmed
         "attestation_skipped": [field_name...], # every attestation field
         "attestation_supplied": [field_name...]}# attestation the profile TRIED to set

    The `values` map is what gets written to the PDF. Attestation fields never
    appear in it. Radios only appear when their value_map is confirmed AND the
    profile value maps to an export state.
    """
    profile = vendor_profile or {}
    values, unfilled, attestation_skipped, attestation_supplied = {}, [], [], []

    for field_name, spec in config.get("fields", {}).items():
        klass = spec.get("class")

        # -- attestation: NEVER emit, regardless of what the profile holds -----
        if klass == ATTESTATION:
            attestation_skipped.append(field_name)
            pkey = spec.get("profile_key")
            if pkey and not _is_empty(profile.get(pkey)):
                attestation_supplied.append(field_name)
                sys.stderr.write(
                    "form_fill: refusing to auto-fill attestation field %r from "
                    "profile key %r — must be completed by an authorized person.\n"
                    % (field_name, pkey))
            continue

        # -- factual radio (/Btn): only fill when the value map is confirmed ----
        if spec.get("type") == "/Btn":
            pkey = spec.get("profile_key")
            raw = profile.get(pkey) if pkey else None
            if not spec.get("value_map_confirmed") or not spec.get("value_map"):
                unfilled.append({"field": field_name,
                                 "reason": "radio export-state order unconfirmed — "
                                           "vendor selects this box by hand"})
                continue
            if _is_empty(raw):
                unfilled.append({"field": field_name,
                                 "reason": "no value for profile key %r" % pkey})
                continue
            state = spec["value_map"].get(raw)
            if state is None:
                unfilled.append({"field": field_name,
                                 "reason": "profile value %r not in value_map" % raw})
                continue
            values[field_name] = state
            continue

        # -- factual text (/Tx) ------------------------------------------------
        pkey = spec.get("profile_key")
        raw = profile.get(pkey) if pkey else None
        if _is_empty(raw):
            unfilled.append({"field": field_name,
                             "reason": "no value for profile key %r" % pkey})
        else:
            values[field_name] = raw

    return {"values": values, "unfilled": unfilled,
            "attestation_skipped": attestation_skipped,
            "attestation_supplied": attestation_supplied}


def fill_report(result):
    """Compact, UI-friendly summary of a build_fill_values result."""
    return {
        "filled": sorted(result["values"].keys()),
        "unfilled": [u["field"] for u in result["unfilled"]],
        "attestation_skipped": sorted(result["attestation_skipped"]),
    }
