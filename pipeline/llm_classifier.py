#!/usr/bin/env python3
"""
Step 4 live LLM classifier — NYS Procurement Vendor Engine.

A thin wrapper around the Anthropic Messages API (claude-sonnet-4-6) that
classifies a procurement opportunity's metadata/text into a triage class. It is
the default Step-4 classifier for step1_triage.py; tests inject a spy so they
never hit the network.

Contract (callable as classify(text) -> dict):
    {"triage_class": BIDDABLE|NON_BIDDABLE|EDGE|HUMAN_REVIEW,
     "confidence": "high"|"low",
     "reason": str}

Safety / guard rails are enforced HERE IN CODE (not merely requested in the
prompt), and again in step1_triage._run_llm / _finalize:
  * No API key configured        -> HUMAN_REVIEW, no network call.
  * anthropic SDK missing / call fails / malformed JSON -> HUMAN_REVIEW.
  * confidence != "high"          -> forced HUMAN_REVIEW, regardless of class.
  * The model may ONLY return BIDDABLE/NON_BIDDABLE/EDGE/HUMAN_REVIEW; anything
    else (incl. OUT_OF_SCOPE or a jurisdiction verdict) is coerced to
    HUMAN_REVIEW. OUT_OF_SCOPE and jurisdiction are decided ONLY by the Step 2
    entity gate, never delegated to the model.
  * The key comes from ANTHROPIC_API_KEY (via llm_config), never hardcoded.

HUMAN_REVIEW is always the safe default.
"""

import json

# triage-class vocabulary (kept in sync with step1_triage).
BIDDABLE = "BIDDABLE"
NON_BIDDABLE = "NON_BIDDABLE"
EDGE = "EDGE"
HUMAN_REVIEW = "HUMAN_REVIEW"
HIGH = "high"
LOW = "low"

# The model may return ONLY these classes (NOT OUT_OF_SCOPE / jurisdiction).
_ALLOWED = {BIDDABLE, NON_BIDDABLE, EDGE, HUMAN_REVIEW}

MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 256

SYSTEM = (
    "You are a procurement triage classifier for New York State opportunities. "
    "Given the metadata and text of a procurement notice, classify it as "
    "BIDDABLE (an open competitive solicitation), NON_BIDDABLE (an award notice, "
    "sole-source, RFI, surplus, or informational posting), or EDGE (a grant or "
    "notice of funds availability). If uncertain, respond HUMAN_REVIEW. Also "
    "assess confidence as high or low. Respond in JSON only: "
    "{triage_class, confidence, reason}."
)


def _human(reason, confidence=LOW):
    return {"triage_class": HUMAN_REVIEW, "confidence": confidence, "reason": reason}


def _parse_json(text):
    """Parse the model's JSON reply, tolerating stray fences/prose."""
    t = (text or "").strip()
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


def _coerce(parsed):
    """Apply the code-enforced guard rails to a parsed model response."""
    if not isinstance(parsed, dict):
        return _human("malformed LLM response (not an object) — human review.")
    tclass = str(parsed.get("triage_class", "")).strip().upper()
    conf = str(parsed.get("confidence", "")).strip().lower()
    reason = str(parsed.get("reason", "")).strip() or "LLM classification"
    if tclass not in _ALLOWED:
        return _human("LLM returned a non-triage class %r — human review." % tclass)
    if conf != HIGH:
        # confidence != high -> HUMAN_REVIEW regardless of class.
        return _human("low/uncertain LLM confidence — human review. (%s)" % reason)
    return {"triage_class": tclass, "confidence": HIGH, "reason": reason}


def classify(text, model=MODEL, max_tokens=_MAX_TOKENS):
    """Classify opportunity metadata/text via claude-sonnet-4-6. Returns the
    contract dict. Never raises: every failure path resolves to HUMAN_REVIEW."""
    # Key from env (never hardcoded). Missing key -> no network call.
    try:
        from llm_config import get_anthropic_api_key
        key = get_anthropic_api_key(required=False)
    except Exception:
        key = None
    if not key:
        return _human("no API key configured — human review.")

    try:
        import anthropic
    except ImportError:
        return _human("anthropic SDK unavailable — human review.")

    try:
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM,
            messages=[{"role": "user", "content":
                       "Classify this NYS procurement notice.\n\n" + (text or "")}],
        )
        if getattr(msg, "stop_reason", None) == "refusal":
            return _human("model refused to classify — human review.")
        raw = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    except Exception as exc:
        return _human("LLM call failed (%s) — human review." % type(exc).__name__)

    try:
        parsed = _parse_json(raw)
    except Exception:
        return _human("malformed LLM JSON — human review.")
    return _coerce(parsed)
