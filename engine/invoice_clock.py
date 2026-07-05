#!/usr/bin/env python3
"""
engine/invoice_clock.py — the full statutory payment clock (PR 2b).

Builds on the PR 2a holiday-source core (engine/payment_clock.py) to implement
the State Finance Law Article 11-A required-payment-date rules, read EXCLUSIVELY
from the in-repo verified goldens (no live fetch, no hardcoded rule text):

  * MIR "receipt of an invoice" later-of semantics — §179-e(6)
    (source-stf-179-e.md).
  * Required-payment-date branches — §179-f(2) (source-stf-179-f.md):
      - 30 calendar days (standard);
      - 15 calendar days for a small business, requiring BOTH the small-business
        expedited certification AND electronic submission (the statute's
        conjunctive "provided that the small business submits its invoice
        electronically ... and identifies that it is seeking expedited payment
        as a small business"); dropping either condition would fabricate a false
        15-day clock, so a missing conjunct falls back to the 30-day branch;
      - 75 calendar days for final payments on highway construction contracts.
  * Every branch is "... calendar days, EXCLUDING LEGAL HOLIDAYS" (§179-f(2)),
    so the required-payment DATE is holiday-dependent and inherits the PR 2a
    attorney gate: while HOLIDAY_MAPPING_ATTORNEY_APPROVED is False the date is
    VERIFY (no confident date). The branch selection, day-count, and MIR start
    are categorical/holiday-independent and are reported regardless.
  * Prompt-payment interest note (non-promissory) + rate_lookup over
    nysinterestrates.csv with a VERIFY_AT_SOURCE fallback — §179-f/§179-g,
    GFO XII.5.I.

No numeric confidence/risk scores (never-green). No tier-3 data. Every
law-derived result carries a verbatim golden Citation.
"""

import datetime

from engine import payment_clock as pcmod
from engine.payment_clock import (
    PaymentClock, ClockResult, KNOWN, VERIFY, BASIS_ADJUSTED,
    _coerce_date)
from engine.citation import Citation, GOLDEN_RULE
from engine.dated_objects import (
    DatedObligation, ObligationGraph, register_kind,
    KNOWN as DATE_KNOWN, VERIFY_AT_SOURCE)

# ---------------------------------------------------------------------------
# Golden sources + verbatim citation anchors (all confirmed verbatim; see
# test_invoice_clock.py::test_all_anchor_quotes_are_verbatim).
# ---------------------------------------------------------------------------

STF179F = "source-stf-179-f.md"
STF179E = "source-stf-179-e.md"
XII5I = "source-xii-5-i-prompt-payment-interest.md"
STF179F_CAPTURED = "2026-06-29"
STF179E_CAPTURED = "2026-06-29"

# §179-e(6) — receipt-of-invoice later-of (MIR).
MIR_LATER_OF_QUOTE = (
    "the date on which a proper invoice is actually received in the designated "
    "payment office, or (b) the date on which the state agency receives the "
    "purchased goods, property, or services covered by the proper invoice, "
    "whichever is later")
# §179-f(2) — the three required-payment-date branches.
NET_DUE_30_QUOTE = "The required payment date shall be thirty calendar days, excluding legal holidays"
NET_DUE_15_SB_QUOTE = ("provided that the small business submits its invoice "
                       "electronically, in conformance with the policies and "
                       "procedures of the accounting and financial management "
                       "system of state government and identifies that it is "
                       "seeking expedited payment as a small business")
NET_DUE_75_HWY_QUOTE = ("in the case of final payments on highway construction "
                        "contracts seventy-five calendar days, excluding legal "
                        "holidays, after receipt of an invoice")

# ---------------------------------------------------------------------------
# Categorical vocabularies (strings — no scores)
# ---------------------------------------------------------------------------

# MIR_DATE_CHECK categorical audit flag.
MIR_KNOWN = "MIR_KNOWN"                    # later-of determinable from both dates
MIR_VERIFY = "MIR_VERIFY"                  # a required date is unknown
MIR_HIGHWAY_VERIFY = "MIR_HIGHWAY_VERIFY"  # §179-e(6)(c): per Highway Law §38(7)(g), not in goldens
MIR_DATE_CHECKS = (MIR_KNOWN, MIR_VERIFY, MIR_HIGHWAY_VERIFY)

