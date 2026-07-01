#!/usr/bin/env python3
"""
BUILD SPEC v2 — Part A support: stdlib-only NYS tender text + requirement extraction.

Takes a real NYS tender / RFP document the vendor uploads, pulls its text, and
surfaces the requirement-bearing passages. Two design commitments govern this
module:

  * PRIVACY (BUILD SPEC v2 §11): extraction is 100% ON-MACHINE. This module
    imports ONLY the Python standard library (zlib, re, io, os) — NO network
    client, NO third-party model, NO OCR service. The bytes of an uploaded
    tender never leave this process. The self-test asserts this.

  * NEVER GUESS. A scanned / image-only PDF has no text layer to extract; this
    module does not hallucinate one. It reports has_text_layer=False so the
    caller can say "no extractable text — not confirmed" and fall back to the
    plain-text paste path, rather than invent requirements.

Provenance note: text pulled here is the VENDOR'S uploaded tender — it is NOT
golden copy. Requirement excerpts are quoted verbatim and tagged "this tender,
page N". They must never be routed through GoldenCopy.cite() (that choke-point
is reserved for verbatim State law). bid_readiness.py holds that line.

Run:
    python3 tender_extractor.py FILE.pdf      # or FILE.txt
    python3 tender_extractor.py --selftest
"""

import io
import os
import re
import sys
import zlib


# ---------------------------------------------------------------------------
# PDF text extraction (text-layer only; stdlib zlib for FlateDecode)
# ---------------------------------------------------------------------------

# A content-stream string-show operator: a (...) literal before Tj, or a [...]
# array before TJ. Strings may contain escaped parens / backslashes.
_SHOW_RE = re.compile(
    r"(\((?:[^()\\]|\\.)*\)|\[(?:[^\[\]\\]|\\.)*\])\s*(Tj|TJ)", re.DOTALL)
_STR_RE = re.compile(r"\((?:[^()\\]|\\.)*\)", re.DOTALL)
# Operators that move to a new line; we emit a newline when one precedes a show.
_NEWLINE_OP_RE = re.compile(r"(?:^|\s)(T\*|Td|TD|')(?=\s|$)")

_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
            "(": "(", ")": ")", "\\": "\\"}


def _unescape_pdf_string(raw):
    """Decode a PDF literal string body (without the surrounding parens)."""
    out = []
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt in _ESCAPES:
                out.append(_ESCAPES[nxt])
                i += 2
                continue
            if nxt.isdigit():  # octal char code, up to 3 digits
                j = i + 1
                digits = ""
                while j < n and len(digits) < 3 and raw[j].isdigit():
                    digits += raw[j]
                    j += 1
                try:
                    out.append(chr(int(digits, 8)))
                except ValueError:
                    pass
                i = j
                continue
            if nxt in "\r\n":  # line continuation
                i += 2
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _strings_in_operand(operand):
    """Pull the visible text out of a Tj '(...)' or TJ '[...]' operand."""
    if operand.startswith("("):
        return _unescape_pdf_string(operand[1:-1])
    parts = [_unescape_pdf_string(m.group(0)[1:-1])
             for m in _STR_RE.finditer(operand)]
    return "".join(parts)


def _text_from_content(content):
    """Reconstruct readable text from one decoded PDF content stream."""
    lines = []
    cur = []
    pos = 0
    for m in _SHOW_RE.finditer(content):
        between = content[pos:m.start()]
        pos = m.end()
        if cur and _NEWLINE_OP_RE.search(between):
            lines.append("".join(cur))
            cur = []
        cur.append(_strings_in_operand(m.group(1)))
    if cur:
        lines.append("".join(cur))
    return "\n".join(s for s in (ln.strip() for ln in lines) if s)


def _iter_raw_streams(data):
    """Yield the raw bytes between each `stream` / `endstream` pair."""
    needle = b"stream"
    end = b"endstream"
    i = 0
    while True:
        s = data.find(needle, i)
        if s == -1:
            return
        body = s + len(needle)
        # Skip the single EOL that PDF requires after the `stream` keyword.
        if data[body:body + 2] == b"\r\n":
            body += 2
        elif data[body:body + 1] in (b"\n", b"\r"):
            body += 1
        e = data.find(end, body)
        if e == -1:
            return
        chunk = data[body:e]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        elif chunk.endswith(b"\n") or chunk.endswith(b"\r"):
            chunk = chunk[:-1]
        yield chunk
        i = e + len(end)


