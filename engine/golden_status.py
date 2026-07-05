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
INTERIM_VERIFY = "INTERIM_VERIFY"
SUPERSEDED_VERSION_PRESENT = "SUPERSEDED_VERSION_PRESENT"
VERIFIED_GOLDEN = "VERIFIED_GOLDEN"

ALL_STATUSES = (
    PENDING_HUMAN_READ, DIVERGENT_FROM_API, PARTIAL_CAPTURE, STALE_CHECK_REQUIRED,
    L_GRADE_INTERPRETIVE, INTERIM_VERIFY, SUPERSEDED_VERSION_PRESENT, VERIFIED_GOLDEN,
)

# Citation eligibility (used by GoldenCopy.cite guardrail).
# INTERIM_VERIFY: a verbatim layer inside a still-PARTIAL/mixed capture that a
# human has explicitly cleared to be cited ONLY into VERIFY / attorney-gated
# outputs on an INTERIM basis, pending a clean recapture via the sanctioned
# statute-capture workflow. It is never confident-eligible.
CITABLE_NORMALLY = frozenset({VERIFIED_GOLDEN, SUPERSEDED_VERSION_PRESENT})
CITABLE_GATED_ONLY = frozenset({L_GRADE_INTERPRETIVE, INTERIM_VERIFY})
NOT_CITABLE = frozenset({PENDING_HUMAN_READ, DIVERGENT_FROM_API, PARTIAL_CAPTURE,
                         STALE_CHECK_REQUIRED})

# Restrictiveness ordering (higher = more restrictive). Used to resolve the
# MOST restrictive eligibility when a quote matches multiple provision markers —
# ambiguity never silently upgrades toward confident.
RESTRICTIVENESS = {
    VERIFIED_GOLDEN: 0, SUPERSEDED_VERSION_PRESENT: 0,
    L_GRADE_INTERPRETIVE: 1, INTERIM_VERIFY: 1,
    STALE_CHECK_REQUIRED: 2,
    PARTIAL_CAPTURE: 3, DIVERGENT_FROM_API: 3, PENDING_HUMAN_READ: 3,
    None: 4,
}

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


# Per-provision eligibility markers -----------------------------------------
#
# A source may carry a `## PROVISION ELIGIBILITY` block (engine metadata, NOT
# part of the verbatim rule) that assigns citation-eligibility to specific
# provisions or to the whole file, overriding the derived whole-file status for
# matching quotes. Two scopes:
#   * scope: provision — a verbatim `anchor` substring; a quote CONTAINED in the
#     anchor takes that eligibility (e.g. EXC/314 5(a) VERIFIED_GOLDEN while the
#     rest of the L-graded file stays gated).
#   * scope: source   — applies to the whole file (e.g. an INTERIM_VERIFY gate on
#     a mixed/PARTIAL capture pending clean recapture).
# This never edits or reflows the STATE TEXT body.

_PROV_HEADER = "## PROVISION ELIGIBILITY"
_PROV_ELIGIBILITIES = frozenset({VERIFIED_GOLDEN, L_GRADE_INTERPRETIVE, INTERIM_VERIFY})


def provision_markers(raw):
    """Parse the PROVISION ELIGIBILITY block into a list of
    {eligibility, scope, anchor}. Returns [] when the block is absent."""
    idx = raw.find(_PROV_HEADER)
    if idx < 0:
        return []
    block = raw[idx + len(_PROV_HEADER):]
    nxt = re.search(r"\n## ", block)
    if nxt:
        block = block[:nxt.start()]
    markers = []
    for chunk in re.split(r"\n-\s+", block)[1:]:
        elig = re.search(r"eligibility:\s*([A-Z_]+)", chunk)
        if not elig or elig.group(1) not in _PROV_ELIGIBILITIES:
            continue
        anchor = re.search(r'anchor:\s*"(.+?)"', chunk, re.S)
        scope = re.search(r"scope:\s*(provision|source)", chunk)
        markers.append({
            "eligibility": elig.group(1),
            "scope": scope.group(1) if scope else ("provision" if anchor else "source"),
            "anchor": anchor.group(1) if anchor else None,
        })
    return markers


def effective_status(raw, quote, base_status):
    """Resolve citation-eligibility for a SPECIFIC quote, applying any provision
    markers on top of the whole-file `base_status`.

      1. provision-scope marker whose verbatim anchor CONTAINS the quote wins
         (explicit human upgrade/downgrade); most restrictive on ambiguity.
      2. else a source-scope marker sets the eligibility (an interim gate).
      3. else the whole-file base_status.
    """
    markers = provision_markers(raw)
    if not markers:
        return base_status
    prov = [m["eligibility"] for m in markers
            if m["scope"] == "provision" and m["anchor"] and quote and quote in m["anchor"]]
    if prov:
        return max(prov, key=lambda s: RESTRICTIVENESS.get(s, 4))
    src = [m["eligibility"] for m in markers if m["scope"] == "source"]
    if src:
        return max(src, key=lambda s: RESTRICTIVENESS.get(s, 4))
    return base_status


def has_confident_provision(raw):
    """True if the source declares a VERIFIED_GOLDEN provision-scope marker
    (e.g. EXC/314 §314(5)(a))."""
    return any(m["eligibility"] == VERIFIED_GOLDEN and m["scope"] == "provision"
               for m in provision_markers(raw))


def has_interim_verify_marker(raw):
    """True if the source declares an INTERIM_VERIFY marker (a mixed/PARTIAL
    capture gated to VERIFY-only pending clean recapture)."""
    return any(m["eligibility"] == INTERIM_VERIFY for m in provision_markers(raw))
