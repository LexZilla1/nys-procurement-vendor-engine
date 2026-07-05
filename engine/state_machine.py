#!/usr/bin/env python3
"""
engine/state_machine.py — tender lifecycle state machine.

A tender moves through a categorical lifecycle. There are NO numeric scores;
progress is expressed only as a named state plus a categorical triage verdict.
Two independent fields (not nested enums):

  tender_state   : where the tender is in the pipeline.
  triage_verdict : the Step-1 biddability call (or None before triage).

Transitions are governed by an explicit table (TRANSITIONS). Any move not in
the table raises IllegalTransition — the machine never silently accepts an
undefined jump. A handful of business constraints layer on top:

  * NO_BID is only valid before SUBMITTED (you cannot 'decline to bid' a bid you
    already submitted).
  * LOST requires a prior SUBMITTED, unless override=True is supplied together
    with an actor, a reason, and an outcome record (e.g. an administrative
    correction).
  * LOST and NO_BID both require an outcome record (engine/outcome_log).
  * Entering AWARDED spawns exactly one Contract — idempotent and replay-safe:
    re-applying the award never creates a second Contract.

Every accepted transition appends a TransitionLogEntry with actor_type,
actor_id, timestamp, from_state, to_state, reason and an optional citation.
"""

import datetime

from engine.citation import Citation

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

WATCHING = "WATCHING"
TRIAGED = "TRIAGED"
PREPARING = "PREPARING"
QUESTIONS_OPEN = "QUESTIONS_OPEN"
READY_TO_SUBMIT = "READY_TO_SUBMIT"
SUBMITTED = "SUBMITTED"
AWARDED = "AWARDED"
LOST = "LOST"
NO_BID = "NO_BID"
CONTRACT_EXECUTION = "CONTRACT_EXECUTION"
ACTIVE = "ACTIVE"
CLOSE_OUT = "CLOSE_OUT"
CLOSED = "CLOSED"

TENDER_STATES = (
    WATCHING, TRIAGED, PREPARING, QUESTIONS_OPEN, READY_TO_SUBMIT, SUBMITTED,
    AWARDED, LOST, NO_BID, CONTRACT_EXECUTION, ACTIVE, CLOSE_OUT, CLOSED,
)

# triage_verdict
BIDDABLE = "BIDDABLE"
NOT_BIDDABLE = "NOT_BIDDABLE"
VERIFY = "VERIFY"
TRIAGE_VERDICTS = (BIDDABLE, NOT_BIDDABLE, VERIFY, None)

# actor_type
USER = "USER"
SYSTEM = "SYSTEM"
ADMIN = "ADMIN"
IMPORT = "IMPORT"
ACTOR_TYPES = (USER, SYSTEM, ADMIN, IMPORT)

# States from which a bid can still be declined (NO_BID valid only before submit).
PRE_SUBMIT_STATES = frozenset({
    WATCHING, TRIAGED, PREPARING, QUESTIONS_OPEN, READY_TO_SUBMIT,
})

# Terminal states — no outgoing transitions (except LOST via explicit override).
TERMINAL_STATES = frozenset({LOST, NO_BID, CLOSED})

# ---------------------------------------------------------------------------
# Explicit transition table
# ---------------------------------------------------------------------------

TRANSITIONS = {
    WATCHING: {TRIAGED, NO_BID},
    TRIAGED: {PREPARING, NO_BID},
    PREPARING: {QUESTIONS_OPEN, READY_TO_SUBMIT, NO_BID},
    QUESTIONS_OPEN: {PREPARING, READY_TO_SUBMIT, NO_BID},
    READY_TO_SUBMIT: {SUBMITTED, NO_BID},
    SUBMITTED: {AWARDED, LOST},
    AWARDED: {CONTRACT_EXECUTION},
    CONTRACT_EXECUTION: {ACTIVE},
    ACTIVE: {CLOSE_OUT},
    CLOSE_OUT: {CLOSED},
    LOST: set(),
    NO_BID: set(),
    CLOSED: set(),
}


class IllegalTransition(Exception):
    """Raised when a requested tender_state transition is not permitted."""


class TransitionLogEntry:
    """One immutable record of a state change."""

    __slots__ = ("actor_type", "actor_id", "timestamp", "from_state",
                 "to_state", "reason", "citation")

    def __init__(self, actor_type, actor_id, timestamp, from_state, to_state,
                 reason, citation=None):
        if actor_type not in ACTOR_TYPES:
            raise ValueError("invalid actor_type %r" % actor_type)
        if citation is not None and not isinstance(citation, Citation):
            raise TypeError("citation must be a Citation or None")
        self.actor_type = actor_type
        self.actor_id = actor_id
        self.timestamp = timestamp
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        self.citation = citation

    def to_dict(self):
        return {
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
            "citation": self.citation.to_dict() if self.citation else None,
        }


class Contract:
    """Minimal Contract shell spawned on AWARDED. Payment-clock logic is PR 2 —
    this carries identity only. entity_id is nullable (future multi-entity)."""

    __slots__ = ("id", "tender_id", "entity_id", "spawned_at")

    def __init__(self, id, tender_id, entity_id=None, spawned_at=None):
        self.id = id
        self.tender_id = tender_id
        self.entity_id = entity_id
        self.spawned_at = spawned_at

    def to_dict(self):
        return {"id": self.id, "tender_id": self.tender_id,
                "entity_id": self.entity_id, "spawned_at": self.spawned_at}


