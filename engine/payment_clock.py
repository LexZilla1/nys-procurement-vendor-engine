#!/usr/bin/env python3
"""
engine/payment_clock.py — source-backed payment-clock deadline / holiday logic.

PR 2. Computes invoice payment-clock deadlines. Two binding design rules govern
everything here:

  1. SOURCE-BACKED, no live fetch. The public-holiday set (GCN §24) and the
     next-business-day roll (GCN §25-a) are read EXCLUSIVELY from the in-repo
     verified-golden captures — golden-copy/sources/source-gcn-24-public-holidays.md
     and source-gcn-25-a-deadline-extension.md — via validator.GoldenCopy. There
     are NO embedded/hardcoded holiday lists. If a source is unavailable the
     clock REFUSES to compute a holiday-adjusted date (VERIFY), never guesses.
     (The freshness workflow is the only thing that ever compares against live
     text.)

  2. ATTORNEY GATE (fail-closed). GCN §24 carries an L-grade interpretive note:
     the GFO XII.5.I "legal holidays" <-> GCN §24 "public holiday" mapping is
     not yet attorney-approved, and §24 also includes DYNAMIC President/
     Governor-appointed days (an open class). So any deadline computation that
     DEPENDS on the holiday calendar fails closed to a VERIFY-level result
     ("deadline may fall on or near a holiday — verify at [citation]") and NEVER
     emits a confident date — until HOLIDAY_MAPPING_ATTORNEY_APPROVED is flipped
     to True after attorney sign-off. The confident path already exists below;
     flipping the flag enables it with no rework. Deadline math that does NOT
     depend on holidays (pure calendar day-count) outputs a confident date
     normally, under the existing never-green / verify-first rules.

No numeric confidence/risk scores anywhere (never-green invariant). No tier-3
data (TIN/SSN/DOB). All law-derived results carry a verbatim golden Citation.
"""

import datetime
import re

from engine.citation import Citation, GOLDEN_RULE
from engine import golden_status as gs

# ---------------------------------------------------------------------------
# ATTORNEY GATE — single flag. See rule 2 above.
# ---------------------------------------------------------------------------

# Binding gate: holiday-dependent deadlines return VERIFY (never a confident
# date) while this is False. Flip to True ONLY after a licensed attorney signs
# off on the GCN §24 "public holiday" <-> GFO XII.5.I "legal holidays" mapping
# (BACKLOG attorney-review list: "flip HOLIDAY_MAPPING_ATTORNEY_APPROVED after
# sign-off"). No other code changes are required to enable the confident path.
HOLIDAY_MAPPING_ATTORNEY_APPROVED = False

HOLIDAY_GATE_REASON = (
    "GCN §24 'public holiday' <-> GFO XII.5.I 'legal holidays' is an L-grade "
    "interpretive mapping pending attorney review; GCN §24 also includes dynamic "
    "President/Governor-appointed days (an open class). Until sign-off, "
    "holiday-dependent deadlines return VERIFY and no confident date is emitted."
)

# ---------------------------------------------------------------------------
# Golden sources + verbatim citation anchors (all confirmed verbatim in the
# STATE TEXT bodies; see test_payment_clock.py::test_*_citations_are_verbatim).
# ---------------------------------------------------------------------------

GCN24_SOURCE = "source-gcn-24-public-holidays.md"
GCN25A_SOURCE = "source-gcn-25-a-deadline-extension.md"
CAPTURED_AT = "2026-07-05"

# GCN §24 — anchor for the public-holiday definition and the Sunday-observed roll.
GCN24_ANCHOR_QUOTE = "The term public holiday includes the following days in each year"
GCN24_SUNDAY_ROLL_QUOTE = "if any of such days except Flag day is Sunday, the next day thereafter"
GCN24_DYNAMIC_QUOTE = ("each day appointed by the president of the United States "
                       "or by the governor of this state")
# GCN §25-a — the next-succeeding-business-day rule (subd. 1).
GCN25A_ROLL_QUOTE = "such act may be done on the next succeeding business day"

