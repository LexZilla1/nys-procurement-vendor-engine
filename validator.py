#!/usr/bin/env python3
"""
Phase 2, Step 3 — NYS Procurement Vendor: Validation Engine Core.

A rule-agnostic validator that checks a vendor document against New York State's
procurement / payment rules and returns a structured result. Every finding is
grounded in a VERBATIM quote pulled from a golden-copy source file — the engine
never paraphrases or invents a rule, and it refuses to emit a citation it cannot
find, character-for-character, in the named source (see CitationError / the
citation-integrity test in test_validator.py).

Principles enforced (PHASE2-BUILD-SPEC §1, §3, §8):
  * Golden copy is the ONLY source of rule truth.
  * Every finding carries a verbatim citation_quote from its named source file.
  * MUST items hard-block (FAIL); SHOULD items advise (WARN). The source file's
    own "must"/"should" wording decides which — the engine never inverts it.
  * Information only — no legal/financial advice, no auto-submission, no logins.

Implemented validators:
  * RM-5 — Invoice pre-flight: proper-invoice required fields (XII.4.F) +
           the §109 vendor certificate (source-stf-109-vendor-certificate.md).
  * RM-1 — Budget-variance pre-check (source-xi-4-b-grant-budget-variance.md).

CLI:
  python3 validator.py --invoice [FILE.json]   # defaults to sample-invoice-pass.json
  python3 validator.py --budget  FILE.json
  python3 validator.py --invoice FILE.json --json     # machine-readable only
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Severity / status vocabulary
# ---------------------------------------------------------------------------

FAIL = "FAIL"    # a MUST item is missing/incorrect → mandatory-rejection risk
WARN = "WARN"    # a SHOULD item is missing → advisory
INFO = "INFO"    # context the user should know; not pass/fail
PASS = "PASS"    # the checked item conforms

STATUS_PASS = "PASS"
STATUS_WARN = "PASS-WITH-WARNINGS"
STATUS_FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Golden copy loader + the citation-integrity gate
# ---------------------------------------------------------------------------

class CitationError(Exception):
    """Raised when the engine tries to emit a quote that is NOT verbatim in its
    named source file. This is a build-failing condition: it means the engine
    paraphrased instead of quoting."""


class GoldenCopy:
    """Loads the verbatim STATE TEXT bodies and gates every citation."""

    H_STATE_TEXT = "## STATE TEXT (verbatim)"
    H_CITATIONS = "## CITATIONS"
    H_AGENCY_GUIDANCE = "## AGENCY GUIDANCE"

    def __init__(self, sources_dir=None):
        self.sources_dir = sources_dir or os.path.join(HERE, "golden-copy", "sources")
        if not os.path.isdir(self.sources_dir):
            alt = os.path.join("/mnt/project", "golden-copy", "sources")
            if os.path.isdir(alt):
                self.sources_dir = alt
        self._raw = {}     # file -> full file text
        self._body = {}    # file -> STATE TEXT body
        self._load()

    def _load(self):
        for name in os.listdir(self.sources_dir):
            if not (name.startswith("source-") and name.endswith(".md")):
                continue
            with open(os.path.join(self.sources_dir, name), "r", encoding="utf-8") as fh:
                text = fh.read()
            self._raw[name] = text
            self._body[name] = self._extract_body(text)

    def _extract_body(self, text):
        lines = text.split("\n")
        idx_state = idx_cit = idx_agency = None
        for i, line in enumerate(lines):
            if idx_state is None and line.startswith(self.H_STATE_TEXT):
                idx_state = i
            elif idx_cit is None and line.startswith(self.H_CITATIONS):
                idx_cit = i
            elif idx_agency is None and line.startswith(self.H_AGENCY_GUIDANCE):
                idx_agency = i
        if idx_state is None:
            return ""
        end = idx_cit if idx_cit is not None else len(lines)
        if idx_agency is not None and idx_state < idx_agency < end:
            end = idx_agency
        return "\n".join(lines[idx_state + 1:end]).strip()

    def has(self, source_file):
        return source_file in self._raw

    def body(self, source_file):
        return self._body.get(source_file, "")

    def cite(self, source_file, quote):
        """Return `quote` only if it is a verbatim substring of the source
        file's STATE TEXT body. Otherwise raise CitationError. This is the
        single choke-point that guarantees no finding can carry a paraphrase."""
        if source_file not in self._raw:
            raise CitationError("unknown source file: {}".format(source_file))
        if not quote or quote not in self._body[source_file]:
            raise CitationError(
                "quote not found verbatim in {} STATE TEXT body: {!r}".format(
                    source_file, (quote or "")[:80]))
        return quote


# ---------------------------------------------------------------------------
# Finding + Result
# ---------------------------------------------------------------------------

class Finding:
    """One structured check result (PHASE2-BUILD-SPEC §3 schema)."""

    def __init__(self, rule_id, source_file, citation_quote, severity,
                 check_description, passed, evidence=None):
        self.rule_id = rule_id
        self.source_file = source_file
        self.citation_quote = citation_quote
        self.severity = severity
        self.check_description = check_description
        self.passed = passed
        self.evidence = evidence or {}
        self.freshness_status = None  # filled in if a freshness report is consulted

    def to_dict(self):
        d = {
            "rule_id": self.rule_id,
            "source_file": self.source_file,
            "citation_quote": self.citation_quote,
            "severity": self.severity,
            "check_description": self.check_description,
            "passed": self.passed,
            "evidence": self.evidence,
        }
        if self.freshness_status:
            d["freshness_status"] = self.freshness_status
        return d


class Result:
    def __init__(self, document_type, findings):
        self.document_type = document_type
        self.findings = findings

    @property
    def overall_status(self):
        if any(f.severity == FAIL and not f.passed for f in self.findings):
            return STATUS_FAIL
        if any(f.severity == WARN and not f.passed for f in self.findings):
            return STATUS_WARN
        return STATUS_PASS

    def to_dict(self):
        return {
            "document_type": self.document_type,
            "overall_status": self.overall_status,
            "findings": [f.to_dict() for f in self.findings],
            "disclaimer": (
                "Information and document-validation only. This output describes "
                "what a rule requires and whether the document conforms. It is not "
                "legal or financial advice, and performs no submission on your behalf."
            ),
        }


# ---------------------------------------------------------------------------
# The validator
# ---------------------------------------------------------------------------

# Proper-invoice MUST fields (XII.4.F). doc_key -> human label.
PROPER_INVOICE_MUST = [
    ("vendor_name", "Vendor name"),
    ("agency_name", "Name of NYS Agency that ordered the goods or services"),
    ("description", "Description of goods or services"),
    ("quantity", "Quantity of goods, property, or services delivered or rendered"),
    ("amount", "Amount requested"),
]
# Proper-invoice SHOULD fields (XII.4.F). doc_key -> human label.
PROPER_INVOICE_SHOULD = [
    ("nys_vendor_id", "NYS Vendor ID number"),
    ("invoice_date", "Invoice Date"),
    ("invoice_number", "Unique invoice number"),
    ("payment_terms", "Payment terms, if other than Net 30"),
]

XII4F = "source-xii-4-f-proper-invoice.md"
STF109 = "source-stf-109-vendor-certificate.md"
XI4B = "source-xi-4-b-grant-budget-variance.md"


def _present(value):
    """A field counts as present when it is non-empty / non-None."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True  # numbers, bools (0 is a meaningful amount only if intended)


