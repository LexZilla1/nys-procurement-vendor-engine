#!/usr/bin/env python3
"""
engine/citation.py — the Citation primitive. NYS Procurement Vendor Engine.

Every law-derived fact in the daily-habit backend carries a Citation, never a
bare string. A Citation names WHERE a claim comes from and quotes the exact
text, so nothing in the engine can silently rely on a paraphrased rule.

`source_type` is a closed vocabulary:
  - golden_rule       : a verbatim quote from a golden-copy source-*.md body.
  - solicitation      : text lifted from a specific solicitation/RFP document.
  - user_entered      : a date/fact the vendor typed in (no external authority).
  - official_page     : a live official .ny.gov page (not yet golden-captured).
  - observed_pattern  : an empirically observed agency behavior — NOT a rule.
                        Anything labelled this way is explicitly not authority.

A golden_rule Citation can be *verified* against the golden copy: verify_golden()
confirms `quote` appears character-for-character in the named source's STATE
TEXT body, reusing the same choke-point the validator uses. This module does
not paraphrase, reconstruct, or persist any tier-3 (TIN/SSN/DOB) data.
"""

GOLDEN_RULE = "golden_rule"
SOLICITATION = "solicitation"
USER_ENTERED = "user_entered"
OFFICIAL_PAGE = "official_page"
OBSERVED_PATTERN = "observed_pattern"

SOURCE_TYPES = (
    GOLDEN_RULE,
    SOLICITATION,
    USER_ENTERED,
    OFFICIAL_PAGE,
    OBSERVED_PATTERN,
)


class CitationError(ValueError):
    """Raised when a Citation is malformed or a golden quote cannot be verified."""


class Citation:
    """A grounded reference: {source_id, source_type, locator, quote, captured_at}.

    - source_id   : stable identifier of the source (e.g. a source-*.md filename,
                    a solicitation id, or an official URL).
    - source_type : one of SOURCE_TYPES.
    - locator     : where inside the source (section/heading/line/table cell).
    - quote       : the exact text being relied upon (verbatim for golden_rule).
    - captured_at : ISO date/timestamp the quote was captured (audit trail).
    """

    __slots__ = ("source_id", "source_type", "locator", "quote", "captured_at")

    def __init__(self, source_id, source_type, locator, quote, captured_at):
        if not source_id:
            raise CitationError("source_id is required")
        if source_type not in SOURCE_TYPES:
            raise CitationError(
                "source_type must be one of %s, got %r" % (SOURCE_TYPES, source_type))
        if not quote:
            raise CitationError("quote is required (no bare/empty citations)")
        if not captured_at:
            raise CitationError("captured_at is required (audit trail)")
        self.source_id = source_id
        self.source_type = source_type
        self.locator = locator or ""
        self.quote = quote
        self.captured_at = captured_at

    def is_golden(self):
        return self.source_type == GOLDEN_RULE

    def verify_golden(self, golden):
        """For a golden_rule citation, confirm `quote` is verbatim in the named
        source's STATE TEXT body. `golden` is a validator.GoldenCopy-like object
        exposing cite(source_id, quote). Raises CitationError on any mismatch.
        No-op (returns True) for non-golden citations."""
        if not self.is_golden():
            return True
        try:
            golden.cite(self.source_id, self.quote)
        except Exception as exc:  # CitationError from GoldenCopy, or unknown source
            raise CitationError(
                "golden citation not verbatim in %s: %s" % (self.source_id, exc))
        return True

    def to_dict(self):
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "locator": self.locator,
            "quote": self.quote,
            "captured_at": self.captured_at,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            source_id=d.get("source_id"),
            source_type=d.get("source_type"),
            locator=d.get("locator"),
            quote=d.get("quote"),
            captured_at=d.get("captured_at"),
        )

    def __repr__(self):
        return "Citation(%s:%s %r)" % (self.source_type, self.source_id, self.quote[:40])

    def __eq__(self, other):
        return isinstance(other, Citation) and self.to_dict() == other.to_dict()
