#!/usr/bin/env python3
"""
Manual smoke test for the Step 4 live LLM fallback — NYS Procurement Vendor Engine.

Runs ONE real claude-sonnet-4-6 call on a single sample ad and prints the full
result object. This is the only place that hits the real API on purpose; the
unit tests never do.

Run (key set locally / in the shell):

    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_triage_llm.py

If ANTHROPIC_API_KEY is not set, it prints how to set it and exits without a
network call (the triage engine safely returns HUMAN_REVIEW in that case).
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import step1_triage as T  # noqa: E402

# A STATE-agency issuer (gate confirms STATE) with pasted ad text and NO ad_type,
# so source_type != nyscr and Step 4 (the live LLM fallback) fires.
SAMPLE_AD = {
    "issuer": "Office of General Services",
    "text": (
        "NOTICE TO BIDDERS — The New York State Office of General Services is "
        "soliciting sealed competitive bids for facility custodial services at "
        "the Empire State Plaza. Interested vendors must submit a responsive bid "
        "package by the stated deadline; bids will be publicly opened. See the "
        "solicitation for insurance, MWBE participation, and submission "
        "requirements."
    ),
}


def main():
    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        print("ANTHROPIC_API_KEY is not set — no API call made.\n"
              "Set it and re-run, e.g.:\n"
              "    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_triage_llm.py",
              file=sys.stderr)
        return 2
    print("Sample ad (issuer=%r, source will be non-NYSCR -> Step 4 live call):\n"
          % SAMPLE_AD["issuer"])
    print(SAMPLE_AD["text"])
    print("\n--- one real claude-sonnet-4-6 call via Step 4 ---\n")
    result = T.triage(SAMPLE_AD)          # no llm injected -> live classifier
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
