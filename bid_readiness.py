#!/usr/bin/env python3
"""
BUILD SPEC v2 — Part A (centerpiece, all vendors): tender bid-readiness scorer.

A vendor uploads a real NYS tender; tender_extractor.py pulls its requirement
passages; this module compares each one to a quick vendor profile and produces
a TRANSPARENT bid-readiness score with a per-requirement GREEN / YELLOW / RED
verdict, a gap list, and an action list.

Two lines this module holds (per BUILD SPEC v2 and the approved plan):

  1. PROVENANCE SPLIT. A requirement excerpt is the VENDOR'S uploaded tender —
     quoted verbatim and tagged "this tender, page N". It is NEVER routed
     through GoldenCopy.cite(). Only a rule that maps to verbatim State law in
     the golden copy carries a real citation (via cite()); everything else is
     explicitly flagged "not confirmed — no golden-copy grounding". The
     grounding table below is SELF-VALIDATING: each quote is checked through
     cite() at import, and any quote that is not verbatim is auto-downgraded to
     "not confirmed" rather than shown as a citation.

  2. SHOW THE WORK. The renderer states what it did — pages read, requirements
     found, how many were checkable against the profile — then the score, then
     every gap and action. Not a bare number.

Colour ↔ engine severity: GREEN→PASS, YELLOW→WARN, RED→FAIL (reusing the
validator's vocabulary; no parallel system).
"""

import json
import os
import re
import sys

from validator import GoldenCopy, FAIL, WARN, PASS, INFO

HERE = os.path.dirname(os.path.abspath(__file__))

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"
_COLOR_SEVERITY = {GREEN: PASS, YELLOW: WARN, RED: FAIL}

# Candidate golden-copy grounding for each requirement kind. Verified verbatim
# at import (see _build_rules); a quote that fails cite() is dropped to None so
# the requirement is honestly labelled "not confirmed" instead of mis-cited.
_GROUNDING_CANDIDATES = {
    "eeo": ("source-mwbe-5nycrr-pass-fail.md",
            "A contractor's failure to submit an EEO policy statement and, where "
            "required by the contracting agency, staffing plan or total work force "
            "data shall result in the rejection of the contractor's bid or proposal"),
    "mwbe": ("source-xi-18-a-mwbe.md",
             "Require contractors to submit a Minority and Women-Owned Business "
             "Enterprise (MWBE) utilization plan for each of their contracts that "
             "meets the applicable thresholds"),
    "sdvob": ("source-sdvob.md",
              "By law, State agencies must make good faith efforts to use SDVOBs "
              "in procurement."),
    "vendor_responsibility": (
        "source-xi-16-vendor-responsibility.md",
        "Such review shall be designed to provide reasonable assurances that the "
        "proposed contractor is responsible."),
    # Appendix A standard clauses — grounded verbatim from the Appendix A source
    # already in the repo (no duplicate source file; cite() resolves the clause
    # text directly out of the Standard-Clauses body).
    # Non-collusion grounds to the STATUTE (§139-d) — it carries the actual
    # bid-rejection consequence, a stronger grounding than the Appendix A
    # contract-form certification.
    "non_collusion": (
        "source-stf-139-d-noncollusion.md",
        "A bid shall not be considered for award nor shall any award be made "
        "where (a) (1) (2) and (3) above have not been complied with"),
    "insurance_workers": (
        "source-wkc-57-workers-comp.md",
        "shall not enter into any such contract unless proof duly subscribed by "
        "an insurance carrier is produced in a form satisfactory to the chair, "
        "that compensation for all employees has been secured as provided by this "
        "chapter."),
    "sexual_harassment": (
        "source-stf-139-l-sexual-harassment.md",
        "A bid shall not be considered for award nor shall any award be made to a "
        "bidder who has not complied with subdivision one of this section"),
    "gender_based_violence": (
        "source-stf-139-m-gender-based-violence.md",
        "A bid shall not be considered for award, nor shall any award be made to a "
        "bidder who has not complied with subdivision one of this section"),
    "iran_divestment": (
        "source-appendix-a-june2023.md",
        "Contractor certifies in accordance with\nState Finance Law § 165-a "
        "that it is not on the"),
    "sales_tax_5a": (
        "source-appendix-a-june2023.md",
        "if the contractor fails to make the certification required by Tax Law\n"
        "§ 5-a"),
    "tropical_hardwoods": (
        "source-appendix-a-june2023.md",
        "Section 165 of the State Finance Law, (Use of\nTropical Hardwoods) which "
        "prohibits purchase and use of tropical hardwoods"),
}

