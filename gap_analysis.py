#!/usr/bin/env python3
"""
Capability 2 — Gap Analysis: Vendor Profile × RFP Checklist → verdict.

LOGIC ENGINE ONLY (no UI this pass). Given an RFP requirements checklist and a
vendor profile, produce a per-requirement verdict:
    ✅ HAVE / ❌ MISSING / ⏰ EXPIRING / ⚠️ UNKNOWN.

Core invariant (CAPABILITY2-BUILD-SPEC §Purpose): NEVER show ✅ when validity
cannot be confirmed. Unknown is safe; a false green is not.

Grounding & compliance boundaries honored here:
  * The requirements catalog is seeded ONLY from currently-golden sources; each
    entry's citation is verified verbatim through GoldenCopy.cite() at import.
    Where a golden source states no validity DURATION, validity_rule is
    "unknown" — the engine never invents a rule.
  * Free-form auto-match (Option 2) suggests IDENTITY only, against
    already-golden catalog entries. A vendor "yes" maps identity; it never
    creates a golden rule and never promotes a credential to golden.
  * SUNSET OVERRIDE: if a requirement's golden rule sits under a LAPSED /
    quarantined authorization (per freshness_checker), the verdict is forced to
    ⚠️ UNKNOWN regardless of dates — no false green on a rule whose program
    expired.
  * UPL: output is information to help prepare a bid, not legal advice.
"""

import argparse
import datetime
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

import freshness_checker as fc
from validator import GoldenCopy
from engine import golden_status as gs

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Verdict vocabulary
# ---------------------------------------------------------------------------

HAVE = "HAVE"
MISSING = "MISSING"
EXPIRING = "EXPIRING"
UNKNOWN = "UNKNOWN"
ICON = {HAVE: "✅", MISSING: "❌", EXPIRING: "⏰", UNKNOWN: "⚠️"}

# candidate_state (free-form only)
SUGGESTED = "suggested"
CONFIRMED = "confirmed"
ATTORNEY_PENDING = "attorney-pending"

UPL_FRAMING = ("This is information to help you prepare your bid, not legal advice. "
               "Verify with counsel where flagged.")

_GC = GoldenCopy()
SOURCES_DIR = _GC.sources_dir


# ---------------------------------------------------------------------------
# Requirements Catalog (seeded from currently-golden sources ONLY)
# ---------------------------------------------------------------------------

@dataclass
class CatalogEntry:
    requirement_id: str
    name: str
    aliases: list
    source_file: str
    citation_quote: str
    validity_rule: str            # fixed-period:<n>y | on-material-change | none | per-submission | unknown
    sunset_source_file: Optional[str] = None  # golden file whose sunset gates this rule


# Seed. Only MWBE §314 carries a golden validity DURATION (fixed-period:5y);
# the others are golden REQUIREMENTS whose validity duration is not stated in
# the golden copy, so validity_rule is "unknown" (never invented).
_CATALOG_SEED = [
    CatalogEntry(
        requirement_id="mwbe-certification",
        name="MWBE certification (Minority and Women-Owned Business Enterprise)",
        aliases=["MWBE", "M/WBE", "WBE", "MBE",
                 "minority and women-owned business enterprise",
                 "minority and women owned business enterprise",
                 "MWBE certification", "M/WBE cert", "MWBE cert"],
        source_file="source-exec-314-mwbe-cert-validity.md",
        citation_quote=("all minority and women-owned business enterprise certifications shall "
                        "be valid for a period of five years."),
        validity_rule="fixed-period:5y",
        sunset_source_file="source-exec-314-mwbe-cert-validity.md",
    ),
    CatalogEntry(
        requirement_id="vendor-responsibility",
        name="Vendor Responsibility determination (VendRep)",
        aliases=["vendor responsibility", "VendRep", "responsibility questionnaire",
                 "vendor responsibility questionnaire", "vendrep questionnaire"],
        source_file="source-xi-16-vendor-responsibility.md",
        citation_quote=("Such review shall be designed to provide reasonable assurances that the "
                        "proposed contractor is responsible."),
        validity_rule="unknown",
    ),
    CatalogEntry(
        requirement_id="workers-comp-insurance",
        name="Workers' compensation coverage",
        aliases=["workers comp", "workers' compensation", "workers compensation insurance",
                 "workers compensation", "WC coverage", "workers comp insurance"],
        source_file="source-wkc-57-workers-comp.md",
        citation_quote=("shall not enter into any such contract unless proof duly subscribed by "
                        "an insurance carrier is produced in a form satisfactory to the chair, "
                        "that compensation for all employees has been secured as provided by "
                        "this chapter."),
        validity_rule="unknown",
    ),
]


