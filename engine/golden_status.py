#!/usr/bin/env python3
"""
engine/golden_status.py — derive a machine-readable per-source citation-eligibility
status from a golden source's EXISTING metadata (Golden Copy Reliability Audit).

This does NOT invent a parallel taxonomy: every status is derived from signals
already written into the source files (Tier line, L/M-grade annotations, Covers
field, superseded-version markers, the standard header) plus, where supplied,
freshness_check outputs (DIVERGENT / sunset-stale). If a source's metadata is
insufficient to derive a status, that is itself a finding (status None + reason).

Statuses (most-restrictive first — the derivation returns the first that matches):

  PENDING_HUMAN_READ        not citable — a fresh capture not yet human-verified.
  DIVERGENT_FROM_API        not citable — freshness says the live text diverged.
  PARTIAL_CAPTURE           not citable — a fragment / mixed / excerpt capture.
  STALE_CHECK_REQUIRED      not citable — freshness sunset/stale flag is set.
  L_GRADE_INTERPRETIVE      citable ONLY into VERIFY / attorney-gated outputs —
                            verified text whose interpretation is gated (L/M grade).
  SUPERSEDED_VERSION_PRESENT citable — verified, but the file also carries a
                            superseded prior version; downstream must pick current.
  VERIFIED_GOLDEN           citable normally.

Pure functions, no I/O, so both validator.GoldenCopy (runtime guardrail) and
scripts/golden_audit.py (CI audit) share one derivation.
"""

import re

# Status constants ----------------------------------------------------------
PENDING_HUMAN_READ = "PENDING_HUMAN_READ"
DIVERGENT_FROM_API = "DIVERGENT_FROM_API"
PARTIAL_CAPTURE = "PARTIAL_CAPTURE"
STALE_CHECK_REQUIRED = "STALE_CHECK_REQUIRED"
L_GRADE_INTERPRETIVE = "L_GRADE_INTERPRETIVE"
SUPERSEDED_VERSION_PRESENT = "SUPERSEDED_VERSION_PRESENT"
VERIFIED_GOLDEN = "VERIFIED_GOLDEN"

ALL_STATUSES = (
    PENDING_HUMAN_READ, DIVERGENT_FROM_API, PARTIAL_CAPTURE, STALE_CHECK_REQUIRED,
    L_GRADE_INTERPRETIVE, SUPERSEDED_VERSION_PRESENT, VERIFIED_GOLDEN,
)

# Citation eligibility (used by GoldenCopy.cite guardrail).
CITABLE_NORMALLY = frozenset({VERIFIED_GOLDEN, SUPERSEDED_VERSION_PRESENT})
CITABLE_GATED_ONLY = frozenset({L_GRADE_INTERPRETIVE})
NOT_CITABLE = frozenset({PENDING_HUMAN_READ, DIVERGENT_FROM_API, PARTIAL_CAPTURE,
                         STALE_CHECK_REQUIRED})

# Output-context vocabulary for the guardrail.
OUTPUT_CONFIDENT = "CONFIDENT"
OUTPUT_VERIFY = "VERIFY"
OUTPUT_ATTORNEY_GATED = "ATTORNEY_GATED"
OUTPUT_CONTEXTS = (OUTPUT_CONFIDENT, OUTPUT_VERIFY, OUTPUT_ATTORNEY_GATED)
GATED_CONTEXTS = frozenset({OUTPUT_VERIFY, OUTPUT_ATTORNEY_GATED})


# Metadata-signal detectors -------------------------------------------------

def _covers(raw):
    m = re.search(r"^- \*\*Covers[^:*]*:\*\*\s*(.+)$", raw, re.M)
    return (m.group(1).strip() if m else "")


def has_pending_tier(raw):
    return "PENDING HUMAN READ" in raw


def has_lm_grade(raw):
    """An L- or M-grade (legal-interpretive / mixed) annotation is present."""
    if re.search(r"legal-interpretive", raw, re.I):
        return True
    # "GRADE — ... = L" / "= **M**" style annotations.
    return bool(re.search(r"grade\b[^\n]{0,60}?=\s*\*{0,2}[LM]\b", raw, re.I))


def has_superseded_version(raw):
    return bool(re.search(r"NB Effective until|superseded|DUAL-VERSION", raw, re.I))


def is_partial_capture(raw):
    covers = _covers(raw).lower()
    if re.search(r"FRAGMENT|MIXED capture|partial capture|single-clause|"
                 r"single clause", raw, re.I):
        return True
    # A Covers value that is explicitly an excerpt / layered / mixed capture.
    if re.search(r"\bexcerpt\b|\+ OSC|form layers|guidance layers", covers):
        return True
    return False


def has_complete_header(raw):
    """The standard header fields the parser also requires: a Link, a copy stamp,
    a Covers field, and a STATE TEXT block. (Enough to be a real golden.)"""
    return (bool(re.search(r"^- \*\*Link[^:*]*:\*\*\s*\S", raw, re.M))
            and bool(re.search(r"^- \*\*Copied exactly on:\*\*\s*\S", raw, re.M))
            and bool(re.search(r"^- \*\*Covers[^:*]*:\*\*\s*\S", raw, re.M))
            and "## STATE TEXT (verbatim)" in raw)


