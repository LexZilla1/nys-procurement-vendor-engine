#!/usr/bin/env python3
"""
engine/dated_objects.py — DatedObligation, the shared date primitive.

A DatedObligation is one thing with a clock: a bid deadline, a certification
expiry, an invoice net-due date, a not-for-profit renewal-notice watch, etc.
The daily-habit backend reasons about *categorical* state only — there are no
numeric confidence or risk scores anywhere here (never-green invariant). The
number of lead-time reminders is an operational count, not a score.

Two hard rules this module enforces:

  1. Verify-first dates. A date we cannot parse or do not yet know is NOT
     guessed and NOT silently dropped: it becomes date_status
     VERIFY_AT_SOURCE and the obligation carries a citation to where the real
     date must be read. Such an obligation derives to state VERIFY.

  2. State and credential legal status are separate axes. DatedObligation.state
     is one of seven operational states (see STATES). A credential's legal
     status (e.g. an MWBE certification) lives in a *different* enum,
     CredentialStatus, defined here for the future credential object. The MWBE
     recertification rebuttable presumption (EXC §314(5)(b)-(c)) is a
     credential-status concern (RECERT_PRESUMPTION_PENDING) — it is NEVER a
     DatedObligation.state and is NEVER rendered as OK.

Law-derived obligations (cert_expiry, nfp_renewal_notice_watch) are built by
factories that attach a golden_rule Citation. User-entered obligations never
carry a golden_rule citation.
"""

import datetime

from engine.citation import Citation, GOLDEN_RULE, USER_ENTERED

# ---------------------------------------------------------------------------
# Categorical enums (strings — no numeric scores anywhere)
# ---------------------------------------------------------------------------

# date_status
KNOWN = "KNOWN"
VERIFY_AT_SOURCE = "VERIFY_AT_SOURCE"
NOT_APPLICABLE = "NOT_APPLICABLE"
DATE_STATUSES = (KNOWN, VERIFY_AT_SOURCE, NOT_APPLICABLE)

# obligation state
PENDING = "PENDING"
DUE_SOON = "DUE_SOON"
OVERDUE = "OVERDUE"
DONE = "DONE"
VERIFY = "VERIFY"
LAPSED = "LAPSED"
BLOCKED = "BLOCKED"
STATES = (PENDING, DUE_SOON, OVERDUE, DONE, VERIFY, LAPSED, BLOCKED)

# credential_status — a SEPARATE axis (never mixed into STATES). Belongs to the
# future credential/certification object; defined here so schemas and callers
# share one vocabulary. RECERT_PRESUMPTION_PENDING models the EXC §314(5)(b)-(c)
# rebuttable presumption and is deliberately NOT one of STATES.
CRED_OK = "OK"
CRED_EXPIRING = "EXPIRING"
CRED_EXPIRED = "EXPIRED"
CRED_LAPSED = "LAPSED"
CRED_VERIFY = "VERIFY"
CRED_RECERT_PRESUMPTION_PENDING = "RECERT_PRESUMPTION_PENDING"
CREDENTIAL_STATUSES = (
    CRED_OK,
    CRED_EXPIRING,
    CRED_EXPIRED,
    CRED_LAPSED,
    CRED_VERIFY,
    CRED_RECERT_PRESUMPTION_PENDING,
)


def credential_is_ok(status):
    """OK iff status is exactly CRED_OK. A pending recertification presumption
    is NEVER OK — the presumption is rebuttable, so it can never be rendered as
    a settled 'good' credential."""
    return status == CRED_OK


# ---------------------------------------------------------------------------
# Kind registry (extensible)
# ---------------------------------------------------------------------------

DEFAULT_LEAD_TIMES = [90, 30, 7, 1]

# Each kind maps to its metadata. `lead_times` is a per-kind override of the
# default reminder cascade; callers may further override per obligation.
KIND_REGISTRY = {}