class Validator:
    def __init__(self, golden=None, freshness_report=None):
        self.gc = golden or GoldenCopy()
        self.freshness = self._load_freshness(freshness_report)

    # -- optional freshness guardrail (PHASE2-BUILD-SPEC §3 Step 2 / §4) ----
    def _load_freshness(self, path):
        if not path or not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return {r["file"]: r.get("status") for r in data.get("rules", [])}
        except Exception:
            return {}

    def _annotate_freshness(self, finding):
        status = self.freshness.get(finding.source_file)
        if status and status != "OK":
            finding.freshness_status = (
                "{} — source pending re-verification per methodology manual; "
                "do not treat as authoritative until re-confirmed".format(status))
        return finding

    def _f(self, *args, **kwargs):
        """Build a Finding, gating its citation, and annotate freshness."""
        rule_id, source_file, quote = args[0], args[1], args[2]
        verified = self.gc.cite(source_file, quote)
        finding = Finding(rule_id, source_file, verified, *args[3:], **kwargs)
        return self._annotate_freshness(finding)

    # ------------------------------------------------------------------ RM-5
    def check_invoice(self, invoice):
        """RM-5 — Invoice pre-flight: proper-invoice fields + §109 certificate."""
        findings = []

        # -- MUST: proper-invoice required fields (XII.4.F) -----------------
        must_quote = ("When an invoice does not contain the above information, "
                      "agencies must reject the invoice.")
        for key, label in PROPER_INVOICE_MUST:
            ok = _present(invoice.get(key))
            findings.append(self._f(
                "RM-5", XII4F, must_quote, FAIL,
                "Proper invoice MUST contain: {}.".format(label),
                ok, evidence={"field": key, "present": ok}))

        # PO number is required only "if applicable" — conditional MUST.
        po_quote = ("Purchase order (PO) number, if applicable, as provided by "
                    "ordering agency.")
        po_applicable = bool(invoice.get("po_applicable", False))
        if po_applicable:
            ok = _present(invoice.get("po_number"))
            findings.append(self._f(
                "RM-5", XII4F, po_quote, FAIL,
                "A PO number applies to this invoice and MUST be provided.",
                ok, evidence={"field": "po_number", "po_applicable": True, "present": ok}))
        else:
            findings.append(self._f(
                "RM-5", XII4F, po_quote, INFO,
                "PO number is required only if a PO applies; none indicated here.",
                True, evidence={"field": "po_number", "po_applicable": False}))

        # -- SHOULD: proper-invoice advisory fields (XII.4.F) ---------------
        should_quote = "In addition, an invoice **should** contain the following information:"
        for key, label in PROPER_INVOICE_SHOULD:
            ok = _present(invoice.get(key))
            findings.append(self._f(
                "RM-5", XII4F, should_quote, WARN,
                "Proper invoice SHOULD contain: {}.".format(label),
                ok, evidence={"field": key, "present": ok}))

        # -- §109 vendor certificate ----------------------------------------
        findings.append(self._check_109(invoice))
        return Result("invoice", findings)

    def _check_109(self, invoice):
        cert_quote = ("Each statement of accounts must contain a certificate by or on "
                      "behalf of the party presenting the same to the effect that it is "
                      "just, true and correct, that no part thereof has been paid, except "
                      "as stated therein, and that the balance therein stated is actually "
                      "due and owing.")
        exception_quote = ("Notwithstanding the provisions of subdivision one of this "
                           "section the comptroller may authorize payment based on any "
                           "invoice used in the vendor's normal course of business without "
                           "requiring certification.")

        valid, why = self._certificate_valid(invoice)
        if valid:
            return self._f(
                "RM-5", STF109, cert_quote, FAIL,
                "Invoice carries the §109 certificate (just, true and correct / "
                "not previously paid / actually due and owing) with a signature.",
                True, evidence={"certificate": "present", "detail": why})

        # Missing/invalid certificate. §109(1-a) is an exception, not a license
        # to skip: only soften to a WARN when the invoice explicitly invokes the
        # normal-course-invoice carve-out AND certification is not required.
        invokes_exception = (bool(invoice.get("normal_course_invoice"))
                             and not invoice.get("certification_required", True))
        if invokes_exception:
            return self._f(
                "RM-5", STF109, exception_quote, WARN,
                "No §109 certificate, but the invoice invokes the normal-course-invoice "
                "exception (§109(1-a)); the Comptroller MAY accept it without separate "
                "certification. Confirm the agency/contract does not require one.",
                False, evidence={"certificate": "absent", "exception_invoked": True, "detail": why})

        return self._f(
            "RM-5", STF109, cert_quote, FAIL,
            "Invoice is missing a valid §109 certificate (must attest the claim is "
            "just, true and correct; not previously paid; actually due and owing) and "
            "the normal-course-invoice exception was not validly invoked.",
            False, evidence={"certificate": "absent_or_invalid", "detail": why})

    @staticmethod
    def _certificate_valid(invoice):
        """A §109 certificate is valid when it attests all three elements AND is
        signed (ink signature or valid e-signature). Accepts a certification
        object, a plain attestation string, or a signed AC 3253-S flag."""
        cert = invoice.get("certification")
        statement = ""
        signed = False
        if isinstance(cert, dict):
            statement = (cert.get("statement") or "").lower()
            signed = bool(cert.get("signed")) or _present(cert.get("signature")) \
                or bool(cert.get("electronic_signature"))
        elif isinstance(cert, str):
            statement = cert.lower()
            signed = bool(invoice.get("signed")) or _present(invoice.get("signature"))

        if invoice.get("ac3253s", {}).get("signed"):
            statement = statement or "just, true and correct due and owing not been paid"
            signed = True

        has_jtc = "just, true and correct" in statement
        has_due = "due and owing" in statement
        has_unpaid = any(p in statement for p in
                         ("no part", "not been paid", "has been paid", "previously paid",
                          "not previously paid"))
        if not (has_jtc and has_due and has_unpaid):
            return (False, "attestation incomplete (need just/true/correct + unpaid + due and owing)")
        if not signed:
            return (False, "attestation present but not signed (ink or valid e-signature required)")
        return (True, "complete attestation with signature")

    # ------------------------------------------------------------------ RM-1
    def check_budget(self, budget):
        """RM-1 — Budget-variance pre-check.

        Input: total_contract_value plus either an explicit transfer amount, or
        approved/proposed budgets per category from which the moved amount is
        derived. Flags a transfer at/above the applicable OSC threshold.
        """
        findings = []
        trigger_quote = ("Any proposed modification to a contract that will result in a "
                         "transfer of funds among program activities or budget cost "
                         "categories, but does not affect the amount, consideration, scope "
                         "or other terms of such contract, must be submitted to OSC for "
                         "approval when:")
        q10 = ("The amount of the modification is equal to or greater than ten percent of "
               "the total value of the contract for contracts of less than five million dollars.")
        q5 = ("The amount of the modification is equal to or greater than five percent of "
              "the total value of the contract for contracts of more than five million dollars.")
        amend_quote = ("Any proposed increase in contract amount, change in contract term, "
                       "or change in scope of work not previously approved by OSC requires a "
                       "contract amendment, and may require either a Contract Reporter "
                       "Exemption, or a new procurement.")

        total = float(budget.get("total_contract_value", 0) or 0)
        moved = self._moved_amount(budget)

        # An amount/scope/term change is a different, amendment-track event — surface,
        # don't conflate with a budget-category transfer.
        if budget.get("changes_amount_scope_or_term"):
            findings.append(self._f(
                "RM-1", XI4B, amend_quote, INFO,
                "This change affects amount/scope/term — that is an amendment-track event "
                "(contract amendment, possibly a Contract Reporter Exemption or new "
                "procurement), distinct from the budget-category transfer threshold below.",
                True, evidence={"changes_amount_scope_or_term": True}))

        if total <= 0:
            findings.append(self._f(
                "RM-1", XI4B, trigger_quote, INFO,
                "No total contract value provided; cannot evaluate the variance threshold.",
                True, evidence={"total_contract_value": total}))
            return Result("budget", findings)

        # Threshold: 10% for contracts of $5,000,000 or less; 5% for contracts
        # over $5,000,000 (corroborated by the Contract for Grants Face Page).
        if total > 5_000_000:
            threshold_pct, threshold_quote, basis = 5.0, q5, "more than $5,000,000"
        else:
            threshold_pct, threshold_quote, basis = 10.0, q10, "$5,000,000 or less"

        pct = (moved / total) * 100.0 if total else 0.0
        crosses = pct >= threshold_pct

        # The trigger sentence (MUST submit to OSC) grounds the gate.
        findings.append(self._f(
            "RM-1", XI4B, trigger_quote, FAIL,
            "A budget-category transfer at/above the OSC threshold MUST be submitted to "
            "OSC for approval (and will halt payment until approved).",
            not crosses,
            evidence={"moved_amount": moved, "total_contract_value": total,
                      "moved_pct": round(pct, 4)}))
        # The specific threshold that applied (names which one — per acceptance).
        findings.append(self._f(
            "RM-1", XI4B, threshold_quote, FAIL if crosses else INFO,
            "Applicable threshold: {:.0f}% (contract is {}). Moved {:.2f}% of total "
            "value.{}".format(threshold_pct, basis, pct,
                              " AT/ABOVE threshold → OSC re-approval triggered."
                              if crosses else " Below threshold."),
            not crosses,
            evidence={"threshold_pct": threshold_pct, "basis": basis,
                      "moved_pct": round(pct, 4), "crosses": crosses}))
        return Result("budget", findings)

    @staticmethod
    def _moved_amount(budget):
        """Determine the amount moved among categories.

        Priority: an explicit `transfer_amount`; else the larger of total
        increases / total decreases derived from approved vs proposed per-category
        budgets (a transfer of X out of one category into another moves X)."""
        if budget.get("transfer_amount") is not None:
            return abs(float(budget["transfer_amount"]))
        approved = budget.get("approved_budget") or {}
        proposed = budget.get("proposed_budget") or {}
        if not approved or not proposed:
            return 0.0
        increases = decreases = 0.0
        for cat in set(approved) | set(proposed):
            delta = float(proposed.get(cat, 0) or 0) - float(approved.get(cat, 0) or 0)
            if delta > 0:
                increases += delta
            else:
                decreases += -delta
        # A pure reallocation moves the same amount in and out; use the larger
        # leg so a lopsided edit isn't undercounted.
        return max(increases, decreases)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# How a finding's severity reads when the check is NOT met, and the rule's
