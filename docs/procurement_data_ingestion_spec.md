# Procurement Data Ingestion Spec — BUILD-NOW Connectors

Companion to the `## Data connectors — verified BUILD-NOW set` entry in
`BACKLOG.md`. This is the engineering blueprint for the six connectors graded
BUILD-NOW on 2026-07-03.

## Verification status (read first)

Dataset IDs and API existence were confirmed via the Socrata catalog and
official documentation. **Live HTTP GETs, exact response schemas, and verbatim
license text were NOT executed** (the research environment blocks outbound
HTTPS). Every 4x4 ID, field list, and rate limit below is **confirm-on-first-GET**
before you code against it. Items still needing a human/legal read are collected
in "Open questions" at the end.

## Product truth (state this in the product, not just the backlog)

- **SAM.gov is the ONLY BUILD-NOW source with live solicitations AND actual
  bid/RFP document links through an API** (`resourceLinks`). It is **federal
  only** — no NY state/local tenders.
- **NYC Open Data** gives **live procurement notices** (City Record Online), but
  **generally not the full bid package** — the documents live in PASSPort.
- **Open Data NY** gives **historical authority / vendor / procurement data**,
  **not live RFP documents**.
- **Checkbook NYC** gives **NYC contract/spending history**, not solicitations or
  documents.
- **USAspending** gives **federal award/spending history**, not solicitations or
  documents.
- **NY Senate Open Legislation** gives **law/compliance monitoring**, not tenders.

Net: this set delivers **federal live tenders+documents (SAM)**, **federal award
intel (USAspending)**, **NY/NYC history + vendor + notice metadata (Socrata x2,
Checkbook)**, and **statute monitoring (Open Legislation)**. It does **not**
deliver NY/NYC live RFP documents — see "NY/NYC RFP document gap and workaround."

---

## 1. NYC Open Data (Socrata / SODA)

1. **Source name:** NYC Open Data (Socrata SODA API), publisher City of New York.
2. **Endpoint(s):**
   - Rows: `https://data.cityofnewyork.us/resource/{4x4}.json` (also `.csv`, `.geojson`)
   - Metadata/license: `https://data.cityofnewyork.us/api/views/{4x4}.json`
   - Discovery: `https://api.us.socrata.com/api/catalog/v1?domains=data.cityofnewyork.us&q=procurement`
   - Core 4x4s: City Record Online `dg92-zbpx`; Recent Contract Awards
     `qyyg-4tf5`; Bid Tabulations (historical) `9k82-ys7w`; M/WBE-LBE-EBE
     Certified list `ci93-uc8s`. **AVOID `3khw-qi8f`** (Current Solicitations —
     private/deprecated).
3. **Auth requirements:** none to read; register a **free Socrata app token**
   (`X-App-Token` header or `$$app_token=` param) to lift rate limits. No token =
   throttled shared pool.
4. **Query examples:**
   - `GET https://data.cityofnewyork.us/resource/dg92-zbpx.json?$limit=1000&$order=:id`
   - Incremental: `?$where=:updated_at > '2026-07-01T00:00:00'&$order=:updated_at`
   - Filter: `?$where=agencyname='Citywide Administrative Services'&$limit=5`
5. **Paging strategy:** keyset over `:id` (preferred) or `$limit`/`$offset`
   (page size <= 50000; avoid deep `$offset` — it degrades). For incremental
   loads page on `:updated_at`. Persist the high-water `:updated_at` per dataset.
6. **Refresh cadence:** CRO `dg92-zbpx` ~daily; Recent Awards `qyyg-4tf5` weekly
   (Fridays, ~30-day window); Bid Tabs `9k82-ys7w` frozen (post-PASSPort) — one
   backfill then stop; Certified list `ci93-uc8s` monthly.
7. **Deduplication key:** business key first — CRO notice ID / `qyyg-4tf5` award
   PIN / vendor account number — with Socrata `:id` as fallback. Store `:id`.
8. **Fields to store:** the row + `:id`, `:updated_at`, source 4x4, ingest ts.
   CRO: hunt the 37-col schema for notice ID, notice type (solicitation vs
   award), agency, section, start/end dates, and any notice-URL / full-body
   column (schema ref: `github.com/CityOfNewYork/CROL-Schema`).
9. **Live RFQs/RFPs:** YES (CRO solicitation notices — notice, not full package).
10. **Historical awards/spending:** YES (CRO award notices; `qyyg-4tf5` recent
    awards; `9k82-ys7w` historical bid pricing).