def _build_catalog():
    """Validate every catalog citation verbatim through GoldenCopy.cite() at
    import. A non-verbatim quote is a build-failing error — the catalog must be
    grounded, never paraphrased."""
    catalog = {}
    for e in _CATALOG_SEED:
        # The catalog is seeded only from currently-golden sources and its
        # citations are surfaced verbatim in vendor-facing verdicts, so validate
        # each into a CONFIDENT output: verbatim AND confident-eligible. A seed
        # quote that is not confident-eligible fails the build here rather than
        # reaching a vendor as a confident citation.
        _GC.cite(e.source_file, e.citation_quote, output_context=gs.OUTPUT_CONFIDENT)
        catalog[e.requirement_id] = e
    return catalog


CATALOG = _build_catalog()


# ---------------------------------------------------------------------------
# Vendor Profile schema
# ---------------------------------------------------------------------------

@dataclass
class VendorCredential:
    vendor_id: str = ""
    requirement_id: Optional[str] = None       # catalog link, or None for free-form
    label: str = ""                            # vendor's own wording
    status: str = "have"                       # have | expired | not-applicable
    issuance_date: Optional[str] = None
    expiry_date: Optional[str] = None          # ISO date, or "no-expiry"
    attachment: Optional[str] = None           # STORED, never parsed as truth
    source_path: str = "checklist"             # checklist | freeform
    candidate_state: Optional[str] = None      # None | suggested | confirmed | attorney-pending


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _parse_date(value):
    if not value or value == "no-expiry":
        return None
    try:
        return datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _add_years(d, n):
    try:
        return d.replace(year=d.year + n)
    except ValueError:            # Feb 29 → Feb 28 in a non-leap year
        return d.replace(year=d.year + n, day=28)


_FIXED_PERIOD_RE = re.compile(r"^fixed-period:(\d+)y$")


# ---------------------------------------------------------------------------
# Free-form auto-match (Option 2 — confirm identity, catalog-only)
# ---------------------------------------------------------------------------

def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (s or "").lower())).strip()


def auto_match(label):
    """Similarity-match a free-form label against ALREADY-GOLDEN catalog entries.

    Returns (entry, suggestion_string) for the best golden match, or (None, None).
    String/alias match only — no external lookup, no fabricated rule.
    """
    nl = _norm(label)
    nl_tokens = set(nl.split())
    if not nl_tokens:
        return (None, None)
    best, best_score = None, 0
    for entry in CATALOG.values():
        for cand in entry.aliases + [entry.name]:
            nc = _norm(cand)
            ct = set(nc.split())
            if not ct:
                continue
            if nc == nl:
                score = 3
            elif ct <= nl_tokens or nl_tokens <= ct:   # one is a token-subset of the other
                score = 2
            else:
                score = 0
            if score > best_score:
                best, best_score = entry, score
    if best is None or best_score < 2:
        return (None, None)
    suggestion = "Did you mean {} ({})?".format(best.name, best.source_file)
    return (best, suggestion)


