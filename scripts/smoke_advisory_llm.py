#!/usr/bin/env python3
"""Manual smoke test for the coverage_advisory live call — NYS Procurement Vendor.

Scores the sample tender, then makes ONE real advisory call over its UNMAPPED /
NEEDS_REVIEW items and prints the advisory (or "no advisory"). This is the only
place that hits the real API on purpose for the advisory layer; the unit tests
never do.

Run (key set locally / in the shell):

    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_advisory_llm.py

If ANTHROPIC_API_KEY is not set, it prints how to set it and exits without a
network call (advise() safely returns None in that case, so the report just
renders without an advisory section).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bid_readiness as BR          # noqa: E402
import coverage_advisory as CA      # noqa: E402
from tender_extractor import extract  # noqa: E402
from llm_config import get_anthropic_model  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TENDER = os.path.join(HERE, "sample-tender.pdf")
PROFILE = os.path.join(HERE, "sample-vendor-profile.json")


def main():
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        print("ANTHROPIC_API_KEY is not set — no API call made.\n"
              "Set it and re-run, e.g.:\n"
              "    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_advisory_llm.py",
              file=sys.stderr)
        return 2
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)
    report = BR.score_bid(extract(TENDER), profile)
    model = get_anthropic_model()
    print("Scored sample tender; advising over UNMAPPED / NEEDS_REVIEW items.")
    print("\n--- one real %s advisory call ---\n" % model)
    advisory = CA.advise(report)                # no injection -> live call
    if advisory is None:
        print("advisory: None (no advisory section rendered)")
    else:
        print(json.dumps(advisory, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