11. **Raw bid/RFP documents:** NO — metadata/notices only; documents in PASSPort.
12. **Raw-document storage rule:** store **metadata + deep links** only.
13. **Legal/reuse status:** VERIFIED OPEN — *"Open Data belongs to all New
    Yorkers. There are no restrictions on the use of Open Data"* (NYC Open Data
    FAQ). Attribution of source/version/modifications + AS-IS per Admin Code
    §23-504 (confirm ToS verbatim — see Open questions).
14. **Failure modes:** dataset flipped private (as `3khw-qi8f` was); column/schema
    drift; 4x4 retirement; `429` rate limit; deep-`$offset` slowdowns; CRO body
    text may be truncated or point out to `a856-cityrecord.nyc.gov`.
15. **MVP priority:** **P0** — CRO is the live NY-market notice backbone.

---

## 2. Open Data NY (Socrata / SODA)

1. **Source name:** Open Data NY (Socrata SODA API), publisher State of New York.
2. **Endpoint(s):**
   - Rows: `https://data.ny.gov/resource/{4x4}.json`
   - Metadata/license: `https://data.ny.gov/api/views/{4x4}.json`
   - Discovery: `https://api.us.socrata.com/api/catalog/v1?domains=data.ny.gov&q=procurement`
   - Procurement reports (historical, ABO/PARIS): State Authorities `ehig-g5x3`,
     Local Authorities `8w5p-k45m`, IDA `p3p6-xqr5`, LDC `d84c-dk28`, MTA
     procurement `gpsc-qqsz`; forward-lead to inspect: "Eye On The Future — MTA
     Contract Solicitations" `e3e7-qwer`. Vendor enrichment: DOS Corporations
     `63wc-4exh` (+ `ekwr-p59j`, `2tms-hftb`); Certified DBEs `pfeu-dsx6`.
3. **Auth requirements:** same as NYC — free app token optional for rate limits.
4. **Query examples:**
   - `GET https://data.ny.gov/resource/ehig-g5x3.json?$limit=1000&$order=:id`
   - `GET https://data.ny.gov/resource/pfeu-dsx6.json?$where=certification_type='DBE'&$limit=50`
   - License check: `GET https://data.ny.gov/api/views/ehig-g5x3.json` → read `.license`, `.rights`, `.attribution`.
5. **Paging strategy:** identical to NYC (keyset on `:id`; incremental on
   `:updated_at`; `$limit` <= 50000).
6. **Refresh cadence:** procurement reports **annual** (ABO/PARIS filings) —
   quarterly poll is ample; DOS corporations ~daily/weekly; DBE directory monthly.
7. **Deduplication key:** report row natural key (authority + fiscal year +
   contract/transaction id) or `:id`; DOS = DOS ID; DBE = firm/cert id.
8. **Fields to store:** procurement — authority, fiscal year, vendor, contract
   description, award/contract value, category; DOS — entity name, DOS ID, status,
   filing dates, address; DBE — firm, cert type/status, NAICS/categories. Plus
   `:id`, `:updated_at`, source 4x4, ingest ts.
9. **Live RFQs/RFPs:** NO (historical transactions). `e3e7-qwer` is the only
   possible forward-looking row — inspect before claiming live coverage.
10. **Historical awards/spending:** YES (procurement transactions >= $5,000, 8
    fiscal years).
11. **Raw bid/RFP documents:** NO.
12. **Raw-document storage rule:** store **metadata** (no documents exist here).
13. **Legal/reuse status:** Open NY license — **READ / RESOLVED 2026-07-03.**
    Public data.ny.gov datasets are usable for commercial/reuse purposes through
    the official Open Data NY / Socrata access path, subject to the license
    conditions: (1) the State gives no warranty on data accuracy or completeness;
    (2) users rely on the data at their own risk; (3) users indemnify / hold the
    State harmless; (4) downstream product pages should include a data-accuracy
    disclaimer + source/date attribution. The license is revocable. Practical
    build impact: safe to build on now; surface the disclaimer + attribution in
    any vendor-facing view that renders this data.
14. **Failure modes:** annual-only freshness (stale mid-year); PARIS reporting
    lag/gaps; schema differences across authority-type reports; 4x4 drift;
    `e3e7-qwer` may be a viz/derived view, not a base dataset.
15. **MVP priority:** **P1** (procurement/vendor/DBE history + enrichment).

