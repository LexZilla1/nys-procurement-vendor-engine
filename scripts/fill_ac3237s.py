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
    "entity_type": "Limited Liability Co.",         # radio -> /3 (confirmed map)
    "entity_type_other": "",
    "tin": "000000000",                              # placeholder, never a real TIN
    "tin_type": "EIN",                               # radio -> /0 (confirmed map)
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
        import pdfrw
    except Exception as exc:
        return "pdfrw unavailable (%s) — report printed, no PDF written" % type(exc).__name__

    def _txt(x):
        s = str(x) if x is not None else None
        return s[1:-1] if s and s.startswith("(") and s.endswith(")") else s

    def _fq(field):
        parts, n = [], field
        while n is not None:
            t = _txt(n.T)
            if t:
                parts.append(t)
            n = n.Parent
        return ".".join(reversed(parts))

    def _terminals(fields):
        for f in fields or []:
            kids = f.Kids or []
            # a kid is a terminal field if it has its own /T (name); pure widget
            # kids (radio options) have no /T and belong to their parent.
            named_kids = [k for k in kids if _txt(k.T)]
            if named_kids:
                for k in named_kids:
                    yield k
            else:
                yield f

    tpl = pdfrw.PdfReader(pdf_path)
    for f in _terminals(tpl.Root.AcroForm.Fields):
        name = _fq(f)
        if name not in values:
            continue
        val = values[name]
        ft = str(f.FT) if f.FT else None
        if ft == "/Btn":                                   # radio: set /V + kid /AS
            st = pdfrw.PdfName(val.lstrip("/"))
            f.V = st
            for k in (f.Kids or [f]):
                ap = k.AP.N if k.AP else None
                keys = [str(s) for s in (ap.keys() if ap else [])]
                k.AS = st if ("/" + val.lstrip("/")) in keys else pdfrw.PdfName("Off")
        else:                                              # text
            f.V = pdfrw.PdfString.encode(val)
    # ask viewers to render appearances for the values we set
    tpl.Root.AcroForm.update(pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject("true")))
    out = os.path.join(tempfile.gettempdir(), "ac3237s-draft.pdf")
    pdfrw.PdfWriter().write(out, tpl)
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
