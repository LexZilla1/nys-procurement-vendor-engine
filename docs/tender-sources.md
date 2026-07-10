# NY State Tender Source Registry

A record of where New York **State** solicitations (IFBs, RFPs, RFQs) and their
documents can be found — so we always know where to go and check. Use it to
build validation corpora and to reason about coverage.

- **Last verified:** 2026-07-10
- **Method:** three parallel research passes over the official indexes (NY.gov
  agency directory, the Authorities Budget Office directory, OGS, OSC).
  **Verification is uneven and is stated per row.** Only rows marked
  `fetched ✓` were retrieved directly (HTTP 200) in this session. Rows marked
  `UNVERIFIED (index)` were **not** fetched — their URL was seen in the live
  web-search index but never opened, because this session's network proxy
  blocked most `.ny.gov`/`.edu` hosts (an egress-policy 403, not a site
  failure). Rows marked `403 (live)` were attempted but blocked by that proxy.
  **Treat every `UNVERIFIED (index)` and `403 (live)` row as unconfirmed:
  re-verify its live-fetchability on an open network before relying on it or
  crawling it.**
- **Verification legend:** `fetched ✓` = retrieved directly, confirmed.
  `UNVERIFIED (index)` = **not fetched, unverified** — URL seen in the search
  index only. `403 (live)` = fetch attempted, proxy-blocked, not confirmed.
- **Scope rule:** State agencies, State public authorities, SUNY/CUNY. NYC and
  municipal sources are intentionally excluded (out of the engine's verified
  jurisdiction). Port Authority is **bi-state** and flagged as such.

## How the engine treats each class

| Class | Engine routing | Why |
|---|---|---|
| **STATE_AGENCY** | Full engine (SFL Art. 11 golden copy applies) | Verified rulebook covers state-agency procurement |
| **AUTHORITY** | HUMAN_REVIEW | Public Authorities Law §2879 not in golden copy |
| **SUNY_CUNY** | HUMAN_REVIEW | Education Law not in golden copy |

So **Section A is your in-scope corpus source**; Sections B–C are catalogued for
completeness and future expansion, but tenders from them currently route to a
human.

## Docs-access legend

| Tag | Meaning |
|---|---|
| `DIRECT_PDF` | Solicitation documents download straight from the site — **best for corpus building** |
| `PORTAL` | Must register/log in to an eProcurement portal (Ariba, Bonfire, BidNet, Bonfire, etc.) to get docs |
| `NYSCR_ONLY` | Documents only via the NYS Contract Reporter (gated — see §D) |
| `DISCOVERY_ONLY` | Page lists/points to opportunities but does not host the documents |
| `AWARDS_ONLY` | Awarded-contract / spending data, not open solicitations |
| `GATED` | Login / registration required |
| `email-request` | Documents obtained by emailing the agency |

---

## ⭐ Quick start — cleanest in-scope document sources

For validation-corpus building, start here (all STATE_AGENCY, all
direct-download). Pull PDFs into a scratch folder **outside the repo**; record
each one's source URL + download date; never commit the PDFs.

1. **OGS Bid Calendar** — https://ogs.ny.gov/procurement/bid-opportunities *(the IFB 23447 source; highest volume)*
2. **ITS — Open Procurements** — https://its.ny.gov/current-open-procurement-opportunities
3. **Dept. of Health — Funding** — https://www.health.ny.gov/funding/
4. **OMH — RFPs** — https://omh.ny.gov/omhweb/rfp/
5. **OASAS — Procurement** — https://oasas.ny.gov/procurement
6. **DOCCS — Procurement** — https://doccs.ny.gov/procurement-opportunities
7. **OTDA — Procurement/Bid** — https://otda.ny.gov/contracts/procurement-bid.asp

---

## A. Executive-branch State agencies — `STATE_AGENCY` (full engine scope)

