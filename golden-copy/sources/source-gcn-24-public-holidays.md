# SOURCE TEXT — NY GCN Law § 24 (Public holidays; half-holidays)

- **Name:** Public holidays; half-holidays
- **Date:** current revision per NY Open Legislation (API activeDate 2020-10-16; confirm exact revision on human read)
- **Issued by:** New York State Legislature; published via NY State Senate Open Legislation
- **Link (permanent identifier):** https://www.nysenate.gov/legislation/laws/GCN/24
- **Copied exactly on:** 2026-07-05
- **API activeDate:** 2020-10-16
- **Capture method:** openleg-api-v3
- **Covers:** full section
- **Verified:** 2026-07-05 — owner read against nysenate.gov/legislation/laws/GCN/24 + two independent fetch cross-checks (three-way confirmed). Captured via the sanctioned statute-capture workflow (openleg-api-v3).
- **Freshness-registered:** yes (data/config/statute_capture_registry.json)

> Captured via the sanctioned GitHub Actions statute-capture workflow (.github/workflows/statute-capture.yml) because interactive Claude Code sessions are egress-blocked from legislation.nysenate.gov. The body below is the verbatim Open Legislation API `text` field, reflowed to the house one-line-per-subdivision style (words unchanged). Human-verified against the primary source on 2026-07-05 (owner read + two independent fetch cross-checks); promoted to golden.

---

## STATE TEXT (verbatim)

§ 24. Public holidays; half-holidays. The term public holiday includes the following days in each year: the first day of January, known as New Year's day; the third Monday of January, known as Dr. Martin Luther King, Jr. day; the twelfth day of February, known as Lincoln's birthday; the third Monday in February, known as Washington's birthday; the last Monday in May, known as Memorial day; the second Sunday in June, known as Flag day; the nineteenth day of June, known as Juneteenth; the fourth day of July, known as Independence day; the first Monday in September, known as Labor day; the second Monday in October, known as Columbus day; the eleventh day of November, known as Veterans' day; the fourth Thursday in November, known as Thanksgiving day; and the twenty-fifth day of December, known as Christmas day, and if any of such days except Flag day is Sunday, the next day thereafter; each general election day, and each day appointed by the president of the United States or by the governor of this state as a day of general thanksgiving, general fasting and prayer, or other general religious observances. The term half-holiday includes the period from noon to midnight of each Saturday which is not a public holiday.

---

## ANNOTATIONS (engine commentary — not part of the rule)

> **GRADE — "legal holidays" (GFO XII.5.I) ↔ "public holiday" (GCN §24) = L (legal-interpretive).**
> GFO XII.5.I (prompt-payment interest) suspends/pauses the payment clock on
> "legal holidays," while this section defines "**public holiday**." Treating the
> GCN §24 public-holiday list as the operative set of "legal holidays" for the
> payment clock is the standard reading, but it is an **interpretive mapping**
> between two differently-worded sources, not a mechanical identity. On the
> attorney-review list (BACKLOG). PR 2's design bounds the practical risk: the
> HolidayCalendarProvider is source-backed and **fail-closed** (it refuses to
> compute rather than guess), and the clock is VERIFY-gated — so a contested
> holiday mapping surfaces for review instead of silently mis-dating a deadline.
>
> **DYNAMIC HOLIDAYS.** The section's list is not fully static: it includes
> "each general election day, and each day appointed by the president of the
> United States or by the governor of this state" as a day of thanksgiving,
> fasting/prayer, or other general religious observance. Those
> proclamation-appointed days cannot be enumerated ahead of time — a
> source-backed calendar must treat them as an open class, not omit them. This
> caveat is preserved verbatim in the STATE TEXT above and must not be dropped
> when the holiday set is operationalized.

---

## CITATIONS THIS TEXT POINTS TO (tagged for traceability — not part of the rule)

- GCN § 25-a — extension of time where an act is due on a Saturday, Sunday or **public holiday** (consumes this section's public-holiday definition; golden-copy/sources/source-gcn-25-a-deadline-extension.md)
- GCN § 25 — extension of time for contract periods (companion to § 25-a; referenced there)
- GFO XII.5.I Prompt Payment Interest — uses "legal holidays" for the payment clock (see the L-grade mapping note above; golden-copy/sources/source-xii-5-i-prompt-payment-interest.md)
- Proclamation-appointed days: days appointed by the President of the United States or the Governor of New York (an open class, not statically enumerable)