def resolve_freeform(cred, vendor_confirms=None):
    """Advance a free-form credential's candidate_state per the Option-2 flow.

    vendor_confirms: True (vendor said YES to the suggestion) → map + confirmed;
    False (vendor said NO) → attorney-pending; None (no answer yet) → suggested
    if a golden match exists, else attorney-pending. NEVER fabricates a rule and
    NEVER promotes to golden.

    Returns (updated_credential, suggestion_string_or_None).
    """
    if cred.source_path != "freeform":
        return (cred, None)
    # Already confirmed to a catalog id — nothing to do.
    if cred.requirement_id and cred.candidate_state == CONFIRMED:
        return (cred, None)

    entry, suggestion = auto_match(cred.label)
    if entry is None:
        cred.candidate_state = ATTORNEY_PENDING
        cred.requirement_id = None
        return (cred, None)

    if vendor_confirms is True:
        cred.requirement_id = entry.requirement_id
        cred.candidate_state = CONFIRMED
        return (cred, suggestion)
    if vendor_confirms is False:
        cred.candidate_state = ATTORNEY_PENDING
        cred.requirement_id = None
        return (cred, suggestion)
    # No answer yet — surface the suggestion, leave unmapped.
    cred.candidate_state = SUGGESTED
    return (cred, suggestion)


# ---------------------------------------------------------------------------
# Sunset lookup (default wired to the freshness checker)
# ---------------------------------------------------------------------------

def default_sunset_status(requirement_id):
    """Return the sunset classification ('OK'/'APPROACHING'/'LAPSED') for a
    requirement's golden rule via the freshness checker, or None if the rule
    carries no sunset watch / the source is unavailable."""
    entry = CATALOG.get(requirement_id)
    if not entry or not entry.sunset_source_file:
        return None
    path = os.path.join(SOURCES_DIR, entry.sunset_source_file)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    sunset = fc.read_sunset({"file": entry.sunset_source_file, "raw": raw})
    if not sunset:
        return None
    status, _days = fc.classify_sunset(sunset[0])
    return status


# ---------------------------------------------------------------------------
# Match logic (checklist × profile → verdict)
# ---------------------------------------------------------------------------

def _result(requirement_id, name, verdict, reason, citation, *, detail=None,
            candidate_state=None):
    legal_consequence = verdict in (MISSING, EXPIRING, UNKNOWN)
    return {
        "requirement_id": requirement_id,
        "requirement_name": name,
        "verdict": verdict,
        "icon": ICON[verdict],
        "reason": reason,
        "citation": citation,
        "attorney_review_required": legal_consequence,
        "candidate_state": candidate_state,
        "detail": detail or {},
    }


def _find_entry(requirement_id, profile):
    """A vendor entry satisfies a requirement when it is a checklist tick for it,
    or a free-form credential CONFIRMED to it. status=not-applicable does not
    satisfy."""
    for c in profile:
        if c.requirement_id != requirement_id:
            continue
        if c.status == "not-applicable":
            continue
        if c.source_path == "freeform" and c.candidate_state != CONFIRMED:
            continue
        return c
    return None