---

## 3. SAM.gov Opportunities API

1. **Source name:** SAM.gov Get Opportunities Public API (GSA).
2. **Endpoint(s):**
   - Search: `https://api.sam.gov/opportunities/v2/search`
   - Document download (per `resourceLinks` entry):
     `https://api.sam.gov/opportunities/resources/files/{fileId}/download?api_key={KEY}`
   - Docs: `https://open.gsa.gov/api/get-opportunities-public-api/`
3. **Auth requirements:** **API key required** (free SAM.gov account; request key
   on the Account Details page). Rate limits are role-based and **strict** for
   personal/non-federal keys — plan windowed, cached pulls, not live per-user.
4. **Query examples:**
   - `GET .../v2/search?api_key={KEY}&postedFrom=01/01/2026&postedTo=07/03/2026&ptype=o&limit=1000&offset=0`
     (`ptype`: `p` presol, `o` solicitation, `k` combined, `r` sources-sought,
     `a` award). Add `naics=`, `state=NY`, `ncode=`, `title=` as needed.
   - Documents: read `resourceLinks[]` on each record, then GET each with the key.
5. **Paging strategy:** `limit` (max 1000) + `offset`; **`postedFrom`/`postedTo`
   window must be <= 1 year** — iterate date windows, then offset within each.
   Incremental by modified/posted date; persist high-water posted date.
6. **Refresh cadence:** **daily** (new + amended solicitations); pull the last
   1–3 days by posted/modified date each run.
7. **Deduplication key:** **`noticeId`** (globally unique). `solicitationNumber`
   is NOT unique across amendments — key on `noticeId`, group by
   `solicitationNumber` for the amendment chain.
8. **Fields to store:** `noticeId`, `title`, `solicitationNumber`, `type`/
   `baseType`, `postedDate`, `responseDeadLine`, `naicsCode`,
   `classificationCode`, `active`, `organizationHierarchy`/office,
   `placeOfPerformance`, `uiLink`, and `resourceLinks[]` (+ downloaded files).
9. **Live RFQs/RFPs:** YES (federal).
10. **Historical awards/spending:** award NOTICES yes (`ptype=a`); not dollar-level
    spend (use USAspending for that).
11. **Raw bid/RFP documents:** **YES** — via `resourceLinks` (when present).
12. **Raw-document storage rule:** **STORE raw documents** — public domain; safe
    to retain + index + reuse.
13. **Legal/reuse status:** U.S. federal government work = public domain
    (the D&B/Entity-data carve-out affects the Entity API, not Opportunities).
14. **Failure modes:** API-key rate limits (`429`/`403`); 1-year window cap;
    `resourceLinks` sometimes empty or gated; strict `MM/dd/yyyy` date format;
    large attachments; amendment supersedes (keep latest per solicitation).
15. **MVP priority:** **P0** — the only live-solicitation + document API.

---

## 4. USAspending API

1. **Source name:** USAspending.gov API (U.S. Treasury).
2. **Endpoint(s):**
   - Award search (POST): `https://api.usaspending.gov/api/v2/search/spending_by_award/`
   - Bulk: `https://api.usaspending.gov/api/v2/bulk_download/awards/`
   - Docs: `https://api.usaspending.gov/docs/endpoints`
3. **Auth requirements:** **none** (open, no key).
4. **Query examples:**
   - `POST /api/v2/search/spending_by_award/` with JSON body:
     `{"filters":{"award_type_codes":["A","B","C","D"],"time_period":[{"start_date":"2025-01-01","end_date":"2026-07-03"}],"recipient_search_text":["ACME"]},"fields":["Award ID","Recipient Name","Award Amount","Awarding Agency","Period of Performance Start Date"],"page":1,"limit":100,"sort":"Award Amount","order":"desc"}`
5. **Paging strategy:** `page` + `limit` (max **100**/page) — expect many pages;
   for large extracts use the `bulk_download` endpoint (async → file URL).
6. **Refresh cadence:** weekly/monthly (award data lags; nightly DB refresh but
   reporting latency). Incremental by `Last Modified Date` filter.
7. **Deduplication key:** `generated_internal_id` / `generated_unique_award_id`
   (stable award identifier); fallback PIID/FAIN + agency.
8. **Fields to store:** Award ID, Recipient Name + UEI, Award Amount, awarding /
   funding agency + sub-agency, NAICS, PSC, award type, period of performance,
   place of performance.
