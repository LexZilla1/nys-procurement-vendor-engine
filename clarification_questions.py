#!/usr/bin/env python3
"""
Step 4.5 — Clarification-Question Generator.

Given (a) the `question_submission` block extracted from a solicitation by the
Cap 1 reader and (b) the gap list from gap analysis (Cap 2), produce an EDITABLE
draft of factual, clarifying questions the vendor can review, edit, and send from
their OWN email.

Hard boundaries (per task):
  * The engine NEVER sends anything and NEVER contacts the agency. It returns
    editable text only.
  * Questions are factual/clarifying ONLY — they ask what a spec or criterion IS.
    They never propose scope changes or bid strategy.
  * Nothing here enters the golden copy. Every rule (contact, deadline, format,
    citation requirement) comes from the solicitation at runtime, verbatim.
  * No credentials, no scraping, no auto-send.

A draft is produced automatically ONLY when ALL of these hold:
  * question_submission is not null,
  * the question deadline is present, parseable, and has NOT passed, and
  * the gap list is non-empty.
Otherwise `generate()` returns a null draft with either a one-line `reason`
(no question window / deadline passed / no gaps found) or, when the block is
present but the deadline can't be confirmed, a `deadline_unverified` status that
asks the vendor to verify the window and offers on-demand generation via
`force=True`.

This module is pure Python (no `anthropic`/network dependency) so it runs and is
tested offline; it consumes the reader's already-parsed output.
"""

import argparse
import datetime
import json
import re
import sys

# Reasons a draft is NOT produced (one line each).
NO_WINDOW = "no question window"
DEADLINE_PASSED = "deadline passed"
NO_GAPS = "no gaps found"

# State 3 status (block present but the question deadline can't be confirmed).
DEADLINE_UNVERIFIED = "deadline_unverified"


def _verify_location(question_submission):
    """Where the vendor should look to confirm the question window is open:
    the question-submission source citation, plus a page if one is provided.
    Returns None if the solicitation stated no location."""
    sc = question_submission.get("source_citation")
    page = question_submission.get("page")
    if sc and page is not None:
        return "{} (p. {})".format(sc, page)
    if sc:
        return sc
    if page is not None:
        return "p. {}".format(page)
    return None

DISCLAIMER = ("This is an editable draft for the vendor to review, edit, and send from "
              "their own email. The engine does not send it and does not contact the agency.")


# ---------------------------------------------------------------------------
# Deadline parsing (tolerant of "as printed" formats)
# ---------------------------------------------------------------------------

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}
_MONTHS.update({m.lower()[:3]: i for m, i in _MONTHS.items()})

_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_MDY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b")
_MONTH_DAY_YEAR_RE = re.compile(r"\b([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")