def evaluate_requirement(requirement_id, rfp_deadline, profile, sunset_status_fn=None):
    """Evaluate one RFP requirement against the vendor profile. Steps 1–5 of the
    build spec, unknown-safe, with the sunset override."""
    sunset_status_fn = sunset_status_fn or default_sunset_status
    deadline = _parse_date(rfp_deadline)
    entry_meta = CATALOG.get(requirement_id)

    # Step 1 — requirement in golden catalog?
    if entry_meta is None:
        return _result(requirement_id, requirement_id, UNKNOWN,
                       "Requirement is not in the golden catalog — new/unverified; queued for "
                       "primary-source verification.", None)

    citation = {"source_file": entry_meta.source_file, "quote": entry_meta.citation_quote}
    name = entry_meta.name

    # Step 2 — vendor has a matching entry?
    cred = _find_entry(requirement_id, profile)
    if cred is None:
        return _result(requirement_id, name, MISSING,
                       "No matching credential in the vendor profile.", citation,
                       detail={"validity_rule": entry_meta.validity_rule})

    sunset_status = sunset_status_fn(requirement_id)
    detail = {"validity_rule": entry_meta.validity_rule, "sunset_status": sunset_status}

    # Step 3 — determine expiry.
    vendor_expiry = _parse_date(cred.expiry_date)
    no_expiry = (cred.expiry_date == "no-expiry")
    computed_expiry = None
    m = _FIXED_PERIOD_RE.match(entry_meta.validity_rule)

    if vendor_expiry is not None:
        computed_expiry = vendor_expiry
        detail["expiry_source"] = "vendor-supplied expiry_date"
    elif no_expiry:
        computed_expiry = None
        detail["expiry_source"] = "vendor states no-expiry"
    elif m and cred.issuance_date and _parse_date(cred.issuance_date):
        computed_expiry = _add_years(_parse_date(cred.issuance_date), int(m.group(1)))
        detail["expiry_source"] = "computed: issuance_date + {}y".format(m.group(1))
        detail["computed_expiry"] = computed_expiry.isoformat()
    elif entry_meta.validity_rule in ("on-material-change", "none", "per-submission"):
        if cred.status == "expired":
            # Vendor marked it expired → not currently valid.
            return _result(requirement_id, name, EXPIRING,
                           "Vendor marked this credential expired — renew before the bid.",
                           citation, detail=detail)
        computed_expiry = None
        detail["expiry_source"] = "valid-unless-expired ({})".format(entry_meta.validity_rule)
    else:
        # validity_rule = unknown, OR fixed-period without an issuance_date → cannot confirm.
        reason = ("Cannot confirm validity: no golden validity rule for this requirement."
                  if entry_meta.validity_rule == "unknown"
                  else "Cannot confirm validity: fixed-period rule but no issuance_date supplied.")
        return _result(requirement_id, name, UNKNOWN, reason, citation, detail=detail)

    # Step 4 — SUNSET OVERRIDE (force UNKNOWN regardless of dates).
    if sunset_status == "LAPSED":
        return _result(requirement_id, name, UNKNOWN,
                       "Underlying authorization may have lapsed — verify. The rule's program "
                       "authorization is past its sunset date (quarantined).", citation,
                       detail=detail)

    # Step 5 — verdict from dates.
    if cred.status == "expired":
        return _result(requirement_id, name, EXPIRING,
                       "Vendor marked this credential expired — renew before the bid.",
                       citation, detail=detail)
    if computed_expiry is None:
        return _result(requirement_id, name, HAVE,
                       "Credential present and not date-limited against this deadline.",
                       citation, detail=detail)
    if deadline is None:
        return _result(requirement_id, name, UNKNOWN,
                       "No RFP deadline provided; cannot compare the expiry.", citation,
                       detail=detail)
    if computed_expiry >= deadline:
        delta = (computed_expiry - deadline).days
        return _result(requirement_id, name, HAVE,
                       "Valid through the RFP deadline (expires {}, {} days after the {} "
                       "deadline).".format(computed_expiry.isoformat(), delta, deadline.isoformat()),
                       citation, detail=detail)
    delta = (deadline - computed_expiry).days
    return _result(requirement_id, name, EXPIRING,
                   "Expires {} — {} days BEFORE the {} deadline; renew before bidding.".format(
                       computed_expiry.isoformat(), delta, deadline.isoformat()),
                   citation, detail=detail)


# ---------------------------------------------------------------------------
# Top-level gap analysis
# ---------------------------------------------------------------------------

