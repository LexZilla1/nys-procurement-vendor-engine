#!/usr/bin/env python3
"""
engine/invoice_status.py — invoice status machine + §109 semantic-concept
pre-flight (PR 2b).

Two pieces:

  1. preflight_109_semantic() — a SEMANTIC-CONCEPT variant of the §109 vendor
     certificate check that goes BEYOND the pre-existing field/signature check in
     validator.check_invoice / _check_109. §109 requires the statement of
     accounts to attest THREE distinct concepts, verbatim:
       - "just, true and correct",
       - "no part thereof has been paid" (not previously paid),
       - "the balance therein stated is actually due and owing".
     This check asks whether each of those three attestation CONCEPTS is present
     (not merely whether a certificate field/signature exists) and returns a
     categorical PREFLIGHT verdict — never a numeric score.

  2. InvoiceStatusMachine — an explicit invoice status transition table whose
     entry gate is DRAFT -> PREFLIGHT_PASS / PREFLIGHT_FLAG, driven by the §109
     semantic pre-flight. Illegal moves raise, mirroring
     engine/state_machine.TenderStateMachine.

No numeric scores; no tier-3 data. The §109 verdict carries a verbatim golden
Citation to source-stf-109-vendor-certificate.md.
"""

from engine.citation import Citation, GOLDEN_RULE

STF109 = "source-stf-109-vendor-certificate.md"
STF109_CAPTURED = "2026-06-28"

# The three §109 attestation concepts, each keyed to a verbatim golden anchor.
# (Substrings of the §109 STATE TEXT body; see test_invoice_clock.py.)
CONCEPT_ANCHORS = {
    "just_true_correct": "just, true and correct",
    "not_previously_paid": "no part thereof has been paid",
    "actually_due_owing": "the balance therein stated is actually due and owing",
}
# Invoice fields that assert each concept.
CONCEPT_FIELDS = {
    "just_true_correct": "cert_just_true_correct",
    "not_previously_paid": "cert_not_previously_paid",
    "actually_due_owing": "cert_actually_due_owing",
}

# ---------------------------------------------------------------------------
# Categorical pre-flight verdicts (strings — no scores)
# ---------------------------------------------------------------------------

PREFLIGHT_PASS = "PREFLIGHT_PASS"
PREFLIGHT_FLAG = "PREFLIGHT_FLAG"
PREFLIGHT_VERDICTS = (PREFLIGHT_PASS, PREFLIGHT_FLAG)

# ---------------------------------------------------------------------------
# Invoice status machine
# ---------------------------------------------------------------------------

DRAFT = "DRAFT"
STATUSES = (DRAFT, PREFLIGHT_PASS, PREFLIGHT_FLAG)

# Explicit transition table. The gate is DRAFT -> PREFLIGHT_PASS / PREFLIGHT_FLAG.
# A flagged invoice can be corrected back to DRAFT and re-run; a passed invoice
# can regress to FLAG if a later check fails. Any move not here raises.
TRANSITIONS = {
    DRAFT: {PREFLIGHT_PASS, PREFLIGHT_FLAG},
    PREFLIGHT_FLAG: {DRAFT, PREFLIGHT_PASS},
    PREFLIGHT_PASS: {PREFLIGHT_FLAG},
}


class IllegalInvoiceTransition(Exception):
    """Raised when a requested invoice status transition is not permitted."""


def _cert_citation():
    quote = ("Each statement of accounts must contain a certificate by or on "
             "behalf of the party presenting the same to the effect that it is "
             "just, true and correct, that no part thereof has been paid, except "
             "as stated therein, and that the balance therein stated is actually "
             "due and owing.")
    return Citation(source_id=STF109, source_type=GOLDEN_RULE,
                    locator="§ 109", quote=quote, captured_at=STF109_CAPTURED)


def preflight_109_semantic(invoice):
    """Semantic-concept §109 check. Returns a dict:
      {verdict, present, missing, citation}
    verdict is PREFLIGHT_PASS iff ALL three §109 attestation concepts are
    asserted, else PREFLIGHT_FLAG (categorical; never a score)."""
    present, missing = [], []
    for concept, field in CONCEPT_FIELDS.items():
        (present if bool(invoice.get(field)) else missing).append(concept)
    verdict = PREFLIGHT_PASS if not missing else PREFLIGHT_FLAG
    return {
        "verdict": verdict,
        "present": present,
        "missing": missing,
        "citation": _cert_citation().to_dict(),
    }


class InvoiceStatusMachine:
    """Owns one invoice's status + transition log. Entry gate DRAFT ->
    PREFLIGHT_PASS / PREFLIGHT_FLAG via the §109 semantic pre-flight."""

    def __init__(self, invoice_id, status=DRAFT):
        if status not in STATUSES:
            raise ValueError("invalid status %r" % status)
        self.invoice_id = invoice_id
        self.status = status
        self.log = []            # list of (from, to, reason)
        self.last_preflight = None

    def transition(self, to_status, reason=""):
        if to_status not in STATUSES:
            raise IllegalInvoiceTransition("unknown status %r" % to_status)
        if to_status not in TRANSITIONS.get(self.status, set()):
            raise IllegalInvoiceTransition(
                "illegal invoice transition %s -> %s" % (self.status, to_status))
        self.log.append((self.status, to_status, reason))
        self.status = to_status
        return self

    def run_preflight(self, invoice):
        """Run the §109 semantic pre-flight and take the DRAFT -> PREFLIGHT_*
        transition accordingly. Must be called from DRAFT (or PREFLIGHT_FLAG for
        a re-run). Returns the pre-flight result dict."""
        result = preflight_109_semantic(invoice)
        self.last_preflight = result
        self.transition(result["verdict"],
                        reason="§109 semantic pre-flight: %s" % result["verdict"])
        return result

    def to_dict(self):
        return {
            "invoice_id": self.invoice_id,
            "status": self.status,
            "last_preflight": self.last_preflight,
            "log": [{"from": f, "to": t, "reason": r} for f, t, r in self.log],
        }


def render_transition_table():
    lines = ["invoice status transition table (illegal moves raise):", ""]
    for src in STATUSES:
        dests = sorted(TRANSITIONS.get(src, set()))
        lines.append("  %-16s -> %s" % (src, ", ".join(dests) or "(terminal)"))
    lines.append("")
    lines.append("  gate: DRAFT -> PREFLIGHT_PASS / PREFLIGHT_FLAG via the §109")
    lines.append("        semantic-concept pre-flight (all three attestation")
    lines.append("        concepts present => PASS, else FLAG).")
    return "\n".join(lines)


if __name__ == "__main__":
    print(render_transition_table())
