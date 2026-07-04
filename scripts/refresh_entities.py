#!/usr/bin/env python3
"""
Refresh the Step 1 Triage entity snapshot from the data.ny.gov ABO datasets.

MANUAL ONLY in this PR — deliberately NOT wired into CI. It mirrors the monthly
freshness-check pattern (Socrata SODA API, stdlib only) but writes the entity
table, not a report. Run it by hand to expand/refresh data/entities/entities.json
against the authoritative ABO State/Local Authorities rosters; STATE_AGENCY and
SUNY_CUNY rows are maintained from the official agency/university rosters.

  python3 scripts/refresh_entities.py --print        # fetch + print, no write
  python3 scripts/refresh_entities.py --write         # merge into the snapshot
  python3 scripts/refresh_entities.py --selftest      # offline shape test

Boundaries: read-only against the network (Socrata public API, optional free
app token via SOCRATA_APP_TOKEN); it never scrapes behind auth. If the network
is unavailable it fails cleanly — the committed snapshot remains the source of
truth for runtime (the triage engine never hits the network).
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(REPO, "data", "entities", "entities.json")

# ABO authority datasets on data.ny.gov (4x4s reused from the connector work).
ABO_SOURCES = [
    {"domain": "data.ny.gov", "fourby": "ehig-g5x3",
     "name_field": "authority_name", "type": "AUTHORITY",
     "label": "ABO State Authorities"},
    {"domain": "data.ny.gov", "fourby": "8w5p-k45m",
     "name_field": "authority_name", "type": "AUTHORITY",
     "label": "ABO Local Authorities (incl. IDAs/LDCs)"},
]


def _fetch(domain, fourby, limit=5000, token=None):
    params = {"$select": "*", "$limit": str(limit)}
    url = "https://%s/resource/%s.json?%s" % (domain, fourby, urllib.parse.urlencode(params))
    headers = {"Accept": "application/json"}
    if token:
        headers["X-App-Token"] = token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_authorities(token=None, capture_date=None):
    rows = []
    for src in ABO_SOURCES:
        try:
            data = _fetch(src["domain"], src["fourby"], token=token)
        except Exception as exc:
            raise SystemExit("FATAL: fetch failed for %s (%s): %s — the committed "
                             "snapshot stays authoritative; no scraping fallback."
                             % (src["label"], src["fourby"], exc))
        for r in data:
            name = (r.get(src["name_field"]) or "").strip()
            if not name:
                continue
            rows.append({"name": name, "type": src["type"], "aliases": [],
                         "list_source": "https://%s/resource/%s.json (%s)"
                         % (src["domain"], src["fourby"], src["label"]),
                         "list_capture_date": capture_date})
    return rows


def merge(existing, fetched):
    """Add fetched rows whose normalized name is not already present. Never
    deletes hand-curated rows or aliases."""
    from step1_triage import normalize  # reuse the exact matching normalization
    have = {normalize(e["name"]) for e in existing["entities"]}
    for e in existing["entities"]:
        for a in e.get("aliases", []):
            have.add(normalize(a))
    added = 0
    for row in fetched:
        if normalize(row["name"]) in have:
            continue
        existing["entities"].append(row)
        have.add(normalize(row["name"]))
        added += 1
    return added


def _selftest():
    # Offline shape test: merge a couple of synthetic authority rows into a
    # copy of the snapshot and confirm de-dup + shape, no network.
    sys.path.insert(0, REPO)
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    before = len(snap["entities"])
    fetched = [
        {"name": "Metropolitan Transportation Authority", "type": "AUTHORITY",
         "aliases": [], "list_source": "x", "list_capture_date": "2026-07-04"},  # dup
        {"name": "Battery Park City Authority", "type": "AUTHORITY",
         "aliases": [], "list_source": "x", "list_capture_date": "2026-07-04"},  # new
    ]
    added = merge(snap, fetched)
    assert added == 1, added
    assert len(snap["entities"]) == before + 1
    print("SELF-TEST: ALL PASS (dedup keeps MTA, adds Battery Park City Authority)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Refresh Step 1 Triage entity snapshot")
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--date", default="2026-07-04", help="capture date (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not (args.do_print or args.write):
        ap.error("choose --print, --write, or --selftest")

    sys.path.insert(0, REPO)
    token = os.environ.get("SOCRATA_APP_TOKEN")
    fetched = fetch_authorities(token=token, capture_date=args.date)
    if args.do_print:
        print(json.dumps(fetched[:20], indent=2))
        print("... fetched %d authority rows total" % len(fetched), file=sys.stderr)
        return 0
    snap = json.load(open(SNAPSHOT, encoding="utf-8"))
    added = merge(snap, fetched)
    with open(SNAPSHOT, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("merged %d new authority rows into %s" % (added, SNAPSHOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