# Static per-kind rule metadata. profile_key is the vendor-profile field that
# answers "does the vendor satisfy this"; must=True means unmet → RED.
_RULE_META = {
    "eeo": {"label": "EEO policy statement", "profile_key": "eeo_policy_statement",
            "must": True,
            "action": "Submit your EEO policy statement with the bid."},
    "mwbe": {"label": "MWBE utilization plan",
             "profile_key": "mwbe_utilization_plan_ready", "must": True,
             "action": "Prepare and submit an MWBE utilization plan meeting the stated goal."},
    "sdvob": {"label": "SDVOB participation", "profile_key": "sdvob_certified",
              "must": False,
              "action": "SDVOB is a participation goal, not a bar — consider SDVOB "
                        "subcontracting to help meet it."},
    "vendor_responsibility": {"label": "Vendor Responsibility Questionnaire",
                              "profile_key": "vendor_responsibility_questionnaire_current",
                              "must": True,
                              "action": "Complete or refresh your VendRep questionnaire."},
    "insurance": {"label": "General liability insurance",
                  "profile_key": "general_liability_insurance", "must": True,
                  "limit_key": "general_liability_limit_usd",
                  "action": "Obtain general liability insurance meeting the stated limit."},
    "insurance_workers": {"label": "Workers' compensation coverage",
                          "profile_key": "workers_compensation_coverage", "must": True,
                          "action": "Obtain or maintain workers' compensation coverage."},
    "bonding": {"label": "Bid bond", "profile_key": "bid_bond_available", "must": True,
                "action": "Secure a bid bond for the required percentage of the bid."},
    "registration": {"label": "NYS Vendor File registration",
                     "profile_key": "nys_vendor_file_registered", "must": True,
                     "action": "Register in the NYS Vendor File before award."},
    "non_collusion": {"label": "Non-collusive bidding certification (§139-d)",
                      "profile_key": "non_collusion_certification_ready",
                      "must": True,
                      "action": "Execute the non-collusive bidding certification "
                                "(§139-d) with your bid."},
    "iran_divestment": {"label": "Iran Divestment Act certification (§165-a)",
                        "profile_key": "iran_divestment_certification_ready",
                        "must": True,
                        "action": "Certify you are not on the §165-a Prohibited "
                                  "Entities List."},
    "sales_tax_5a": {"label": "Sales-tax registration certification (Tax Law §5-a)",
                     "profile_key": "sales_tax_certificate_of_authority",
                     "must": True,
                     "action": "File the Tax Law §5-a sales-tax certification "
                               "(applies to contracts over $100,000)."},
    "tropical_hardwoods": {"label": "Tropical hardwoods certification (§165)",
                           "profile_key": "tropical_hardwoods_certification_ready",
                           "must": True,
                           "action": "Certify tropical-hardwoods compliance (§165) "
                                     "if wood products are supplied."},
    "sexual_harassment": {"label": "Sexual-harassment policy certification (§139-l)",
                          "profile_key": "sexual_harassment_policy", "must": True,
                          "action": "Certify a written sexual-harassment-prevention "
                                    "policy meeting Labor Law §201-g."},
    "gender_based_violence": {
        "label": "Gender-based-violence policy certification (§139-m)",
        "profile_key": "gender_based_violence_policy", "must": True,
        "action": "Certify a written gender-based-violence-and-the-workplace "
                  "policy meeting Executive Law §575(11)."},
}

_WEIGHT_MUST = 2
_WEIGHT_SHOULD = 1
_STATUS_VALUE = {GREEN: 1.0, YELLOW: 0.5, RED: 0.0}
_DOLLAR_RE = re.compile(r"\$\s?([\d][\d,]*)")


def _build_rules(golden):
    """Attach verified grounding to each kind; downgrade unverifiable quotes."""
    rules = {}
    for kind, meta in _RULE_META.items():
        grounding = None
        cand = _GROUNDING_CANDIDATES.get(kind)
        if cand:
            src, quote = cand
            try:
                golden.cite(src, quote)  # raises if not verbatim
                grounding = {"source_file": src, "citation_quote": quote}
            except Exception:
                grounding = None
        rule = dict(meta)
        rule["grounding"] = grounding
        rules[kind] = rule
    return rules


def _required_dollar(text):
    m = _DOLLAR_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _verdict(vendor_has, must, grounded, partial):
    """GREEN/YELLOW/RED. GREEN demands BOTH satisfied AND golden-copy grounded —
    a met-but-unconfirmed rule is YELLOW, never a confident green."""
    if vendor_has is False:
        return RED if must else YELLOW
    if vendor_has is None:
        return YELLOW  # not mapped to the profile → cannot confirm
    if partial:
        return YELLOW
    return GREEN if grounded else YELLOW


