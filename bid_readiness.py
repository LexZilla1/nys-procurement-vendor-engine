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
from engine import golden_status as gs
from tender_extractor import has_obligation_cue, is_incomplete_fragment

HERE = os.path.dirname(os.path.abspath(__file__))

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"
NA = "N/A"  # threshold-gated rule that genuinely does not apply at this contract size
_COLOR_SEVERITY = {GREEN: PASS, YELLOW: WARN, RED: FAIL}

# --- Coverage taxonomy (PR #45) --------------------------------------------
# A RELIABILITY / COVERAGE status for each RFQ-derived item — NOT a legal
# conclusion and NOT new legal logic. It answers only "did we verify this item
# against the golden copy?", so the report can never imply complete readiness
# while unverified / unmapped items remain.
#   VERIFIED_MATCH  — mapped to a known rule AND backed by golden-copy grounding.
#   NEEDS_REVIEW    — kind-mapped but not confidently/exactly verified by golden
#                     grounding (a.k.a. POSSIBLE_MATCH).
#   UNMAPPED        — an RFQ requirement / form / authority / mandatory passage
#                     not mapped to a verified golden-copy rule.
VERIFIED_MATCH = "VERIFIED_MATCH"
NEEDS_REVIEW = "NEEDS_REVIEW"
POSSIBLE_MATCH = NEEDS_REVIEW  # spec alias — NEEDS_REVIEW / POSSIBLE_MATCH
UNMAPPED = "UNMAPPED"

# The report headline distinguishes "we VERIFIED X" from "there are no other
# requirements". These exact markers are asserted by the standing coverage test:
# the COMPLETE marker must never render while coverage_complete is False. (Note
# "NOT COMPLETE" does not contain the substring "COVERAGE STATUS: COMPLETE".)
HEADLINE_COVERAGE_COMPLETE = "COVERAGE STATUS: COMPLETE"
HEADLINE_COVERAGE_INCOMPLETE = "COVERAGE STATUS: NOT COMPLETE"

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
    "public_work_registration": (
        "source-lab-220-i-public-work-registration.md",
        "No contractor shall bid on a contract for public work unless such "
        "contractor is registered pursuant to this section."),
    "international_boycott": (
        "source-stf-139-h-international-boycott.md",
        "Any such contract shall be rendered forfeit and void by the state "
        "comptroller"),
}