def _decode_stream(chunk):
    """Return the stream's text content, FlateDecoding if needed; or None."""
    for attempt in (chunk,):
        try:
            return zlib.decompress(attempt).decode("latin-1")
        except (zlib.error, UnicodeDecodeError):
            pass
    try:  # raw DEFLATE (no zlib header)
        return zlib.decompressobj(-zlib.MAX_WBITS).decompress(chunk).decode("latin-1")
    except (zlib.error, UnicodeDecodeError):
        pass
    # Possibly an already-uncompressed content stream.
    try:
        text = chunk.decode("latin-1")
    except UnicodeDecodeError:
        return None
    return text if ("Tj" in text or "TJ" in text) else None


def _dehyphenate(text):
    """Rejoin words split by a hyphen across a line break so goal lines and
    dollar limits reassemble: 'Women-\\nOwned' → 'Women-Owned', 'MWBE utiliza-
    \\ntion plan' → 'MWBE utilization plan'. A hyphen between two letters at a
    line break is a wrap artifact; join the lines (drop a soft hyphen inside a
    single word, keep it in a real compound)."""
    # letter + soft-wrap hyphen + lowercase continuation → drop the hyphen
    text = re.sub(r"([A-Za-z])-\n([a-z])", r"\1\2", text)
    # letter + hyphen + Capitalized continuation → keep hyphen (real compound)
    text = re.sub(r"([A-Za-z])-\n([A-Z])", r"\1-\2", text)
    return text


def extract_pdf(path):
    """Extract text-layer content from a PDF, one entry per text-bearing page.

    Returns {"source", "page_count", "pages": [str, ...], "has_text_layer"}.
    has_text_layer is False for a scanned/image PDF we cannot read — the caller
    must then say "not confirmed", never guess.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    pages = []
    for chunk in _iter_raw_streams(data):
        decoded = _decode_stream(chunk)
        if not decoded:
            continue
        text = _text_from_content(decoded)
        if text:
            pages.append(_dehyphenate(text))
    return {
        "source": os.path.basename(path),
        "page_count": len(pages),
        "pages": pages,
        "has_text_layer": bool(pages),
    }


def extract_txt(path):
    """Read a plain-text paste-fallback file. Form feeds (\\f) split pages."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    pages = [p.strip() for p in raw.split("\f")]
    pages = [p for p in pages if p]
    return {
        "source": os.path.basename(path),
        "page_count": len(pages),
        "pages": pages,
        "has_text_layer": bool(pages),
    }


def extract(path):
    """Dispatch on extension: .pdf → text-layer parse, anything else → text."""
    if path.lower().endswith(".pdf"):
        return extract_pdf(path)
    return extract_txt(path)


# ---------------------------------------------------------------------------
# Requirement detection (heuristic; flags passages, never invents rules)
# ---------------------------------------------------------------------------

# Mandatory-language signals NYS RFPs use for binding requirements.
_SIGNAL_RE = re.compile(
    r"\b(shall|must|is required to|are required to|will be required|"
    r"required to|responsible for|no later than|prior to award|"
    r"as a condition of)\b", re.IGNORECASE)