# nature (what the State's own "must"/"should" wording makes it).
UNMET_MARK = {FAIL: "✗ FAIL", WARN: "▲ WARN", INFO: "• INFO"}
BASIS = {FAIL: "MUST (mandatory — hard-block if unmet)",
         WARN: "SHOULD (advisory)",
         INFO: "informational"}


def render_human(result):
    lines = []
    lines.append("=" * 78)
    lines.append("NYS Procurement Vendor — Validation Result ({})".format(result.document_type))
    lines.append("=" * 78)
    lines.append("OVERALL: {}".format(result.overall_status))
    lines.append("")
    for f in result.findings:
        # Leading mark reflects the actual OUTCOME; basis records the rule nature.
        mark = "✓ met " if f.passed else UNMET_MARK.get(f.severity, f.severity)
        lines.append("[{}] [{}] {}".format(mark, f.rule_id, f.check_description))
        lines.append('      basis  : {}'.format(BASIS.get(f.severity, f.severity)))
        lines.append('      source : {}'.format(f.source_file))
        lines.append('      cite   : "{}"'.format(f.citation_quote))
        if f.freshness_status:
            lines.append('      fresh  : {}'.format(f.freshness_status))
    lines.append("")
    lines.append("-" * 78)
    counts = {}
    for f in result.findings:
        if not f.passed:
            counts[f.severity] = counts.get(f.severity, 0) + 1
    lines.append("Unmet: FAIL={} (mandatory) WARN={} (advisory)".format(
        counts.get(FAIL, 0), counts.get(WARN, 0)))
    lines.append(result.to_dict()["disclaimer"])
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYS Procurement Vendor validation engine")
    ap.add_argument("--invoice", nargs="?", const="__default__", metavar="FILE.json",
                    help="run RM-5 invoice pre-flight (defaults to sample-invoice-pass.json)")
    ap.add_argument("--budget", metavar="FILE.json",
                    help="run RM-1 budget-variance pre-check")
    ap.add_argument("--freshness", metavar="REPORT.json",
                    help="consult a freshness-checker JSON report and annotate findings "
                         "whose grounding source is not OK")
    ap.add_argument("--json", action="store_true", help="emit JSON only (no human report)")
    args = ap.parse_args(argv)

    if not args.invoice and not args.budget:
        ap.error("specify --invoice [FILE] and/or --budget FILE")

    validator = Validator(freshness_report=args.freshness)
    results = []

    if args.invoice:
        path = (os.path.join(HERE, "sample-invoice-pass.json")
                if args.invoice == "__default__" else args.invoice)
        if not os.path.isfile(path):
            print("ERROR: invoice file not found: {}".format(path), file=sys.stderr)
            return 2
        results.append(validator.check_invoice(_load_json(path)))

    if args.budget:
        if not os.path.isfile(args.budget):
            print("ERROR: budget file not found: {}".format(args.budget), file=sys.stderr)
            return 2
        results.append(validator.check_budget(_load_json(args.budget)))

    payload = [r.to_dict() for r in results]
    if not args.json:
        for r in results:
            print(render_human(r))
            print()
    print(json.dumps(payload if len(payload) > 1 else payload[0],
                     ensure_ascii=False, indent=2))

    # Exit 1 if any document FAILs (a MUST item unmet); else 0.
    return 1 if any(r.overall_status == STATUS_FAIL for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