9. **Live RFQs/RFPs:** NO.
10. **Historical awards/spending:** YES (deep federal award/spend history).
11. **Raw bid/RFP documents:** NO.
12. **Raw-document storage rule:** store **metadata** (CC0 — reuse freely).
13. **Legal/reuse status:** *"The USAspending API License is CC0 1.0 Universal."*
14. **Failure modes:** 100/page cap → pagination volume; POST body schema changes;
    data latency vs "live"; throttling on aggressive crawls; endpoint version
    changes.
15. **MVP priority:** **P2** — federal incumbent/competitor enrichment.

---

## 5. Checkbook NYC API

1. **Source name:** Checkbook NYC API (NYC Comptroller).
2. **Endpoint(s):**
   - Contract API: `https://www.checkbooknyc.com/contract-api`
     (POST XML to the Checkbook API endpoint); also spending/budget/payroll APIs.
   - Open source: `github.com/NYCComptroller/Checkbook`.
3. **Auth requirements:** **none**, but **rate limit: "1 concurrent session per
   IP and at a rate of 1 per second."**
4. **Query examples (XML over HTTP POST):**
   ```xml
   <request>
     <type_of_data>Contracts</type_of_data>
     <records_from>1</records_from>
     <max_records>20000</max_records>
     <search_criteria>
       <criteria><name>fiscal_year</name><type>value</type><value>2026</value></criteria>
     </search_criteria>
     <response_columns>
       <column>contract_id</column><column>vendor_name</column>
       <column>agency_name</column><column>current_amount</column>
     </response_columns>
   </request>
   ```
5. **Paging strategy:** `records_from` + `max_records` (<= **20000**/call); loop
   incrementing `records_from` until a short page returns. Respect 1 req/sec.
6. **Refresh cadence:** weekly/monthly for contracts (registration cadence);
   daily possible for payments. Incremental by fiscal year + status change.
7. **Deduplication key:** `contract_id` (Checkbook contract identifier); fallback
   agency + contract PIN.
8. **Fields to store:** `contract_id`, agency, vendor (+ vendor id), purpose/
   description, `current_amount`/`original_amount`, spend-to-date, start/end
   dates, status, category, M/WBE flags if present.
9. **Live RFQs/RFPs:** NO.
10. **Historical awards/spending:** YES (deep NYC contract + spend + vendor-payment
    history).
11. **Raw bid/RFP documents:** NO.
12. **Raw-document storage rule:** store **metadata** (no documents exist here).
13. **Legal/reuse status:** public transparency API (open-source codebase), but
    **redistribution terms REVIEW PENDING** (Open questions) — verify before
    commercial redistribution.
14. **Failure modes:** XML parsing/verbosity; 1 req/sec throttle makes bulk slow
    (design a batched, cached ingester); 20k-record cap paging; single-session
    concurrency limit; schema changes.
15. **MVP priority:** **P1** — historical award/spend spine + vendor profiles.

---

## 6. NY Senate Open Legislation API

1. **Source name:** NY Senate Open Legislation API (NY State Senate).
2. **Endpoint(s):**
   - Law text: `https://legislation.nysenate.gov/api/3/laws/{lawId}?key={KEY}`
     (e.g. `.../laws/EXC` for Executive Law; append `/{locationId}` for a section).
   - Bill updates: `https://legislation.nysenate.gov/api/3/bills/updates/{from}/{to}?key=`
   - Search: `https://legislation.nysenate.gov/api/3/bills/search?term=procurement&key=`
   - Docs: `https://legislation.nysenate.gov/static/docs/html/index.html`
3. **Auth requirements:** **free API key** (self-service signup; `key=` param).
4. **Query examples:**
   - `GET .../api/3/laws/EXC?key={KEY}` (Executive Law tree)
   - `GET .../api/3/laws/EXC/314?key={KEY}` (the §314 node — MWBE cert validity)
   - `GET .../api/3/bills/updates/2026-01-01T00:00:00/2026-07-03T00:00:00?key={KEY}`
5. **Paging strategy:** `limit`/`offset` on list/search endpoints (limit <= 1000);
   law documents return as a tree — walk `documents`/`children`.
6. **Refresh cadence:** statute monitoring weekly/on-demand; bills daily during
   session. Change-detect via the bill `updates` window or by diffing law nodes'
   `activeDate`.
7. **Deduplication key:** `lawId` + `locationId` (law sections); bills =
   `printNo` + `session`.
