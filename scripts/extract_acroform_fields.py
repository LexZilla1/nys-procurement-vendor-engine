#!/usr/bin/env python3
"""
Extract the AcroForm field inventory from a committed form PDF (pure-Python,
pdfrw — no native crypto dependency). Regenerates tests/fixtures/<form>_fields.json
so the committed inventory is provably derived from the real PDF, and prints the
radio-group export-state order confirmed from widget /Rect positions.

    python3 scripts/extract_acroform_fields.py tests/fixtures/ac3237s.pdf
    python3 scripts/extract_acroform_fields.py tests/fixtures/ac3237s.pdf --write tests/fixtures/ac3237s_fields.json
"""

import argparse
import json
import sys


def _txt(x):
    s = str(x) if x is not None else None
    if s and s.startswith("(") and s.endswith(")"):
        return s[1:-1]
    return s


def _fq(field):
    parts, n = [], field
    while n is not None:
        t = _txt(n.T)
        if t:
            parts.append(t)
        n = n.Parent
    return ".".join(reversed(parts))


def _states(widget):
    ap = widget.AP.N if widget.AP else None
    return [str(s) for s in (ap.keys() if ap else [])]


def _rect(widget):
    try:
        return [float(v) for v in widget.Rect]
    except Exception:
        return None


def extract(pdf_path):
    import pdfrw
    r = pdfrw.PdfReader(pdf_path)
    fields = []
    for f in r.Root.AcroForm.Fields:
        ft = str(f.FT) if f.FT else None
        kids = f.Kids or []
        # a parent with kids that carry the type/name suffix
        if ft is None and kids:
            ft = str(kids[0].FT) if kids[0].FT else None
        name = _fq(f)
        if not f.T and kids:
            name = _fq(kids[0])
        elif kids and _txt(kids[0].T):
            name = _fq(f) + "." + _txt(kids[0].T)
        entry = {"name": name, "type": ft}
        if ft == "/Btn":
            # collect export states across the field's own AP or its kids' APs,
            # ordered by widget reading position (top->bottom, then left->right)
            widgets = kids if kids else [f]
            # bucket y into ~8pt rows so same-row widgets group before x-sort
            def _key(w):
                rc = _rect(w) or [0, 0]
                return (-(int(rc[1]) // 8), rc[0])
            ordered = []
            for w in sorted(widgets, key=_key):
                for s in _states(w):
                    if s not in ordered:
                        ordered.append(s)
            # keep /Off last if present
            off = [s for s in ordered if s == "/Off"]
            ordered = [s for s in ordered if s != "/Off"] + off
            entry["states"] = ordered
        fields.append(entry)
    return {"field_count": len(fields), "fields": fields}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--write", help="write the inventory JSON to this path")
    args = ap.parse_args(argv)
    inv = extract(args.pdf)
    payload = {
        "_source": "AcroForm field dump extracted via pdfrw from the committed "
                   "PDF %s (canonical OSC form). Regenerate with "
                   "scripts/extract_acroform_fields.py." % args.pdf,
        "_note": "Authoritative field inventory used by the config-completeness "
                 "test. Radio 'states' are ordered by widget reading position "
                 "(top->bottom, left->right); /Off last.",
        "field_count": inv["field_count"],
        "fields": inv["fields"],
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        with open(args.write, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote %d fields to %s" % (inv["field_count"], args.write), file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
