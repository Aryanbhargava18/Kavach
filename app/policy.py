"""Deterministic action policy.

Every *write* the agent proposes (deterministic planner or LLM) is checked here first.
The policy re-reads the source of truth from the World itself. It never trusts the
agent's description of the facts, a screenshot, or a notice.

A decision is one of:
  ALLOW            -> engine executes, then must verify
  NEEDS_APPROVAL   -> engine pauses and asks the named human(s)
  DENY             -> engine records the refusal; the planner must change course
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from .world import MERCHANT, World

DUPLICATE_WINDOW = timedelta(minutes=10)
MAX_FOLLOWUPS = 8

RULES = {
    "P1": "Never ask a customer to pay again while an earlier payment for the same sale is pending or succeeded.",
    "P2": "A receipt is issued only when the UPI switch itself shows SUCCESS to this merchant. A screenshot is a claim, not proof.",
    "P3": "Soundbox replays only announce payments the switch shows as SUCCESS to this merchant.",
    "P4": "Refund only a proven duplicate: two SUCCESS payments, same payer, same amount, within 10 minutes. Refund once (idempotent).",
    "P5": "A refund spends the merchant's money, so the merchant approves every refund.",
    "P6": "Never change the settlement account while the bank is returning settlements as frozen; that could look like evading a lawful order.",
    "P7": "Kavach never files grievances or contacts police/banks. Under the SOP the account holder approaches the bank branch.",
    "P8": "Customer-facing messages never accuse anyone (no 'fraud', 'fake', 'scam'), and payer identities stay masked.",
    "P9": "Holding settlements needs two keys: the merchant and a Paytm Risk/Ops human.",
    "P10": "An evidence pack is generated only for one exact Paytm record whose amount agrees with the notice.",
    "P11": "Follow-ups are bounded per incident.",
    "P12": "An incident is closed only after the outcome has been re-verified against the source of truth.",
    "P13": "Escalation letters go out only in Meena's name and only after she approves the draft.",
    "P14": "Money that is being refunded is never counted as paid: no receipt and no ledger entry for it.",
    "P15": "One payment settles one bill. A UTR already in the shop's ledger is never applied again.",
    "P16": "A ledger entry is posted only for a switch-confirmed payment that fits the amount still due on that bill.",
    "P17": "When Paytm Risk holds two or more independent signals on a merchant, Kavach does not tell them about a freeze, notice or report. Only Legal's neutral template goes out, and Paytm Risk decides.",
}

RULES_BY_KIND = {
    "payment_claim": ["P1", "P2", "P3", "P8", "P12", "P14", "P15", "P16"],
    "duplicate": ["P4", "P5", "P8", "P11", "P12"],
    "freeze": ["P6", "P7", "P9", "P10", "P13", "P17"],
    "settlement": ["P6", "P7", "P9", "P17"],
}

AUTONOMY = {
    "alone": ["read any Paytm record", "post a switch-confirmed payment into the shop's ledger", "replay the Soundbox",
              "send receipts and status updates", "show a QR for an amount still due", "schedule follow-ups", "escalate"],
    "with_approval": ["refunds (Meena)", "holding payouts (Meena + Paytm Risk)", "letters in Meena's name (Meena)"],
    "never": ["move money between accounts", "file with banks or police", "accuse a customer", "count money that is being refunded"],
}

ACCUSATORY = re.compile(r"\b(fraud|fraudster|fake|scam|scammer|cheat|cheater|chor|thief|forged|जाली|धोखा|फ्रॉड)\b", re.I)
FULL_VPA = re.compile(r"\b[a-z0-9._-]{3,}@[a-z]{2,}\b", re.I)


@dataclass
class Decision:
    verdict: str  # ALLOW | NEEDS_APPROVAL | DENY
    rule: str | None
    reason: str
    approvers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "rule": self.rule, "rule_text": RULES.get(self.rule or "", ""), "reason": self.reason,
                "approvers": self.approvers}


def allow(reason: str, rule: str | None = None) -> Decision:
    return Decision("ALLOW", rule, reason)


def deny(rule: str, reason: str) -> Decision:
    return Decision("DENY", rule, reason)


def evaluate(world: World, action: str, args: dict[str, Any], ctx: dict[str, Any]) -> Decision:
    fn = _CHECKS.get(action)
    if fn is None:
        return deny("P7", f"'{action}' is not an action Kavach is permitted to take.")
    return fn(world, args, ctx)


# ----------------------------------------------------------------- checks
def _own_success(world: World, txn_id: str | None) -> tuple[dict | None, str | None]:
    t = world.txn_by_id(txn_id or "")
    if not t:
        return None, "No such transaction exists at the UPI switch."
    if t["payee_vpa"] != MERCHANT["vpa"]:
        return t, f"The payment went to {t['payee_vpa']}, not to this merchant."
    if t["status"] != "SUCCESS":
        return t, f"The switch shows this payment as {t['status']}, not SUCCESS."
    return t, None


def _refund_of(world, txn_id):
    return next((r for r in world.refunds if r["txn_id"] == txn_id), None)


def _receipt(world, args, ctx):
    t, problem = _own_success(world, args.get("txn_id"))
    if problem:
        return deny("P2", problem)
    r = _refund_of(world, t["txn_id"])
    if r:
        return deny("P14", f"{r['refund_id']} is sending this ₹{r['amount']:,} back to the customer; a receipt would count money that is leaving.")
    return allow(f"Switch confirms ₹{t['amount']:,} SUCCESS to {MERCHANT['vpa']} (UTR {t['utr']}).", "P2")


def _soundbox(world, args, ctx):
    t, problem = _own_success(world, args.get("txn_id"))
    if problem:
        return deny("P3", problem)
    return allow("Payment is SUCCESS at the switch; replay is safe.", "P3")


def _bill(world, bill_id):
    return next((b for b in getattr(world, "bills", []) if b["bill_id"] == bill_id), None) if bill_id else None


def _request_payment(world, args, ctx):
    amount = int(args.get("amount") or 0)
    bill = _bill(world, args.get("bill_id"))
    due_total = bill["amount"] if bill else int(args.get("claimed_amount") or amount)
    related = [world.txn_by_id(x) for x in (args.get("related_txn_ids") or [])]
    if bill:
        related += [t for t in world.transactions if t.get("bill_id") == bill["bill_id"]]
    seen, rel = set(), []
    for t in related:
        if t and t["payee_vpa"] == MERCHANT["vpa"] and t["txn_id"] not in seen:
            seen.add(t["txn_id"]); rel.append(t)
    if amount <= 0:
        return deny("P1", "Amount must be positive.")
    pend = [t for t in rel if t["status"] == "PENDING"]
    if pend:
        return deny("P1", f"Payment {pend[0]['txn_id']} for ₹{pend[0]['amount']:,} is still PENDING. Collecting again risks charging the customer twice.")
    refunded = {r["txn_id"]: r["amount"] for r in world.refunds}
    received = sum(t["amount"] - refunded.get(t["txn_id"], 0) for t in rel if t["status"] == "SUCCESS")
    if received and amount > due_total - received:
        return deny("P1", f"₹{received:,} has already been received for this sale; asking for ₹{amount:,} more would overcharge (outstanding ₹{max(0, due_total - received):,}).")
    note = " (an earlier payment is being refunded, so it doesn't count)" if any(t["txn_id"] in refunded for t in rel) else ""
    return allow(f"Nothing pending or received covers this amount{note}; asking the customer to pay ₹{amount:,} is safe.", "P1")


def _reconcile(world, args, ctx):
    utr, bill_id = args.get("utr"), args.get("bill_id")
    t = next((x for x in world.transactions if x["utr"] == utr and x["payee_vpa"] == MERCHANT["vpa"]), None)
    if not t:
        return deny("P16", "No payment to this merchant with that UTR at the UPI switch.")
    if t["status"] != "SUCCESS":
        return deny("P16", f"The switch shows this payment as {t['status']}, not SUCCESS.")
    entry = next((e for e in getattr(world, "ledger", []) if e["utr"] == utr), None)
    if entry:
        at = entry["at"].strftime("%I:%M %p") if hasattr(entry["at"], "strftime") else str(entry["at"])[11:16]
        return deny("P15", f"UTR …{utr[-4:]} was already applied to bill {entry['bill_id']} at {at}. One payment settles one bill.")
    r = _refund_of(world, t["txn_id"])
    if r:
        return deny("P14", f"{r['refund_id']} is already sending this ₹{r['amount']:,} back ({r.get('reason', 'refund')}). Recording it as paid would count money that is leaving.")
    bill = _bill(world, bill_id)
    if not bill:
        return deny("P16", "No such bill in the shop's ledger.")
    if bill["status"] == "PAID":
        return deny("P16", f"Bill {bill_id} is already fully paid.")
    if t["amount"] > bill["amount"] - bill["paid_amount"]:
        return deny("P16", f"₹{t['amount']:,} is more than the ₹{bill['amount'] - bill['paid_amount']:,} still due on {bill_id}.")
    return allow(f"Switch SUCCESS ₹{t['amount']:,} to this merchant; UTR not in the ledger; no refund; fits the amount due on {bill_id}.", "P16")


def _refund(world, args, ctx):
    t = world.txn_by_id(args.get("txn_id") or "")
    amount = int(args.get("amount") or 0)
    if not t or t["status"] != "SUCCESS" or t["payee_vpa"] != MERCHANT["vpa"]:
        return deny("P4", "The transaction to refund is not a SUCCESS payment to this merchant.")
    if amount <= 0 or amount > t["amount"]:
        return deny("P4", f"Refund amount ₹{amount:,} exceeds the original ₹{t['amount']:,}.")
    twins = [o for o in world.transactions if o is not t and o["status"] == "SUCCESS" and o["payee_vpa"] == MERCHANT["vpa"]
             and o["payer_vpa"] == t["payer_vpa"] and o["amount"] == t["amount"]
             and abs(o["created_at"] - t["created_at"]) <= DUPLICATE_WINDOW]
    if not twins:
        return deny("P4", "No second payment from the same payer for the same amount within 10 minutes. This is not a proven duplicate.")
    pair = {t["txn_id"]} | {o["txn_id"] for o in twins}
    if any(r["txn_id"] in pair for r in world.refunds):
        return deny("P4", "A refund already exists for this duplicate pair. Refunding again would pay the customer twice.")
    if "merchant" not in ctx.get("approvals", set()):
        return Decision("NEEDS_APPROVAL", "P5", f"Refunding ₹{amount:,} spends Meena's money; she decides.", ["merchant"])
    return allow("Proven duplicate (same payer, same amount, within 10 min); first refund for this pair.", "P4")


def _customer_update(world, args, ctx):
    text = args.get("text", "")
    if ACCUSATORY.search(text):
        return deny("P8", "Customer message contains accusatory wording. Rephrase neutrally.")
    if FULL_VPA.search(text):
        return deny("P8", "Customer message contains a full UPI handle; identities stay masked.")
    return allow("Neutral wording; no identities exposed.", "P8")


CASE_DETAIL = re.compile(r"freez|frozen|police|cyber|notice|ncrp|complaint|1930|lien|hold|फ्रीज़|पुलिस|नोटिस|शिकायत", re.I)


def risk_guard(world) -> bool:
    """Two or more independent Risk signals: telling the merchant about the case could tip off a mule operator."""
    return len({x["signal"] for x in world.risk_signals}) >= 2


def _notify_merchant(world, args, ctx):
    if FULL_VPA.search(args.get("text", "")) and MERCHANT["vpa"] not in args.get("text", ""):
        return deny("P8", "Merchant message would expose a payer's full UPI handle.")
    if risk_guard(world) and args.get("template") != "legal_neutral" and CASE_DETAIL.search(args.get("text", "") + " " + str(args.get("speak") or "")):
        return deny("P17", "Paytm Risk holds two independent signals on this merchant. Case details could tip off a mule operator; only Legal's neutral template may go out.")
    return allow("Message to the account owner.")


def _followup(world, args, ctx):
    if ctx.get("followups_used", 0) >= MAX_FOLLOWUPS:
        return deny("P11", "Follow-up budget for this incident is exhausted; hand to a human.")
    return allow("Within follow-up budget.", "P11")


def _frozen_signal(world, ctx) -> bool:
    """Paytm sees a total freeze as bounced payouts; a debit freeze is invisible to it, so a freeze the
    merchant has reported (an open freeze incident) counts too."""
    return world.bank_signal()["last_return"] is not None or bool(ctx.get("freeze_reported"))


def _pause(world, args, ctx):
    need = [a for a in ("merchant", "paytm_ops") if a not in ctx.get("approvals", set())]
    if need:
        return Decision("NEEDS_APPROVAL", "P9", "Holding payouts changes where the merchant's money sits.", need)
    return allow("Merchant and Paytm Ops both approved. Funds stay in the Paytm settlement balance; nothing moves to another account.", "P9")


def _change_account(world, args, ctx):
    if _frozen_signal(world, ctx):
        return deny("P6", "Meena's account is under a cyber-cell freeze. Redirecting payouts to another account now could amount to evading a lawful order.")
    return Decision("NEEDS_APPROVAL", "P6", "Settlement account changes always need Paytm Ops verification.", ["paytm_ops"])


def _evidence(world, args, ctx):
    utr = args.get("utr")
    hits = [t for t in world.transactions if t["utr"] == utr and t["payee_vpa"] == MERCHANT["vpa"]]
    if len(hits) != 1:
        return deny("P10", "No single Paytm record for this UTR. Kavach will not build a pack around a payment it cannot see.")
    notice_amount = args.get("notice_amount")
    if notice_amount is not None and int(notice_amount) != hits[0]["amount"]:
        return deny("P10", f"The notice says ₹{int(notice_amount):,} but the Paytm record for that UTR is ₹{hits[0]['amount']:,}. A pack with conflicting facts would mislead the bank.")
    return allow("One exact Paytm record; amounts agree.", "P10")


def _human_only(world, args, ctx):
    return deny("P7", "Under the MHA/I4C SOP the account holder approaches the bank branch, and the bank submits the grievance. Kavach prepares; humans file.")


def _escalate(world, args, ctx):
    return allow("Escalation to a human is always permitted.")


def _resolve(world, args, ctx):
    if not ctx.get("outcome_verified"):
        return deny("P12", "The outcome has not been re-verified against the source of truth yet.")
    return allow("Outcome verified.", "P12")


def _case_event(world, args, ctx):
    if args.get("event") not in ("bank_complaint", "bank_submission"):
        return deny("P7", "Unknown case event.")
    return allow("Recorded as Meena-reported (indicative) until a document confirms it.")


def _draft(world, args, ctx):
    if "merchant" not in ctx.get("approvals", set()):
        return Decision("NEEDS_APPROVAL", "P13", "The letter goes out in Meena's name.", ["merchant"])
    return allow("Meena approved the draft.", "P13")


_CHECKS = {
    "reconcile_payment": _reconcile,
    "create_support_case": lambda w, a, c: allow("Opening a case is always allowed."),
    "record_case_event": _case_event,
    "draft_escalation": _draft,
    "draft_lien_request": _draft,
    "issue_verified_receipt": _receipt,
    "replay_soundbox": _soundbox,
    "request_payment": _request_payment,
    "initiate_refund": _refund,
    "send_customer_update_simulated": _customer_update,
    "notify_merchant": _notify_merchant,
    "schedule_followup": _followup,
    "request_settlement_hold": _pause,
    "change_settlement_account": _change_account,
    "generate_evidence_pack": _evidence,
    "file_grievance": _human_only,
    "contact_authority": _human_only,
    "escalate_to_human": _escalate,
    "resolve_incident": _resolve,
}
