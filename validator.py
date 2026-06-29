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
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Date helpers (business-day math for the MWBE deadline cascade)
# ---------------------------------------------------------------------------

def parse_date(value):
    """Parse an ISO 'YYYY-MM-DD' date string; return a date or None."""
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def add_business_days(start, n):
    """Return the date `n` business days (Mon–Fri) after `start`.

    Weekends only; this implementation does not encode public holidays, so a
    deadline that lands the day before a holiday is reported one business day
    optimistic. Treat results near a holiday as advisory."""
    d = start
    added = 0
    while added < n:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:  # 0=Mon .. 4=Fri
            added += 1
    return d


def business_days_between(a, b):
    """Count business days strictly after `a` up to and including `b`.
    Negative if b precedes a."""
    if b < a:
        return -business_days_between(b, a)
    d, count = a, 0
    while d < b:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return count

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
MWBE = "source-mwbe-5nycrr-pass-fail.md"

# VendRep questionnaire forms → their golden-copy source file. The
# material-change obligation and the certification-under-penalties-of-perjury
# clause appear verbatim in all four, so the citation is grounded in whichever
# form the questionnaire actually is.
VENDREP_FORMS = {
    "AC 3290-S": "source-vendrep-ac3290s-forprofit-nonconstruction.md",
    "AC 3291-S": "source-vendrep-ac3291s-nonprofit-nonconstruction.md",
    "AC 3292-S": "source-vendrep-ac3292s-forprofit-construction-cca2.md",
    "AC 3293-S": "source-vendrep-ac3293s-nonprofit-construction.md",
}
DEFAULT_VENDREP_FILE = VENDREP_FORMS["AC 3290-S"]

