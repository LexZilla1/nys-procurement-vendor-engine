#!/usr/bin/env python3
"""
Step 1 — Triage. NYS Procurement Vendor Engine.

Classify an incoming procurement opportunity as one of:
    BIDDABLE | NON_BIDDABLE | EDGE | HUMAN_REVIEW | OUT_OF_SCOPE

Input may come from NYSCR, NYC PASSPort, municipal portals, forwarded email, or
pasted text. PUBLIC metadata/text only — no login, no credentials, no document
scraping, and NO retention of NYSCR ad body text (ToS gate: the caller passes
transient text; this module keeps none of it).

Pipeline:
  Step 1  source detection      -> nyscr | other | unknown
  Step 2  jurisdiction gate      -> STATE proceeds; everything else STOPs
          (always first, any source, via the offline entity lookup)
  Step 3  ad-type classification -> only when STATE confirmed AND source==nyscr
  Step 4  LLM path               -> non-nyscr, or unrecognized ad_type, or
          "General" + sole-source/award trigger language in text

Design notes:
  * golden copy is verified for STATE-agency procurement (SFL Art. 11) ONLY.
    The jurisdiction gate STOPS-and-ROUTES on anything else — the conservative
    default is never flag-and-continue.
  * The rule layer (Steps 1–3) is pure Python with no network dependency; the
    entity table and ad-type config are offline repo snapshots.
  * The LLM (Step 4, claude-sonnet-4-6) is injected so the module is testable
    offline; it only ever runs after the gate has confirmed STATE.
  * Golden-copy references use citation-ID style (data/citations.json), never
    hardcoded source filenames (per the architecture assessment).

CONFIDENCE: a rule-layer EXACT ad-type label match ⇒ "high". Everything else
inherits the LLM's confidence. No other path sets "high".

INVARIANT (never-green): no confident BIDDABLE/NON_BIDDABLE when
  (a) jurisdiction is not confirmed STATE via the entity lookup, or
  (b) the matched label is provisional AND confidence is low.
When in doubt: HUMAN_REVIEW. `_finalize()` enforces this as a hard backstop.
"""

import json
import os
import re

from engine import state_machine as _sm
import jurisdiction as _jur

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# -- triage classes -----------------------------------------------------------
BIDDABLE = "BIDDABLE"
NON_BIDDABLE = "NON_BIDDABLE"
EDGE = "EDGE"
HUMAN_REVIEW = "HUMAN_REVIEW"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
TRIAGE_CLASSES = frozenset({BIDDABLE, NON_BIDDABLE, EDGE, HUMAN_REVIEW, OUT_OF_SCOPE})

# Triage CLASS (this module, 5-valued) -> lifecycle triage_verdict
# (engine.state_machine, 3-valued: BIDDABLE / NOT_BIDDABLE / VERIFY). These are two
# DISTINCT vocabularies at two layers, so they are NOT merged into one constant —
# this shim is the ONE place that translates class -> verdict, so a future PR wiring
# triage output into TenderStateMachine.transition is safe. engine.state_machine is
# not modified. Per never-green, every non-confident class (EDGE / HUMAN_REVIEW /
# OUT_OF_SCOPE) maps to VERIFY (a human confirms) — discarding is the risky
# alternative, so we never auto-decline.
TRIAGE_CLASS_TO_VERDICT = {
    BIDDABLE: _sm.BIDDABLE,          # confident open competitive solicitation
    NON_BIDDABLE: _sm.NOT_BIDDABLE,  # confident award / exemption / RFI / surplus notice
    EDGE: _sm.VERIFY,                # borderline ad-type -> human confirms
    HUMAN_REVIEW: _sm.VERIFY,        # explicitly low-confidence / provisional -> human
    OUT_OF_SCOPE: _sm.VERIFY,        # not NY-state / unclassifiable -> human confirms
}


