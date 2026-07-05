# SOURCE TEXT — NY GCN Law § 25-A (Public holiday, Saturday or Sunday in statutes; extension of time where performance of act is due on Saturday, Sunday or public holiday)

- **Name:** Public holiday, Saturday or Sunday in statutes; extension of time where performance of act is due on Saturday, Sunday or public holiday
- **Date:** current revision per NY Open Legislation (API activeDate 2014-09-22; confirm exact revision on human read)
- **Issued by:** New York State Legislature; published via NY State Senate Open Legislation
- **Link (permanent identifier):** https://www.nysenate.gov/legislation/laws/GCN/25-A
- **Copied exactly on:** 2026-07-05
- **API activeDate:** 2014-09-22
- **Capture method:** openleg-api-v3
- **Covers:** full section
- **Verified:** 2026-07-05 — owner read against nysenate.gov/legislation/laws/GCN/25-A + two independent fetch cross-checks (three-way confirmed); both numbered subdivisions present. Captured via the sanctioned statute-capture workflow (openleg-api-v3).
- **Freshness-registered:** yes (data/config/statute_capture_registry.json)

> Captured via the sanctioned GitHub Actions statute-capture workflow (.github/workflows/statute-capture.yml) because interactive Claude Code sessions are egress-blocked from legislation.nysenate.gov. The body below is the verbatim Open Legislation API `text` field, reflowed to the house one-line-per-subdivision style (words unchanged). Human-verified against the primary source on 2026-07-05 (owner read + two independent fetch cross-checks); promoted to golden.

---

## STATE TEXT (verbatim)

§ 25-a. Public holiday, Saturday or Sunday in statutes; extension of time where performance of act is due on Saturday, Sunday or public holiday. 1. When any period of time, computed from a certain day, within which or after which or before which an act is authorized or required to be done, ends on a Saturday, Sunday or a public holiday, such act may be done on the next succeeding business day and if the period ends at a specified hour, such act may be done at or before the same hour of such next succeeding business day, except that where a period of time specified by contract ends on a Saturday, Sunday or a public holiday, the extension of such period is governed by section twenty-five of this chapter.
2. Where time is extended by virtue of the provisions of this section, such extended time shall not be included in the computation of interest, except that when the period is specified as a number of months, such extended time shall be included in the computation of interest.

---

## ANNOTATIONS (engine commentary — not part of the rule)

> **SUBDIVISION COUNT — capture-report artifact, not missing text.** The
> 2026-07-05 capture report recorded "1 subdivision" for this section. That was a
> **line-start counting artifact**: reflow parked subdivision **1.** on the same
> line as the "§ 25-a." heading, so the metric (which matched markers only at a
> line start) saw only the line-start "2." The verbatim STATE TEXT above is
> **complete and contains BOTH numbered subdivisions**:
> - **1.** — an act due on a Saturday, Sunday or public holiday may be done on
>   the next succeeding business day (contract periods are governed by § 25);
> - **2.** — extended time is excluded from the computation of interest, **except**
>   where the period is specified as a number of months (then it is included).
> The metric was corrected on 2026-07-05 to also detect a subdivision marker on
> the section-heading line; this section now reads 2/2. Human read on 2026-07-05
> confirmed both subdivisions verbatim.

---

## CITATIONS THIS TEXT POINTS TO (tagged for traceability — not part of the rule)

- GCN § 25 — "the extension of such period is governed by section twenty-five of this chapter" (subd. 1 cross-reference for contract periods)
- GCN § 24 — defines "public holiday," the trigger for the next-business-day extension in subd. 1 (golden-copy/sources/source-gcn-24-public-holidays.md)
- Computation of interest (subd. 2) — interacts with prompt-payment interest under SFL Art. 11-A / GFO XII.5.I; the month-based-period exception is preserved verbatim above
