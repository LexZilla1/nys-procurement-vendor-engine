#!/usr/bin/env python3
"""
engine/outcome_log.py — outcome & observation capture (data only, no analytics).

This module *records* what happened; it does not score, rank, or predict. There
are no numeric confidence or risk fields anywhere. Analytics (e.g. a
'defects-prevented' count) is a later PR and will read these records — it is
deliberately not built here.

Four record types:

  InvoiceOutcome   : the pre-flight verdict we gave vs. the actual result
                     (accepted, or rejected with the agency's rejection code).
  BidOutcome       : WON | LOST | NOT_SUBMITTED, plus a categorical reason and
                     free-text detail.
  AskedQuestion    : the questions a vendor asked an agency about a solicitation,
                     and the agency's answer if/when it came back.
  AgencyObservation: an empirically observed agency behavior. This is NOT an
                     official rule: it MUST carry the label
                     observed_pattern_not_official_rule and a citation whose
                     source_type is observed_pattern. The loader rejects any
                     observation that is missing either — so an observed pattern
                     can never masquerade as authority.
"""

from engine.citation import Citation, OBSERVED_PATTERN

# ---------------------------------------------------------------------------
# Categorical vocabularies
# ---------------------------------------------------------------------------

# invoice actual result
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
INVOICE_RESULTS = (ACCEPTED, REJECTED)

# bid result
WON = "WON"
LOST = "LOST"
NOT_SUBMITTED = "NOT_SUBMITTED"
BID_RESULTS = (WON, LOST, NOT_SUBMITTED)

# bid-loss / no-bid reason (categorical; free text carries the specifics)
REASON_PRICE = "PRICE"
REASON_TECHNICAL = "TECHNICAL"
REASON_MISSED_DEADLINE = "MISSED_DEADLINE"
REASON_INCOMPLETE = "INCOMPLETE"
REASON_NON_RESPONSIVE = "NON_RESPONSIVE"
REASON_NOT_ELIGIBLE = "NOT_ELIGIBLE"
REASON_CAPACITY = "CAPACITY"
REASON_WITHDREW = "WITHDREW"
REASON_OTHER = "OTHER"
BID_REASONS = (
    REASON_PRICE, REASON_TECHNICAL, REASON_MISSED_DEADLINE, REASON_INCOMPLETE,
    REASON_NON_RESPONSIVE, REASON_NOT_ELIGIBLE, REASON_CAPACITY, REASON_WITHDREW,
    REASON_OTHER,
)

# The mandatory label on every agency observation.
OBSERVED_PATTERN_LABEL = "observed_pattern_not_official_rule"


class OutcomeLogError(ValueError):
    """Raised when a record is malformed (e.g. an unlabelled observation)."""


class InvoiceOutcome:
    """Pre-flight verdict vs. actual invoice result. Data capture only."""

    def __init__(self, invoice_id, preflight_verdict, actual,
                 rejection_code=None, recorded_at=None):
        if actual not in INVOICE_RESULTS:
            raise OutcomeLogError("actual must be one of %s" % (INVOICE_RESULTS,))
        if actual == REJECTED and not rejection_code:
            raise OutcomeLogError("a REJECTED invoice requires the agency rejection_code")
        if actual == ACCEPTED and rejection_code:
            raise OutcomeLogError("an ACCEPTED invoice has no rejection_code")
        self.invoice_id = invoice_id
        self.preflight_verdict = preflight_verdict     # categorical string we issued
        self.actual = actual
        self.rejection_code = rejection_code           # the agency's own code (free text)
        self.recorded_at = recorded_at

    def to_dict(self):
        return {
            "type": "invoice_outcome",
            "invoice_id": self.invoice_id,
            "preflight_verdict": self.preflight_verdict,
            "actual": self.actual,
            "rejection_code": self.rejection_code,
            "recorded_at": self.recorded_at,
        }


class BidOutcome:
    """WON | LOST | NOT_SUBMITTED + categorical reason + free-text detail."""

    def __init__(self, tender_id, result, reason_code=REASON_OTHER,
                 reason_text="", recorded_at=None):
        if result not in BID_RESULTS:
            raise OutcomeLogError("result must be one of %s" % (BID_RESULTS,))
        if reason_code not in BID_REASONS:
            raise OutcomeLogError("reason_code must be one of %s" % (BID_REASONS,))
        self.tender_id = tender_id
        self.result = result
        self.reason_code = reason_code
        self.reason_text = reason_text or ""
        self.recorded_at = recorded_at

    def to_dict(self):
        return {
            "type": "bid_outcome",
            "tender_id": self.tender_id,
            "result": self.result,
            "reason_code": self.reason_code,
            "reason_text": self.reason_text,
            "recorded_at": self.recorded_at,
        }