# Domain buckets. The first matching keyword wins; order matters (specific
# before general). "kind" lets bid_readiness map a passage to a known rule.
_KIND_KEYWORDS = [
    # "work force" (two words) is the §143.3(c) EEO term; the single word
    # "workforce" (e.g. "Workforce Innovation and Opportunity Act") is NOT — the
    # required space keeps a WIOA program mention from tripping EEO.
    ("eeo", re.compile(r"\b(equal employment opportunity|\beeo\b|staffing plan|"
                       r"work\s+force)\b", re.IGNORECASE)),
    ("mwbe", re.compile(r"\b(m/?wbe|minority[ -]and[ -]women|minority and women|"
                        r"minority-? ?and ?-?women-?owned|utilization plan)\b",
                        re.IGNORECASE)),
    ("sdvob", re.compile(r"\b(sdvob|service-?disabled veteran)\b", re.IGNORECASE)),
    ("insurance", re.compile(r"\b(insurance|liability coverage|certificate of "
                             r"insurance|indemnif)\b", re.IGNORECASE)),
    ("bonding", re.compile(r"\b(bid bond|performance bond|surety|bonding)\b",
                           re.IGNORECASE)),
    ("vendor_responsibility", re.compile(
        r"\b(vendor responsibility|responsibility questionnaire|vendrep|"
        r"vendor responsible)\b", re.IGNORECASE)),
    # Appendix A standard clauses (grounded verbatim in the golden copy).
    ("non_collusion", re.compile(r"\b(non-?collusi|collusion|139-d)\b",
                                 re.IGNORECASE)),
    ("iran_divestment", re.compile(r"\b(iran divestment|prohibited entities "
                                   r"list|165-a)\b", re.IGNORECASE)),
    ("sales_tax_5a", re.compile(r"\b(sales and compensating use tax|tax law "
                                r"§?\s?5-a|certificate of authority)\b",
                                re.IGNORECASE)),
    ("tropical_hardwoods", re.compile(r"\btropical hardwood", re.IGNORECASE)),
    ("sexual_harassment", re.compile(r"\b(sexual harassment|201-g|139-l)\b",
                                     re.IGNORECASE)),
    ("gender_based_violence", re.compile(r"\b(gender-?based violence|139-m)\b",
                                         re.IGNORECASE)),
    # §220-i is the contractor-REGISTRATION requirement. Bare "public work"
    # appears in boilerplate standard clauses (§142, prevailing-wage) and must
    # NOT trip it; only a specific registration reference does.
    ("public_work_registration", re.compile(
        r"\b(220-i|certificate of registration|nysdol contractor|"
        r"contractor registry|prevailing wage.{0,40}registrat)\b",
        re.IGNORECASE)),
    ("international_boycott", re.compile(
        r"\b(international boycott|139-h|export administration)\b", re.IGNORECASE)),
    ("registration", re.compile(r"\b(vendor file|registered in the nys|"
                                r"vendor registration)\b", re.IGNORECASE)),
    ("certification", re.compile(r"\b(certif(?:ied|ication)|certificate)\b",
                                 re.IGNORECASE)),
    ("insurance_workers", re.compile(r"\bworkers'? compensation\b", re.IGNORECASE)),
]


def _classify(text):
    for kind, rx in _KIND_KEYWORDS:
        if rx.search(text):
            return kind
    return "general"


def _segments(page_text):
    """Split a page into candidate requirement segments (lines + sentences)."""
    segs = []
    for line in page_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Also split long lines into sentences so one bullet ≠ many rules.
        for piece in re.split(r"(?<=[.;:])\s+", line):
            piece = piece.strip()
            if len(piece) >= 8:
                segs.append(piece)
    return segs


def find_requirements(extracted):
    """From an extract() result, return requirement rows.

    Each row: {"text", "page", "kind"} where text is verbatim tender language
    and page is 1-based. A passage qualifies if it uses mandatory language OR
    names a known compliance domain (so a terse "MWBE goal: 30%" is not missed).
    """
    rows = []
    seen = set()
    for idx, page_text in enumerate(extracted.get("pages", []), start=1):
        for seg in _segments(page_text):
            kind = _classify(seg)
            has_signal = bool(_SIGNAL_RE.search(seg))
            if not has_signal and kind == "general":
                continue
            key = (seg.lower(), kind)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"text": seg, "page": idx, "kind": kind})
    return rows


# ---------------------------------------------------------------------------
# Self-test (privacy guarantee + round-trip)
# ---------------------------------------------------------------------------

def _assert_no_network_imports():
    """Privacy guard: this module must not pull in any network/model client."""
    import tender_extractor as me
    forbidden = ("socket", "urllib", "http", "ssl", "ftplib", "requests",
                 "openai", "anthropic")
    src = io.open(me.__file__, "r", encoding="utf-8").read()
    bad = [name for name in forbidden
           if re.search(r"\bimport\s+%s\b|\bimport\s+%s\." % (name, name), src)]
    assert not bad, "network/model import found: %s" % bad


def _selftest():
    _assert_no_network_imports()
    ok = True
    sample = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "sample-tender.pdf")
    if os.path.isfile(sample):
        ex = extract(sample)
        reqs = find_requirements(ex)
        print("read %d page(s), found %d requirement passage(s)"
              % (ex["page_count"], len(reqs)))
        ok = ex["has_text_layer"] and len(reqs) > 0
    else:
        print("(no sample-tender.pdf present; skipped round-trip)")
    print("privacy: stdlib-only, on-machine — OK")
    return 0 if ok else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] == "--selftest":
        return _selftest()
    ex = extract(argv[0])
    if not ex["has_text_layer"]:
        print("no extractable text layer — not confirmed "
              "(scanned/image PDF?). Use a .txt paste fallback.")
        return 1
    print("source: %s   pages: %d" % (ex["source"], ex["page_count"]))
    for r in find_requirements(ex):
        print("  [p%d/%s] %s" % (r["page"], r["kind"], r["text"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