| Agency | Procurement/bid page | Verified | Docs access | Notes |
|---|---|---|---|---|
| Office of General Services (OGS) — Procurement Services | https://ogs.ny.gov/procurement/bid-opportunities | fetched ✓ | PORTAL→DIRECT | Statewide centralized-contract bid calendar; links to solicitation docs. Highest-volume single source. Awards: /procurement/bid-opening-results |
| Dept. of Transportation (NYSDOT) | https://www.dot.ny.gov/doing-business/opportunities | UNVERIFIED (index) | PORTAL + DIRECT_PDF | Construction lettings via Electronic Bid System; consultant/A-E active solicitations. High volume |
| Dept. of Health (DOH) | https://www.health.ny.gov/funding/ | UNVERIFIED (index) | DIRECT_PDF | RFO/RFA/RFP/IFB/RFI; per-RFP pages under /funding/rfp/, forms at /funding/forms/. High volume |
| Dept. of Environmental Conservation (DEC) | https://dec.ny.gov/about/doing-business | UNVERIFIED (index) | NYSCR_ONLY (mixed) | Advertises ≥$50k in NYSCR; own-site docs mainly remediation construction |
| Office of Information Technology Services (ITS) | https://its.ny.gov/current-open-procurement-opportunities | UNVERIFIED (index) | DIRECT_PDF | Large IT buyer; RFP PDFs at its.ny.gov/system/files/. Runs many statewide/agency IT buys |
| Office of Mental Health (OMH) | https://omh.ny.gov/omhweb/rfp/ | UNVERIFIED (index) | DIRECT_PDF | RFP/RFI index + /upcoming-procurement-opportunities.html. High volume |
| Office for People With Developmental Disabilities (OPWDD) | https://opwdd.ny.gov/procurement-opportunities | UNVERIFIED (index) | DIRECT_PDF | Per-solicitation subpages; some responses via SFS |
| Dept. of Corrections & Community Supervision (DOCCS) | https://doccs.ny.gov/procurement-opportunities | UNVERIFIED (index) | DIRECT_PDF | IFB/RFP pages + PDFs. Corcraft (corcraft.ny.gov/procurement-opportunities) is a related sub-entity |
| Office of Children & Family Services (OCFS) | https://ocfs.ny.gov/main/contracts/funding/ | UNVERIFIED (index) | DIRECT_PDF | Funding/RFQ with bid sheets, OCFS-4822 lobbying forms; awards at /main/contracts/awards/ |
| Office of Temporary & Disability Assistance (OTDA) | https://otda.ny.gov/contracts/procurement-bid.asp | UNVERIFIED (index) | DIRECT_PDF | Dated IFB/RFQ/RFP list, regularly updated |
| Dept. of Labor (DOL) | https://dol.ny.gov/contract-bid-grant-opportunities | UNVERIFIED (index) | DIRECT_PDF | Contract/bid/grant; RFP PDFs at dol.ny.gov/system/files/ |
| Parks, Recreation & Historic Preservation (OPRHP) | https://parks.ny.gov/business/procurement-opportunities.aspx | UNVERIFIED (index) | DIRECT_PDF | IFB/RFQ PDFs; per-procurement bidders list by email; capital/concessions via NYSCR |
| Dept. of Agriculture & Markets | https://agriculture.ny.gov/funding-opportunities | UNVERIFIED (index) | DIRECT_PDF | RFP/IFB with PDFs, incl. State Fair procurements |
| Dept. of Taxation & Finance | https://www.tax.ny.gov/about/procure/current-bid-opportunities.htm | UNVERIFIED (index) | DIRECT_PDF | Current bids with electronic bid documents |
| Division of State Police (NYSP) | https://troopers.ny.gov/procurement | UNVERIFIED (index) | NYSCR_ONLY | Contract Unit posts to NYSCR; limited own-site hosting |
| Dept. of Financial Services (DFS) | https://www.dfs.ny.gov/procurement | UNVERIFIED (index) | DIRECT_PDF | RFP/RFI PDFs at dfs.ny.gov/system/files/. Inquiries RFP@dfs.ny.gov |
| Dept. of State (DOS) | https://dos.ny.gov/funding-bid-opportunities | UNVERIFIED (index) | DIRECT_PDF | RFP/RFQ/RFA PDFs; forms at /procurement-forms. Best-value awards |
| Division of Criminal Justice Services (DCJS) | https://www.criminaljustice.ny.gov/ofpa/index.htm | UNVERIFIED (index) | DIRECT_PDF + PORTAL | Funding opps under /ofpa/pdfdocs/; grants portal grants.criminaljustice.ny.gov |
| Division of Homeland Security & Emergency Services (DHSES) | https://www.dhses.ny.gov/grants | UNVERIFIED (index) | PORTAL | Federal preparedness + state grants; mostly NOFOs/E-Grants, fewer commodity IFBs |
| Office of Addiction Services & Supports (OASAS) | https://oasas.ny.gov/procurement | UNVERIFIED (index) | DIRECT_PDF | Numbered RFPs w/ per-RFP pages + PDFs. High volume |
| Office for the Aging (NYSOFA) | https://aging.ny.gov/procurement | UNVERIFIED (index) | PORTAL + DIRECT_PDF | RFA listings (e.g. Age-Friendly Planning). Lower volume |
| Dept. of Public Service (DPS) | https://dps.ny.gov/procurements | UNVERIFIED (index) | email-request | Lists procurements in process; docs by emailed request. Low volume |
| Gaming Commission | https://gaming.ny.gov/procurement | UNVERIFIED (index) | DIRECT_PDF | RFP PDFs incl. large Lottery Operations RFP; also NYSCR |
| Homes & Community Renewal (HCR) | https://hcr.ny.gov/procurement-opportunities | UNVERIFIED (index) | DIRECT_PDF | RFP/RFA PDFs (HTFC/HCR programs). Umbrella for HFA/SONYMA/AHC — see §B note |
| Council on the Arts (NYSCA) | https://arts.ny.gov/nysca-grant-opportunities | UNVERIFIED (index) | PORTAL | Grants via SmartSimple; competitive grants, not commodity IFBs |
| Office of Victim Services (OVS) | https://ovs.ny.gov/ | UNVERIFIED (index) | PORTAL + DIRECT_PDF | RFA-driven (e.g. ovs.ny.gov/26RFA). Grant-oriented |
| Office of Cannabis Management (OCM) | https://cannabis.ny.gov/procurement | UNVERIFIED (index) | DIRECT_PDF | RFA/IFB/RFP PDFs. Newer agency, growing volume |
| Workers' Compensation Board (WCB) | https://www.wcb.ny.gov/procurements/ | UNVERIFIED (index) | DIRECT_PDF | Procurements incl. SDVOB section; posts to NYSCR + own site |

