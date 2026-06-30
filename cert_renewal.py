#!/usr/bin/env python3
"""
BUILD SPEC v2 — Part B (certified firms only): certification-renewal panel.

For a firm that already holds NYS certifications, this surfaces renewal risk:

  * MWBE 5-year validity. The five-year period is STATUTORY and is cited
    verbatim from NY Executive Law § 314(5) (source-exec-314-mwbe-cert-validity
    .md) through GoldenCopy.cite(). The 90-day renewal window is ESD AGENCY
    GUIDANCE, not statute — it lives in the source's CITATIONS section, not the
    verbatim STATE TEXT body, so it CANNOT pass the cite() choke-point and is
    labelled "agency guidance (not statutory)". We hold that line rather than
    fake a statutory citation for it.

  * SDVOB lapse warning. NYS golden copy confirms the SDVOB PROGRAM (good-faith
    participation, 6% goal) — cited from source-sdvob.md — but it does NOT fix a
    certification CYCLE LENGTH. So the cycle stays USER-PROVIDED and every SDVOB
    finding is flagged "not confirmed — verify with OGS" until a verbatim source
    is added. Never assert an SDVOB cycle as fact.

Colour ↔ severity matches the rest of the engine: GREEN→PASS, YELLOW→WARN,
RED→FAIL.
"""

import json
import os
import sys
import datetime

from validator import GoldenCopy, parse_date, FAIL, WARN, PASS, INFO

HERE = os.path.dirname(os.path.abspath(__file__))

GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"

RENEWAL_WINDOW_DAYS = 90  # ESD agency guidance: recert window opens 90 days out.

EXEC314 = "source-exec-314-mwbe-cert-validity.md"
EXEC314_QUOTE = ("all minority and women-owned business enterprise certifications "
                 "shall be valid for a period of five years")
SDVOB_SRC = "source-sdvob.md"
SDVOB_QUOTE = ("By law, State agencies must make good faith efforts to use SDVOBs "
               "in procurement.")


class PanelItem:
    def __init__(self, program, status, days_to_expiry, expiry, message,
                 grounding=None, agency_guidance=None, not_confirmed=None,
                 action=None):
        self.program = program
        self.status = status
        self.days_to_expiry = days_to_expiry
        self.expiry = expiry
        self.message = message
        self.grounding = grounding            # confirmed verbatim cite, or None
        self.agency_guidance = agency_guidance  # non-statutory note (string)
        self.not_confirmed = not_confirmed    # string reason, or None
        self.action = action

    def to_dict(self):
        d = {
            "program": self.program,
            "status": self.status,
            "expiry": self.expiry,
            "days_to_expiry": self.days_to_expiry,
            "message": self.message,
        }
        if self.grounding:
            d["grounding"] = {"source_file": self.grounding["source_file"],
                              "citation_quote": self.grounding["citation_quote"],
                              "confirmed": True}
        if self.agency_guidance:
            d["agency_guidance"] = {"note": self.agency_guidance,
                                    "statutory": False}
        if self.not_confirmed:
            d["not_confirmed"] = self.not_confirmed
        if self.action:
            d["action"] = self.action
        return d


class CertRenewalReport:
    def __init__(self, vendor_name, today, items, is_certified_firm):
        self.vendor_name = vendor_name
        self.today = today
        self.items = items
        self.is_certified_firm = is_certified_firm

    def to_dict(self):
        return {
            "feature": "cert_renewal",
            "vendor_name": self.vendor_name,
            "as_of": self.today,
            "is_certified_firm": self.is_certified_firm,
            "panel": [i.to_dict() for i in self.items],
            "disclaimer": (
                "Information only. The MWBE five-year validity period is cited "
                "verbatim from statute; the 90-day window is ESD agency guidance; "
                "the SDVOB cycle is user-provided and not confirmed against golden "
                "copy. Verify dates with the issuing office before relying on them."
            ),
        }


def _window_status(days):
    if days is None:
        return YELLOW
    if days < 0:
        return RED
    if days <= RENEWAL_WINDOW_DAYS:
        return YELLOW
    return GREEN