class RequirementRow:
    def __init__(self, kind, label, tender_excerpt, page, vendor_has, status,
                 grounding, must, gap=None, action=None, note=None):
        self.kind = kind
        self.label = label
        self.tender_excerpt = tender_excerpt
        self.page = page
        self.vendor_has = vendor_has
        self.status = status
        self.grounding = grounding  # dict or None
        self.must = must
        self.gap = gap
        self.action = action
        self.note = note

    @property
    def checkable(self):
        return self.vendor_has is not None

    def to_dict(self):
        d = {
            "kind": self.kind,
            "requirement": self.label,
            "tender_excerpt": self.tender_excerpt,
            "tender_provenance": "this tender, page {}".format(self.page),
            "vendor_satisfies": self.vendor_has,
            "status": self.status,
            "mandatory": self.must,
        }
        if self.grounding:
            d["grounding"] = {
                "source_file": self.grounding["source_file"],
                "citation_quote": self.grounding["citation_quote"],
                "confirmed": True,
            }
        else:
            d["grounding"] = {
                "confirmed": False,
                "reason": "no golden-copy rule backs this tender requirement",
            }
        if self.gap:
            d["gap"] = self.gap
        if self.action:
            d["action"] = self.action
        if self.note:
            d["note"] = self.note
        return d


class BidReadinessReport:
    def __init__(self, vendor_name, source, pages_read, requirements_found,
                 rows):
        self.vendor_name = vendor_name
        self.source = source
        self.pages_read = pages_read
        self.requirements_found = requirements_found
        self.rows = rows

    @property
    def checkable_rows(self):
        return [r for r in self.rows if r.checkable]

    @property
    def score(self):
        rows = self.checkable_rows
        if not rows:
            return 0.0
        num = den = 0.0
        for r in rows:
            w = _WEIGHT_MUST if r.must else _WEIGHT_SHOULD
            num += w * _STATUS_VALUE[r.status]
            den += w
        return round(100.0 * num / den, 1)

    @property
    def counts(self):
        c = {GREEN: 0, YELLOW: 0, RED: 0}
        for r in self.rows:
            c[r.status] += 1
        return c

    @property
    def gaps(self):
        return [r for r in self.rows if r.status in (RED, YELLOW) and r.gap]

    @property
    def actions(self):
        seen, out = set(), []
        for r in self.rows:
            if r.status in (RED, YELLOW) and r.action and r.action not in seen:
                seen.add(r.action)
                out.append({"for": r.label, "status": r.status, "action": r.action})
        return out

    @property
    def blocking(self):
        return [r for r in self.rows if r.status == RED]

    def to_dict(self):
        return {
            "feature": "bid_readiness",
            "vendor_name": self.vendor_name,
            "tender_source": self.source,
            "work_summary": {
                "pages_read": self.pages_read,
                "requirements_found": self.requirements_found,
                "requirements_checked_against_profile": len(self.checkable_rows),
            },
            "bid_readiness_score": self.score,
            "status_counts": self.counts,
            "requirements": [r.to_dict() for r in self.rows],
            "gaps": [
                {"requirement": r.label, "status": r.status, "gap": r.gap}
                for r in self.gaps
            ],
            "action_list": self.actions,
            "blocking_count": len(self.blocking),
            "disclaimer": (
                "Information and document-readiness only. Requirement excerpts are "
                "quoted from the uploaded tender (not legal advice); only rules "
                "marked confirmed are grounded in verbatim NYS golden-copy text. "
                "This tool performs no submission on your behalf."
            ),
        }