**Known procurers without a dedicated bid page:** DMV (buys via OGS/ITS/NYSCR,
no dmv.ny.gov bid portal); Division of Veterans' Services (footprint is the OGS
SDVOB program at ogs.ny.gov/veterans, not DVS-hosted bids).

**Borderline (state carrier, not a classic department):** NY State Insurance
Fund (NYSIF) posts DIRECT_PDF RFP/RFQ at ww3.nysif.com/…/Procurement — include
only if the engine's scope admits state-carrier entities.

---

## B. State public authorities — `AUTHORITY` (→ HUMAN_REVIEW)

Catalogued for completeness; tenders here route to human review until Public
Authorities Law is brought into the golden copy.

| Authority | Procurement/bid page | Verified | Docs access | Notes |
|---|---|---|---|---|
| Metropolitan Transportation Authority (MTA) | https://www.mta.info/doing-business-with-us/procurement/current-opportunities | UNVERIFIED (index) | PORTAL | Very high volume. Capital projects: /agency/construction-and-development/contracting/current-opportunities. Own "My MTA Portal" |
| NYS Thruway Authority | https://www.thruway.ny.gov/business/purchasing/index.html | UNVERIFIED (index) | PORTAL (mixed) | Bid schedule + docs at pbss.thruway.ny.gov; construction via Bid Express |
| NYS Canal Corporation | https://www.canals.ny.gov/Doing-Business | UNVERIFIED (index) | PORTAL | NYPA subsidiary; uses NYPA SAP Ariba |
| Dormitory Authority of the State of NY (DASNY) | https://www.dasny.org/opportunities/rfps-bids | UNVERIFIED (index) | DIRECT_PDF + PORTAL | High volume (construction/design); weekly-updated list w/ docs + email alerts |
| New York Power Authority (NYPA) | https://www.nypa.gov/Procurement | UNVERIFIED (index) | PORTAL | SAP Ariba; docs need registration + bid-event invite (NYPARFQ@nypa.gov). Also NYSCR |
| Empire State Development (ESD / NYS UDC) | https://esd.ny.gov/requests-proposals | UNVERIFIED (index) | DIRECT_PDF | RFP list w/ PDF links. d/b/a UDC |
| NYSERDA | https://www.nyserda.ny.gov/Funding-Opportunities/Current-Funding-Opportunities | UNVERIFIED (index) | PORTAL + DIRECT_PDF | High volume PONs/RFPs/RFQs; portal.nyserda.ny.gov |
| Port Authority of NY & NJ | https://www.panynj.gov/port-authority/en/business-opportunities/solicitations-advertisements.html | UNVERIFIED (index) | PORTAL | **BI-STATE (NY+NJ).** High volume; vendor portal paprocure.com |
| NYS Homes & Community Renewal (HFA/SONYMA/AHC) | https://hcr.ny.gov/procurement-opportunities | UNVERIFIED (index) | DIRECT_PDF | Umbrella for state housing public-benefit corps; consolidated under HCR (do not double-count with §A) |
| Environmental Facilities Corporation (EFC) | https://efc.ny.gov/rfp | UNVERIFIED (index) | DIRECT_PDF | RFP/RFQ w/ doc links; MWBE/SDVOB goals |
| Battery Park City Authority (Hugh L. Carey BPCA) | https://bpca.ny.gov/apply/rfp-opp/ | UNVERIFIED (index) | DIRECT_PDF | Current + archived; PDFs on bpca.ny.gov. Also NYSCR + NYC City Record |
| NYS Bridge Authority | https://nysba.ny.gov/business-opportunities | UNVERIFIED (index) | NYSCR_ONLY | Lower volume; leans on NYSCR; legacy RFP page 404s |
| Olympic Regional Development Authority (ORDA) | https://orda.org/do-business/other-opportunities/ | UNVERIFIED (index) | DIRECT_PDF | Multiple categories; docs/addenda on orda.org; also NYSCR |
| New York Racing Association (NYRA) | https://www.nyra.com/inc/bidding/ | UNVERIFIED (index) | PORTAL | Docs via BidNet Direct (bidnetdirect.com/new-york/nyra) |
| Long Island Power Authority (LIPA) | https://www.lipower.org/procurement/lipa-procurement-opportunities/ | UNVERIFIED (index) | DIRECT_PDF | Active + prior RFPs w/ PDFs. Day-to-day via PSEG Long Island |
| Roswell Park Comprehensive Cancer Center | https://www.roswellpark.org/diversity/supplier-diversity | UNVERIFIED (index) | NYSCR / UNKNOWN | Page is vendor-registration only; solicitations via NYSCR + aggregators |
| Niagara Frontier Transportation Authority (NFTA) | https://bids.nfta.com/ | UNVERIFIED (index) | PORTAL | Bonfire portal; registration required for docs |
| Capital District Transportation Authority (CDTA) | https://www.cdta.org/procurements/procurement-opportunities | UNVERIFIED (index) | PORTAL | cdta.org registration required |
| Rochester-Genesee RTA (RGRTA / RTS) | https://www.myrts.com/do-business-with-us/procurement | UNVERIFIED (index) | PORTAL | Supplier Portal supplierportal.myrts.com; also NYSCR |
| Central NY RTA (CNYRTA / Centro) | https://www.centro.org/procurement-department | UNVERIFIED (index) | PORTAL | Bonfire portal; free registration required |
| NY State Insurance Fund (NYSIF) | https://ww3.nysif.com/FooterPages/Column1/AboutNYSIF/Procurement | UNVERIFIED (index) | DIRECT_PDF | RFP/RFQ PDFs hosted directly; contracts@nysif.com |
| Development Authority of the North Country (DANC) | https://www.danc.org/bids | UNVERIFIED (index) | DIRECT_PDF / PORTAL | Many entries are municipal bids DANC administers (mixed authority/municipal) |
| Albany Port District Commission | https://www.portofalbany.us/procurement | UNVERIFIED (index) | PORTAL | Via BidNet Direct / Empire State Purchasing Group + NYSCR |
| Ogdensburg Bridge and Port Authority | https://www.bidnetdirect.com/new-york/ogdensburgbridgeandportauthority | UNVERIFIED (index) | PORTAL | No native bid page; publishes via BidNet Direct |