# Net-due branch (categorical).
BRANCH_30 = "BRANCH_30_STANDARD"
BRANCH_15_SB = "BRANCH_15_SMALL_BUSINESS"
BRANCH_75_HWY = "BRANCH_75_HIGHWAY_FINAL"
NET_DUE_BRANCHES = (BRANCH_30, BRANCH_15_SB, BRANCH_75_HWY)

# rate_lookup status (categorical).
RATE_KNOWN = "RATE_KNOWN"
RATE_VERIFY_AT_SOURCE = "RATE_VERIFY_AT_SOURCE"

# New law-derived obligation kind for the MIR receipt gate.
register_kind("invoice_mir_receipt", law_derived=True,
              description="§179-e(6) receipt-of-invoice (MIR) later-of date")


def _cite(src, quote, captured, locator):
    return Citation(source_id=src, source_type=GOLDEN_RULE, locator=locator,
                    quote=quote, captured_at=captured)


def _mir_citation():
    return _cite(STF179E, MIR_LATER_OF_QUOTE, STF179E_CAPTURED, "§ 179-e(6)")


def _branch_citation(branch):
    if branch == BRANCH_15_SB:
        return _cite(STF179F, NET_DUE_15_SB_QUOTE, STF179F_CAPTURED, "§ 179-f(2)")
    if branch == BRANCH_75_HWY:
        return _cite(STF179F, NET_DUE_75_HWY_QUOTE, STF179F_CAPTURED, "§ 179-f(2)")
    return _cite(STF179F, NET_DUE_30_QUOTE, STF179F_CAPTURED, "§ 179-f(2)")


# ---------------------------------------------------------------------------
# MIR — §179-e(6) later-of receipt of an invoice
# ---------------------------------------------------------------------------

def mir_receipt(invoice):
    """Compute the MIR ("receipt of an invoice") date per §179-e(6): the LATER of
    (a) the proper invoice actually received at the designated payment office and
    (b) the agency's receipt of the goods/property/services. Highway final
    payments use §179-e(6)(c) (Highway Law §38(7)(g)), which is NOT in the
    goldens -> MIR_HIGHWAY_VERIFY (never guessed).

    Returns (mir_date_or_None, check, citation) where `check` is a MIR_* flag.
    Holiday-INDEPENDENT (a max of two known dates), so it is not gated.
    """
    if invoice.get("highway_final_payment"):
        return (None, MIR_HIGHWAY_VERIFY, _mir_citation())
    inv = _coerce_date(invoice.get("invoice_received_date"))
    goods = _coerce_date(invoice.get("goods_received_date"))
    if inv is None or goods is None:
        return (None, MIR_VERIFY, _mir_citation())
    return (max(inv, goods), MIR_KNOWN, _mir_citation())


def mir_date_check(invoice):
    """MIR_DATE_CHECK — a categorical audit flag (never numeric) describing
    whether the §179-e(6) later-of MIR date is determinable, and which input
    governed."""
    mir, check, cite = mir_receipt(invoice)
    governing = None
    if check == MIR_KNOWN:
        inv = _coerce_date(invoice.get("invoice_received_date"))
        goods = _coerce_date(invoice.get("goods_received_date"))
        governing = "goods_received" if goods >= inv else "invoice_received"
    return {
        "check": check,
        "mir_date": mir.isoformat() if mir else None,
        "governing": governing,
        "citation": cite.to_dict(),
    }


# ---------------------------------------------------------------------------
# Net-due branch selection — §179-f(2)
# ---------------------------------------------------------------------------

def net_due_branch(invoice):
    """Select the required-payment-date branch (categorical) + its calendar-day
    count + verbatim citation. CONJUNCTIVE 15-day rule: a small business gets the
    15-day clock ONLY if it is expedited-certified AND submits electronically
    (§179-f(2)); missing either conjunct falls back to the 30-day branch so no
    false 15-day clock is ever produced. Highway final payments -> 75 days.

    Returns (branch, days, citation, note)."""
    if invoice.get("highway_final_payment"):
        return (BRANCH_75_HWY, 75, _branch_citation(BRANCH_75_HWY),
                "Final payment on a highway construction contract: 75 calendar "
                "days, excluding legal holidays (§179-f(2)).")
    sb_cert = bool(invoice.get("sb_15day_certified"))
    electronic = bool(invoice.get("submitted_electronically"))
    if sb_cert and electronic:
        return (BRANCH_15_SB, 15, _branch_citation(BRANCH_15_SB),
                "Small business seeking expedited payment AND submitting "
                "electronically: 15 calendar days, excluding legal holidays "
                "(§179-f(2), conjunctive).")
    # Small business but a conjunct is missing -> 30-day (never a false 15-day).
    note = "Standard 30 calendar days, excluding legal holidays (§179-f(2))."
    if sb_cert and not electronic:
        note += (" 15-day small-business clock NOT applied: §179-f(2) requires "
                 "electronic submission in addition to expedited certification.")
    elif electronic and not sb_cert:
        note += (" 15-day small-business clock NOT applied: §179-f(2) requires "
                 "expedited small-business certification in addition to "
                 "electronic submission.")
    return (BRANCH_30, 30, _branch_citation(BRANCH_30), note)


