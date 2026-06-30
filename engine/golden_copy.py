"""Golden-copy loader + citation-by-construction.

The golden copy (``/golden-copy/sources/source-*.md``) is the ONLY source of rule truth
(PHASE2-BUILD-SPEC §1). Every rule this engine shows the user must trace to a verbatim passage
in one of those files. ``GoldenCopy.cite()`` enforces that: you can only assert a passage if the
passage is present, character-for-character, in the named source file. If it is not, ``cite()``
raises -- the engine cannot assert what it cannot cite (no paraphrase, no reconstruction).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# Grounding states a fact shown to the user can carry (BUILD SPEC v2 §3).
CONFIRMED = "CONFIRMED"          # primary source, cited verbatim
CLAIM = "NOT CONFIRMED / CLAIM"  # flagged "verify with certifying body"
USER_PROVIDED = "USER-PROVIDED"  # the vendor entered it

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SOURCES_DIR = os.path.join(_REPO_ROOT, "golden-copy", "sources")
_INDEX_FILE = os.path.join(_REPO_ROOT, "golden-copy", "golden-copy-INDEX.md")
_VERIFICATION_FILE = os.path.join(_REPO_ROOT, "golden-copy", "VERIFICATION-REPORT.md")


@dataclass(frozen=True)
class SourceRecord:
    """One parsed verbatim source file."""

    slug: str           # filename without the source- prefix or .md suffix, e.g. "xi-16-vendor-responsibility"
    filename: str
    name: str
    date: str
    issued_by: str
    link: str
    copied_on: str
    body: str           # the verbatim STATE TEXT block

    def contains(self, passage: str) -> bool:
        return _normalize(passage) in _normalize(self.body)


@dataclass(frozen=True)
class Citation:
    """A verbatim-grounded citation, safe to render to the user."""

    state: str              # CONFIRMED / CLAIM / USER_PROVIDED
    quote: str              # the verbatim passage pulled from the source file
    source_name: str
    source_file: str
    url: str
    capture_date: str

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "quote": self.quote,
            "source_name": self.source_name,
            "source_file": self.source_file,
            "url": self.url,
            "capture_date": self.capture_date,
        }


def _normalize(text: str) -> str:
    """Collapse whitespace so a citation check ignores formatting noise, not wording."""
    return re.sub(r"\s+", " ", text).strip()


_LABEL_RE = {
    "name": re.compile(r"^- \*\*Name:\*\*\s*(.+?)\s*$", re.M),
    "date": re.compile(r"^- \*\*Date:\*\*\s*(.+?)\s*$", re.M),
    "issued_by": re.compile(r"^- \*\*Issued by:\*\*\s*(.+?)\s*$", re.M),
    "link": re.compile(r"^- \*\*Link[^:]*:\*\*\s*(.+?)\s*$", re.M),
    "copied_on": re.compile(r"^- \*\*Copied exactly on:\*\*\s*(.+?)\s*$", re.M),
}


def _parse_source(path: str) -> SourceRecord:
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()

    def label(key: str) -> str:
        m = _LABEL_RE[key].search(raw)
        return m.group(1).strip() if m else ""

    # Body = everything under "## STATE TEXT (verbatim)" up to the next "## " heading.
    body = ""
    m = re.search(r"##\s*STATE TEXT \(verbatim\)\s*\n(.*?)(?:\n##\s|\Z)", raw, re.S)
    if m:
        body = m.group(1).strip()

    fname = os.path.basename(path)
    slug = fname[len("source-"):-len(".md")] if fname.startswith("source-") else fname[:-3]
    return SourceRecord(
        slug=slug,
        filename=fname,
        name=label("name"),
        date=label("date"),
        issued_by=label("issued_by"),
        link=label("link"),
        copied_on=label("copied_on"),
        body=body,
    )


class GoldenCopy:
    """Loads and indexes the verbatim source files; serves verbatim-checked citations."""

    def __init__(self, sources_dir: str = _SOURCES_DIR):
        self.sources_dir = sources_dir
        self._records: Dict[str, SourceRecord] = {}
        self._load()

    def _load(self) -> None:
        for fname in sorted(os.listdir(self.sources_dir)):
            if not (fname.startswith("source-") and fname.endswith(".md")):
                continue
            rec = _parse_source(os.path.join(self.sources_dir, fname))
            self._records[rec.slug] = rec

    # ----- access -------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._records)

    def slugs(self) -> List[str]:
        return sorted(self._records)

    def get(self, slug: str) -> SourceRecord:
        slug = _strip_slug(slug)
        if slug not in self._records:
            raise KeyError(f"No golden-copy source for slug {slug!r}")
        return self._records[slug]

    # ----- integrity (PHASE2 Step 1) -----------------------------------------
    def integrity_problems(self) -> List[str]:
        """Return a list of integrity failures; empty list == clean."""
        problems: List[str] = []
        for slug, rec in self._records.items():
            for field in ("name", "date", "issued_by", "link", "copied_on"):
                if not getattr(rec, field):
                    problems.append(f"{rec.filename}: missing label {field!r}")
            if not _normalize(rec.body):
                problems.append(f"{rec.filename}: empty verbatim body")
        return problems

    # ----- citation-by-construction ------------------------------------------
    def cite(self, slug: str, passage: str, state: str = CONFIRMED) -> Citation:
        """Return a Citation for ``passage`` IF it is verbatim-present in ``slug``.

        This is the load-bearing guarantee: the engine can only state a rule it can quote from
        the golden copy. A passage that is not present is a build/logic bug, surfaced loudly.
        """
        rec = self.get(slug)
        if not rec.contains(passage):
            raise ValueError(
                f"Citation integrity failure: passage not found verbatim in {rec.filename}:\n"
                f"  wanted: {passage[:120]!r}"
            )
        return Citation(
            state=state,
            quote=_normalize(passage),
            source_name=rec.name,
            source_file=f"golden-copy/sources/{rec.filename}",
            url=rec.link,
            capture_date=rec.copied_on or rec.date,
        )


def _strip_slug(slug: str) -> str:
    slug = slug.strip()
    if slug.endswith(".md"):
        slug = slug[:-3]
    if slug.startswith("source-"):
        slug = slug[len("source-"):]
    return slug


# A single shared instance is convenient and cheap (files are small, read once).
_DEFAULT: Optional[GoldenCopy] = None


def default_golden_copy() -> GoldenCopy:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = GoldenCopy()
    return _DEFAULT
