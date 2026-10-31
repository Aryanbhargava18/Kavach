"""The business case, as data: what we measured, what Paytm already has, what it would take, and what only Paytm can tell us.

Nothing here is a forecast. Measured numbers come from eval/results.json (synthetic runs); everything else is either a
Paytm capability we can point to or an input left blank on purpose for Paytm to fill.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# feasibility: high = Paytm already holds the signal and the action; medium = needs a workflow or sign-off; low = needs a partner
COMPONENTS = [
    {"part": "Payout-return watcher", "signal": "Settlement return file (credits a merchant's bank refuses)", "paytm_has": "Yes: Paytm settles merchant payouts and receives returns",
     "needs": "A consumer of the return feed", "feasibility": "high", "demo": "simulated"},
    {"part": "Debit-freeze watcher", "signal": "UPI decline code YE on the merchant's own payments", "paytm_has": "Yes, for merchants who pay through the Paytm app (Paytm is their PSP)",
     "needs": "Join PSP responses to merchant profiles", "feasibility": "high", "demo": "simulated"},
    {"part": "Chargeback clock", "signal": "Dispute desk deadline (silence = deemed valid)", "paytm_has": "Yes: Paytm documents the chargeback flow and netting",
     "needs": "Dispute desk read + reply API (target)", "feasibility": "high", "demo": "simulated"},
    {"part": "₹1 validation before release", "signal": "Account-validation credit", "paytm_has": "Standard practice for settlement accounts",
     "needs": "Nothing new", "feasibility": "high", "demo": "simulated"},
    {"part": "Two-key payout hold and release", "signal": "Settlement config", "paytm_has": "Settlement engine exists",
     "needs": "Risk workflow + Legal sign-off", "feasibility": "medium", "demo": "simulated approval"},
    {"part": "Tipping-off guard", "signal": "Risk EDD signals", "paytm_has": "Paytm Risk runs EDD (SOP 9.5(iv))",
     "needs": "Risk signal feed + Legal's neutral template + an SLA", "feasibility": "medium", "demo": "simulated signals"},
    {"part": "SOP 9.5(ii) nodal upload", "signal": "Settlement trail of a reported payment", "paytm_has": "Paytm's PA nodal team does this today",
     "needs": "Officer review step", "feasibility": "high", "demo": "draft in ops queue"},
    {"part": "Bank grievance desk", "signal": "Signed, SOP-mapped case + JSON", "paytm_has": "Paytm Intelligence sells agents to banks",
     "needs": "One bank partner", "feasibility": "low (near term)", "demo": "verifier page; bank simulated"},
    {"part": "Hindi voice", "signal": "Soundbox + app", "paytm_has": "AI Soundbox speaks 11 languages",
     "needs": "Paytm's Indic model or Sarvam behind the same adapter", "feasibility": "high", "demo": "browser voice; Sarvam with a key"},
]

ROLLOUT = [
    {"phase": "0 · Shadow", "what": "Run the watchers read-only on 90 days of returns, declines and disputes. No merchant contact.",
     "proves": "How many freezes and chargebacks Kavach would have caught, and how early", "risk": "None"},
    {"phase": "1 · Alerts + clocks", "what": "Warn merchants and show the clocks row. No money moves.", "proves": "Fewer chargebacks lost to silence; earlier freeze reports",
     "risk": "Low; P17 guard on day one"},
    {"phase": "2 · Actions with approvals", "what": "Two-key holds, dispute replies, 9.5(ii) drafts, release after ₹1 validation.",
     "proves": "₹ kept per merchant; nodal minutes saved", "risk": "Medium; Risk and Legal sign-off"},
    {"phase": "3 · Pi bank desk", "what": "One bank receives signed, SOP-mapped cases and files through the desk.", "proves": "Bank turnaround; first-pass acceptance",
     "risk": "Partner-dependent"},
]

PRICING = {"model": "Per verified resolution, not per seat",
           "unit": "One resolved clock: a chargeback answered in time, a freeze case filed and scoped, a hold released after validation",
           "buyers": ["Paytm itself first (merchant base, nodal ops)", "Banks and acquirers through Paytm Intelligence"],
           "merchant_price": "₹0"}

# Why this is a problem today, not one we invented. Each line says what the source shows, and nothing more.
EVIDENCE = [
    {"claim": "One ₹1,000 UPI sale froze a shop's whole ₹8.26 lakh account for about ten months; the High Court ordered it released.",
     "source": "Sri Sai Wines v. Union of India, AP HC, WP 969/2026 (22 Jun 2026)", "url": None},
    {"claim": "I4C's own grievance table: about ₹303 crore frozen against ₹29 crore disputed (our sum of its rows; contested cases only).",
     "source": "I4C letter and Annexure I, 3 Jul 2026 (court-hosted)", "url": "https://cdnbbsr.s3waas.gov.in/s3ec0292a08bf918f44ccd961477be3002/uploads/2026/08/2026081767.pdf"},
    {"claim": "Courts keep saying: hold the disputed amount, not the whole account.",
     "source": "Allahabad HC, Aug 2026 (also Karnataka HC 27 Mar, Kerala HC 21 May 2026)", "url": "https://www.livelaw.in/high-court/allahabad-high-court/cyber-fraud-allahabad-hc-bank-lien-disputed-amount-mha-sop-545790"},
    {"claim": "The Supreme Court told the RBI to frame an SOP for mule accounts and debit holds.",
     "source": "Supreme Court, 4 Aug 2026 (suo motu, digital-arrest case)", "url": "https://www.thestatesman.com/india/freeze-faster-restore-money-sooner-sc-tightens-digital-arrest-scam-response-gives-rbi-4-weeks-for-mule-account-sop-1503624478.html"},
    {"claim": "The RBI's draft would make holds on the suspected amount the default and require telling the customer why and how to get it removed. Draft, not yet in force.",
     "source": "RBI draft KYC (Amendment) Directions, 2026 (11 Sep 2026)", "url": "https://www.dsci.in/resource/content/brief-draft-rbi-kyc-amendment-directions-2026"},
    {"claim": "The government SOP sets the route: the merchant complains at the branch; the bank files within 7 days; payment aggregators upload settlement details (9.5(ii)).",
     "source": "MHA/I4C SOP for NCRP-CFCFRMS, 02.01.2026", "url": "https://cdnbbsr.s3waas.gov.in/s3ec03936824c0191953647ec609b4f49b/uploads/2026/06/2026061955.pdf"},
    {"claim": "Paytm nets refunds and chargebacks from settlements, and leaves merchants to match bank credits to their records.",
     "source": "Paytm Payments docs: settlement processing", "url": "https://paytmpayments.com/docs/settlement-processing-in-paytm"},
]

PAYTM_ONLY_INPUTS = [
    "Freezes per 10,000 merchants per month, and how many show a payout return or a YE decline",
    "Chargebacks per merchant, and the share deemed valid for no reply",
    "Minutes a nodal officer spends on one SOP 9.5(ii) upload",
    "Minutes Paytm Risk spends on one freeze case today",
    "Churn and GMV of merchants after a freeze, vs similar merchants without one",
]


def build() -> dict[str, Any]:
    p = ROOT / "eval" / "results.json"
    r = json.loads(p.read_text()) if p.exists() else {}
    fw = r.get("freeze_watch", {})
    rechecked = next((m["kavach"] for m in r.get("metrics", []) if "re-checked" in m["label"]), None)
    per_incident = None
    if rechecked and r.get("n"):
        done, total = (int(x) for x in rechecked.split("/"))
        per_incident = round(total / r["n"], 1)
    measured = [
        {"label": "Verified actions per everyday incident", "value": per_incident, "note": f"{rechecked} actions re-checked across {r.get('n')} incidents"},
        {"label": "Tool calls per money-clock case (median)", "value": fw.get("median_tool_calls_per_case"), "note": f"{fw.get('scenarios')} freeze and chargeback scenarios"},
        {"label": "Model calls per case, offline mode", "value": 0, "note": "Decisions are rules; a model is only used for language when a key is set"},
        {"label": "Human taps per freeze case", "value": "3 + 2", "note": "Meena: hold, request, branch. Paytm Risk: hold, release."},
        {"label": "Caught when Paytm has a signal", "value": fw.get("detected_when_paytm_has_a_signal"), "note": "False alarms: " + str(fw.get("false_alarms_on_healthy_or_blind"))},
    ]
    from . import paytm_live
    live = {"part": "Paytm Transaction Status API (live read path)", "signal": "v3/order/status, signed with Paytm's checksum library",
            "paytm_has": "Public API; staging keys from the Paytm dashboard", "needs": "PAYTM_MID + PAYTM_MERCHANT_KEY in .env",
            "feasibility": "high", "demo": "LIVE" if paytm_live.configured() else "ready; keys not set on this machine"}
    return {"evidence": EVIDENCE, "live": live, "measured": measured, "components": [live] + COMPONENTS, "rollout": ROLLOUT, "pricing": PRICING, "paytm_only_inputs": PAYTM_ONLY_INPUTS,
            "label": "Measured numbers are from synthetic runs in this repo. Paytm capabilities are as publicly described; integrations are targets, not live."}
