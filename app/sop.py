"""Freeze branch: notice reading, SOP routing and clocks.

Rules are encoded from the MHA/I4C 'SOP for NCRP-CFCFRMS, Custody, Restoration of Money and
Grievance Redressal' (02.01.2026, government-hosted copy). They are an engineering aid, not
legal advice. LLMs never choose a rule; this module does.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

SOP_SOURCE = "https://cdnbbsr.s3waas.gov.in/s3ec03936824c0191953647ec609b4f49b/uploads/2026/06/2026061955.pdf"

RULES = {
    "PA-ESCROW-9.5.i": {"para": "9.5(i)", "when": "Reported funds still sit in the payment aggregator's escrow/pool (not yet settled).",
                        "who": "Payment aggregator", "next": "PA holds only the reported amount and updates beneficiary details on CFCFRMS."},
    "PA-SETTLED-9.5.ii": {"para": "9.5(ii)", "when": "Reported payment was already settled to the merchant's bank account.",
                          "who": "PA uploads settlement details; the account holder follows the bank-side grievance route.",
                          "next": "Paytm can share the settlement trail; the merchant approaches the bank branch."},
    "PA-REPEAT-9.5.iv": {"para": "9.5(iv)", "when": "Same UPI ID reported in multiple CFCFRMS cases.",
                         "who": "TPAP/PA performs enhanced due diligence", "next": "Human EDD review. A review signal, never a guilt finding."},
    "BANK-HOLD-10.1": {"para": "10.1(a)–(f)", "when": "An amount hold/debit freeze contested by the account holder.",
                       "who": "Account holder → bank branch; bank does CDD/EDD and submits to the grievance module within 7 calendar days of the complaint.",
                       "next": "Merchant files a written complaint at the branch and keeps the dated acknowledgement."},
    "SUSPENSION-SEIZURE-10.2": {"para": "10.2(a)–(h)", "when": "Suspension of digital banking or seizure.",
                                "who": "Account holder → bank; IO, then district and state officers review in stages.",
                                "next": "Branch complaint; escalation ladder per 10.2."},
}

FIELDS = {
    "ack_number": r"(?i)acknowledg(?:e)?ment\s*(?:no\.?|number)?\s*[:#-]\s*(\d[\d ]{10,})",
    "case_reference": r"(?i)case\s*ref(?:erence)?\s*[:#-]\s*([^\n]+)",
    "authority": r"(?i)^(?:from|issuing\s*authority|authority)\s*[:#-]\s*([^\n]+)",
    "action": r"(?i)^action\s*[:#-]\s*([^\n]+)",
    "amount": r"(?i)(?:disputed|reported)\s*amount\s*[:#-]\s*(?:₹|Rs\.?\s*)?([\d,]+)",
    "transaction_date": r"(?i)(?:transaction|txn)\s*date\s*[:#-]\s*(\d{4}-\d{2}-\d{2})",
    "utr": r"(?i)\bUTR\s*[:#-]\s*(\d{12})",
    "hold_date": r"(?i)hold\s*(?:placed\s*)?date\s*[:#-]\s*(\d{4}-\d{2}-\d{2})",
}

INJECTION = re.compile(r"(?i)ignore (all |any )?(previous|prior) instructions|mark (this|the) merchant as|you are now")


def parse_notice(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    fields: dict[str, Any] = {}
    for name, pat in FIELDS.items():
        for i, line in enumerate(lines, 1):
            m = re.search(pat, line.strip())
            if m:
                v: Any = m.group(1).strip()
                if name == "amount":
                    v = int(v.replace(",", ""))
                fields[name] = {"value": v, "line": i}
                break
    checks = []
    ack = (fields.get("ack_number") or {}).get("value", "").replace(" ", "")
    if ack:
        ok = len(ack) == 14 and ack[0] in "23"
        checks.append({"check": "NCRP acknowledgement format (SOP 6.1/6.2: 14 digits, starts 2 or 3)", "pass": ok,
                       "note": "Format check only. It does not authenticate the notice."})
    injected = [i for i, l in enumerate(lines, 1) if INJECTION.search(l)]
    action = str((fields.get("action") or {}).get("value", "")).lower()
    kind = ("seizure" if "seiz" in action else "suspension" if "suspen" in action
            else "amount_hold" if any(k in action for k in ("hold", "freeze", "lien")) else "unknown")
    return {"fields": fields, "checks": checks, "action_kind": kind, "injection_lines": injected,
            "missing": [f for f in ("utr", "amount", "action", "hold_date") if f not in fields]}


def route(action_kind: str, fund_location: str | None, location_source: str | None, repeat_reports: int = 1) -> dict[str, Any]:
    """Route only on facts backed by a system-of-record source. Unknown stays unknown."""
    out: list[str] = []
    if action_kind in ("seizure", "suspension"):
        out.append("SUSPENSION-SEIZURE-10.2")
    elif action_kind == "amount_hold":
        if not location_source:
            return {"rules": [], "status": "UNKNOWN", "why": "Who holds the money is not established by a system record. Kavach will not guess."}
        if fund_location == "pa_escrow":
            out.append("PA-ESCROW-9.5.i")
        elif fund_location == "settled_to_merchant":
            out += ["PA-SETTLED-9.5.ii", "BANK-HOLD-10.1"]
    else:
        return {"rules": [], "status": "OUT_OF_SCOPE", "why": "The notice does not describe a hold, suspension or seizure under this SOP."}
    if repeat_reports > 1:
        out.append("PA-REPEAT-9.5.iv")
    return {"rules": [{"id": r, **RULES[r]} for r in out], "status": "ROUTED" if out else "UNKNOWN", "source": SOP_SOURCE}


def clocks(events: dict[str, str | None]) -> list[dict[str, Any]]:
    """A message to Kavach is NOT the statutory trigger. No bank-complaint date -> 'Needs confirmation'."""
    out = []
    bank = _d(events.get("bank_complaint_date"))
    out.append({"clock": "Bank must submit grievance (SOP 10.1(a))", "starts_on": "Merchant's written complaint to the bank",
                "start": bank.isoformat() if bank else None, "due": (bank + timedelta(days=7)).isoformat() if bank else None,
                "state": "running" if bank else "needs_confirmation"})
    hold = _d(events.get("hold_date"))
    out.append({"clock": "90-day anchor B: from date of hold (SOP Annexure I template)", "starts_on": "Hold date on notice",
                "start": hold.isoformat() if hold else None, "due": (hold + timedelta(days=90)).isoformat() if hold else None,
                "state": "ambiguous_anchor"})
    sub = _d(events.get("bank_submission_date"))
    out.append({"clock": "90-day anchor A: from bank's grievance submission (SOP 10.1(f))", "starts_on": "Bank's submission to grievance module",
                "start": sub.isoformat() if sub else None, "due": (sub + timedelta(days=90)).isoformat() if sub else None,
                "state": "needs_confirmation" if not sub else "ambiguous_anchor"})
    return out


def _d(v):
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None