---

## C. SUNY / CUNY — `SUNY_CUNY` (→ HUMAN_REVIEW)

Most campus pages are discovery hubs that funnel to NYSCR. The exceptions that
host documents directly are the construction funds (SUCF, CUCF), Binghamton, and
Stony Brook's DemandStar-backed portal.

| Source | URL | Verified | Docs access | Notes |
|---|---|---|---|---|
| SUNY System — Procurement | https://system.suny.edu/procurement/ | UNVERIFIED (index) | DISCOVERY_ONLY | EDL §142: SUNY buys >$50k advertised in NYSCR; routes vendors there |
| SUNY Contracts Search | https://www.suny.edu/business/contractsearch/ | UNVERIFIED (index) | AWARDS_ONLY | Awarded university-wide contracts, not open solicitations |
| State University Construction Fund (SUCF) — Construction | https://sucf.suny.edu/opportunities/construction | UNVERIFIED (index) | DIRECT_PDF | Construction bid opportunities + Bid Calendar PDF |
| SUCF — Bid Calendar (PDF) | https://sucf.suny.edu/sites/default/files/docs/BidCalendar.pdf | UNVERIFIED (index) | DIRECT_PDF | Direct PDF calendar of upcoming construction bids |
| SUCF — Design/Consulting Advertised | https://sucf.suny.edu/design-consulting-services/procurements-advertised | UNVERIFIED (index) | DIRECT_PDF | A/E and consulting solicitations |
| University at Buffalo — Procurement Services | https://www.buffalo.edu/administrative-services/…/procurement-services.html | UNVERIFIED (index) | DISCOVERY_ONLY | Formal bids via NYSCR; announcements page for notices |
| Stony Brook University — Procurement | https://www.stonybrook.edu/procurement/ | UNVERIFIED (index) | PORTAL | Public Bids Portal via DemandStar; procurementbids@stonybrook.edu |
| University at Albany — Procurement | https://www.albany.edu/procurement/ | UNVERIFIED (index) | DISCOVERY_ONLY | >$50k in NYSCR |
| Binghamton University — Bid Information | https://www.binghamton.edu/offices/purchasing/bids/ | UNVERIFIED (index) | DIRECT_PDF | Current bids + email signup; formal bids also NYSCR |
| CUNY — Procurement Services | https://www.cuny.edu/about/administration/offices/procurement-services/ | UNVERIFIED (index) | DISCOVERY_ONLY | Central policy office; routes to NYSCR / NYC City Record / campuses |
| CUNY — Procurement Opportunities | https://www.cuny.edu/…/doing-business-with-cuny/procurement-opportunities/ | UNVERIFIED (index) | DISCOVERY_ONLY | Docs may require NYSCR and/or NYC City Record registration |
| CUNYBuy (eProcurement) | https://www.cuny.edu/…/cuny-buy/ | UNVERIFIED (index) | PORTAL | CUNY eProcurement/supplier platform |
| CUNY Construction Fund (CUCF) — Procurements | https://www.cuny.edu/about/administration/offices/fpcm/cucf/procurement/current/ | UNVERIFIED (index) | DIRECT_PDF | Click a title for that solicitation's documents |