# ---------------------------------------------------------------------------
# Required payment date — §179-f(2), holiday-dependent (attorney-gated)
# ---------------------------------------------------------------------------

def _statutory_due(start, days, calendar):
    """`days` calendar days after `start`, EXCLUDING legal (public) holidays from
    the count (§179-f(2)), then rolled off any Saturday/Sunday/public holiday to
    the next succeeding business day (GCN §25-a). Legal holidays are the
    source-backed GCN §24 public-holiday set."""
    d = start
    counted = 0
    while counted < days:
        d += datetime.timedelta(days=1)
        if not calendar.is_public_holiday(d):   # exclude legal holidays from the count
            counted += 1
    return calendar.next_business_day(d)


def required_payment_date(invoice, clock=None):
    """Compute the §179-f required payment date as a ClockResult.

    Gated exactly like the PR 2a holiday-adjusted path, because §179-f(2) counts
    days "excluding legal holidays":
      * MIR not determinable            -> VERIFY (clock cannot start);
      * attorney gate not approved      -> VERIFY (no confident date);
      * golden holiday source missing   -> VERIFY (refuse to compute);
      * approved + source available     -> confident KNOWN date.
    """
    clock = clock or PaymentClock()
    mir, mir_check, mir_cite = mir_receipt(invoice)
    branch, days, branch_cite, branch_note = net_due_branch(invoice)

    if mir is None:
        why = ("Highway final-payment receipt date is set by Highway Law "
               "§38(7)(g) (§179-e(6)(c)), not in the golden copy — verify at "
               "source." if mir_check == MIR_HIGHWAY_VERIFY else
               "MIR receipt date (§179-e(6) later-of invoice/goods receipt) is "
               "unknown — verify at source.")
        return ClockResult(VERIFY, None, BASIS_ADJUSTED, citation=mir_cite,
                           message="%s Net-due clock cannot start." % why)

    base = ("%s Required payment date = %d calendar days after MIR (%s), "
            "excluding legal holidays (§179-f(2))."
            % (branch_note, days, mir.isoformat()))

    if not clock.approved:
        return ClockResult(
            VERIFY, None, BASIS_ADJUSTED, citation=branch_cite,
            message=("%s Holiday mapping pending attorney review "
                     "(HOLIDAY_MAPPING_ATTORNEY_APPROVED=False) — no confident "
                     "date asserted; verify at GCN §24 / §25-a." % base))
    if clock.calendar is None:
        return ClockResult(
            VERIFY, None, BASIS_ADJUSTED, citation=branch_cite,
            message=("%s Holiday source unavailable — refusing to compute a "
                     "date; verify at GCN §24 / §25-a." % base))

    due = _statutory_due(mir, days, clock.calendar)
    dyn = (" Note: GCN §24 also includes dynamic President/Governor-appointed "
           "days not in the computed set — confirm none applies."
           if clock.calendar.has_dynamic_holidays else "")
    return ClockResult(KNOWN, due, BASIS_ADJUSTED, citation=branch_cite,
                       message="%s Computed excluding legal holidays and rolled "
                               "to the next succeeding business day.%s" % (base, dyn))


# ---------------------------------------------------------------------------
# Obligation wiring — VERIFY mir -> invoice_net_due BLOCKED
# ---------------------------------------------------------------------------