# ---------------------------------------------------------------------------
# Categorical result vocabulary (strings — no scores)
# ---------------------------------------------------------------------------

KNOWN = "KNOWN"      # a confident, emitted date
VERIFY = "VERIFY"    # fail-closed: verify at source; no date emitted
CLOCK_STATUSES = (KNOWN, VERIFY)

BASIS_PURE = "pure_day_count"          # holiday-INDEPENDENT
BASIS_ADJUSTED = "holiday_adjusted"    # holiday-DEPENDENT (gated)


class HolidaySourceUnavailable(Exception):
    """Raised when a required GCN golden source is missing or its verbatim
    anchor is absent. Callers translate this into a fail-closed VERIFY rather
    than guessing a calendar."""


# ---------------------------------------------------------------------------
# Ordinal / weekday / month vocabulary for parsing the GCN §24 prose
# ---------------------------------------------------------------------------

_ONES = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
         "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth",
         "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth",
         "nineteenth"]
_TENS = {"twent": 20, "thirt": 30}


def _build_day_ordinals():
    """Map ordinal words (1..31) to ints, e.g. 'first'->1, 'twenty-fifth'->25."""
    out = {}
    for i in range(1, 20):
        out[_ONES[i]] = i
    out["twentieth"] = 20
    out["thirtieth"] = 30
    tens_word = {20: "twenty", 30: "thirty"}
    unit_word = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
                 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth"}
    for base in (20, 30):
        for u in range(1, 10):
            if base + u <= 31:
                out["%s-%s" % (tens_word[base], unit_word[u])] = base + u
    return out


DAY_ORDINALS = _build_day_ordinals()

# Ordinal words for the "Nth weekday" pattern (plus 'last').
WEEK_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
                 "last": "last"}

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}