def _now_iso(timestamp):
    if timestamp is None:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    if isinstance(timestamp, (datetime.date, datetime.datetime)):
        return timestamp.isoformat()
    return str(timestamp)


class TenderStateMachine:
    """Owns a single tender's state, verdict, transition log, and (once awarded)
    its spawned Contract."""

    def __init__(self, tender_id, entity_id=None, state=WATCHING,
                 triage_verdict=None):
        if state not in TENDER_STATES:
            raise ValueError("invalid initial state %r" % state)
        if triage_verdict not in TRIAGE_VERDICTS:
            raise ValueError("invalid triage_verdict %r" % triage_verdict)
        self.tender_id = tender_id
        self.entity_id = entity_id
        self.state = state
        self.triage_verdict = triage_verdict
        self.log = []
        self.contract = None       # exactly one, spawned on AWARDED

    # -- helpers ------------------------------------------------------------

    def _record(self, actor_type, actor_id, from_state, to_state, reason,
                citation, timestamp):
        self.log.append(TransitionLogEntry(
            actor_type=actor_type, actor_id=actor_id, timestamp=_now_iso(timestamp),
            from_state=from_state, to_state=to_state, reason=reason,
            citation=citation))

    def _spawn_contract(self, timestamp):
        # Idempotent + replay-safe: exactly one Contract per tender, ever.
        if self.contract is None:
            self.contract = Contract(
                id="contract:%s" % self.tender_id, tender_id=self.tender_id,
                entity_id=self.entity_id, spawned_at=_now_iso(timestamp))
        return self.contract

    # -- the one public mutator --------------------------------------------

    def transition(self, to_state, actor_type, actor_id, reason,
                   triage_verdict=None, citation=None, override=False,
                   outcome=None, timestamp=None):
        """Attempt a transition. Raises IllegalTransition on any disallowed move
        or unmet constraint. On success, appends a log entry and returns self."""
        if to_state not in TENDER_STATES:
            raise IllegalTransition("unknown target state %r" % to_state)
        if actor_type not in ACTOR_TYPES:
            raise ValueError("invalid actor_type %r" % actor_type)

        frm = self.state

        # Idempotent replay of a terminal/settled award: re-applying AWARDED when
        # already AWARDED is a no-op that must not spawn a second Contract.
        if to_state == frm == AWARDED:
            self._spawn_contract(timestamp)
            return self

        allowed = to_state in TRANSITIONS.get(frm, set())

        # --- constraint: NO_BID only before SUBMITTED ---
        if to_state == NO_BID and frm not in PRE_SUBMIT_STATES:
            raise IllegalTransition(
                "NO_BID is only valid before SUBMITTED (from %s)" % frm)

        # --- constraint: LOST needs prior SUBMITTED unless override+outcome ---
        if to_state == LOST:
            if frm != SUBMITTED:
                if not (override and outcome is not None and actor_id and reason):
                    raise IllegalTransition(
                        "LOST requires a prior SUBMITTED, or override=True with "
                        "actor+reason+outcome (from %s)" % frm)
                allowed = True     # override authorizes the off-table LOST

        # --- constraint: LOST / NO_BID require an outcome record ---
        if to_state in (LOST, NO_BID) and outcome is None:
            raise IllegalTransition(
                "%s requires an outcome record" % to_state)

        if not allowed:
            raise IllegalTransition(
                "illegal transition %s -> %s" % (frm, to_state))

        # --- accept ---
        if to_state == TRIAGED:
            if triage_verdict not in TRIAGE_VERDICTS or triage_verdict is None:
                raise IllegalTransition(
                    "TRIAGED requires a triage_verdict (BIDDABLE/NOT_BIDDABLE/VERIFY)")
            self.triage_verdict = triage_verdict

        self.state = to_state
        self._record(actor_type, actor_id, frm, to_state, reason, citation, timestamp)

        if to_state == AWARDED:
            self._spawn_contract(timestamp)

        return self

    def to_dict(self):
        return {
            "tender_id": self.tender_id,
            "entity_id": self.entity_id,
            "tender_state": self.state,
            "triage_verdict": self.triage_verdict,
            "contract": self.contract.to_dict() if self.contract else None,
            "log": [e.to_dict() for e in self.log],
        }


def render_transition_table():
    """Human-readable rendering of the legal transition graph (for docs/report)."""
    lines = ["tender_state transition table (illegal moves raise):", ""]
    for src in TENDER_STATES:
        dests = sorted(TRANSITIONS.get(src, set()))
        arrow = ", ".join(dests) if dests else "(terminal)"
        lines.append("  %-20s -> %s" % (src, arrow))
    lines.append("")
    lines.append("  constraints: NO_BID only from {WATCHING,TRIAGED,PREPARING,")
    lines.append("               QUESTIONS_OPEN,READY_TO_SUBMIT}; LOST only from")
    lines.append("               SUBMITTED unless override+outcome; LOST/NO_BID")
    lines.append("               require an outcome record; AWARDED spawns exactly")
    lines.append("               one Contract (idempotent).")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_transition_table())