def analyze(rfp_requirement_ids, rfp_deadline, profile, freeform_answers=None,
            sunset_status_fn=None):
    """Run the gap analysis.

    rfp_requirement_ids: the RFP checklist (requirement_ids from Capability 1).
    profile: list[VendorCredential].
    freeform_answers: optional {label: bool} — vendor YES/NO to a suggestion for
        a free-form credential (resolved before matching).
    Returns the structured result bundle (data only — no UI).
    """
    freeform_answers = freeform_answers or {}

    # Resolve free-form credentials first (identity only).
    freeform_report = []
    for cred in profile:
        if cred.source_path == "freeform" and cred.candidate_state != CONFIRMED:
            ans = freeform_answers.get(cred.label)
            _, suggestion = resolve_freeform(cred, vendor_confirms=ans)
            freeform_report.append({
                "label": cred.label,
                "candidate_state": cred.candidate_state,
                "mapped_requirement_id": cred.requirement_id,
                "suggestion": suggestion,
            })

    results = [evaluate_requirement(rid, rfp_deadline, profile, sunset_status_fn)
               for rid in rfp_requirement_ids]

    # Any attorney-pending free-form credential is surfaced as its own ⚠️ row so
    # it is never silently dropped.
    for cred in profile:
        if cred.source_path == "freeform" and cred.candidate_state == ATTORNEY_PENDING:
            results.append(_result(
                None, cred.label or "(free-form credential)", UNKNOWN,
                "Noted — not yet verified. Free-form credential did not match a golden catalog "
                "entry (or was declined); queued for attorney/primary-source review.",
                None, candidate_state=ATTORNEY_PENDING))

    summary = {"have": 0, "missing": 0, "expiring": 0, "unknown": 0}
    keymap = {HAVE: "have", MISSING: "missing", EXPIRING: "expiring", UNKNOWN: "unknown"}
    for r in results:
        summary[keymap[r["verdict"]]] += 1

    return {
        "upl_framing": UPL_FRAMING,
        "rfp_deadline": rfp_deadline,
        "results": results,
        "freeform_resolution": freeform_report,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Renderer (structured text; still data-first — no UI framework)
# ---------------------------------------------------------------------------

def render(bundle):
    lines = []
    lines.append("=" * 78)
    lines.append("GAP ANALYSIS — Vendor Profile × RFP Checklist")
    lines.append("RFP deadline: {}".format(bundle["rfp_deadline"]))
    lines.append("=" * 78)
    for r in bundle["results"]:
        lines.append("{} {}  [{}]".format(r["icon"], r["requirement_name"], r["verdict"]))
        lines.append("     reason  : {}".format(r["reason"]))
        if r["citation"]:
            lines.append('     citation: {} — "{}"'.format(
                r["citation"]["source_file"], r["citation"]["quote"]))
        else:
            lines.append("     citation: (none — not grounded in the golden copy)")
        if r["attorney_review_required"]:
            lines.append("     ⚑ attorney_review_required")
    s = bundle["summary"]
    lines.append("-" * 78)
    lines.append("Summary: ✅ have={have}  ❌ missing={missing}  ⏰ expiring={expiring}  "
                 "⚠️ unknown={unknown}".format(**s))
    lines.append(bundle["upl_framing"])
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo entry point (no UI — prints structured results + JSON)
# ---------------------------------------------------------------------------

def _demo():
    profile = [
        VendorCredential(vendor_id="v1", requirement_id="mwbe-certification",
                         status="have", issuance_date="2022-03-01", source_path="checklist"),
        VendorCredential(vendor_id="v1", requirement_id="vendor-responsibility",
                         status="have", source_path="checklist"),
        VendorCredential(vendor_id="v1", label="Acme Gizmo License", source_path="freeform"),
    ]
    bundle = analyze(
        ["mwbe-certification", "vendor-responsibility", "workers-comp-insurance"],
        "2026-09-01", profile)
    print(render(bundle))
    print("\n--- JSON ---")
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Capability 2 gap-analysis engine (logic only)")
    ap.add_argument("--profile", metavar="FILE.json",
                    help="vendor profile JSON: {rfp_requirement_ids, rfp_deadline, profile[]}")
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    args = ap.parse_args(argv)

    if not args.profile:
        return _demo()

    with open(args.profile, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    profile = [VendorCredential(**c) for c in doc.get("profile", [])]
    bundle = analyze(doc.get("rfp_requirement_ids", []), doc.get("rfp_deadline"),
                     profile, freeform_answers=doc.get("freeform_answers"))
    if not args.json:
        print(render(bundle))
    print(json.dumps(bundle, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
