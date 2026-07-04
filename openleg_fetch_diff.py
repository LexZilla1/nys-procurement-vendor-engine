#!/usr/bin/env python3
"""
Open Legislation fetch + diff for the golden-copy full-text rebuild (Phase 2).

Fetches each STATUTE-CLASS source's full section from the NY Senate Open
Legislation API and diffs it against the stored `## STATE TEXT (verbatim)`
block. Classifies each as FULL-MATCH / FRAGMENT / DIVERGENT and records the
API activeDate + repealed/repealedDate fields.

READ-ONLY with respect to the golden copy: this script NEVER writes to
golden-copy/. It emits a JSON report to stdout; the Phase-3 rebuild is a
separate, human-reviewed step.

Auth: reads NYSLEG_API_KEY from the environment. The key is never logged,
never written to disk, and must never be committed. Fails hard if unset.
No fallback to scraping any website — API errors stop the run (per task).

Status: written offline (network + key unavailable in the authoring
environment); untested against the live API. Validate on first networked
run with the LAB/220-I check below before trusting bulk output.

Usage:
    NYSLEG_API_KEY=... python3 openleg_fetch_diff.py [--only STF/139-J] [--json out.json]

Validation gate (per task): LAB/220-I must return a multi-subdivision
section (subds. 1-10, revision ~2025-01-03). The stored capture is a
confirmed one-subdivision fragment (subd. 6). If the API pull for LAB/220-I
does NOT show a section larger than the stored fragment, the run STOPS —
that indicates a fetch problem, not a corpus problem.
"""

import difflib
import json
import os
import re
import sys
import urllib.parse
import urllib.request

API_BASE = "https://legislation.nysenate.gov/api/3/laws"
SOURCES_DIR = os.path.join("golden-copy", "sources")

# STATUTE-CLASS mapping: source file -> (lawId, locationId), from the Phase-1
# classification (docs/API-REBUILD-PHASE1-CLASSIFICATION.md). The 23 non-
# statute sources (GFO chapters, OGS boilerplate, forms, NYCRR regulation)
# are deliberately absent — they are not in this API.
STATUTE_SOURCES = {
    "source-exec-314-mwbe-cert-validity.md": ("EXC", "314"),   # see DESIGN NOTE below
    "source-lab-220-i-public-work-registration.md": ("LAB", "220-I"),
    "source-stf-109-vendor-certificate.md": ("STF", "109"),    # MIXED capture — statute part only
    "source-stf-112.md": ("STF", "112"),
    "source-stf-139-d-noncollusion.md": ("STF", "139-D"),
    "source-stf-139-h-international-boycott.md": ("STF", "139-H"),
    "source-stf-139-j.md": ("STF", "139-J"),
    "source-stf-139-k.md": ("STF", "139-K"),
    "source-stf-139-l-sexual-harassment.md": ("STF", "139-L"),
    "source-stf-139-m-gender-based-violence.md": ("STF", "139-M"),
    "source-stf-163.md": ("STF", "163"),
    "source-stf-179-d.md": ("STF", "179-D"),
    "source-stf-179-e.md": ("STF", "179-E"),
    "source-stf-179-f.md": ("STF", "179-F"),
    "source-stf-179-g.md": ("STF", "179-G"),
    "source-stf-179-p.md": ("STF", "179-P"),
    "source-stf-179-q.md": ("STF", "179-Q"),
    "source-stf-179-s.md": ("STF", "179-S"),
    "source-stf-179-t.md": ("STF", "179-T"),
    "source-stf-179-u.md": ("STF", "179-U"),
    "source-stf-179-v.md": ("STF", "179-V"),
    "source-wkc-57-workers-comp.md": ("WKC", "57"),
}

# DESIGN NOTE — EXC/314: the stored capture is a DELIBERATE single-clause
# capture (only the current 5.(a) validity clause + its NB markers, per the
# file's VERSION NOTE). The diff will classify it FRAGMENT by construction.
# Do NOT auto-rebuild it to full section without an explicit human decision —
# that would reverse a documented capture-design choice.
DESIGN_PARTIAL = {"source-exec-314-mwbe-cert-validity.md"}

# Sunset cross-check targets (Phase 3): API repealed/repealedDate vs our records.
SUNSET_EXPECT = {
    ("EXC", "314"): "2028-07-01",
    ("STF", "139-J"): "2028-07-31",
    ("STF", "139-K"): "2028-07-31",
    ("STF", "163"): "2031-06-30",
}


def die(msg, code=1):
    print("FATAL: %s" % msg, file=sys.stderr)
    sys.exit(code)