def register_kind(name, lead_times=None, law_derived=False, description=""):
    """Register (or re-register) an obligation kind. Extensible by design —
    later PRs add kinds without touching this module's core logic."""
    if not name:
        raise ValueError("kind name is required")
    KIND_REGISTRY[name] = {
        "lead_times": list(lead_times) if lead_times else list(DEFAULT_LEAD_TIMES),
        "law_derived": bool(law_derived),
        "description": description,
    }
    return KIND_REGISTRY[name]


# The initial registry. Every kind defaults to the [90,30,7,1] cascade; the
# per-kind override hook exists so later PRs can tune individual kinds (e.g. a
# shorter cascade for invoice_net_due) without inventing numbers here now.
for _k, _law in (
    ("bid_deadline", False),
    ("question_deadline", False),
    ("site_visit", False),
    ("cert_expiry", True),                 # EXC §314(5)(a)
    ("vendrep_staleness", False),
    ("insurance_expiry", False),
    ("statute_sunset", True),
    ("contract_deliverable", False),
    ("nfp_renewal_notice_watch", True),    # GFO XI.4.A
    ("invoice_net_due", False),
    ("retainage_release", False),
    ("closeout_deliverable", False),
):
    register_kind(_k, law_derived=_law)


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def parse_date(value):
    """Parse an ISO 'YYYY-MM-DD' string (or pass through a date). Returns a
    date, or None if the value is missing/unparseable. Callers turn a None
    here into date_status=VERIFY_AT_SOURCE — never a guessed default."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# DatedObligation
# ---------------------------------------------------------------------------

class DatedObligation:
    """One thing with a clock. See module docstring for the two hard rules."""

    def __init__(self, id, kind, source_object_id, due_date=None,
                 date_status=None, lead_times=None, citation=None,
                 depends_on=None, done=False, lapsed=False):
        if not id:
            raise ValueError("id is required")
        if kind not in KIND_REGISTRY:
            raise ValueError(
                "unknown kind %r — register it via register_kind()" % kind)

        self.id = id
        self.kind = kind
        self.source_object_id = source_object_id
        self.due_date = parse_date(due_date) if not isinstance(due_date, datetime.date) else due_date

        # Verify-first: if we were handed a due_date we could not parse, and no
        # explicit status was given, the date is unknown -> VERIFY_AT_SOURCE.
        if date_status is None:
            if self.due_date is not None:
                date_status = KNOWN
            elif due_date not in (None, ""):      # a value was supplied but failed to parse
                date_status = VERIFY_AT_SOURCE
            else:
                date_status = VERIFY_AT_SOURCE     # no date known -> verify, never guessed
        if date_status not in DATE_STATUSES:
            raise ValueError("invalid date_status %r" % date_status)
        # NOT_APPLICABLE is a factory signal, never a live obligation: the
        # sanctioned way to represent an inapplicable obligation is for the
        # factory to return None. Constructing one directly is a programming
        # error and must raise — it must NEVER collapse to DONE, because DONE
        # feeds future outcome / defects-prevented counts and an N/A item would
        # contaminate them.
        if date_status == NOT_APPLICABLE:
            raise ValueError(
                "date_status=NOT_APPLICABLE must not be constructed directly; "
                "an inapplicable obligation is represented by the factory "
                "returning None (see make_nfp_renewal_watch)")
        self.date_status = date_status

        # KNOWN must actually have a date; a KNOWN-without-date is incoherent.
        if self.date_status == KNOWN and self.due_date is None:
            raise ValueError("date_status KNOWN requires a due_date")

        self.lead_times = (list(lead_times) if lead_times is not None
                           else list(KIND_REGISTRY[kind]["lead_times"]))
        if citation is not None and not isinstance(citation, Citation):
            raise TypeError("citation must be a Citation")
        self.citation = citation
        self.depends_on = list(depends_on) if depends_on else []
        self.done = bool(done)
        self.lapsed = bool(lapsed)

    # -- state derivation is done by ObligationGraph so dependencies resolve --

    def to_dict(self, state=None):
        return {
            "id": self.id,
            "kind": self.kind,
            "source_object_id": self.source_object_id,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "date_status": self.date_status,
            "lead_times": list(self.lead_times),
            "citation": self.citation.to_dict() if self.citation else None,
            "depends_on": list(self.depends_on),
            "state": state,
        }

    def __repr__(self):
        return "DatedObligation(%s/%s due=%s status=%s)" % (
            self.id, self.kind, self.due_date, self.date_status)


# ---------------------------------------------------------------------------
# ObligationGraph — state derivation + dependency blast-radius
# ---------------------------------------------------------------------------

class ObligationGraph:
    """Holds a set of DatedObligations and derives categorical state, honoring
    dependencies. BLOCKED propagates: a dependent of an unresolved obligation
    (dependency date is VERIFY_AT_SOURCE, or the dependency is itself VERIFY /
    BLOCKED) is BLOCKED, because it cannot progress until the dependency
    resolves."""

    def __init__(self, obligations=None):
        self._by_id = {}
        for o in (obligations or []):
            self.add(o)

    def add(self, obligation):
        self._by_id[obligation.id] = obligation
        return obligation

    def get(self, oid):
        return self._by_id.get(oid)

    def all(self):
        return list(self._by_id.values())

    def _unresolved_dep(self, dep, dep_state):
        # A dependency is "unresolved" (blocking) when we cannot yet know its
        # date, or it is itself waiting/blocked. A LAPSED/OVERDUE dependency is
        # *resolved* (we know what happened) and does not, by itself, block.
        return (dep.date_status == VERIFY_AT_SOURCE
                or dep_state in (VERIFY, BLOCKED))

    def state_of(self, oid, today=None, _stack=None):
        """Derive the categorical state of one obligation as of `today`
        (defaults to actual today). Pure function of the obligation set."""
        today = today or datetime.date.today()
        obl = self._by_id[oid]
        _stack = _stack or frozenset()

        if oid in _stack:
            # Dependency cycle: cannot resolve -> BLOCKED (never guessed).
            return BLOCKED
        if obl.done:
            return DONE
        if obl.lapsed:
            return LAPSED

        # Dependency gate first — blocking beats everything except done/lapsed.
        for dep_id in obl.depends_on:
            dep = self._by_id.get(dep_id)
            if dep is None:
                return BLOCKED                     # dangling dependency = unresolved
            dep_state = self.state_of(dep_id, today, _stack | {oid})
            if self._unresolved_dep(dep, dep_state):
                return BLOCKED

        if obl.date_status == VERIFY_AT_SOURCE:
            return VERIFY
        # date_status is necessarily KNOWN here: NOT_APPLICABLE can never reach a
        # live obligation (the constructor rejects it), so there is no NA branch.

        # KNOWN date -> pure calendar math against the lead-time cascade.
        delta = (obl.due_date - today).days
        if delta < 0:
            return OVERDUE
        max_lead = max(obl.lead_times) if obl.lead_times else 0
        if delta <= max_lead:
            return DUE_SOON
        return PENDING

    def states(self, today=None):
        """Return {id: state} for every obligation."""
        return {oid: self.state_of(oid, today) for oid in self._by_id}

    def dependents(self, oid, today=None, live_only=True):
        """Blast radius: every obligation that transitively depends on `oid`.
        With live_only (default), DONE dependents are excluded — we return the
        *live* work that an expiring/failed obligation puts at risk."""
        reverse = {}
        for o in self._by_id.values():
            for dep in o.depends_on:
                reverse.setdefault(dep, []).append(o.id)

        seen, out, stack = set(), [], list(reverse.get(oid, []))
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            stack.extend(reverse.get(cur, []))

        if live_only:
            out = [i for i in out if self.state_of(i, today) != DONE]
        return sorted(out)


# ---------------------------------------------------------------------------
# Golden-cited factories for law-derived kinds
# ---------------------------------------------------------------------------

# EXC §314(5)(a) — MWBE certification five-year validity. Verbatim quote (present
# in golden-copy/sources/source-exec-314-mwbe-cert-validity.md STATE TEXT body).
EXC314_SOURCE = "source-exec-314-mwbe-cert-validity.md"
EXC314_QUOTE = ("all minority and women-owned business enterprise certifications "
                "shall be valid for a period of five years")
EXC314_CAPTURED = "2026-07-03"

# GFO XI.4.A — agency duty to notify an NFP of intent to renew 90 days before the
# contract end date. Verbatim quote (present in
# golden-copy/sources/source-xi-4-a-nfp-prompt-contracting.md STATE TEXT body).
XI4A_SOURCE = "source-xi-4-a-nfp-prompt-contracting.md"
XI4A_QUOTE = ("notify the NFP organization of their intent to renew the "
              "contract 90 days prior to the contract end date")
XI4A_CAPTURED = "2026-06-28"

# Fixed, non-conclusory wording for the NFP renewal-notice watch. It reports an
# absence of a recorded notice and points to verification — it does NOT assert
# that the agency failed a legal duty (that would be a legal conclusion / UPL).
NFP_RENEWAL_WATCH_MESSAGE = (
    "No renewal notice recorded by the 90-day watch date; "
    "verify with agency/source.")


def _mwbe_validity_years():
    return 5


def make_cert_expiry(id, source_object_id, expiry_date, lead_times=None):
    """Build a cert_expiry obligation for an MWBE certification. The five-year
    validity is statutory (EXC §314(5)(a)); this obligation tracks the *expiry
    date's* operational clock only. Credential legal status (including any
    recertification presumption) is a separate axis and is NOT set here.

    If expiry_date is unknown/unparseable, the obligation is VERIFY_AT_SOURCE —
    the date is never guessed from the certification date."""
    citation = Citation(
        source_id=EXC314_SOURCE, source_type=GOLDEN_RULE,
        locator="§ 314(5)(a)", quote=EXC314_QUOTE, captured_at=EXC314_CAPTURED)
    parsed = parse_date(expiry_date)
    return DatedObligation(
        id=id, kind="cert_expiry", source_object_id=source_object_id,
        due_date=parsed,
        date_status=KNOWN if parsed else VERIFY_AT_SOURCE,
        lead_times=lead_times, citation=citation)


def make_nfp_renewal_watch(id, contract_id, contract_end_date, xi4a_covered,
                           notice_recorded=False, lead_times=None):
    """Vendor-side watch for the GFO XI.4.A agency duty to notify an NFP of
    intent to renew 90 days before contract end.

    Returns None when the contract is not XI.4.A-covered (the watch is
    NOT_APPLICABLE, so it is simply not instantiated). When covered, the watch
    fires (due_date) at contract_end - 90 days. If a notice has been recorded,
    the obligation is DONE. If the end date is unknown, VERIFY_AT_SOURCE."""
    if not xi4a_covered:
        return None
    citation = Citation(
        source_id=XI4A_SOURCE, source_type=GOLDEN_RULE,
        locator="Notification of Intent to Renew",
        quote=XI4A_QUOTE, captured_at=XI4A_CAPTURED)
    end = parse_date(contract_end_date)
    watch_date = (end - datetime.timedelta(days=90)) if end else None
    return DatedObligation(
        id=id, kind="nfp_renewal_notice_watch", source_object_id=contract_id,
        due_date=watch_date,
        date_status=KNOWN if watch_date else VERIFY_AT_SOURCE,
        lead_times=lead_times, citation=citation, done=bool(notice_recorded))


def make_user_obligation(id, kind, source_object_id, due_date, lead_times=None,
                         locator="", captured_at=None):
    """Build an obligation from a date the vendor entered. It is grounded with a
    user_entered citation — NEVER golden_rule — so law-derived and self-reported
    facts can never be confused."""
    parsed = parse_date(due_date)
    citation = Citation(
        source_id="user_entered:%s" % source_object_id, source_type=USER_ENTERED,
        locator=locator, quote=(str(due_date) if due_date else "(no date given)"),
        captured_at=captured_at or datetime.date.today().isoformat())
    return DatedObligation(
        id=id, kind=kind, source_object_id=source_object_id,
        due_date=parsed,
        date_status=KNOWN if parsed else VERIFY_AT_SOURCE,
        lead_times=lead_times, citation=citation)