def score_bid(extracted, profile, golden=None):
    """Build a BidReadinessReport from an extract() result and a vendor profile."""
    golden = golden or GoldenCopy()
    rules = _build_rules(golden)
    from tender_extractor import find_requirements
    requirements = find_requirements(extracted)

    rows = []
    seen_kinds = set()
    for req in requirements:
        kind = req["kind"]
        meta = rules.get(kind)
        if meta is None:
            # A real requirement passage with no profile mapping — show it as
            # context (YELLOW, unmapped), but do not invent a check.
            rows.append(RequirementRow(
                kind=kind, label="General / unmapped requirement",
                tender_excerpt=req["text"], page=req["page"],
                vendor_has=None, status=YELLOW, grounding=None, must=False,
                note="not mapped to a profile field — review manually"))
            continue
        # Collapse multiple tender lines of the same kind to one verdict row,
        # but keep the first verbatim excerpt as the provenance anchor.
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)

        vendor_has = profile.get(meta["profile_key"])
        if vendor_has is not None:
            vendor_has = bool(vendor_has)
        grounded = meta["grounding"] is not None
        partial = False
        gap = None

        # Insurance: compare the tender's stated dollar limit to the profile.
        if kind == "insurance" and vendor_has:
            need = _required_dollar(req["text"])
            have = profile.get(meta.get("limit_key"))
            if need and isinstance(have, (int, float)) and have < need:
                partial = True
                gap = ("carries ${:,} general-liability limit; this tender asks "
                       "for ${:,}".format(int(have), need))

        status = _verdict(vendor_has, meta["must"], grounded, partial)

        if status == RED:
            gap = gap or "{} not satisfied by the vendor profile".format(meta["label"])
        elif status == YELLOW and gap is None:
            if vendor_has is False:
                gap = "{} not satisfied (advisory / goal)".format(meta["label"])
            elif not grounded:
                gap = ("{} satisfied, but no golden-copy rule confirms this tender "
                       "requirement (not confirmed)".format(meta["label"]))

        action = meta["action"] if status in (RED, YELLOW) else None
        rows.append(RequirementRow(
            kind=kind, label=meta["label"], tender_excerpt=req["text"],
            page=req["page"], vendor_has=vendor_has, status=status,
            grounding=meta["grounding"], must=meta["must"], gap=gap,
            action=action))

    return BidReadinessReport(
        vendor_name=profile.get("vendor_name", "(unnamed vendor)"),
        source=extracted.get("source", "(unknown)"),
        pages_read=extracted.get("page_count", 0),
        requirements_found=len(requirements),
        rows=rows)


# ---------------------------------------------------------------------------
# Human render — show the work
# ---------------------------------------------------------------------------

_MARK = {GREEN: "GREEN ", YELLOW: "YELLOW", RED: "RED   "}


def render_bid_readiness(report):
    L = []
    L.append("=" * 78)
    L.append("BID-READINESS — {}".format(report.vendor_name))
    L.append("Tender: {}".format(report.source))
    L.append("=" * 78)
    L.append("Read {} page(s), found {} requirement passage(s), checked {} against "
             "your profile.".format(report.pages_read, report.requirements_found,
                                    len(report.checkable_rows)))
    c = report.counts
    L.append("Verdicts: GREEN={}  YELLOW={}  RED={}   →   BID-READINESS SCORE: "
             "{}/100".format(c[GREEN], c[YELLOW], c[RED], report.score))
    L.append("Score = weighted mean over the {} checkable requirements "
             "(mandatory ×2, advisory ×1; GREEN=1.0, YELLOW=0.5, RED=0.0)."
             .format(len(report.checkable_rows)))
    L.append("")
    L.append("PER-REQUIREMENT")
    L.append("-" * 78)
    for r in report.rows:
        flag = "MUST" if r.must else "goal"
        L.append("[{}] {} ({})".format(_MARK[r.status], r.label, flag))
        L.append('   tender : "{}"'.format(r.tender_excerpt))
        L.append("   from   : this tender, page {}".format(r.page))
        if r.grounding:
            L.append("   rule   : {} (confirmed)".format(r.grounding["source_file"]))
            L.append('   cite   : "{}"'.format(r.grounding["citation_quote"]))
        else:
            L.append("   rule   : NOT CONFIRMED — no golden-copy rule backs this "
                     "tender requirement")
        if r.vendor_has is None:
            L.append("   you    : (not in profile)")
        else:
            L.append("   you    : {}".format("YES" if r.vendor_has else "NO"))
        if r.gap:
            L.append("   gap    : {}".format(r.gap))
        if r.note:
            L.append("   note   : {}".format(r.note))
        L.append("")
    L.append("-" * 78)
    if report.blocking:
        L.append("BLOCKING (RED) — fix before bidding:")
        for r in report.blocking:
            L.append("  • {}".format(r.label))
    else:
        L.append("No RED blockers.")
    L.append("")
    L.append("ACTION LIST")
    for a in report.actions:
        L.append("  [{}] {} — {}".format(a["status"], a["for"], a["action"]))
    if not report.actions:
        L.append("  (nothing outstanding)")
    L.append("")
    L.append(report.to_dict()["disclaimer"])
    L.append("=" * 78)
    return "\n".join(L)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("usage: bid_readiness.py TENDER.(pdf|txt) PROFILE.json [--json]",
              file=sys.stderr)
        return 2
    from tender_extractor import extract
    tender_path, profile_path = argv[0], argv[1]
    extracted = extract(tender_path)
    if not extracted["has_text_layer"]:
        print("no extractable text layer — not confirmed (scanned/image PDF?). "
              "Re-upload a text PDF or paste the text as .txt.", file=sys.stderr)
        return 1
    report = score_bid(extracted, _load_json(profile_path))
    if "--json" in argv:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_bid_readiness(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