class AskedQuestion:
    """A question a vendor asked an agency about a solicitation (and the answer,
    if it came)."""

    def __init__(self, question, solicitation, date, agency_answer=None,
                 vendor_id=None, agency=None):
        if not question:
            raise OutcomeLogError("question text is required")
        self.question = question
        self.solicitation = solicitation
        self.date = date
        self.agency_answer = agency_answer      # None until/unless answered
        self.vendor_id = vendor_id
        self.agency = agency

    def to_dict(self):
        return {
            "type": "asked_question",
            "question": self.question,
            "solicitation": self.solicitation,
            "date": self.date,
            "agency_answer": self.agency_answer,
            "vendor_id": self.vendor_id,
            "agency": self.agency,
        }


class AgencyObservation:
    """An observed agency behavior — explicitly NOT an official rule. Must carry
    the observed_pattern_not_official_rule label and an observed_pattern
    citation; construct via OutcomeLog.load_agency_observation for validation."""

    def __init__(self, agency, observation, citation, label=OBSERVED_PATTERN_LABEL,
                 recorded_at=None):
        if label != OBSERVED_PATTERN_LABEL:
            raise OutcomeLogError(
                "agency observation must carry label %r" % OBSERVED_PATTERN_LABEL)
        if not isinstance(citation, Citation):
            raise OutcomeLogError("agency observation requires a Citation")
        if citation.source_type != OBSERVED_PATTERN:
            raise OutcomeLogError(
                "agency observation citation.source_type must be %r, got %r"
                % (OBSERVED_PATTERN, citation.source_type))
        self.agency = agency
        self.observation = observation
        self.citation = citation
        self.label = label
        self.recorded_at = recorded_at

    def to_dict(self):
        return {
            "type": "agency_observation",
            "label": self.label,
            "agency": self.agency,
            "observation": self.observation,
            "citation": self.citation.to_dict(),
            "recorded_at": self.recorded_at,
        }


class OutcomeLog:
    """In-memory collector. Persistence layer is out of scope for PR 1."""

    def __init__(self):
        self.invoice_outcomes = []
        self.bid_outcomes = []
        self.asked_questions = []
        self.agency_observations = []

    def add_invoice_outcome(self, **kw):
        rec = InvoiceOutcome(**kw)
        self.invoice_outcomes.append(rec)
        return rec

    def add_bid_outcome(self, **kw):
        rec = BidOutcome(**kw)
        self.bid_outcomes.append(rec)
        return rec

    def add_asked_question(self, **kw):
        rec = AskedQuestion(**kw)
        self.asked_questions.append(rec)
        return rec

    def load_agency_observation(self, data):
        """Load an agency observation from a dict, enforcing the label and the
        observed_pattern citation. Rejects (raises) anything non-compliant so an
        observed pattern can never be stored as if it were an official rule."""
        if not isinstance(data, dict):
            raise OutcomeLogError("agency observation must be a dict")
        if data.get("label") != OBSERVED_PATTERN_LABEL:
            raise OutcomeLogError(
                "agency observation rejected: missing/incorrect label (need %r)"
                % OBSERVED_PATTERN_LABEL)
        cite_data = data.get("citation")
        if not isinstance(cite_data, dict):
            raise OutcomeLogError("agency observation rejected: missing citation")
        citation = Citation.from_dict(cite_data)
        rec = AgencyObservation(
            agency=data.get("agency"), observation=data.get("observation"),
            citation=citation, label=data.get("label"),
            recorded_at=data.get("recorded_at"))
        self.agency_observations.append(rec)
        return rec

    def to_dict(self):
        return {
            "invoice_outcomes": [r.to_dict() for r in self.invoice_outcomes],
            "bid_outcomes": [r.to_dict() for r in self.bid_outcomes],
            "asked_questions": [r.to_dict() for r in self.asked_questions],
            "agency_observations": [r.to_dict() for r in self.agency_observations],
        }