def lifecycle_verdict_for(triage_class):
    """Translate a triage CLASS (this module's vocabulary) into a lifecycle
    triage_verdict (engine.state_machine's vocabulary). Raises KeyError on an
    unmapped class; the guard test asserts every class maps to a valid, non-None
    verdict, so a new triage label cannot be added without wiring it here."""
    return TRIAGE_CLASS_TO_VERDICT[triage_class]


# -- jurisdiction values ------------------------------------------------------
J_STATE = "STATE"
J_AUTHORITY = "AUTHORITY"
J_SUNY_CUNY = "SUNY_CUNY"
J_MUNICIPAL = "MUNICIPAL"
J_NON_NY = "NON_NY"
J_UNDETERMINED = "UNDETERMINED"

HIGH = "high"
LOW = "low"


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def _load_abs(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# Entity roster, ad-type table, and citation map all come from the active
# jurisdiction pack (defaults to ny-state, which resolves to the historical
# data/ paths — byte-identical).
_PACK = _jur.load_pack()
_ENTITIES = _load_abs(_PACK.entities_path)
_AD_TYPES = _load_abs(_PACK.ad_types_path)
_CITATIONS = _load_abs(_PACK.citations_path)

# --------------------------------------------------------------------------
# Normalization + entity lookup (exact + alias ONLY — never keyword/fuzzy)
# --------------------------------------------------------------------------

def normalize(s):
    if not s:
        return ""
    s = s.lower().strip()
    s = re.sub(r"^the\s+", "", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)   # drop punctuation
    s = re.sub(r"\bnew york state\b", "", s)
    s = re.sub(r"\bnys\b", "", s)
    s = re.sub(r"\bstate of new york\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _build_index():
    idx = {}
    for row in _ENTITIES["entities"]:
        keys = [row["name"]] + row.get("aliases", [])
        for k in keys:
            nk = normalize(k)
            if nk:
                idx.setdefault(nk, row)
    return idx


_INDEX = _build_index()

# Municipal + non-NY indicators are EXPLICIT jurisdiction signals, distinct from
# entity-list matching (they are checked only when no entity row matched).
_MUNICIPAL_RE = re.compile(
    r"\b(city of|town of|village of|county of|school district|"
    r"board of education|public library district|fire district)\b", re.I)

_NON_NY_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "north carolina", "north dakota", "ohio", "oklahoma",
    "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "commonwealth of",
]
_NON_NY_RE = re.compile(r"\b(" + "|".join(re.escape(s) for s in _NON_NY_STATES) + r")\b", re.I)


def lookup_entity(issuer):
    """Exact normalized / alias match against the offline entity table. Returns
    the entity row (dict) or None (AMBIGUOUS). Never keyword/fuzzy: a bare
    'Authority' token does not match anything."""
    if not issuer:
        return None
    return _INDEX.get(normalize(issuer))


# --------------------------------------------------------------------------
# Step 1 — source detection
# --------------------------------------------------------------------------

def _ad_type_row(ad_type):
    """Exact (normalized) match of an ad_type string against the 12-label config
    (label or alias). Returns the config row or None."""
    if not ad_type:
        return None
    n = normalize(ad_type)
    for row in _AD_TYPES["labels"]:
        if normalize(row["label"]) == n:
            return row
        if any(normalize(a) == n for a in row.get("aliases", [])):
            return row
    return None


def detect_source(opp):
    """nyscr iff a structured ad_type field matches the known label set."""
    ad_type = opp.get("ad_type")
    if ad_type and _ad_type_row(ad_type) is not None:
        return "nyscr"
    if ad_type:                       # structured field present but not a NYSCR label
        return "unknown"
    if opp.get("text") or opp.get("body") or opp.get("description"):
        return "other"
    return "unknown"


# --------------------------------------------------------------------------
# Step 2 — jurisdiction gate
# --------------------------------------------------------------------------

def _match_payload(row):
    return {"entity_name": row["name"], "list_source": row["list_source"],
            "list_capture_date": row["list_capture_date"]}


def jurisdiction_gate(opp):
    """Return (jurisdiction, jurisdiction_match|None, terminal_result|None).

    terminal_result is a full output dict when the gate STOPS (anything that is
    not a confirmed STATE agency). When it is a STATE agency, terminal_result is
    None and the caller proceeds to Step 3/4.

    NOTE: the golden copy is verified for STATE-agency procurement (SFL Art. 11)
    ONLY. Stop-and-route is the conservative default — never flag-and-continue.
    """
    issuer = opp.get("issuer") or opp.get("agency") or opp.get("issuing_entity")
    row = lookup_entity(issuer)
    if row is not None:
        if row["type"] == "STATE_AGENCY":
            return (J_STATE, _match_payload(row), None)
        if row["type"] == "AUTHORITY":
            return (J_AUTHORITY, _match_payload(row), _stop(
                J_AUTHORITY, _match_payload(row), HUMAN_REVIEW,
                "authority procurement governed by Public Authorities Law §2879 "
                "or bi-state compact — not in golden copy.", "entity_lookup"))
        if row["type"] == "SUNY_CUNY":
            return (J_SUNY_CUNY, _match_payload(row), _stop(
                J_SUNY_CUNY, _match_payload(row), HUMAN_REVIEW,
                "SUNY/CUNY procurement partially under separate Education Law "
                "authority — coverage unverified.", "entity_lookup"))

    # No entity match: explicit jurisdiction indicators, else undetermined.
    text_blob = " ".join(str(opp.get(k, "")) for k in
                         ("issuer", "agency", "issuing_entity"))
    if _NON_NY_RE.search(text_blob):
        return (J_NON_NY, None, _stop(
            J_NON_NY, None, OUT_OF_SCOPE, "non-NY jurisdiction.", "issuer"))
    if _MUNICIPAL_RE.search(text_blob):
        return (J_MUNICIPAL, None, _stop(
            J_MUNICIPAL, None, HUMAN_REVIEW,
            "requires General Municipal Law — not in golden copy.", "issuer"))
    return (J_UNDETERMINED, None, _stop(
        J_UNDETERMINED, None, HUMAN_REVIEW,
        "issuer not on verified entity lists — jurisdiction undetermined.",
        "entity_lookup"))


# --------------------------------------------------------------------------
# Output construction + never-green backstop
# --------------------------------------------------------------------------

def _out(source_type, jurisdiction, jurisdiction_match, triage_class, reason,
         confidence, source_field, label_provisional, route=None,
         citation_id=None):
    o = {
        "source_type": source_type,
        "jurisdiction": jurisdiction,
        "jurisdiction_match": jurisdiction_match,
        "triage_class": triage_class,
        "reason": reason,
        "confidence": confidence,
        "source_field": source_field,
        "label_provisional": bool(label_provisional),
    }
    if route is not None:
        o["route"] = route
    if citation_id is not None:
        o["citation_id"] = citation_id
    return o


def _stop(jurisdiction, jurisdiction_match, triage_class, reason, source_field):
    # Gate stops are deterministic routing, NOT a high-confidence biddability
    # call, so confidence is low (only an exact label match earns "high").
    return _out("", jurisdiction, jurisdiction_match, triage_class, reason,
                LOW, source_field, False)


def _finalize(o):
    """Hard backstop for the never-green invariant: no confident BIDDABLE/
    NON_BIDDABLE unless jurisdiction is STATE and not (provisional AND low)."""
    if o["triage_class"] in (BIDDABLE, NON_BIDDABLE):
        if o["jurisdiction"] != J_STATE:
            o["triage_class"] = HUMAN_REVIEW
            o["reason"] = ("never-green: biddability withheld — jurisdiction not "
                           "confirmed STATE. (" + o["reason"] + ")")
            o["confidence"] = LOW
        elif o["label_provisional"] and o["confidence"] == LOW:
            o["triage_class"] = HUMAN_REVIEW
            o["reason"] = ("never-green: provisional label with low confidence — "
                           "routed to human review. (" + o["reason"] + ")")
    return o


# --------------------------------------------------------------------------
# Step 4 — LLM path (injectable; only runs after STATE is confirmed)
# --------------------------------------------------------------------------

SOLE_SOURCE_TRIGGERS = [t.lower() for t in _AD_TYPES.get("sole_source_triggers", [])]


def has_sole_source_language(text):
    t = (text or "").lower()
    return any(trigger in t for trigger in SOLE_SOURCE_TRIGGERS)


def _default_llm(payload):
    """Default Step-4 classifier: the live claude-sonnet-4-6 wrapper in
    pipeline/llm_classifier.py. Import-guarded so this module still loads if that
    package (or the anthropic SDK) is unavailable — in which case, and whenever
    ANTHROPIC_API_KEY is unset, the wrapper itself returns HUMAN_REVIEW (never a
    silent green). Tests inject a spy and never reach this path."""
    try:
        from pipeline.llm_classifier import classify
    except Exception:
        return {"triage_class": HUMAN_REVIEW, "confidence": LOW,
                "reason": "Step-4 classifier unavailable — routed to human review."}
    return classify(payload)


def _run_llm(opp, source_type, jurisdiction, jurisdiction_match, llm, why):
    text = opp.get("text") or opp.get("body") or opp.get("description") or ""
    verdict = (llm or _default_llm)(text)
    tclass = verdict.get("triage_class", HUMAN_REVIEW)
    conf = verdict.get("confidence", LOW)
    reason = verdict.get("reason", "LLM classification")
    # LLM LOW must never be silently BIDDABLE/NON_BIDDABLE.
    if conf != HIGH and tclass in (BIDDABLE, NON_BIDDABLE):
        tclass = HUMAN_REVIEW
        reason = "low-confidence LLM classification — routed to human review. (%s)" % reason
        conf = LOW
    reason = "%s [Step 4 — %s]" % (reason, why)
    return _finalize(_out(source_type, jurisdiction, jurisdiction_match, tclass,
                          reason, conf, "llm", False))


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------

def triage(opp, llm=None):
    """Classify one opportunity dict. `llm` is a callable(text)->{triage_class,
    confidence,reason} used ONLY in Step 4; injected for tests/production."""
    source_type = detect_source(opp)                       # Step 1

    jurisdiction, jmatch, terminal = jurisdiction_gate(opp)  # Step 2 (always first)
    if terminal is not None:
        terminal["source_type"] = source_type
        return terminal

    # -- STATE confirmed from here on --------------------------------------
    if source_type == "nyscr":                             # Step 3
        row = _ad_type_row(opp.get("ad_type"))
        if row is not None:
            # "General" + sole-source/award trigger language -> escalate to Step 4.
            if normalize(row["label"]) == normalize("General") and \
               has_sole_source_language(opp.get("text") or opp.get("description")):
                return _run_llm(opp, source_type, jurisdiction, jmatch, llm,
                                "General label but sole-source/award language present")
            if row["class"] == EDGE:
                # Tag-only route; NO downstream call (LLM is not invoked).
                return _finalize(_out(
                    source_type, jurisdiction, jmatch, EDGE, row["reason"],
                    HIGH, "ad_type", row.get("provisional", True),
                    route=row.get("route"), citation_id=row.get("citation_id")))
            # BIDDABLE / NON_BIDDABLE exact rule match ⇒ high confidence.
            return _finalize(_out(
                source_type, jurisdiction, jmatch, row["class"], row["reason"],
                HIGH, "ad_type", row.get("provisional", True),
                citation_id=row.get("citation_id")))
        # ad_type present but unrecognized -> Step 4.
        return _run_llm(opp, source_type, jurisdiction, jmatch, llm,
                        "ad_type unrecognized")

    # Non-nyscr source -> skip Step 3, go straight to Step 4.
    return _run_llm(opp, source_type, jurisdiction, jmatch, llm,
                    "non-NYSCR source")


def resolve_citation(citation_id):
    """Resolve a citation-ID to its human description (never a source filename)."""
    return _CITATIONS["citations"].get(citation_id)


if __name__ == "__main__":
    import sys
    demo = {"issuer": "Office of General Services", "ad_type": "General"}
    print(json.dumps(triage(demo), indent=2))
    sys.exit(0)