---

## D. Statewide / centralized infrastructure

| Source | URL | Verified | Docs access | Notes |
|---|---|---|---|---|
| OGS Procurement Services (Centralized Contracts) | https://ogs.ny.gov/procurement | fetched ✓ | PORTAL | ~1,500 centralized contracts; searchable DB, bid-opening results. Use bare `ogs.ny.gov` |
| **NYS Contract Reporter (NYSCR)** | https://www.nyscr.ny.gov/ | 403 (live) | DISCOVERY_ONLY / GATED | **Master statewide index of opportunities >$50k.** Registration + copyright-gated. **Use to DISCOVER only — then fetch the doc from the issuing agency's own site. Do NOT scrape/redistribute.** |
| Statewide Financial System (SFS) | https://www.sfs.ny.gov/ | UNVERIFIED (index) | PORTAL / GATED | State accounting system; vendor portal + grant search; most functions need NYS Vendor ID |
| SFS Vendor Self-Service (eSupplier) | https://esupplier.sfs.ny.gov/ | UNVERIFIED (index) | GATED | Login-only vendor portal (invoices, POs, e-invoicing) |
| Grants Gateway / NYS Grants Management | https://grantsmanagement.ny.gov/ | UNVERIFIED (index) | DISCOVERY_ONLY / GATED | "View Opportunities" is public; applying needs registration + nonprofit prequalification. Grant-specific |
| Office of the State Comptroller — Procurement | https://www.osc.ny.gov/procurement | UNVERIFIED (index) | DISCOVERY_ONLY | OSC's own opportunities + oversight guidance (vendor responsibility, bid protests, §112) |
| ITS — Open Procurements | https://its.ny.gov/current-open-procurement-opportunities | 403 (live) | DIRECT_PDF | Each title links to description + documents |
| data.ny.gov (Open Data) | https://data.ny.gov/ | fetched ✓ | AWARDS_ONLY | Contract/award/spending data — **NOT solicitation documents.** For analytics, not tender discovery |

---

## Maintenance

- Re-run the three-category scan periodically (agencies reorganize; URLs move).
- When a source is first used for a real tender, re-verify its live-fetchability
  and upgrade its "Verified" mark from *index* to *fetched ✓* with the date.
- This registry is operational sourcing metadata, **not** golden copy: it records
  *where* to look, never a verified rule. Nothing here is a legal citation.
