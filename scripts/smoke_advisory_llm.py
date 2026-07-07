#!/usr/bin/env python3
"""Manual smoke test for the coverage_advisory live call — NYS Procurement Vendor.

Scores a tender fixture, then makes ONE real advisory call over its UNMAPPED /
NEEDS_REVIEW items via coverage_advisory.advise_with_diagnostics() and prints the
diagnostic (null_reason / validation_reason / stop_reason / usage / latency) plus
the advisory (or None) and, when non-null, the rendered ADVISORY section exactly
as a vendor would see it. This is the only place that hits the real API on
purpose for the advisory layer; the unit tests never do.

The diagnostic fields are SMOKE/DEBUG ONLY — they are never part of the
vendor-facing report.

Usage:

    # default fixture (sample-tender.pdf), backwards-compatible:
    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_advisory_llm.py

    # target a specific real RFQ fixture:
    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_advisory_llm.py test-tenders/rfp25003mediation.pdf

If ANTHROPIC_API_KEY is not set, it prints the deterministic parts (model,
fixture, bucket + payload counts) and exits WITHOUT a network call — advise()
safely returns None in that case, so the report just renders without an advisory
section. The API key is never printed. There is no automatic retry.
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
DEFAULT_TENDER = os.path.join(HERE, "sample-tender.pdf")
PROFILE = os.path.join(HERE, "sample-vendor-profile.json")


def resolve_fixture(argv):
    """The fixture path from argv[0], or the default sample tender when none is
    given. Pure — no key, no network — so callers/tests can resolve a fixture
    without a live key."""
    return argv[0] if argv else DEFAULT_TENDER


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    fixture = resolve_fixture(argv)
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)
    report = BR.score_bid(extract(fixture), profile)
    model = get_anthropic_model()
    payload = CA.build_payload(report)

    print("resolved model : {}".format(model))
    print("fixture        : {}".format(fixture))
    print("coverage buckets: {}".format(dict(report.coverage_counts)))
    print("payload counts : needs_review={} unmapped={} possible_authorities={} "
          "captured_authorities={} known_kinds={}".format(
              len(payload["needs_review"]), len(payload["unmapped"]),
              len(payload["possible_authorities"]),
              len(payload.get("captured_authorities", [])),
              len(payload["known_kinds"])))

    if not (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        print("\nANTHROPIC_API_KEY is not set — no API call made.\n"
              "Set it and re-run, e.g.:\n"
              "    ANTHROPIC_API_KEY=sk-ant-... python3 scripts/smoke_advisory_llm.py "
              "[FIXTURE]", file=sys.stderr)
        return 2

    print("\n--- one real {} advisory call (no retry) ---\n".format(model))
    diag = CA.advise_with_diagnostics(report)        # no injection -> live call
    print("null_reason      : {}".format(diag["null_reason"]))
    print("validation_reason: {}".format(diag["validation_reason"]))
    print("stop_reason      : {}".format(diag["stop_reason"]))
    print("usage            : {}".format(diag["usage"]))
    print("latency_seconds  : {}".format(diag["latency_seconds"]))
    print("suppressed_captured           : {}".format(
        json.dumps(diag.get("suppressed_captured", []), ensure_ascii=False)))
    print("captured_authorities_unnormalized: {}".format(
        diag.get("captured_authorities_unnormalized", [])))
    advisory = diag["advisory"]
    print("advisory         :")
    print(json.dumps(advisory, indent=2, ensure_ascii=False)
          if advisory is not None else "None")
    if advisory is not None:
        print("\n=== RENDERED ADVISORY SECTION (as a vendor would see it) ===")
        print("\n".join(CA.render_advisory(advisory)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