# Derivation ---------------------------------------------------------------

def derive_status(raw, freshness_verdict=None, sunset_stale=False):
    """Return (status, reasons). status is None when metadata is insufficient
    to derive one (itself an audit finding). `freshness_verdict` is the latest
    freshness verdict for this source ('DIVERGENT'/'FULL-MATCH'/... or None);
    `sunset_stale` is True when a freshness sunset/stale flag is set."""
    reasons = []
    if has_pending_tier(raw):
        return PENDING_HUMAN_READ, ["Tier: PENDING HUMAN READ present"]
    if freshness_verdict == "DIVERGENT":
        return DIVERGENT_FROM_API, ["freshness verdict DIVERGENT"]
    if is_partial_capture(raw):
        return PARTIAL_CAPTURE, ["partial/mixed/excerpt capture marker in metadata"]
    if sunset_stale:
        return STALE_CHECK_REQUIRED, ["freshness sunset/stale flag set"]
    if has_lm_grade(raw):
        return L_GRADE_INTERPRETIVE, ["L/M-grade (legal-interpretive) annotation present"]
    if has_superseded_version(raw):
        return SUPERSEDED_VERSION_PRESENT, ["superseded prior version present in file"]
    if has_complete_header(raw):
        return VERIFIED_GOLDEN, ["complete header + STATE TEXT, no restrictive marker"]
    reasons.append("insufficient metadata to derive a status "
                   "(missing header field / STATE TEXT / recognizable marker)")
    return None, reasons


def lgrade_provisions(raw):
    """List the L/M-grade provisions noted in the source, kept SEPARATE from the
    verified text (audit requirement). Returns the annotation snippets."""
    out = []
    for m in re.finditer(r"(?:^|\n)>?\s*\*{0,2}GRADE\b[^\n]*", raw):
        out.append(m.group(0).strip().lstrip("> ").strip())
    return out


def parse_provision_markers(raw):
    """Parse machine-readable per-provision eligibility markers from a source's
    ANNOTATIONS. One directive per line (documented format):

        - provision-eligibility: status=<STATUS> grade=<F|L|M> locator="<loc>" anchor="<verbatim substring>"

    Returns a list of {status, grade, locator, anchor}. Anchor-specific: a marker
    governs a citation only when its verbatim anchor overlaps the cited quote, so
    a VERIFIED marker for one provision cannot bless a different (e.g. L-grade)
    provision in the same file."""
    out = []
    for m in re.finditer(r"^- provision-eligibility:\s*(.+)$", raw, re.M):
        line = m.group(1)
        sm = re.search(r"status=(\S+)", line)
        am = re.search(r'anchor="([^"]+)"', line)
        if not (sm and am):
            continue
        lm = re.search(r'locator="([^"]+)"', line)
        gm = re.search(r"grade=(\S+)", line)
        out.append({"status": sm.group(1), "anchor": am.group(1),
                    "locator": lm.group(1) if lm else "",
                    "grade": gm.group(1) if gm else ""})
    return out


# Restrictiveness order for picking a governing marker when >1 anchor overlaps.
_RESTRICTIVENESS = {s: i for i, s in enumerate(
    (PENDING_HUMAN_READ, DIVERGENT_FROM_API, PARTIAL_CAPTURE, STALE_CHECK_REQUIRED,
     L_GRADE_INTERPRETIVE, SUPERSEDED_VERSION_PRESENT, VERIFIED_GOLDEN))}


def resolve_status(raw, quote, freshness_verdict=None, sunset_stale=False):
    """Status governing a SPECIFIC cited quote: a provision-level marker whose
    anchor overlaps the quote wins (most-restrictive if several overlap); else the
    file-level derive_status. Returns (status, reasons)."""
    matched = []
    for m in parse_provision_markers(raw):
        a = m["anchor"]
        if a and (a in quote or quote in a):
            matched.append(m)
    if matched:
        gov = min(matched, key=lambda m: _RESTRICTIVENESS.get(m["status"], 0))
        return gov["status"], ["provision-level marker %s (%s)"
                               % (gov.get("locator", ""), gov["status"])]
    return derive_status(raw, freshness_verdict, sunset_stale)


def is_citable(status, output_context):
    """Eligibility rule for the cite() guardrail. Returns (ok, reason)."""
    if status in CITABLE_NORMALLY:
        return True, ""
    if status in CITABLE_GATED_ONLY:
        if output_context in GATED_CONTEXTS:
            return True, ""
        return False, ("%s is citable only into VERIFY / attorney-gated outputs, "
                       "not a %s output" % (status, output_context))
    if status in NOT_CITABLE:
        return False, "%s sources are not citable" % status
    return False, "source has no derivable status; not citable"
