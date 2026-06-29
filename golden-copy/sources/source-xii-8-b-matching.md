# SOURCE TEXT — GFO XII.8.B Matching

- **Name:** XII.8.B Matching
- **Date:** REV. 07/16/2018
- **Issued by:** New York State Office of the State Comptroller (OSC), Guide to Financial Operations
- **Link (permanent identifier):** https://www.osc.ny.gov/state-agencies/gfo/chapter-xii/xii8b-matching
- **Copied exactly on:** 2026-06-28

> Everything below the line is the State's own text, copied word-for-word, including all tables.
> Nothing here is reworded. Before relying on this in production, re-open the link above and confirm
> the text and the REV. date still match.

---

## STATE TEXT (verbatim)

**SECTION OVERVIEW AND POLICIES**

Matching is an automated process in the Statewide Financial System (SFS) that compares a voucher to a purchase order referenced on the voucher. Where applicable, matching also compares the voucher to receiving and inspection information. Matching is required on every voucher that references a purchase order, except when the Payment Method on the purchase order is the Procurement Card.

Receipts are required and inspection information is optional on all purchase order lines for commodities. Vouchers that reference purchase order lines for commodities will be matched against the purchase order lines, associated receipts and, where applicable, inspection information.

These matching and receiving requirements will help to ensure vouchers are appropriate for payment.

In addition, the Office of the State Comptroller approved the use of payment tolerances in the SFS for select items to allow for slight variations in price between purchase orders and vouchers during the matching process. For more information about payment tolerances, please see *Chapter XI-A, Section 8 – Payment Tolerances* of this Guide.

*Process and Transaction Preparation:*

**Online Agencies**

Matching is a scheduled batch job in the SFS that runs once every hour during business hours and once again during the nightly batch processes. Matching will run on all vouchers that reference a purchase order, except when the Payment Method on the purchase order is the Procurement Card. An agency must address match exceptions before a voucher processor can submit a voucher into workflow. An agency can view match exceptions associated with a particular voucher via a link on the voucher or in the match exceptions workbench. The match exceptions report (Report ID APX1090) allows an agency to monitor all of its match exceptions. Agencies can run the match exceptions report in the SFS at Accounts Payable - Reports - Vouchers - Match Exceptions.

Online agencies can configure purchase orders in four basic ways and these configurations affect how associated vouchers are matched. The four basic configurations for purchase orders are:

| Match Basis | Receipts Required | Impact on Matching |
| --- | --- | --- |
| Amount | Yes | 1. The dollar amount on the voucher line must be less than or equal to the dollar amount on the purchase order line. 2. Amount based purchase order lines can only have a quantity equal to one. |
| Amount | No | The voucher line dollar amount must be less than or equal to the remaining balance on the purchase order line. |
| Quantity | Yes | 1. The quantity on the voucher line must be less than or equal to the unmatched quantity received; and 2. The voucher line dollar amount must be less than or equal to the remaining balance on the purchase order line. |
| Quantity | No | 1. The quantity on the voucher line must be less than or equal to the unmatched quantity on the purchase order line; and 2. The voucher line dollar amount must be less than or equal to the remaining balance on the purchase order line |

Requiring receipts for commodity purchases and requiring matching on all vouchers that reference a purchase order, except when the Payment Method on the purchase order is the Procurement Card, will help to ensure that:

- Agencies pay vendors only for commodities received.
- Agencies pay no more than the price agreed upon in the purchase order.
- Agencies do not exceed the amounts and quantities on purchase order lines.

**Bulkload Agencies**

Agencies will approve vouchers in their financial management systems and submit approved vouchers to the SFS via the bulkload process. Vouchers that reference purchase orders are subject to the matching process. Bulkload agencies can configure purchase orders in two basic ways and these configurations affect how associated vouchers are matched. The two basic configurations for purchase orders are:

| Match Basics | Receipts Required | Impact on Matching |
| --- | --- | --- |
| Amount | No | The voucher line dollar amount must be less than or equal to the remaining balance on the purchase order line. |
| Quantity | No | 1. The quantity on the voucher line must be less than or equal to the unmatched quantity on the purchase order line; and 2. The voucher line dollar amount must be less than or equal to the remaining balance on the purchase order line. |

Agencies are responsible for (1) reviewing the Match Exception Report to identify vouchers that failed matching and (2) resolving match exceptions by updating the voucher via bulkload. For additional instruction on this topic, visit job aid on matching published to SFS Coach. SFS Coach is accessible from the SFS home page after logging in with your SFS user ID and password.

The following match results may appear on the daily voucher extract:

| Approval Status | Match Status | Match Result |
| --- | --- | --- |
| B – Pending Budget Check  OR  V – Pending OSC | M – Matched | Pass |
| B – Pending Budget Check | P - Pending Budget | Pending |
| B – Pending Budget Check  OR  V – Pending OSC | T – To Be Matched | Pending |
| B – Pending Budget Check  OR  V – Pending OSC | N – Not Applicable | Not Applicable |
| B – Pending Budget Check | E – Match Exceptions Exist | Fail |

Once an agency has resolved the match exceptions, the voucher will be matched again during the next scheduled matching batch job.

Guide to Financial Operations

REV. 07/16/2018

---

## CITATIONS THIS TEXT POINTS TO (tagged for traceability — not part of the rule)

- GFO Chapter XI-A, Section 8 — Payment Tolerances