MONTHS = {m.lower(): i for i, m in enumerate(
    ["", "January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

_WD = "(?:%s)" % "|".join(WEEKDAYS)
_MO = "(?:%s)" % "|".join(m for m in MONTHS if m)
# "the <ordinal> <Weekday> of|in <Month>"  (nth-weekday holidays)
_NTH_WEEKDAY_RE = re.compile(
    r"the ([a-z-]+) (%s) (?:of|in) (%s)" % (_WD, _MO), re.I)
# "the <ordinal> day of <Month>"  (fixed day-of-month holidays)
_DAY_OF_MONTH_RE = re.compile(r"the ([a-z-]+) day of (%s)" % _MO, re.I)


# ---------------------------------------------------------------------------
# Date math helpers (pure, stdlib)
# ---------------------------------------------------------------------------

def _nth_weekday(year, month, weekday_idx, n):
    """Date of the n-th <weekday> of month (n is 1..5 or 'last')."""
    if n == "last":
        d = datetime.date(year, month, _days_in_month(year, month))
        while d.weekday() != weekday_idx:
            d -= datetime.timedelta(days=1)
        return d
    d = datetime.date(year, month, 1)
    while d.weekday() != weekday_idx:
        d += datetime.timedelta(days=1)
    d += datetime.timedelta(weeks=n - 1)
    if d.month != month:
        raise ValueError("no %d-th weekday %d in %04d-%02d" % (n, weekday_idx, year, month))
    return d


def _days_in_month(year, month):
    if month == 12:
        nxt = datetime.date(year + 1, 1, 1)
    else:
        nxt = datetime.date(year, month + 1, 1)
    return (nxt - datetime.timedelta(days=1)).day


# ---------------------------------------------------------------------------
# ClockResult — categorical, citation-bearing
# ---------------------------------------------------------------------------

class ClockResult:
    """One payment-clock deadline computation.

    status  : KNOWN (a confident date is emitted) or VERIFY (fail-closed; no
              date, verify at the cited source).
    deadline: a datetime.date when KNOWN, else None (NEVER a guessed date).
    basis   : BASIS_PURE (holiday-independent) or BASIS_ADJUSTED (holiday-dependent).
    citation: a verbatim golden Citation for the governing rule (may be None for
              a pure day-count with no law dependency).
    message : factual, non-conclusory wording (information, not legal advice).
    """

    __slots__ = ("status", "deadline", "basis", "citation", "message")

    def __init__(self, status, deadline, basis, citation=None, message=""):
        if status not in CLOCK_STATUSES:
            raise ValueError("invalid clock status %r" % status)
        if status == KNOWN and deadline is None:
            raise ValueError("KNOWN result requires a deadline date")
        if status == VERIFY and deadline is not None:
            raise ValueError("VERIFY result must not carry a date (fail-closed)")
        if citation is not None and not isinstance(citation, Citation):
            raise TypeError("citation must be a Citation")
        self.status = status
        self.deadline = deadline
        self.basis = basis
        self.citation = citation
        self.message = message

    def to_dict(self):
        return {
            "status": self.status,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "basis": self.basis,
            "citation": self.citation.to_dict() if self.citation else None,
            "message": self.message,
        }

    def __repr__(self):
        return "ClockResult(%s %s %s)" % (self.status, self.basis, self.deadline)


def _gcn25a_citation():
    return Citation(source_id=GCN25A_SOURCE, source_type=GOLDEN_RULE,
                    locator="§ 25-a(1)", quote=GCN25A_ROLL_QUOTE,
                    captured_at=CAPTURED_AT)


def _gcn24_citation():
    return Citation(source_id=GCN24_SOURCE, source_type=GOLDEN_RULE,
                    locator="§ 24", quote=GCN24_ANCHOR_QUOTE,
                    captured_at=CAPTURED_AT)


# ---------------------------------------------------------------------------
# HolidayCalendarProvider — source-backed, fail-closed
# ---------------------------------------------------------------------------

class HolidayCalendarProvider:
    """Derives the NY public-holiday set from the GCN §24 golden STATE TEXT and
    the next-business-day roll from GCN §25-a. SOURCE-BACKED: it parses the
    verbatim golden body — it never carries a hardcoded holiday list. Fail-closed:
    if either golden source (or its verbatim anchor) is missing, construction
    raises HolidaySourceUnavailable and no calendar is produced.

    Note on the ATTORNEY GATE: this provider computes the *confident* holiday
    calendar (rule 2's "the confident path exists"). Whether a caller is ALLOWED
    to use it is gated separately by HOLIDAY_MAPPING_ATTORNEY_APPROVED in
    PaymentClock — the provider itself does not decide policy.
    """

    def __init__(self, golden=None):
        if golden is None:
            from validator import GoldenCopy
            golden = GoldenCopy()
        self.golden = golden
        for src, anchor in ((GCN24_SOURCE, GCN24_ANCHOR_QUOTE),
                            (GCN25A_SOURCE, GCN25A_ROLL_QUOTE)):
            if not golden.has(src):
                raise HolidaySourceUnavailable(
                    "required golden source missing: %s" % src)
            try:
                # Verbatim anchor must be present AND the source citation-eligible
                # for the holiday calendar's disposition. GCN §24 is L-grade and
                # the adjusted-date path is fail-closed VERIFY / attorney-gated, so
                # the anchor is cited into a gated (VERIFY) context — never
                # confident. (The confident KNOWN date, once attorney-approved,
                # cites the VERIFIED_GOLDEN GCN §25-a rule, not this L-grade §24.)
                golden.cite(src, anchor, output_context=gs.OUTPUT_VERIFY)
            except Exception as exc:
                raise HolidaySourceUnavailable(
                    "verbatim anchor absent or not citation-eligible in %s: %s"
                    % (src, exc))
        self._gcn24_body = golden.body(GCN24_SOURCE)
        self._rules = self._parse_holiday_rules(self._gcn24_body)
        if not self._rules:
            raise HolidaySourceUnavailable(
                "parsed zero holiday rules from %s — refusing to build an empty "
                "calendar" % GCN24_SOURCE)
        # Dynamic (unenumerable) holidays are present in §24 (general election
        # day; President/Governor-appointed days). We surface their existence;
        # we do not fabricate their dates.
        self.has_dynamic_holidays = GCN24_DYNAMIC_QUOTE in self._gcn24_body
        self.sunday_roll = GCN24_SUNDAY_ROLL_QUOTE in self._gcn24_body

    # -- parsing --------------------------------------------------------------

    @staticmethod
    def _parse_holiday_rules(body):
        """Extract enumerable holiday rules from the verbatim GCN §24 text.

        Returns a list of dicts: {'type':'fixed','month':m,'day':d} or
        {'type':'weekday','month':m,'weekday':wd,'n':n|'last'}. Dynamic days
        (general election day, proclamation days) are intentionally NOT returned
        — they are an open class handled as `has_dynamic_holidays`.
        """
        rules = []
        seen = set()
        for m in _NTH_WEEKDAY_RE.finditer(body):
            ordn, wd, mon = m.group(1).lower(), m.group(2).lower(), m.group(3).lower()
            if ordn not in WEEK_ORDINALS:
                continue
            key = ("weekday", MONTHS[mon], WEEKDAYS[wd], WEEK_ORDINALS[ordn])
            if key in seen:
                continue
            seen.add(key)
            rules.append({"type": "weekday", "month": MONTHS[mon],
                          "weekday": WEEKDAYS[wd], "n": WEEK_ORDINALS[ordn]})
        for m in _DAY_OF_MONTH_RE.finditer(body):
            ordn, mon = m.group(1).lower(), m.group(2).lower()
            if ordn not in DAY_ORDINALS:
                continue
            key = ("fixed", MONTHS[mon], DAY_ORDINALS[ordn])
            if key in seen:
                continue
            seen.add(key)
            rules.append({"type": "fixed", "month": MONTHS[mon],
                          "day": DAY_ORDINALS[ordn]})
        return rules

    # -- calendar -------------------------------------------------------------

    def public_holidays(self, year):
        """The enumerable public-holiday dates for `year`, derived from §24.

        Includes the §24 Sunday-observed roll ("if any of such days except Flag
        day is Sunday, the next day thereafter") for fixed-date holidays. Does
        NOT include dynamic proclamation/election days (see has_dynamic_holidays).
        """
        dates = set()
        fixed = set()
        for r in self._rules:
            if r["type"] == "fixed":
                d = datetime.date(year, r["month"], r["day"])
                dates.add(d)
                fixed.add(d)
            else:
                dates.add(_nth_weekday(year, r["month"], r["weekday"], r["n"]))
        if self.sunday_roll:
            for d in list(fixed):
                if d.weekday() == 6:  # Sunday -> observed the next day
                    dates.add(d + datetime.timedelta(days=1))
        return dates

    def is_public_holiday(self, d):
        return d in self.public_holidays(d.year)

    def is_business_day(self, d):
        # GCN §25-a triggers on "a Saturday, Sunday or a public holiday".
        return d.weekday() < 5 and not self.is_public_holiday(d)

    def next_business_day(self, d):
        """The next succeeding business day on/after `d` (GCN §25-a(1))."""
        cur = d
        while not self.is_business_day(cur):
            cur += datetime.timedelta(days=1)
        return cur


# ---------------------------------------------------------------------------
# PaymentClock — the gated public API
# ---------------------------------------------------------------------------

class PaymentClock:
    """Payment-clock deadline computations. Holds a HolidayCalendarProvider when
    the golden sources are available; degrades fail-closed (holiday-adjusted ->
    VERIFY) when they are not. The attorney gate is applied here, not in the
    provider."""

    def __init__(self, golden=None, approved=None):
        # `approved` overrides the module flag (tests flip it without mutating
        # global state). Defaults to the binding module-level gate.
        self.approved = (HOLIDAY_MAPPING_ATTORNEY_APPROVED
                         if approved is None else bool(approved))
        try:
            self.calendar = HolidayCalendarProvider(golden=golden)
        except HolidaySourceUnavailable:
            self.calendar = None   # fail-closed; holiday-adjusted -> VERIFY

    # -- holiday-INDEPENDENT: always confident (never-green day-count) ---------

    def net_due_pure(self, received_date, net_terms_days):
        """Raw net-due date = received_date + net_terms_days CALENDAR days.

        Holiday-INDEPENDENT, so it is NOT gated: it returns a confident KNOWN
        date whenever the inputs are known (verify-first if not). This is the
        pure day-count deadline the binding plan permits to output normally.
        """
        received = _coerce_date(received_date)
        if received is None or net_terms_days is None or net_terms_days < 0:
            return ClockResult(
                VERIFY, None, BASIS_PURE, citation=None,
                message="received date or net-term day-count unknown — verify at source.")
        due = received + datetime.timedelta(days=int(net_terms_days))
        return ClockResult(
            KNOWN, due, BASIS_PURE, citation=None,
            message=("Net-due date by calendar day-count (%d days from receipt); "
                     "not holiday-adjusted." % int(net_terms_days)))

    # -- holiday-DEPENDENT: gated behind the attorney flag ---------------------

    def net_due_adjusted(self, received_date, net_terms_days):
        """Net-due date rolled to the next succeeding business day if it lands on
        a Saturday, Sunday or public holiday (GCN §25-a(1) over the GCN §24
        calendar).

        DEPENDS on the holiday calendar, so it is GATED:
          * attorney gate not approved  -> VERIFY (no date emitted);
          * golden source unavailable   -> VERIFY (refuse to compute, no guess);
          * approved + source available -> confident KNOWN (rolled) date.
        """
        received = _coerce_date(received_date)
        if received is None or net_terms_days is None or net_terms_days < 0:
            return ClockResult(
                VERIFY, None, BASIS_ADJUSTED, citation=_gcn25a_citation(),
                message="received date or net-term day-count unknown — verify at source.")

        if not self.approved:
            return ClockResult(
                VERIFY, None, BASIS_ADJUSTED, citation=_gcn25a_citation(),
                message=("Deadline may fall on or near a Saturday, Sunday or public "
                         "holiday — verify at GCN §25-a / §24 [source-backed]. "
                         "Holiday mapping pending attorney review; no adjusted date "
                         "asserted."))
        if self.calendar is None:
            return ClockResult(
                VERIFY, None, BASIS_ADJUSTED, citation=_gcn25a_citation(),
                message=("Holiday source unavailable — refusing to compute a "
                         "holiday-adjusted date; verify at GCN §24 / §25-a."))

        raw = received + datetime.timedelta(days=int(net_terms_days))
        rolled = self.calendar.next_business_day(raw)
        rolled_note = "" if rolled == raw else (
            " Raw due date %s fell on a Saturday/Sunday/public holiday; rolled to "
            "the next succeeding business day." % raw.isoformat())
        dyn_note = (" Note: GCN §24 also includes dynamic President/Governor-"
                    "appointed days not in the computed set — confirm none applies."
                    if self.calendar.has_dynamic_holidays else "")
        return ClockResult(
            KNOWN, rolled, BASIS_ADJUSTED, citation=_gcn25a_citation(),
            message=("Net-due date adjusted to the next succeeding business day "
                     "per GCN §25-a over the GCN §24 public-holiday calendar.%s%s"
                     % (rolled_note, dyn_note)))

    # -- invoice-shell convenience --------------------------------------------

    def invoice_due_dates(self, invoice):
        """Fill the invoice-shell clock: given an Invoice dict with
        `received_date` and `net_terms_days`, return both the pure and the
        (gated) holiday-adjusted results. No mutation of the input."""
        received = invoice.get("received_date")
        terms = invoice.get("net_terms_days")
        return {
            "pure_day_count": self.net_due_pure(received, terms),
            "holiday_adjusted": self.net_due_adjusted(received, terms),
        }


def _coerce_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