def _mwbe_item(data, today, golden):
    expiry = parse_date(data.get("mwbe_cert_expiry"))
    grounding = {"source_file": EXEC314,
                 "citation_quote": golden.cite(EXEC314, EXEC314_QUOTE)}
    guidance = ("ESD recertification window opens {} days before expiry "
                "(agency guidance, not statutory).".format(RENEWAL_WINDOW_DAYS))
    if expiry is None:
        return PanelItem(
            "MWBE", YELLOW, None, None,
            "No MWBE expiry date provided — cannot compute the 5-year renewal "
            "clock. Provide the certification expiry date.",
            grounding=grounding, agency_guidance=guidance,
            action="Provide your MWBE certification expiry date.")
    days = (expiry - today).days
    status = _window_status(days)
    if status == RED:
        msg = ("MWBE certification EXPIRED {} ({} day(s) ago). It must be valid; "
               "recertify immediately.".format(expiry.isoformat(), -days))
        action = "Recertify your MWBE certification — it has lapsed."
    elif status == YELLOW:
        msg = ("MWBE certification expires {} ({} day(s) out) — inside the {}-day "
               "renewal window. Begin recertification now.".format(
                   expiry.isoformat(), days, RENEWAL_WINDOW_DAYS))
        action = "Start MWBE recertification (renewal window is open)."
    else:
        msg = ("MWBE certification valid until {} ({} day(s) out). No action yet; "
               "the {}-day window opens {}.".format(
                   expiry.isoformat(), days, RENEWAL_WINDOW_DAYS,
                   (expiry - datetime.timedelta(days=RENEWAL_WINDOW_DAYS)).isoformat()))
        action = None
    return PanelItem("MWBE", status, days, expiry.isoformat(), msg,
                     grounding=grounding, agency_guidance=guidance, action=action)


def _sdvob_item(data, today, golden):
    expiry = parse_date(data.get("sdvob_cert_expiry"))
    cycle = data.get("sdvob_cycle_years_user_provided")
    grounding = {"source_file": SDVOB_SRC,
                 "citation_quote": golden.cite(SDVOB_SRC, SDVOB_QUOTE)}
    not_conf = ("SDVOB certification cycle ({}) is USER-PROVIDED and not confirmed "
                "against golden copy — verify the renewal cycle with NYS OGS."
                .format("{} yr".format(cycle) if cycle else "unspecified"))
    if expiry is None:
        return PanelItem(
            "SDVOB", YELLOW, None, None,
            "No SDVOB expiry date provided — cannot compute a lapse warning.",
            grounding=grounding, not_confirmed=not_conf,
            action="Provide your SDVOB certification expiry date.")
    days = (expiry - today).days
    status = _window_status(days)
    if status == RED:
        msg = ("SDVOB certification appears EXPIRED {} ({} day(s) ago) per the "
               "user-provided date.".format(expiry.isoformat(), -days))
        action = "Confirm SDVOB status with OGS and recertify if lapsed."
    elif status == YELLOW:
        msg = ("SDVOB certification expires {} ({} day(s) out) — within the {}-day "
               "lapse-warning window.".format(expiry.isoformat(), days,
                                              RENEWAL_WINDOW_DAYS))
        action = "Confirm SDVOB renewal timing with OGS."
    else:
        msg = ("SDVOB certification valid until {} ({} day(s) out) per the "
               "user-provided date.".format(expiry.isoformat(), days))
        action = None
    return PanelItem("SDVOB", status, days, expiry.isoformat(), msg,
                     grounding=grounding, not_confirmed=not_conf, action=action)


def check_cert_renewal(data, golden=None, today=None):
    golden = golden or GoldenCopy()
    today = today or parse_date(data.get("today")) or datetime.date.today()
    items = []
    certified = False
    if data.get("mwbe_certified"):
        certified = True
        items.append(_mwbe_item(data, today, golden))
    if data.get("sdvob_certified"):
        certified = True
        items.append(_sdvob_item(data, today, golden))
    if not certified:
        items.append(PanelItem(
            "—", INFO, None, None,
            "No MWBE or SDVOB certification on file — the renewal panel applies "
            "to certified firms only.",
            grounding=None))
    return CertRenewalReport(
        vendor_name=data.get("vendor_name", "(unnamed vendor)"),
        today=today.isoformat(), items=items, is_certified_firm=certified)


_MARK = {GREEN: "GREEN ", YELLOW: "YELLOW", RED: "RED   ", INFO: "INFO  "}


def render_cert_renewal(report):
    L = []
    L.append("=" * 78)
    L.append("CERTIFICATION-RENEWAL PANEL — {}".format(report.vendor_name))
    L.append("As of {}   (certified firm: {})".format(
        report.today, "YES" if report.is_certified_firm else "NO"))
    L.append("=" * 78)
    for it in report.items:
        L.append("[{}] {}".format(_MARK.get(it.status, it.status), it.program))
        L.append("   {}".format(it.message))
        if it.grounding:
            L.append("   rule   : {} (confirmed, statutory)".format(
                it.grounding["source_file"]))
            L.append('   cite   : "{}"'.format(it.grounding["citation_quote"]))
        if it.agency_guidance:
            L.append("   note   : {}".format(it.agency_guidance))
        if it.not_confirmed:
            L.append("   NOT CONFIRMED: {}".format(it.not_confirmed))
        if it.action:
            L.append("   action : {}".format(it.action))
        L.append("")
    L.append("-" * 78)
    L.append(report.to_dict()["disclaimer"])
    L.append("=" * 78)
    return "\n".join(L)


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: cert_renewal.py CERT.json [--json]", file=sys.stderr)
        return 2
    report = check_cert_renewal(_load_json(argv[0]))
    if "--json" in argv:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_cert_renewal(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
