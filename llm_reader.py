#!/usr/bin/env python3
"""
BUILD SPEC v2 §14 — LLM-based RFP reader (Capability 1: requirements checklist).

A NEW, SEPARATE reader that runs ALONGSIDE the stdlib pattern-matcher — it does
NOT replace or modify tender_extractor.py. Pipeline:

  1. Reuse the existing stdlib PDF→text extractor (tender_extractor.extract) to
     get the raw text. (The RFP is a PUBLIC government document, so reading it
     with a commercial LLM carries no privacy concern — spec §14.)
  2. Send that text to Claude (claude-sonnet-4-6) and ask it to extract EVERY
     requirement a vendor must satisfy to participate.
  3. Emit a clean, structured requirements CHECKLIST (item + what's required +
     any number/deadline).

Deliberately OUT OF SCOPE for this build (per instructions): no golden-copy
grounding, no GoldenCopy.cite(), no readiness score, no vendor profile. This
answers ONE question — does Claude read the RFP more completely and cleanly
than the stdlib pattern-matcher (which produced ~348 noisy rows)?

The API key comes from llm_config.get_anthropic_api_key() (env var / .env).
"""

import json
import sys

import anthropic

from llm_config import get_anthropic_api_key
from tender_extractor import extract

MODEL = "claude-sonnet-4-6"

SYSTEM = (
    "You are a meticulous New York State procurement analyst. You read a public "
    "NYS tender (RFP / IFB / bid package) and extract the COMPLETE list of "
    "requirements a vendor must satisfy in order to participate and submit a "
    "responsive bid.\n\n"
    "Extract EVERY requirement, including:\n"
    "- Required documents, forms, and attachments (e.g. VendRep questionnaire, "
    "EEO policy, MWBE/SDVOB utilization plans, W-9, non-collusion, Iran "
    "divestment, sales-tax cert, etc.)\n"
    "- Certifications and signatures\n"
    "- Insurance requirements WITH their dollar amounts/limits\n"
    "- MWBE and SDVOB participation goals WITH their percentages\n"
    "- Bonding / bid-deposit requirements with amounts\n"
    "- Submission deadline(s), method, and number of copies\n"
    "- Pre-bid / pre-proposal conferences (mandatory or optional) with date/time\n"
    "- References, experience, and staffing / key-personnel requirements\n"
    "- Any disqualification / non-responsiveness triggers and post-award "
    "reporting obligations\n\n"
    "RULES:\n"
    "- Extract ONLY what is actually stated in the tender text. Do NOT invent or "
    "infer requirements that are not present. If a value (amount, %, date) is "
    "not stated, use null.\n"
    "- Be exhaustive but DEDUPLICATE: one entry per distinct requirement, not one "
    "per sentence.\n"
    "- Use the '=== PAGE n ===' markers in the text to record the page.\n"
    "- Return ONLY a single valid JSON object, no markdown fences, no prose. "
    "Schema:\n"
    "{\n"
    '  "tender_title": string|null,\n'
    '  "submission_deadline": string|null,\n'
    '  "requirements": [\n'
    "    {\n"
    '      "category": string,            // e.g. "Form", "Certification", '
    '"Insurance", "MWBE/SDVOB", "Deadline", "Conference", "References", '
    '"Staffing", "Bonding", "Other"\n'
    '      "item": string,                // short name of the requirement\n'
    '      "requirement": string,         // what specifically is required\n'
    '      "value": string|null,          // the number/amount/% if any (e.g. '
    '"$2,000,000", "30%")\n'
    '      "deadline": string|null,       // date/time if this item has one\n'
    '      "mandatory": boolean,          // true if failing it makes the bid '
    "non-responsive, false if optional/goal\n"
    '      "page": integer|null,          // page number from the === PAGE n === '
    "markers\n"
    '      "source_quote": string         // a short verbatim snippet from the '
    "tender\n"
    "    }\n"
    "  ]\n"
    "}\n"
)