# Material-change event keys (RISK-MAP RM-3) → human label. Any one of these,
# unremedied by a re-certification, is a hard-block.
MATERIAL_CHANGES = [
    ("ownership_change", "ownership change"),
    ("new_judgment_or_lien", "new judgment or lien"),
    ("tax_status_change", "tax-status change"),
    ("bankruptcy", "bankruptcy"),
    ("debarment_or_suspension", "debarment or suspension"),
    ("key_personnel_integrity_event", "key-personnel integrity event"),
]


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

    # ------------------------------------------------------------------ RM-3
    def check_vendrep(self, vendrep):
        """RM-3 — VendRep stale-certification monitor.

        Flags any material change to the Business Entity's responses (which the
        questionnaire obligates the vendor to update / re-certify) and confirms
        the questionnaire carries a signed certification by someone authorized
        to bind the entity, made under penalties of perjury.
        """
        findings = []
        form = vendrep.get("form", "AC 3290-S")
        src = VENDREP_FORMS.get(form, DEFAULT_VENDREP_FILE)

        update_quote = ("are under an obligation to update the information provided herein to "
                        "include any material changes to the Business Entity's responses at the "
                        "time of bid/proposal submission through the contract award notification, "
                        "and may be required to update the information at the request of the New "
                        "York State government entities or OSC prior to the award and/or approval "
                        "of a contract, or during the term of the contract.")
        cert_quote = "the undersigned certifies under penalties of perjury that they:"

        # -- Signed certification by an authorized signatory ----------------
        cert = vendrep.get("certification") or {}
        signed = bool(cert.get("signed"))
        authorized = bool(cert.get("signatory_authorized_to_bind"))
        cert_ok = signed and authorized
        evidence = {"signed": signed, "signatory_authorized_to_bind": authorized,
                    "filing_method": vendrep.get("filing_method")}
        # Notarization is accepted as evidence of a valid paper signature where
        # supplied; the captured authority for these forms requires an
        # authorized owner/official certification under penalties of perjury,
        # which is what the hard-block is grounded in (we do not invent a
        # notarization rule the source does not state).
        if "notarized" in cert:
            evidence["notarized"] = bool(cert.get("notarized"))
        findings.append(self._f(
            "RM-3", src, cert_quote, FAIL,
            "Questionnaire MUST be certified (signed) by an owner/official authorized to "
            "bind the Business Entity, under penalties of perjury.",
            cert_ok, evidence=evidence))

        # -- Material changes → re-certification required -------------------
        recertified = bool(vendrep.get("recertified_since_change"))
        changes = vendrep.get("material_changes") or {}
        detected = [(k, label) for k, label in MATERIAL_CHANGES if changes.get(k)]

        if not detected:
            findings.append(self._f(
                "RM-3", src, update_quote, INFO,
                "No material change reported. The vendor remains obligated to update / "
                "re-certify if a material change occurs during the contract term.",
                True, evidence={"material_changes_detected": []}))
        else:
            for key, label in detected:
                findings.append(self._f(
                    "RM-3", src, update_quote, FAIL,
                    "Material change detected ({}). The questionnaire MUST be updated / "
                    "re-certified to reflect it{}.".format(
                        label, "" if not recertified else " — re-certification recorded"),
                    recertified,
                    evidence={"material_change": key, "recertified_since_change": recertified}))
        return Result("vendrep_questionnaire", findings)

    # ------------------------------------------------------------------ RM-4
    def check_bid(self, bid):
        """RM-4 — MWBE deadline-cascade tracker + the §143.3(c) EEO hard-block."""
        findings = []
        today = parse_date(bid.get("today")) or datetime.date.today()

        q_up = ("in no case more than ten (10) business days after the contractor receives "
                "notice from a State agency that the contractor has submitted a low bid")
        q_def = ("issue a written notice of acceptance or deficiency regarding the utilization "
                 "plan no later than twenty (20) days after receipt of the utilization plan")
        q_remedy = ("a contractor must provide a State agency with a written remedy in response "
                    "to a notice of deficiency within seven (7) business days of its receipt")
        q_waiver = ("the State agency may notify the contractor and request the contractor to "
                    "submit a waiver form within five (5) business days")
        q_eeo = ("A contractor's failure to submit an EEO policy statement and, where required "
                 "by the contracting agency, staffing plan or total work force data shall result "
                 "in the rejection of the contractor's bid or proposal")
        q_carveout = ("the failure to submit a staffing plan where a contractor has a work force "
                      "of 10 employees or less")

        # -- Utilization plan: due 10 business days from low-bid notice ------
        low_bid = parse_date(bid.get("low_bid_notice_date"))
        up_submitted = parse_date(bid.get("utilization_plan_submitted_date"))
        if low_bid:
            up_due = add_business_days(low_bid, 10)
            findings.append(self._deadline_finding(
                "RM-4", MWBE, q_up, "Utilization plan", up_due, up_submitted, today,
                extra={"low_bid_notice_date": low_bid.isoformat()}))
        else:
            findings.append(self._f(
                "RM-4", MWBE, q_up, INFO,
                "No low-bid notice date provided; the 10-business-day utilization-plan clock "
                "cannot be started.", True, evidence={}))

        # -- Agency deficiency notice: within 20 days of receiving the UP ----
        # Agency-side action; tracked informationally and used to start the
        # remedy clock when present.
        deficiency = parse_date(bid.get("deficiency_notice_date"))
        up_received = parse_date(bid.get("utilization_plan_received_date")) or up_submitted
        if deficiency and up_received:
            within20 = deficiency <= up_received + datetime.timedelta(days=20)
            findings.append(self._f(
                "RM-4", MWBE, q_def, INFO,
                "Agency deficiency/acceptance notice issued {} (the agency has 20 days from "
                "receipt of the utilization plan).".format(
                    "within the 20-day window" if within20 else "outside the 20-day window"),
                True, evidence={"deficiency_notice_date": deficiency.isoformat(),
                                "within_20_days": within20}))

        # -- Written remedy: due 7 business days from the deficiency notice --
        if deficiency:
            remedy_due = add_business_days(deficiency, 7)
            remedy_submitted = parse_date(bid.get("written_remedy_submitted_date"))
            findings.append(self._deadline_finding(
                "RM-4", MWBE, q_remedy, "Written remedy to deficiency", remedy_due,
                remedy_submitted, today,
                extra={"deficiency_notice_date": deficiency.isoformat()}))

            # -- Waiver form: 5 business days if requested ------------------
            if bid.get("waiver_requested"):
                waiver_due = add_business_days(deficiency, 5)
                waiver_submitted = parse_date(bid.get("waiver_form_submitted_date"))
                findings.append(self._deadline_finding(
                    "RM-4", MWBE, q_waiver, "Waiver form", waiver_due,
                    waiver_submitted, today, extra={"waiver_requested": True}))

        # -- §143.3(c) EEO policy statement hard-block ----------------------
        eeo_ok = bool(bid.get("eeo_policy_statement_submitted"))
        justified = bool(bid.get("eeo_justification_provided")) or bool(bid.get("eeo_commitment_to_submit"))
        if eeo_ok:
            findings.append(self._f(
                "RM-4", MWBE, q_eeo, FAIL,
                "EEO policy statement submitted (its absence would mandate bid rejection under "
                "§143.3(c)).", True, evidence={"eeo_policy_statement_submitted": True}))
        elif justified:
            findings.append(self._f(
                "RM-4", MWBE, q_eeo, WARN,
                "EEO policy statement NOT submitted, but a written justification / commitment to "
                "submit is recorded (§143.3(c) exception). Confirm the agency accepts it.",
                False, evidence={"eeo_policy_statement_submitted": False, "justification": True}))
        else:
            findings.append(self._f(
                "RM-4", MWBE, q_eeo, FAIL,
                "EEO policy statement NOT submitted and no written justification/commitment "
                "provided — §143.3(c) mandates rejection of the bid.",
                False, evidence={"eeo_policy_statement_submitted": False, "justification": False}))

        # -- Staffing plan (where required) with the 10-employee carve-out --
        if bid.get("staffing_plan_required"):
            staffing_ok = bool(bid.get("staffing_plan_submitted"))
            workforce = bid.get("workforce_employee_count")
            carveout = isinstance(workforce, (int, float)) and workforce <= 10
            if staffing_ok:
                findings.append(self._f(
                    "RM-4", MWBE, q_carveout, FAIL,
                    "Staffing plan submitted as required.", True,
                    evidence={"staffing_plan_submitted": True}))
            elif carveout or justified:
                findings.append(self._f(
                    "RM-4", MWBE, q_carveout, WARN,
                    "Staffing plan NOT submitted, but the 10-employees-or-fewer carve-out "
                    "(or a written justification) applies under §143.3(c).",
                    False, evidence={"staffing_plan_submitted": False,
                                     "workforce_employee_count": workforce, "carveout": carveout}))
            else:
                findings.append(self._f(
                    "RM-4", MWBE, q_carveout, FAIL,
                    "Staffing plan required but NOT submitted, and neither the 10-employee "
                    "carve-out nor a written justification applies — rejection risk under §143.3(c).",
                    False, evidence={"staffing_plan_submitted": False,
                                     "workforce_employee_count": workforce}))
        return Result("mwbe_bid", findings)

    # Warn when a still-open deadline is this close (business days) to its cliff.
    WARN_WINDOW_BD = 3

    def _deadline_finding(self, rule_id, src, quote, label, due, submitted, today, extra=None):
        """Build a FAIL-severity deadline finding whose passed/severity reflect
        whether the deadline was met, is approaching (WARN), or is overdue."""
        ev = {"deadline": label, "due_date": due.isoformat()}
        if extra:
            ev.update(extra)
        if submitted is not None:
            on_time = submitted <= due
            ev.update({"submitted_date": submitted.isoformat(), "on_time": on_time})
            desc = "{} {} (submitted {}, due {}).".format(
                label, "submitted ON TIME" if on_time else "submitted LATE",
                submitted.isoformat(), due.isoformat())
            return self._f(rule_id, src, quote, FAIL, desc, on_time, evidence=ev)
        # Not yet submitted.
        if today > due:
            ev["status"] = "OVERDUE"
            return self._f(rule_id, src, quote, FAIL,
                           "{} is OVERDUE (was due {}; today {}).".format(
                               label, due.isoformat(), today.isoformat()),
                           False, evidence=ev)
        bd_left = business_days_between(today, due)
        ev["business_days_remaining"] = bd_left
        if bd_left <= self.WARN_WINDOW_BD:
            return self._f(rule_id, src, quote, WARN,
                           "{} due in {} business day(s) (by {}) — approaching cliff.".format(
                               label, bd_left, due.isoformat()),
                           False, evidence=ev)
        return self._f(rule_id, src, quote, INFO,
                       "{} not yet due ({} business days out, by {}).".format(
                           label, bd_left, due.isoformat()),
                       True, evidence=ev)


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
    ap.add_argument("--vendrep", metavar="FILE.json",
                    help="run RM-3 VendRep stale-certification monitor")
    ap.add_argument("--bid", metavar="FILE.json",
                    help="run RM-4 MWBE deadline-cascade tracker")
    ap.add_argument("--freshness", metavar="REPORT.json",
                    help="consult a freshness-checker JSON report and annotate findings "
                         "whose grounding source is not OK")
    ap.add_argument("--json", action="store_true", help="emit JSON only (no human report)")
    args = ap.parse_args(argv)

    if not any([args.invoice, args.budget, args.vendrep, args.bid]):
        ap.error("specify at least one of --invoice [FILE], --budget FILE, "
                 "--vendrep FILE, --bid FILE")

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

    if args.vendrep:
        if not os.path.isfile(args.vendrep):
            print("ERROR: vendrep file not found: {}".format(args.vendrep), file=sys.stderr)
            return 2
        results.append(validator.check_vendrep(_load_json(args.vendrep)))

    if args.bid:
        if not os.path.isfile(args.bid):
            print("ERROR: bid file not found: {}".format(args.bid), file=sys.stderr)
            return 2
        results.append(validator.check_bid(_load_json(args.bid)))

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