def api_get(path, key, params=None):
    params = dict(params or {})
    params["key"] = key
    url = "%s/%s?%s" % (API_BASE, path, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # API error/unreachable -> STOP (no scraping fallback)
        die("API request failed for %s: %s — stopping (no fallback)." % (path, exc))
    if not payload.get("success", False):
        die("API returned success=false for %s: %s" % (path, payload.get("message")))
    return payload


def fetch_section(law_id, location_id, key):
    """GET /api/3/laws/{lawId}/{locationId} -> dict with text/activeDate/repealed*."""
    payload = api_get("%s/%s" % (law_id, location_id), key)
    doc = payload.get("result", {})
    return {
        "text": doc.get("text") or "",
        "activeDate": doc.get("activeDate"),
        "repealed": doc.get("repealed"),
        "repealedDate": doc.get("repealedDate"),
        "title": doc.get("title"),
        "docType": doc.get("docType"),
    }


def stored_state_text(fn):
    raw = open(os.path.join(SOURCES_DIR, fn), encoding="utf-8").read()
    m = re.search(r"^##\s*STATE TEXT[^\n]*\n(.*?)(?=^##\s|\Z)", raw, re.M | re.S)
    body = m.group(1) if m else ""
    return re.sub(r"\n?-{3,}\s*$", "", body).strip()


def norm(s):
    """Whitespace-insensitive normalization for containment/equality checks.
    Also strips the capture's leading '** ' emphasis markers (markdown-escaping
    of the Senate site's markers), so comparison is on the words themselves."""
    s = re.sub(r"^\*+\s*", "", s, flags=re.M)
    return re.sub(r"\s+", " ", s).strip()


def classify(stored, live):
    ns, nl = norm(stored), norm(live)
    if not ns:
        return "EMPTY-STORED"
    if ns == nl:
        return "FULL-MATCH"
    if ns in nl:
        return "FRAGMENT"
    # fuzzy: full-match with minor formatting drift?
    ratio = difflib.SequenceMatcher(None, ns, nl).ratio()
    if ratio > 0.98:
        return "FULL-MATCH~"   # near-identical; treat as full match, eyeball the diff
    return "DIVERGENT"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    key = os.environ.get("NYSLEG_API_KEY")
    if not key:
        die("NYSLEG_API_KEY is not set. Export it and re-run. "
            "(The key must never be committed to the repo.)")
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]

    # ---- Validation gate first: LAB/220-I must be a multi-subdivision section
    gate = fetch_section("LAB", "220-I", key)
    gate_subds = re.findall(r"^\s*(\d{1,2})\.\s", gate["text"], re.M)
    stored_220i = stored_state_text("source-lab-220-i-public-work-registration.md")
    if len(set(gate_subds)) < 2 or len(norm(gate["text"])) <= len(norm(stored_220i)):
        die("VALIDATION GATE FAILED: LAB/220-I did not return a multi-subdivision "
            "section larger than the stored fragment (subds seen: %s, activeDate: %s). "
            "Something is wrong with the FETCH — stopping before bulk run."
            % (sorted(set(gate_subds)), gate["activeDate"]))
    print("validation gate OK: LAB/220-I subds %s, activeDate %s"
          % (sorted(set(gate_subds), key=int), gate["activeDate"]), file=sys.stderr)

    report = []
    for fn, (law, loc) in sorted(STATUTE_SOURCES.items()):
        if only and only.upper() != "%s/%s" % (law, loc):
            continue
        live = fetch_section(law, loc, key)
        stored = stored_state_text(fn)
        verdict = classify(stored, live["text"])
        row = {
            "source": fn, "lawId": law, "locationId": loc, "verdict": verdict,
            "activeDate": live["activeDate"], "repealed": live["repealed"],
            "repealedDate": live["repealedDate"],
            "stored_chars": len(stored), "live_chars": len(live["text"]),
            "design_partial": fn in DESIGN_PARTIAL,
        }
        exp = SUNSET_EXPECT.get((law, loc))
        if exp is not None:
            row["sunset_expected"] = exp
            row["sunset_mismatch"] = (live.get("repealedDate") != exp)
        report.append(row)
        print("%-52s %-11s active=%s repealed=%s" %
              (fn, verdict, live["activeDate"], live.get("repealedDate")), file=sys.stderr)

    out = {"phase": 2, "api": API_BASE, "results": report}
    if "--json" in argv:
        path = argv[argv.index("--json") + 1]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
    else:
        json.dump(out, sys.stdout, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