def parse_deadline(text):
    """Best-effort parse of a printed deadline string to a date. Returns a date,
    or None if no date can be recognised (caller treats None as 'not proven
    passed' — unknown-safe: we do not suppress a draft on an unparseable date)."""
    if not text:
        return None
    if isinstance(text, datetime.date):
        return text
    s = str(text)
    m = _ISO_RE.search(s)
    if m:
        return _safe(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _MONTH_DAY_YEAR_RE.search(s)
    if m and m.group(1).lower() in _MONTHS:
        return _safe(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
    m = _MDY_RE.search(s)
    if m:
        yr = int(m.group(3))
        yr = yr + 2000 if yr < 100 else yr
        return _safe(yr, int(m.group(1)), int(m.group(2)))
    return None


def _safe(y, mo, d):
    try:
        return datetime.date(y, mo, d)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Gap-record field extraction (agnostic to which module produced the gap)
# ---------------------------------------------------------------------------

def _gap_label(gap):
    for k in ("requirement", "item", "requirement_name", "label", "name"):
        v = gap.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return "(unspecified requirement)"


def _gap_citation(gap):
    """The RFP citation (page/section) for a gap. Deliberately does NOT use a
    golden-copy 'citation' dict — that grounds STATE law, not the RFP location."""
    for k in ("rfp_citation", "source_citation", "rfp_section", "section"):
        v = gap.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    c = gap.get("citation")
    if isinstance(c, str) and c.strip():   # only if it's a plain string, not a golden dict
        return c.strip()
    page = gap.get("page")
    if isinstance(page, int):
        return "p. {}".format(page)
    return None


def _gap_ambiguity(gap):
    """The specific ambiguity the engine found (gap['gap']), verbatim. None if
    the gap record states no ambiguity — the caller then falls back to neutral
    phrasing rather than fabricating one."""
    v = gap.get("gap")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def generate(question_submission, gaps, run_date=None, force=False):
    """Return a result dict. When a draft is produced:
        {"draft": <text>, "reason": None, "questions": [...], "contact": ...,
         "deadline": ..., "format": ..., "citation_requirement": ...,
         "question_count": N, "disclaimer": ...}
    When not produced, one of:
        State 1 — {"draft": None, "reason": "no question window"}
        State 2 — {"draft": None, "reason": "deadline passed"}
        (original) {"draft": None, "reason": "no gaps found"}
        State 3 — {"draft": None, "status": "deadline_unverified", "message": ...,
                   "verify_location": ..., "can_generate_on_demand": True}

    `force=True` is the ONLY way to produce a draft in State 3 (deadline
    absent/unparseable). It never overrides State 1 or State 2.
    """
    run_date = run_date or datetime.date.today()

    # -- State 1 — no question-submission block (UNCHANGED; ignores force) ----
    if not question_submission:
        return {"draft": None, "reason": NO_WINDOW}

    # -- State 2 — deadline present, parseable, and PASSED (UNCHANGED; ignores
    #    force). Only suppress when we can PROVE the deadline has passed. -------
    deadline_raw = question_submission.get("deadline")
    deadline_date = parse_deadline(deadline_raw)
    if deadline_date is not None and deadline_date < run_date:
        return {"draft": None, "reason": DEADLINE_PASSED}

    gaps = gaps or []
    if not gaps:
        return {"draft": None, "reason": NO_GAPS}

    # -- State 3 — block present but deadline absent/unparseable → UNVERIFIED.
    #    No auto-draft: the vendor must confirm the window is open and opt in
    #    via force=True (which then falls through to the SAME draft builder). ---
    if deadline_date is None and not force:
        loc = _verify_location(question_submission)
        return {
            "draft": None,
            "status": DEADLINE_UNVERIFIED,
            "message": ("Couldn't confirm the question deadline. Verify the window is open "
                        "at: {}. If confirmed open, generate the draft.".format(
                            loc or "the solicitation's question-submission section")),
            "verify_location": loc,
            "can_generate_on_demand": True,
        }

    contact = question_submission.get("contact")
    fmt = question_submission.get("format")
    citation_req = question_submission.get("citation_requirement")
    source_citation = question_submission.get("source_citation")

    # -- Build the editable draft --------------------------------------------
    lines = []
    lines.append("To: {}".format(contact or "[designated contact not stated in the RFP — verify]"))
    lines.append("Subject: Bidder clarification questions")
    if deadline_raw:
        lines.append("Questions due: {}".format(deadline_raw))
    if fmt:
        lines.append("Submit via: {}".format(fmt))
    if source_citation:
        lines.append("(Per RFP {})".format(source_citation))
    lines.append("")
    lines.append("To the designated contact,")
    lines.append("")
    intro = ("We are preparing a responsive bid and request clarification on the items below. "
             "These are factual questions about what each requirement entails; they do not "
             "propose any change to the solicitation's scope, terms, or evaluation.")
    if citation_req:
        intro += " Each question cites its RFP location as required ({}).".format(citation_req)
    lines.append(intro)
    lines.append("")

    questions = []
    for i, gap in enumerate(gaps, start=1):
        label = _gap_label(gap)
        cite = _gap_citation(gap)
        ambiguity = _gap_ambiguity(gap)
        tag = "[RFP {}]".format(cite) if cite else "[RFP citation: please verify location]"
        if ambiguity:
            # Weave the SPECIFIC ambiguity (gap['gap'], verbatim) + the item into a
            # factual clarifying question. The ask is neutral — it requests the
            # criteria and how they'll be checked; it never proposes a scope change,
            # suggests a preferred answer, or steers the procurement.
            amb = ambiguity.rstrip(" .")
            text = ("{}. {} {}: {}. Can you confirm the applicable criteria and how "
                    "conformance/acceptance will be verified?".format(i, tag, label, amb))
        else:
            # No stated ambiguity → fall back to the neutral phrasing (unchanged).
            text = ('{}. {} Regarding "{}": can you confirm exactly what a bidder must submit or '
                    "demonstrate to satisfy this requirement, and the acceptable form of proof?"
                    .format(i, tag, label))
        lines.append(text)
        questions.append({"n": i, "requirement": label, "rfp_citation": cite,
                          "ambiguity": ambiguity, "text": text})

    lines.append("")
    lines.append("Thank you. We will incorporate your response into our submission.")
    lines.append("")
    lines.append("[Vendor name / authorized signatory]")

    return {
        "draft": "\n".join(lines),
        "reason": None,
        "questions": questions,
        "question_count": len(questions),
        "contact": contact,
        "deadline": deadline_raw,
        "format": fmt,
        "citation_requirement": citation_req,
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# CLI / demo (prints structured result; never sends anything)
# ---------------------------------------------------------------------------

def _demo():
    qs = {
        "contact": "procurement.questions@example.ny.gov",
        "deadline": "August 15, 2026",
        "format": "Exhibit 1 – Bidder Questions form",
        "citation_requirement": "cite the RFP page, section, and paragraph",
        "source_citation": "§3.1",
    }
    gaps = [
        {"requirement": "MWBE utilization plan", "rfp_citation": "§5.2, p. 14"},
        {"requirement": "Workers' compensation coverage", "rfp_citation": "Appendix A, p. 31"},
    ]
    result = generate(qs, gaps, run_date=datetime.date(2026, 7, 2))
    if result["draft"]:
        print("--- EDITABLE DRAFT (engine does not send) ---")
        print(result["draft"])
        print("\n[note] " + result["disclaimer"])
    else:
        print("No draft: {}".format(result["reason"]))
    print("\n--- JSON ---")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Clarification-question generator (Step 4.5)")
    ap.add_argument("--input", metavar="FILE.json",
                    help="JSON with {question_submission, gaps, run_date?}")
    ap.add_argument("--json", action="store_true", help="emit JSON only")
    args = ap.parse_args(argv)
    if not args.input:
        return _demo()
    with open(args.input, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    run_date = parse_deadline(doc.get("run_date")) if doc.get("run_date") else None
    result = generate(doc.get("question_submission"), doc.get("gaps"), run_date=run_date,
                      force=bool(doc.get("force")))
    if not args.json and result["draft"]:
        print(result["draft"])
        print("\n[note] " + result["disclaimer"])
    elif not args.json:
        print("No draft: {}".format(result["reason"]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