# Static per-kind rule metadata. profile_key is the vendor-profile field that
# answers "does the vendor satisfy this"; must=True means unmet → RED.
_RULE_META = {
    "eeo": {"label": "EEO policy statement", "profile_key": "eeo_policy_statement",
            "must": True, "threshold": 25000,
            "action": "Submit your EEO policy statement with the bid."},
    "mwbe": {"label": "MWBE utilization plan",
             "profile_key": "mwbe_utilization_plan_ready", "must": True,
             "threshold": 25000,
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
                     "must": True, "threshold": 100000,
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
    # Scope-gated (public work / Article 8), not dollar-gated. FAIL only when the
    # tender IS public work; N/A when it is not; YELLOW when we cannot tell.
    "public_work_registration": {
        "label": "Public-work contractor registration (Labor Law §220-i)",
        "profile_key": "public_work_contractor_registered", "must": True,
        "scope": "public_work",
        "action": "Register at the NYSDOL Contractor Registry and include your "
                  "Certificate of Registration with the bid — an application is "
                  "not a substitute."},
    # Threshold-gated at >$5,000. Material contract CONDITION, not a bid-rejection
    # (must=False → WARN, never RED); consequence is forfeiture on later conviction.
    "international_boycott": {
        "label": "International boycott prohibition (§139-h)",
        "profile_key": "international_boycott_certification_ready", "must": False,
        "threshold": 5000,
        "action": "Note the §139-h international-boycott clause — a material "
                  "condition of contracts over $5,000; you agree not to participate "
                  "in a prohibited international boycott."},
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
                # Vendor-facing readiness grounding. Gated at the VERIFY floor so a
                # gated source (e.g. the EEO rule's mwbe-5nycrr INTERIM_VERIFY
                # citation) is admitted only as a VERIFY/attorney-gated citation,
                # never confident, and any source not citable at VERIFY is dropped
                # (grounding=None) rather than shown — fail-soft, no false citation.
                golden.cite(src, quote, output_context=gs.OUTPUT_VERIFY)
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


# A labelled TOTAL contract value ("total/estimated contract value $X",
# "contract amount $X", "not to exceed $X", ...). The label must sit right next
# to the amount. Groups: (between-label-and-$)(amount)(text-after-amount).
_CV_LABEL_RE = re.compile(
    r"(?:total\s+contract\s+value|estimated\s+contract\s+value|"
    r"annual\s+contract\s+value|estimated\s+value|contract\s+amount|"
    r"annual\s+value|total\s+value|value\s+of\s+(?:this|the)\s+contract|"
    r"contract\s+value|not\s+to\s+exceed)"
    r"([^$\n]{0,40}?)\$\s?([\d][\d,]*(?:\.\d{2})?)([^\n]{0,22})", re.IGNORECASE)

# Rate / per-unit context — a $ next to any of these is a RATE, never a total.
_RATE_CTX_RE = re.compile(
    r"\b(per\s+hour|per\s+day|per\s+week|per\s+month|per\s+year|per\s+session|"
    r"per\s+visit|per\s+unit|per\s+item|per\s+mile|per\s+each|per\s+diem|"
    r"per\s+person|hourly|each\s+additional|/\s*hr|/\s*hour|/\s*day)\b",
    re.IGNORECASE)

# Comparison / quoted-threshold context — a $ introduced by any of these is a
# statutory threshold cited in boilerplate ("in excess of $300,000", "equal or
# exceed $100,000"), NOT this contract's value.
_CMP_CTX_RE = re.compile(
    r"\b(in\s+excess\s+of|exceeds?|greater\s+than|less\s+than|more\s+than|"
    r"at\s+least|not\s+less\s+than|up\s+to|minimum|maximum|above|over|under|"
    r"below|equal\s+or\s+exceed)\b", re.IGNORECASE)


def _extract_contract_value(extracted):
    """Find a labelled TOTAL contract value in the tender. Returns a POSITIVE int
    ONLY on a high-confidence match — a strong total-value label with clean
    context. A per-unit rate ($50 per hour) or a quoted statutory threshold ($X
    in excess of / equal or exceed) is rejected → None. None means 'unknown',
    which the caller must treat as YELLOW 'verify', NEVER as below-threshold.
    Failing safe toward 'verify' is the whole point (a wrong positive can void a
    mandatory rule)."""
    blob = "\n".join(extracted.get("pages", []))
    for m in _CV_LABEL_RE.finditer(blob):
        between, num, after = m.group(1), m.group(2), m.group(3)
        # The label 'not to exceed' legitimately contains 'exceed'; the reject
        # checks apply only to the text BETWEEN the label and the amount and the
        # text AFTER the amount, so the label itself never trips them.
        if _RATE_CTX_RE.search(after) or _RATE_CTX_RE.search(between):
            continue  # per-unit rate, not a total
        if _CMP_CTX_RE.search(between):
            continue  # a quoted statutory threshold, not this contract's value
        try:
            v = int(num.replace(",", "").split(".")[0])
        except ValueError:
            continue
        if v > 0:
            return v
    return None


def _contract_value(extracted, profile):
    """Resolve the tender's contract value for threshold gating. A profile-
    supplied `contract_value_usd` wins when it is a real positive number; a 0 /
    null / non-numeric value is NOT a valid 'below threshold' signal — it falls
    through to 'unknown' (None), same as a value we could not extract."""
    if "contract_value_usd" in profile:
        v = profile.get("contract_value_usd")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            return int(v)
        return None  # 0 / blank / null / invalid → unknown, never below-threshold
    return _extract_contract_value(extracted)


# Surface the specific number a requirement carries (goal %, insurance $ limit)
# from text NEAR the keyword — these sit on lines adjacent to the match.
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_GOAL_HINT_RE = re.compile(
    r"\b(goal|participation rate|participation goal|utilization|rate of)\b",
    re.IGNORECASE)
_INS_LIMIT_RE = re.compile(
    r"(?:not less than|no less than|minimum of|at least|in an amount of|"
    r"combined single limit of|limit of|amount not less than)\s*\$\s?"
    r"([\d][\d,]*)", re.IGNORECASE)


def _goal_pct_near(blob, term_re, window=200):
    """Find a participation-goal percentage near a term (MWBE/SDVOB). Returns a
    string like '30%' or None. Requires a goal-hint word next to the % so a
    random percentage isn't mistaken for a goal."""
    for m in term_re.finditer(blob):
        seg = blob[m.start():m.end() + window]
        for pm in _PCT_RE.finditer(seg):
            around = seg[max(0, pm.start() - 45):pm.end() + 10]
            if _GOAL_HINT_RE.search(around):
                return pm.group(1) + "%"
    return None


def _insurance_limit(blob):
    """Find a stated insurance dollar minimum ('not less than $X'). Returns int
    or None."""
    m = _INS_LIMIT_RE.search(blob)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


_MWBE_TERM_RE = re.compile(r"m/?wbe|minority[\s-]*and[\s-]*women", re.IGNORECASE)
_SDVOB_TERM_RE = re.compile(r"sdvob|service-?disabled veteran", re.IGNORECASE)


def _is_public_work(extracted, profile):
    """True / False / None.

    A profile `public_work_project` flag wins. Otherwise we return None
    (unknown) — we deliberately do NOT infer public-work status from the tender
    text. Real-tender testing showed the tell-tale phrases ('prevailing wage',
    'Article 8 of the Labor Law', 'public work contract') appear in the Appendix
    A standard clauses attached to virtually EVERY NYS tender, so they cannot
    distinguish a genuine public-work construction project from boilerplate.
    Guessing 'True' off boilerplate would wrongly RED-flag a services/goods
    bid; unknown → YELLOW 'verify' is the honest, safe default (§220-i scope)."""
    if "public_work_project" in profile:
        v = profile.get("public_work_project")
        if isinstance(v, bool):
            return v
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


# §139-d carries a limited, agency-discretion cure provision. Per the build
# spec this note attaches to the non-collusion finding ONLY; §139-l and §139-m
# are absolute and get no such note.
NONCOLLUSION_CURE_NOTE = (
    "Note: §139-d contains a limited cure provision — if the certification is "
    "missing, the agency head MAY still award if they determine the non-disclosure "
    "was not made to restrict competition. This is at the agency's sole discretion, "
    "not the bidder's right. Include the certification; do not rely on the cure "
    "provision.")


def _issue_and_fix(meta, status, vendor_has, grounded, shortfall):
    """Every non-green finding explains itself: a plain-English ISSUE (what's
    wrong) and a concrete FIX (how to resolve it). GREEN → (None, None)."""
    if status == GREEN:
        return None, None
    label = meta["label"]
    base_fix = meta.get("action")
    if shortfall is not None:
        have_amt, need_amt = shortfall
        issue = ("Your profile shows ${:,}; this tender requires ${:,}."
                 .format(have_amt, need_amt))
        fix = ("Obtain a certificate of insurance for at least ${:,} and attach it "
               "to your bid.".format(need_amt))
        return issue, fix
    if vendor_has is False:
        if meta["must"]:
            issue = ("This tender requires {} and it is not included in your "
                     "profile.".format(label))
        else:
            issue = ("{} is a participation goal for this tender and your profile "
                     "does not show it.".format(label))
        return issue, base_fix
    if vendor_has is None:
        issue = ("This tender requires {}, but your profile does not record it."
                 .format(label))
        return issue, base_fix or ("Confirm you meet this requirement and add it to "
                                   "your profile before bidding.")
    # vendor_has True but still YELLOW → satisfied yet not golden-copy-confirmed.
    if not grounded:
        issue = ("This tender requires {}, but we have no verified golden-copy rule "
                 "backing it.".format(label))
        fix = ("Verify this against the original tender and confirm with the issuing "
               "agency.")
        return issue, fix
    return ("{} needs review against the original tender.".format(label),
            base_fix or "Review this requirement against the original tender.")


class RequirementRow:
    def __init__(self, kind, label, tender_excerpt, page, vendor_has, status,
                 grounding, must, issue=None, fix=None, note=None, detail=None):
        self.kind = kind
        self.label = label
        self.tender_excerpt = tender_excerpt
        self.page = page
        self.vendor_has = vendor_has
        self.status = status
        self.grounding = grounding  # dict or None
        self.must = must
        self.issue = issue          # plain-English "what's wrong" (non-green only)
        self.fix = fix              # concrete action to resolve it (non-green only)
        self.note = note
        self.detail = detail        # extracted specific number (goal %, $ limit)

    @property
    def checkable(self):
        return self.vendor_has is not None

    @property
    def coverage(self):
        """Reliability/coverage status of this MAPPED requirement. VERIFIED_MATCH
        demands BOTH (a) a golden-copy-grounded rule kind AND (b) an obligation
        cue in THIS RFQ passage — so a cue-less keyword hit (e.g. a passing
        "workers' compensation" mention) inherits the rule's grounding but stays
        NEEDS_REVIEW, never a confident VERIFIED_MATCH. Not a legal conclusion."""
        if self.grounding and has_obligation_cue(self.tender_excerpt):
            return VERIFIED_MATCH
        return NEEDS_REVIEW

    def to_dict(self):
        d = {
            "kind": self.kind,
            "requirement": self.label,
            "tender_excerpt": self.tender_excerpt,
            "tender_provenance": "this tender, page {}".format(self.page),
            "vendor_satisfies": self.vendor_has,
            "status": self.status,
            "coverage": self.coverage,
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
        if self.detail:
            d["detail"] = self.detail
        if self.issue:
            d["issue"] = self.issue
        if self.fix:
            d["fix"] = self.fix
        if self.note:
            d["note"] = self.note
        return d


class BidReadinessReport:
    def __init__(self, vendor_name, source, pages_read, requirements_found,
                 rows, other_requirements=None, possible_authorities=None):
        self.vendor_name = vendor_name
        self.source = source
        self.pages_read = pages_read
        self.requirements_found = requirements_found
        self.rows = rows
        # Unmapped "shall/must" passages with no known rule — kept OUT of the
        # per-requirement findings (they flood the output) and surfaced as a
        # clustered summary instead. These are UNMAPPED coverage items.
        self.other_requirements = other_requirements or []
        # Authority/form references captured without mandatory language — held in
        # a visually distinct "possible authorities referenced — review" bucket
        # rather than mixed into the scored UNMAPPED passages (they are uncertain
        # by construction). Still counted as unverified coverage.
        self.possible_authorities = possible_authorities or []
        self.contract_value = None  # set by score_bid; None = not determined

    @staticmethod
    def _cluster(items, limit=8):
        """De-dupe a list of {text, page} passages → (unique_count, samples)."""
        seen, samples = set(), []
        for o in items:
            key = " ".join(o["text"].lower().split())
            if key in seen:
                continue
            seen.add(key)
            if len(samples) < limit:
                samples.append({"page": o["page"], "text": o["text"]})
        return len(seen), samples

    def cluster_other(self, limit=8):
        """De-dupe the unmapped passages and return (unique_count, samples)."""
        return self._cluster(self.other_requirements, limit)

    def cluster_possible_authorities(self, limit=8):
        """De-dupe the possible-authority references → (unique_count, samples)."""
        return self._cluster(self.possible_authorities, limit)

    @property
    def checkable_rows(self):
        # N/A rows (rule below its contract-value threshold) are excluded from
        # scoring entirely — they are not requirements for this contract.
        return [r for r in self.rows if r.checkable and r.status != NA]

    @property
    def na_rows(self):
        return [r for r in self.rows if r.status == NA]

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
            if r.status in c:
                c[r.status] += 1
        return c

    @property
    def nongreen(self):
        # NA rows are neither a problem to fix nor a green pass — exclude them.
        return [r for r in self.rows if r.status not in (GREEN, NA)]

    # --- Coverage taxonomy / fail-closed completeness gate (PR #45) ---------

    @property
    def coverage_buckets(self):
        """(verified_match_rows, needs_review_rows) over the MAPPED requirement
        rows. N/A rows (a rule that genuinely does not apply at this contract
        size) are excluded — they are not requirements for this contract."""
        verified, needs_review = [], []
        for r in self.rows:
            if r.status == NA:
                continue
            (verified if r.coverage == VERIFIED_MATCH else needs_review).append(r)
        return verified, needs_review

    @property
    def coverage_counts(self):
        """Item counts behind the coverage gate. UNMAPPED folds together the
        unmapped 'shall/must' passages and the possible-authority references —
        both are RFQ-specific items not verified against the golden copy."""
        verified, needs_review = self.coverage_buckets
        unmapped_unique, _ = self.cluster_other()
        possible_unique, _ = self.cluster_possible_authorities()
        return {
            VERIFIED_MATCH: len(verified),
            NEEDS_REVIEW: len(needs_review),
            UNMAPPED: unmapped_unique + possible_unique,
        }

    @property
    def coverage_complete(self):
        """LITERAL fail-closed gate, derived from item counts every time (never a
        separately-stored flag): coverage is complete ONLY when nothing is
        unmapped AND nothing needs review. Any UNMAPPED or NEEDS_REVIEW item
        forces False. This is a reliability/coverage judgment, not a legal PASS."""
        c = self.coverage_counts
        return c[UNMAPPED] == 0 and c[NEEDS_REVIEW] == 0

    @property
    def coverage_headline(self):
        """The one-line coverage verdict. It never reads as a final PASS/COMPLETE
        while coverage_complete is False; it distinguishes 'we verified X' from
        'there are no other requirements'."""
        c = self.coverage_counts
        if self.coverage_complete:
            return ("{} — all {} detected RFQ item(s) mapped to a verified "
                    "golden-copy rule. Coverage/reliability judgment, not a legal "
                    "conclusion.".format(HEADLINE_COVERAGE_COMPLETE,
                                         c[VERIFIED_MATCH]))
        return ("{} — verified {} item(s) against the golden copy, but {} need "
                "review and {} unmapped / possible-authority item(s) remain. This "
                "lists what we VERIFIED; it does NOT assert there are no other "
                "requirements. Review required before final bid-readiness."
                .format(HEADLINE_COVERAGE_INCOMPLETE, c[VERIFIED_MATCH],
                        c[NEEDS_REVIEW], c[UNMAPPED]))

    @property
    def actions(self):
        """The action list = collected FIX texts from all RED + YELLOW findings,
        RED first then YELLOW, deduped on the fix text."""
        seen, out = set(), []
        for status in (RED, YELLOW):
            for r in self.rows:
                if r.status == status and r.fix and r.fix not in seen:
                    seen.add(r.fix)
                    out.append({"for": r.label, "status": status, "fix": r.fix})
        return out

    @property
    def blocking(self):
        return [r for r in self.rows if r.status == RED]

    def _other_dict(self):
        unique, samples = self.cluster_other()
        return {
            "detected": len(self.other_requirements),
            "unique": unique,
            "note": "Additional 'shall/must' passages with no matched golden-copy "
                    "rule — review these against the tender; not scored.",
            "samples": samples,
        }

    def _possible_authorities_dict(self):
        unique, samples = self.cluster_possible_authorities()
        return {
            "detected": len(self.possible_authorities),
            "unique": unique,
            "note": "Possible authorities referenced — review. Authority/form "
                    "references found in the RFQ without mandatory language; "
                    "uncertain, not scored, and not verified in the golden copy.",
            "samples": samples,
        }

    def _coverage_dict(self):
        verified, needs_review = self.coverage_buckets
        return {
            "coverage_complete": self.coverage_complete,
            "headline": self.coverage_headline,
            "counts": self.coverage_counts,
            "verified_match": [
                {"requirement": r.label,
                 "source_file": r.grounding["source_file"]} for r in verified],
            "needs_review": [
                {"requirement": r.label, "status": r.status,
                 "reason": "kind-mapped but not verified in the golden copy"}
                for r in needs_review],
            "unmapped": self._other_dict(),
            "possible_authorities": self._possible_authorities_dict(),
            "note": "Reliability/coverage status, not legal advice. VERIFIED means "
                    "grounded in verbatim golden copy; NEEDS_REVIEW / UNMAPPED "
                    "items are NOT confirmed and do not mean 'no requirement'. "
                    "Found in RFQ but not verified in the golden copy → review "
                    "required before final bid-readiness.",
        }

    def to_dict(self):
        return {
            "feature": "bid_readiness",
            "vendor_name": self.vendor_name,
            "tender_source": self.source,
            "work_summary": {
                "pages_read": self.pages_read,
                "requirements_found": self.requirements_found,
                "mapped_findings": len(self.rows),
                "requirements_checked_against_profile": len(self.checkable_rows),
                "contract_value": self.contract_value,
                "requirements_not_applicable": len(self.na_rows),
                "other_requirements_detected": len(self.other_requirements),
                "possible_authorities_detected": len(self.possible_authorities),
            },
            # Top-level fail-closed gate — literal, derived from item counts.
            "coverage_complete": self.coverage_complete,
            "coverage": self._coverage_dict(),
            "bid_readiness_score": self.score,
            "status_counts": self.counts,
            "requirements": [r.to_dict() for r in self.rows],
            "issues": [
                {"requirement": r.label, "status": r.status,
                 "issue": r.issue, "fix": r.fix}
                for r in self.nongreen
            ],
            "action_list": self.actions,
            "blocking_count": len(self.blocking),
            "other_requirements": self._other_dict(),
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

    contract_value = _contract_value(extracted, profile)
    public_work = _is_public_work(extracted, profile)

    # Surface the specific numbers a tender carries, pulled from text near the
    # keyword (goal %, insurance $ limit) — computed once over the whole doc.
    blob = "\n".join(extracted.get("pages", []))
    mwbe_goal = _goal_pct_near(blob, _MWBE_TERM_RE)
    sdvob_goal = _goal_pct_near(blob, _SDVOB_TERM_RE)
    ins_limit = _insurance_limit(blob)

    def _detail_for(kind):
        if kind == "mwbe" and mwbe_goal:
            return "This tender's MWBE participation goal: {}".format(mwbe_goal)
        if kind == "sdvob" and sdvob_goal:
            return "This tender's SDVOB participation goal: {}".format(sdvob_goal)
        if kind == "insurance" and ins_limit:
            return "This tender's stated insurance minimum: ${:,}".format(ins_limit)
        return None

    rows = []
    other = []
    possible_authorities = []
    seen_kinds = set()
    seen_other = set()
    for req in requirements:
        # Authority/form reference captured without mandatory language (silent-
        # drop fix). Uncertain by construction → its own possible-authority
        # bucket, never a scored requirement row.
        if req.get("capture") == "authority_reference":
            possible_authorities.append({"text": req["text"], "page": req["page"]})
            continue
        kind = req["kind"]
        meta = rules.get(kind)
        if meta is None:
            # A "shall/must" passage with no known rule. Do NOT emit one row per
            # passage (a 68-page tender yields hundreds and buries the real
            # findings). Collect them for a single clustered summary instead —
            # after pruning PDF line-wrap leftovers (whole obligations are stitched
            # upstream and survive; incomplete fragments are dropped) and deduping
            # by normalized text. This does not change what counts as an obligation.
            if is_incomplete_fragment(req["text"]):
                continue
            norm = " ".join(req["text"].split()).lower()
            if norm in seen_other:
                continue
            seen_other.add(norm)
            other.append({"text": req["text"], "page": req["page"], "kind": kind})
            continue
        # Collapse multiple tender lines of the same kind to one verdict row,
        # but keep the first verbatim excerpt as the provenance anchor.
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)

        detail = _detail_for(kind)
        vendor_has = profile.get(meta["profile_key"])
        if vendor_has is not None:
            vendor_has = bool(vendor_has)
        grounded = meta["grounding"] is not None

        # Scope gating (public work / Article 8). Like threshold gating but on a
        # boolean applicability: applies only to public-work tenders. Not being
        # able to tell → YELLOW (never silently skip), NOT a confident N/A.
        if meta.get("scope") == "public_work":
            if public_work is None:
                rows.append(RequirementRow(
                    kind=kind, label=meta["label"], tender_excerpt=req["text"],
                    page=req["page"], vendor_has=vendor_has, status=YELLOW,
                    grounding=meta["grounding"], must=meta["must"],
                    issue="Not confirmed: couldn't determine if this is an Article 8 "
                          "public-work project; if so, a NYSDOL Certificate of "
                          "Registration is required.",
                    fix="Confirm whether this tender is public work (Article 8). If "
                        "it is, register at the NYSDOL Contractor Registry and submit "
                        "your Certificate of Registration with the bid."))
                continue
            if public_work is False:
                rows.append(RequirementRow(
                    kind=kind, label=meta["label"], tender_excerpt=req["text"],
                    page=req["page"], vendor_has=vendor_has, status=NA,
                    grounding=meta["grounding"], must=meta["must"],
                    note="N/A — not an Article 8 public-work project; contractor "
                         "registration does not apply to this tender."))
                continue
            # public_work is True → the rule applies; evaluate against the profile.
            status = _verdict(vendor_has, meta["must"], grounded, False)
            if status == GREEN:
                issue = fix = None
            else:
                issue = ("This is a public-work project; you must hold a NYSDOL "
                         "Certificate of Registration and submit it with your bid.")
                fix = meta["action"]
            rows.append(RequirementRow(
                kind=kind, label=meta["label"], tender_excerpt=req["text"],
                page=req["page"], vendor_has=vendor_has, status=status,
                grounding=meta["grounding"], must=meta["must"], issue=issue,
                fix=fix))
            continue

        # Part 4 — threshold gating. A rule that only applies above a contract-
        # value threshold has three branches. Crucially, a 0 / blank / unknown
        # value is NOT a "below threshold" signal (it almost always means the
        # value couldn't be extracted) — it must NOT silently skip the rule.
        threshold = meta.get("threshold")
        if threshold is not None:
            thr_s = "${:,}".format(threshold)
            note = NONCOLLUSION_CURE_NOTE if kind == "non_collusion" else None
            if contract_value is None:
                # Unknown → YELLOW, not confirmed. Never skip silently.
                rows.append(RequirementRow(
                    kind=kind, label=meta["label"], tender_excerpt=req["text"],
                    page=req["page"], vendor_has=vendor_has, status=YELLOW,
                    grounding=meta["grounding"], must=meta["must"],
                    issue=("This requirement depends on the contract value "
                           "(threshold {}), but the tender's dollar value couldn't "
                           "be determined (read as zero/blank).".format(thr_s)),
                    fix=("Confirm the tender's contract value. If it exceeds {}, "
                         "this certification is required — verify against the "
                         "original tender.".format(thr_s)),
                    note=note, detail=detail))
                continue
            if contract_value <= threshold:
                # Genuinely below threshold → N/A; excluded from score & counts.
                rows.append(RequirementRow(
                    kind=kind, label=meta["label"], tender_excerpt=req["text"],
                    page=req["page"], vendor_has=vendor_has, status=NA,
                    grounding=meta["grounding"], must=meta["must"],
                    note="N/A — contract value ${:,} is below the {} threshold; "
                         "this certification is not required at this contract "
                         "size.".format(contract_value, thr_s), detail=detail))
                continue
            # else contract_value > threshold → the rule applies; evaluate below.

        partial = False
        shortfall = None

        # Insurance: compare the tender's required limit to the profile. Prefer a
        # limit on the matched line; fall back to the doc-wide stated minimum
        # (Fix 3: the amount often sits on a different line than the keyword).
        if kind == "insurance" and vendor_has:
            need = _required_dollar(req["text"]) or ins_limit
            have = profile.get(meta.get("limit_key"))
            if need and isinstance(have, (int, float)) and have < need:
                partial = True
                shortfall = (int(have), need)

        status = _verdict(vendor_has, meta["must"], grounded, partial)
        issue, fix = _issue_and_fix(meta, status, vendor_has, grounded, shortfall)

        # Part 3 — §139-d cure-provision note, attached to non-collusion ONLY.
        note = NONCOLLUSION_CURE_NOTE if kind == "non_collusion" else None

        rows.append(RequirementRow(
            kind=kind, label=meta["label"], tender_excerpt=req["text"],
            page=req["page"], vendor_has=vendor_has, status=status,
            grounding=meta["grounding"], must=meta["must"], issue=issue,
            fix=fix, note=note, detail=detail))

    report = BidReadinessReport(
        vendor_name=profile.get("vendor_name", "(unnamed vendor)"),
        source=extracted.get("source", "(unknown)"),
        pages_read=extracted.get("page_count", 0),
        requirements_found=len(requirements),
        rows=rows, other_requirements=other,
        possible_authorities=possible_authorities)
    report.contract_value = contract_value
    return report


# ---------------------------------------------------------------------------
# Human render — show the work
# ---------------------------------------------------------------------------

_MARK = {GREEN: "GREEN ", YELLOW: "YELLOW", RED: "RED   ", NA: " N/A  "}


def render_bid_readiness(report, advisory=None):
    L = []
    L.append("=" * 78)
    L.append("BID-READINESS — {}".format(report.vendor_name))
    L.append("Tender: {}".format(report.source))
    L.append("=" * 78)
    cv = ("${:,}".format(report.contract_value) if report.contract_value
          else "NOT DETERMINED (threshold-gated rules verified, not skipped)")
    L.append("Contract value: {}".format(cv))
    L.append("Read {} page(s), found {} requirement passage(s) → {} matched to a "
             "known rule, {} other; checked {} against your profile.".format(
                 report.pages_read, report.requirements_found, len(report.rows),
                 len(report.other_requirements), len(report.checkable_rows)))
    c = report.counts
    na = len(report.na_rows)
    score_caveat = ("" if report.coverage_complete
                    else "  (coverage NOT complete — not a final pass; see below)")
    L.append("Verdicts: GREEN={}  YELLOW={}  RED={}  N/A={}   →   BID-READINESS "
             "SCORE: {}/100{}".format(c[GREEN], c[YELLOW], c[RED], na,
                                      report.score, score_caveat))
    L.append("Score = weighted mean over the {} checkable requirements "
             "(mandatory ×2, advisory ×1; GREEN=1.0, YELLOW=0.5, RED=0.0)."
             .format(len(report.checkable_rows)))
    # Fail-closed coverage headline — never reads as PASS/COMPLETE while
    # coverage_complete is False. Distinguishes "we verified X" from "there are
    # no other requirements."
    L.append(report.coverage_headline)
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
        if r.detail:
            L.append("   detail : {}".format(r.detail))
        if r.vendor_has is None:
            L.append("   you    : (not in profile)")
        else:
            L.append("   you    : {}".format("YES" if r.vendor_has else "NO"))
        if r.issue:
            L.append("   ISSUE  : {}".format(r.issue))
        if r.fix:
            L.append("   FIX    : {}".format(r.fix))
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
    L.append("ACTION LIST (RED first, then YELLOW)")
    for a in report.actions:
        L.append("  [{}] {} — {}".format(a["status"], a["for"], a["fix"]))
    if not report.actions:
        L.append("  (nothing outstanding)")
    # -------- COVERAGE (reliability/completeness), separated by taxonomy --------
    verified, needs_review = report.coverage_buckets
    cc = report.coverage_counts
    L.append("")
    L.append("COVERAGE (reliability judgment, not legal advice)")
    L.append("-" * 78)
    L.append("VERIFIED against golden copy ({}):".format(cc[VERIFIED_MATCH]))
    for r in verified:
        L.append("  ✓ {} — {}".format(r.label, r.grounding["source_file"]))
    if not verified:
        L.append("  (none)")
    L.append("NEEDS REVIEW — kind-mapped but NOT verified in the golden copy ({}):"
             .format(cc[NEEDS_REVIEW]))
    for r in needs_review:
        L.append("  ? {} — no verified golden-copy rule backs this; review "
                 "required.".format(r.label))
    if not needs_review:
        L.append("  (none)")
    if report.other_requirements:
        unique, samples = report.cluster_other()
        L.append("UNMAPPED RFQ passages — found in RFQ but not verified in the "
                 "golden copy ({} passage(s), {} unique):".format(
                     len(report.other_requirements), unique))
        L.append("  Not scored. Review required before final bid-readiness. "
                 "Examples:")
        for s in samples:
            txt = s["text"] if len(s["text"]) <= 90 else s["text"][:87] + "..."
            L.append("  • [p{}] {}".format(s["page"], txt))
        if unique > len(samples):
            L.append("  ...and {} more.".format(unique - len(samples)))
    if report.possible_authorities:
        unique, samples = report.cluster_possible_authorities()
        L.append("POSSIBLE AUTHORITIES REFERENCED — REVIEW ({} reference(s), {} "
                 "unique):".format(len(report.possible_authorities), unique))
        L.append("  Authority/form references without mandatory language — "
                 "uncertain, not scored. Found in RFQ but not verified in the "
                 "golden copy. Examples:")
        for s in samples:
            txt = s["text"] if len(s["text"]) <= 90 else s["text"][:87] + "..."
            L.append("  • [p{}] {}".format(s["page"], txt))
        if unique > len(samples):
            L.append("  ...and {} more.".format(unique - len(samples)))
    # -------- ADVISORY (sibling, read-only) — appended AFTER coverage. Only
    # rendered when an advisory dict is present; a null advisory (default)
    # renders nothing, so output is byte-identical to the pre-advisory report.
    if advisory:
        import coverage_advisory
        L.extend(coverage_advisory.render_advisory(advisory))
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
    # Post-score, sibling-only advisory layer (PR 2). Read-only: it never changes
    # the report, its counts, score, grounding, or the coverage gate. Returns
    # None (no advisory section) whenever no key / SDK / valid output is present.
    import coverage_advisory
    advisory = coverage_advisory.advise(report)
    if "--json" in argv:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_bid_readiness(report, advisory=advisory))
    return 0


if __name__ == "__main__":
    sys.exit(main())