def build_invoice_obligations(invoice, clock=None):
    """Build an ObligationGraph with a MIR-receipt obligation and the
    invoice_net_due obligation that depends on it.

    * MIR unknown/highway-verify -> the MIR obligation is VERIFY_AT_SOURCE, and
      invoice_net_due (which depends_on it) derives to **BLOCKED** — the net-due
      clock cannot start until MIR resolves.
    * MIR known but holiday-gated -> MIR resolves; invoice_net_due carries no
      date (VERIFY_AT_SOURCE) and derives to VERIFY (holiday mapping pending),
      NOT blocked.
    * MIR known + attorney-approved + source available -> invoice_net_due carries
      the computed required payment date (KNOWN).
    """
    clock = clock or PaymentClock()
    inv_id = invoice.get("id") or "invoice"
    mir, mir_check, mir_cite = mir_receipt(invoice)
    _, _, branch_cite, _ = net_due_branch(invoice)

    mir_obl = DatedObligation(
        id="%s:mir" % inv_id, kind="invoice_mir_receipt",
        source_object_id=inv_id, due_date=mir,
        date_status=DATE_KNOWN if mir else VERIFY_AT_SOURCE, citation=mir_cite)

    rpd = required_payment_date(invoice, clock=clock)
    net_obl = DatedObligation(
        id="%s:net_due" % inv_id, kind="invoice_net_due",
        source_object_id=inv_id, due_date=rpd.deadline,
        date_status=DATE_KNOWN if rpd.deadline else VERIFY_AT_SOURCE,
        citation=branch_cite, depends_on=["%s:mir" % inv_id])

    return ObligationGraph([mir_obl, net_obl])


# ---------------------------------------------------------------------------
# Prompt-payment interest note + rate lookup (§179-f/§179-g, GFO XII.5.I)
# ---------------------------------------------------------------------------

def rate_lookup(day, rates=None):
    """Look up the prompt-payment (overpayment) annual rate in effect on `day`
    from nysinterestrates.csv (reusing validator.RatesTable). Returns a dict with
    a categorical status. VERIFY_AT_SOURCE when the day is unknown, the quarter
    is absent, or the request falls outside the CSV's coverage (stale)."""
    if rates is None:
        from validator import InterestRates
        rates = InterestRates()
    d = _coerce_date(day)
    if d is None:
        return {"status": RATE_VERIFY_AT_SOURCE, "rate": None, "quarter": None,
                "reason": "no date supplied"}
    cov = rates.coverage
    if cov and (d < cov[0] or d > cov[1]):
        return {"status": RATE_VERIFY_AT_SOURCE, "rate": None, "quarter": None,
                "reason": "date outside CSV coverage (stale) — verify current "
                          "rate at the OSC prompt-payment source"}
    rate, quarter, url = rates.annual_rate_on(d)
    if rate is None:
        return {"status": RATE_VERIFY_AT_SOURCE, "rate": None, "quarter": None,
                "reason": "no quarter row covers this date — verify at source"}
    return {"status": RATE_KNOWN, "rate": rate, "quarter": quarter,
            "source_url": url}


def prompt_payment_note(invoice, clock=None, rates=None):
    """A NON-PROMISSORY, information-only note about prompt-payment interest. It
    describes the statutory possibility and points to verification; it NEVER
    promises that interest is owed or states an amount. UPL-safe: information,
    not legal or financial advice."""
    clock = clock or PaymentClock()
    rpd = required_payment_date(invoice, clock=clock)
    note = ("Information only — not a promise that interest is or will be owed. "
            "If a required payment date applies and passes without payment, State "
            "Finance Law Article 11-A (§179-f) may provide for prompt-payment "
            "interest computed at the §179-g overpayment rate, subject to the "
            "§179-f $10 de-minimis floor and the Article 11-A exclusions. Any "
            "such interest is determined and, where applicable, paid by the State "
            "— this tool does not calculate or guarantee it.")
    if rpd.status == VERIFY:
        note += (" The required payment date itself is not asserted here "
                 "(verify at source), so no interest timing is implied.")
        rate_day = None
    else:
        rate_day = rpd.deadline
    rate = rate_lookup(rate_day, rates=rates) if rate_day else {
        "status": RATE_VERIFY_AT_SOURCE, "rate": None, "quarter": None,
        "reason": "required payment date not asserted"}
    if rate["status"] == RATE_VERIFY_AT_SOURCE:
        note += " Applicable quarter's overpayment rate: VERIFY_AT_SOURCE."
    return {
        "note": note,
        "required_payment_status": rpd.status,
        "rate": rate,
        "citation": _cite(STF179F, NET_DUE_30_QUOTE, STF179F_CAPTURED,
                          "§ 179-f").to_dict(),
    }