8. **Fields to store:** for compliance/freshness — `lawId`, `locationId`, title,
   `text`, `activeDate`, published date. Store law text + `activeDate` to diff
   against the golden copy (e.g. the §314 sunset/version watch).
9. **Live RFQs/RFPs:** NO.
10. **Historical awards/spending:** NO.
11. **Raw bid/RFP documents:** NO.
12. **Raw-document storage rule:** store **statute text** (U.S. law is not
    copyrightable). NB: the explicit **data-payload** license is unverified
    (their open-source posture is worded around source code) — Open questions.
13. **Legal/reuse status:** free key; *"Because public funds are used ... they
    return the source code to the public domain"* (code); statutory text itself
    is public/non-copyrightable.
14. **Failure modes:** key rate limits; law versioning (`activeDate`) confusion
    across amendments; large law trees; API v3 changes.
15. **MVP priority:** **P2** — powers compliance monitoring + golden-copy
    freshness, not tender discovery.

---

## Storage rule (rights-driven, applies across all connectors)

- **Store raw documents ONLY from SAM.gov public `resourceLinks`** — federal
  public domain; safe to retain, index, and reuse.
- **Store metadata + deep links** for NYC Open Data, Open Data NY, and Checkbook
  NYC (open/again-verify reuse; they carry no documents anyway).
- **Do NOT store NYSCR or PASSPort documents** unless the vendor uploads them or
  written permission exists (NYSCR is ESD-proprietary; PASSPort has no sanctioned
  reuse feed).
- **Vendor-uploaded documents** live **only inside that vendor's workspace** and
  are **not** reused for a general commercial document database unless rights are
  confirmed. Extract per-vendor; retain the extracted checklist/requirements, not
  the restricted raw source, for any cross-vendor/commercial use.

---

## NY/NYC RFP document gap and workaround

The gap: no BUILD-NOW source exposes the **full NY/NYC bid package** through a
reusable API. SAM covers federal documents; NY/NYC live documents sit in NYSCR
(locked) and PASSPort (viewer-only). Workaround pipeline that stays inside the
rights boundary:

1. **Detect the opportunity** from open metadata — NYC via City Record Online
   (`dg92-zbpx`); NY-state via NYSCR listing metadata / agency pages (metadata
   only, no copying of protected bodies).
2. **Extract the identifier** — EPIN / RFx / PIN / solicitation number from the
   open notice.
3. **Deep-link the vendor** to the authoritative source (PASSPort Public RFx,
   NYSCR listing, or the agency page) to obtain the full package themselves.
4. **Vendor uploads or forwards** the bid package into their own workspace
   (own-use; transient — mirrors the cleared "own-use" case in the ToS gates).
5. **AI analyzes the documents for that vendor** (requirements checklist, gaps,
   clarification questions) — scoped to the vendor's workspace.
6. **Store the extracted checklist/requirements**, NOT the restricted raw
   documents, for anything beyond that vendor's session. No resale of source
   documents; no shared commercial corpus of restricted bodies.

This gives a full end-to-end analysis experience without the engine ever
retaining or redistributing NYSCR/PASSPort-protected document bodies.

---

## Resolved (2026-07-03)

- **Open NY license — RESOLVED.** The Open NY license was read on 2026-07-03. It
  confirms public data.ny.gov datasets are usable for commercial/reuse purposes
  through the official Open Data NY / Socrata access path, subject to conditions.
  The license is revocable and includes important conditions/disclaimers:
  (1) the State gives no warranty about data accuracy or completeness;
  (2) users rely on the data at their own risk;
  (3) users indemnify / hold the State harmless;
  (4) downstream product pages should include a data-accuracy disclaimer and
  source/date attribution.
  Build impact: Open Data NY is cleared for build; carry the disclaimer +
  attribution in any vendor-facing view rendering this data.

## Open questions (block promotion / must be resolved by a human)

1. **Checkbook NYC redistribution terms.** Verify the exact reuse/redistribution
   terms before any commercial redistribution of Checkbook-sourced data.
2. **PASSPort sanctioned feed.** Ask NYC MOCS whether a sanctioned bulk feed / API
   exists (vs. web viewer + manual export) before depending on any undocumented
   endpoint.
3. **NYSCR licensing.** Determine whether a data-licensing / data-access
   arrangement is possible through ESD (written permission is "case-by-case at the
   sole discretion of the Department") — a BD/legal path, never a scrape.
