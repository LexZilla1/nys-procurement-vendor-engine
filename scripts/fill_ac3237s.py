#!/usr/bin/env python3
"""
Local demo — AC 3237-S (Substitute W-9) fill. NYS Procurement Vendor Engine.

Runs the reference fill engine on a SAMPLE vendor profile (fake data only) and
prints the fill report. If pypdf is installed AND a blank AC 3237-S PDF is
provided via --pdf, it also writes a filled draft to /tmp (factual fields only;
attestation/Part V never touched). No data is persisted or submitted.

    python3 scripts/fill_ac3237s.py                 # report only (no PDF needed)
    python3 scripts/fill_ac3237s.py --pdf blank.pdf # + write /tmp/ac3237s-draft.pdf

Sample TIN is the obvious placeholder 000000000 — never a realistic SSN/EIN.
"""

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.form_fill import load_form_config, build_fill_values, fill_report  # noqa: E402

NOTICE = ("Draft for vendor review — signature and Part V certification must be "
          "completed by an authorized person.")

# Fake sample profile — placeholders only. It also carries a certification_date;
# because "Certification Date" is an attestation field with no profile_key, the
# engine simply skips it (it appears under attestation_skipped, never filled).
SAMPLE_PROFILE = {
    "legal_business_name": "Acme Widgets LLC",
    "dba": "Acme",
    "entity_type": "Limited Liability Co.",         # radio -> unfilled (unconfirmed)
    "entity_type_other": "",
    "tin": "000000000",                              # placeholder, never a real TIN
    "tin_type": "EIN",                               # radio -> unfilled (unconfirmed)
    "remittance_address_street": "100 Example St, Suite 2",
    "remittance_address_csz": "Albany, NY 12207-0000",
    "ordering_address_street": "100 Example St, Suite 2",
    "ordering_address_csz": "Albany, NY 12207-0000",
    "business_email": "ap@example.com",
    "primary_contact_name": "Pat Vendor",
    "primary_contact_title": "Managing Member",
    "primary_contact_email": "pat@example.com",
    "primary_contact_phone": "518-555-0100",
    # attestation key the engine MUST refuse to auto-fill:
    "certification_date": "2026-07-04",
}


def _write_pdf(pdf_path, values):
    """Best-effort filled draft via pypdf. Returns output path or a reason string."""
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception as exc:
        return "pypdf unavailable (%s) — report printed, no PDF written" % type(exc).__name__
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, values)
    out = os.path.join(tempfile.gettempdir(), "ac3237s-draft.pdf")
    with open(out, "wb") as fh:
        writer.write(fh)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="AC 3237-S fill demo (sample data)")
    ap.add_argument("--pdf", help="path to a blank AC 3237-S PDF to fill (optional)")
    args = ap.parse_args(argv)

    config = load_form_config("ac3237s")
    result = build_fill_values(config, SAMPLE_PROFILE)
    report = fill_report(result)
    report["attestation_supplied_but_refused"] = sorted(result["attestation_supplied"])

    print(NOTICE)
    print()
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.pdf:
        outcome = _write_pdf(args.pdf, result["values"])
        print("\nPDF: %s" % outcome)
    else:
        print("\n(no --pdf given; report only. Attestation/Part V fields are never "
              "written — vendor completes and signs them.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