def _build_text(extracted):
    """Join the stdlib-extracted pages with page markers so Claude can cite pages."""
    return "\n\n".join(
        "=== PAGE {} ===\n{}".format(i, p)
        for i, p in enumerate(extracted.get("pages", []), start=1)
    )


def _parse_json(text):
    """Parse the model's JSON reply, tolerating stray fences/prose."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(t[start:end + 1])
        raise


def read_requirements(extracted, model=MODEL, max_tokens=32000):
    """Send the extracted tender text to Claude and return (parsed, meta)."""
    client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    text = _build_text(extracted)
    user = (
        "Here is the full text of a NYS tender, extracted from the PDF "
        "(page markers included). Extract the complete requirements checklist "
        "as specified.\n\n" + text
    )
    # Stream (the doc is large; streaming avoids HTTP timeouts). Adaptive thinking
    # helps the model be thorough across a 50-70 page document.
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()

    reply = "".join(b.text for b in msg.content if b.type == "text")
    meta = {
        "model": msg.model,
        "stop_reason": msg.stop_reason,
        "input_tokens": msg.usage.input_tokens,
        "output_tokens": msg.usage.output_tokens,
    }
    if msg.stop_reason == "refusal":
        return None, {**meta, "error": "model refused"}
    parsed = _parse_json(reply)
    return parsed, meta


# ---------------------------------------------------------------------------
# Human render — the checklist
# ---------------------------------------------------------------------------

def render_checklist(parsed, meta, source):
    L = []
    L.append("=" * 78)
    L.append("REQUIREMENTS CHECKLIST (LLM reader — {}) — {}".format(meta["model"], source))
    L.append("=" * 78)
    if parsed.get("tender_title"):
        L.append("Tender: {}".format(parsed["tender_title"]))
    if parsed.get("submission_deadline"):
        L.append("Submission deadline: {}".format(parsed["submission_deadline"]))
    reqs = parsed.get("requirements", [])
    L.append("{} requirements extracted   |   input {} tok / output {} tok / "
             "stop={}".format(len(reqs), meta["input_tokens"], meta["output_tokens"],
                              meta["stop_reason"]))
    L.append("")
    # Group by category, mandatory first.
    by_cat = {}
    for r in reqs:
        by_cat.setdefault(r.get("category", "Other"), []).append(r)
    for cat in sorted(by_cat):
        L.append("── {} ──".format(cat.upper()))
        for r in by_cat[cat]:
            mark = "[ ]" if r.get("mandatory") else "( )"
            line = "  {} {}".format(mark, r.get("item", "(unnamed)"))
            bits = []
            if r.get("value"):
                bits.append(r["value"])
            if r.get("deadline"):
                bits.append("by " + str(r["deadline"]))
            if r.get("page"):
                bits.append("p{}".format(r["page"]))
            if bits:
                line += "   — " + " | ".join(str(b) for b in bits)
            L.append(line)
            if r.get("requirement"):
                L.append("        {}".format(r["requirement"]))
        L.append("")
    L.append("-" * 78)
    L.append("[ ] = mandatory (non-responsive if missing)   ( ) = optional / goal")
    L.append("LLM-extracted from the uploaded tender; verify against the original "
             "document. Not legal advice; no golden-copy grounding in this view.")
    L.append("=" * 78)
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: llm_reader.py TENDER.(pdf|txt) [--json]", file=sys.stderr)
        return 2
    path = argv[0]
    extracted = extract(path)
    if not extracted["has_text_layer"]:
        print("no extractable text layer — not confirmed (scanned/image PDF?).",
              file=sys.stderr)
        return 1
    parsed, meta = read_requirements(extracted)
    if parsed is None:
        print("LLM did not return a checklist: {}".format(meta), file=sys.stderr)
        return 1
    if "--json" in argv:
        print(json.dumps({"meta": meta, "checklist": parsed}, indent=2,
                         ensure_ascii=False))
    else:
        print(render_checklist(parsed, meta, extracted.get("source", path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
