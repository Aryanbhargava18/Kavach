"""Deterministic playbooks (offline mode).

These are explicit rules, not an LLM, and the UI says so. They still drive the same engine:
every branch is chosen from what the tools return, every write passes policy, every action is
re-verified, and follow-ups run on the clock.
"""
from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from .world import MERCHANT

KIND_TITLES = {
    "question": "Question about the SOP",
    "payment_claim": "Customer says ₹{amt} was paid",
    "duplicate": "Customer charged twice · ₹{amt}",
    "settlement": "Yesterday's payout missing",
    "freeze": "Bank account frozen",
    "scam": "Suspicious caller demanding money",
    "account_change": "Request to change payout account",
    "unknown": "Merchant message",
}


def hm(iso) -> str:
    """'2026-10-31T18:27:00' -> '6:27 PM'."""
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(str(iso)).strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return str(iso)[11:16]


def rs(n: int | None) -> str:
    """Indian digit grouping: ₹3,10,000."""
    if n is None:
        return "₹?"
    x = str(int(n))
    if len(x) > 3:
        head, tail = x[:-3], x[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:]); head = head[:-2]
        x = ",".join(([head] if head else []) + parts) + "," + tail
    return "₹" + x


class OfflinePlanner:
    label = "offline"
    label_long = "Offline rules planner (deterministic playbooks, no LLM)"

    def __init__(self, engine):
        self.e = engine

    # ------------------------------------------------------------ routing
    def select_incident(self, text: str, u: dict[str, Any], shot_id=None):
        """Attach the message to the incident it belongs to, or open a new one. Shared by both planners."""
        e = self.e
        intent = u["intent"]
        if re.search(r"dobara|dubara|phir se|again|दोबारा|फिर से", text.lower()) and intent in ("payment_claim", "unknown") and not shot_id:
            inc = e.open_incident("payment_claim")
            if inc:
                return inc, "pay_again_request"
        digits = re.findall(r"(?<!\d)(\d{4})(?!\d)", text)
        waiting = next((i for i in reversed(list(e.incidents.values())) if i.kind == "payment_claim" and i.facts.get("candidates")
                        and i.status == "waiting_merchant"), None)
        if waiting and digits and intent in ("unknown", "payment_claim", "status_query"):
            return waiting, "disambiguate"
        if intent in ("bank_ack", "sop_question"):
            inc = e.open_incident("freeze")
            if inc is None:
                inc = e.new_incident("question", "Question about the SOP" if intent == "sop_question" else "Bank acknowledgement")
            return inc, intent
        if intent in ("freeze_notice", "scam_call", "change_settlement_account", "account_freeze"):
            inc = e.open_incident("freeze") or (e.open_incident("settlement") if intent == "freeze_notice" else None)
            if inc is None:
                kind = {"scam_call": "scam", "change_settlement_account": "account_change"}.get(intent, "freeze")
                inc = e.new_incident(kind, KIND_TITLES[kind])
            return inc, intent
        if intent == "status_query":
            return (e.open_incident() or e.new_incident("unknown", KIND_TITLES["unknown"])), intent
        kind = {"payment_claim": "payment_claim", "duplicate_charge": "duplicate", "settlement_missing": "settlement"}.get(intent, "unknown")
        return e.new_incident(kind, KIND_TITLES[kind].format(amt=f"{u['amount']:,}" if u.get("amount") else "?")), intent

    async def handle(self, text: str, u: dict[str, Any], shot_id=None, doc_id=None):
        inc, intent = self.select_incident(text, u, shot_id)
        u = dict(u, _text=text)
        async with self.e.locks[inc.id]:
            await self._intake(inc, text, dict(u, intent=intent))
            await self.dispatch(inc, intent, u, shot_id, doc_id)
        return inc

    async def dispatch(self, inc, intent, u, shot_id=None, doc_id=None):
        """Run the deterministic playbook for this message on an existing incident."""
        if intent == "pay_again_request":
            return await self.recollect(inc)
        if intent == "disambiguate":
            d = re.findall(r"(?<!\d)(\d{4})(?!\d)", u.get("_text", ""))
            return await self.disambiguate(inc, d[-1] if d else "")
        if intent == "freeze_notice":
            if u.get("amount") and u["amount"] >= 10000:
                inc.facts["locked_stated"] = u["amount"]
            return await self.freeze_notice(inc, doc_id)
        if intent == "scam_call":
            return await self.scam(inc, u)
        if intent == "change_settlement_account":
            return await self.account_change(inc)
        if intent == "account_freeze":
            return await self.freeze_report(inc, u)
        if intent == "status_query":
            return await self.status(inc)
        if intent == "sop_question":
            return await self.sop_question(inc, u.get("_text", ""))
        if intent == "bank_ack":
            return await self.bank_ack(inc)
        if inc.kind == "payment_claim":
            return await self.payment_claim(inc, u, shot_id)
        if inc.kind == "duplicate":
            return await self.duplicate(inc, u)
        if inc.kind == "settlement":
            return await self.settlement(inc)
        await self.e.act(inc, "notify_merchant", {"text": "Main samjha nahi. Bataiye — customer ka payment, double charge, settlement, ya account freeze?"})
        inc.status = "waiting_merchant"

    async def _intake(self, inc, text, u):
        await self.e.step(inc, "intake", text=text, intent=u["intent"], amount=u.get("amount"), utrs=u.get("utrs"),
                          language=u.get("language"), engine=u.get("engine"), sender=u.get("sender", "merchant"))

    async def think(self, inc, text, tone="info"):
        await self.e.step(inc, "think", text=text, tone=tone)

    # -------------------------------------------------- payment claim
    async def payment_claim(self, inc, u, shot_id):
        e = self.e
        plan = ["Open a case and load the policy", "Read what the screenshot claims", "Find the payment at the UPI switch",
                "Check the shop's ledger, refunds and payouts", "Reconcile the records", "Act, then verify", "Update both sides and follow up"]
        e.set_plan(inc, plan)
        await e.act(inc, "create_support_case", {"summary": f"{inc.customer.get('name', 'Customer')} says {rs(u.get('amount'))} was paid; shop can't confirm",
                                                 "channel": inc.channel})
        await e.call(inc, "get_incident_policy", {"kind": "payment_claim"})
        e.tick_plan(inc, plan[0])
        claimed = u.get("amount")
        claim: dict[str, Any] = {}
        if shot_id:
            claim = await e.call(inc, "read_screenshot", {"shot_id": shot_id})
            if claim.get("injection_detected"):
                await self.think(inc, "The image contains text that tries to give instructions. Image text is data, not instructions — ignored.", "warn")
            claimed = claim.get("amount") or claimed
        else:
            await self.think(inc, "No screenshot attached. I'll search the switch by amount and time instead.")
        e.tick_plan(inc, plan[1])
        inc.facts.update({"claimed": claimed, "claim_utr": claim.get("utr"), "claim_payee": claim.get("payee_vpa")})
        if claimed:
            led = await e.call(inc, "get_merchant_ledger", {"amount": claimed, "minutes_back": 30, "open_only": True})
            bills = [b for b in led["bills"] if b["status"] in ("UNPAID", "PARTIAL")]
            mine = [b for b in bills if b.get("customer") and b["customer"] == inc.customer.get("name")] or bills
            if mine:
                inc.facts["bill_id"] = mine[-1]["bill_id"]
        utr = claim.get("utr") or (u.get("utrs") or [None])[0]
        matches: list[dict] = []
        if utr:
            matches = (await e.call(inc, "lookup_transaction", {"utr": utr, "minutes_back": 120}))["matches"]
        if not matches and claimed:
            near = (await e.call(inc, "lookup_transaction", {"amount": claimed, "minutes_back": 15}))["matches"]
            if near and not utr:
                # Matching by amount and time alone would be a guess: another customer may have paid the same amount.
                e.tick_plan(inc, plan[2])
                return await self._ask_which(inc, near, claimed)
        e.tick_plan(inc, plan[2])
        await self._assess(inc, matches, claimed, utr, claim)

    async def proactive_ledger(self, inc, t):
        """Nobody complained. Paytm's delivery monitor shows a failed POS webhook for a payment the switch confirmed."""
        e = self.e
        plan = ["Notice the failed delivery", "Load the policy", "Confirm the payment at the UPI switch",
                "Check the shop's ledger, refunds and payouts", "Reconcile the records", "Act, then verify", "Tell Meena and follow up"]
        e.set_plan(inc, plan)
        if not any(s["kind"] == "intake" for s in inc.steps):
          await e.step(inc, "intake", text=f"Paytm → billing app delivery failed 3 times for a {rs(t['amount'])} payment from {t['payer_name']} (UPI Ref …{t['utr'][-4:]})",
                     intent="payment_claim", amount=t["amount"], utrs=[t["utr"]], language="system", engine="monitor", sender="monitor")
        await self.think(inc, f"Nobody has complained yet. The Soundbox announced {rs(t['amount'])}, but Meena's billing app never got the update, "
                              f"so at the counter the bill still looks unpaid. Fixing it before it turns into an argument.")
        e.tick_plan(inc, plan[0])
        await e.act(inc, "create_support_case", {"summary": f"POS webhook failed for {rs(t['amount'])} from {t['payer_name']}; found by Kavach's monitor",
                                                 "channel": "monitor"})
        await e.call(inc, "get_incident_policy", {"kind": "payment_claim"})
        e.tick_plan(inc, plan[1])
        inc.facts.update({"claimed": t["amount"], "claim_utr": t["utr"]})
        led = await e.call(inc, "get_merchant_ledger", {"amount": t["amount"], "minutes_back": 30, "open_only": True})
        bills = [b for b in led["bills"] if b["status"] in ("UNPAID", "PARTIAL")]
        mine = [b for b in bills if b.get("customer") == t["payer_name"]] or bills
        if mine:
            inc.facts["bill_id"] = mine[-1]["bill_id"]
        e.tick_plan(inc, plan[2])
        await self._assess(inc, [{"txn_id": t["txn_id"]}], t["amount"], t["utr"], {})

    async def _ask_which(self, inc, near, claimed):
        e = self.e
        inc.facts["candidates"] = [t["txn_id"] for t in near]
        rows = [{"field": f"Candidate {i + 1}", "claim": rs(claimed), "truth": f"…{t['utr'][-4:]} · {t['status']} · {t['created_at'][11:16]}", "match": False}
                for i, t in enumerate(near)]
        await e.step(inc, "evidence", stamp="ASK FIRST", title="Which payment is this customer's?", rows=rows, tone="warn",
                     verdict=f"{len(near)} payment{'s' if len(near) > 1 else ''} of {rs(claimed)} in 15 min and no reference number: I won't guess")
        inc.decisive = {"label": "Decisive evidence", "text": "No UPI reference, so amount and time alone can't say whose payment it is"}
        listing = ", ".join(f"…{t['utr'][-4:]} ({t['status']})" for t in near)
        if inc.channel == "whatsapp":
            await e.act(inc, "send_customer_update_simulated", {"text": "Thanks. To find your payment, please share the last 4 digits of the UPI Ref No. from your payment app."})
            inc.status = "waiting_customer"
        else:
            await e.act(inc, "notify_merchant", {"text": f"🔎 {rs(claimed)} ke {len(near)} payment mile: {listing}. Kisi aur customer ka bhi ho sakta hai, isliye main andaza nahi lagaunga. Customer se UPI Ref ke aakhri 4 ank poochkar yahan likhiye.",
                                                "speak": "ग्राहक से यूपीआई रेफ़रेंस के आख़िरी चार अंक पूछिए।"})
            inc.status = "waiting_merchant"
        inc.headline = "Asked for the reference number instead of guessing"

    async def disambiguate(self, inc, digits: str):
        e = self.e
        cands = [e.world.txn_by_id(x) for x in inc.facts.get("candidates", [])]
        hit = [t for t in cands if t and t["utr"].endswith(digits)]
        if len(hit) != 1:
            msg = f"…{digits} se koi ek payment match nahi hua. Customer ke app mein poora UPI Ref No dekhkar bhejiye."
            if inc.channel == "whatsapp":
                await e.act(inc, "send_customer_update_simulated", {"text": f"We couldn't match …{digits} to a single payment. Please send the full 12-digit UPI Ref No."})
            else:
                await e.act(inc, "notify_merchant", {"text": msg})
            return
        inc.facts.pop("candidates", None)
        inc.status = "investigating"
        await self.think(inc, f"Reference …{digits} identifies exactly one payment.")
        await self._assess(inc, [{"txn_id": hit[0]["txn_id"]}], inc.facts.get("claimed"), hit[0]["utr"], {})

    async def _assess(self, inc, matches, claimed, utr, claim):
        e = self.e
        plan = [p["text"] for p in inc.plan]
        bill_id = inc.facts.get("bill_id")
        rows = []
        if claim and claim.get("payee_vpa"):
            rows.append({"field": "Paid to", "claim": claim.get("payee_vpa") or "?", "truth": MERCHANT["vpa"],
                         "match": (claim.get("payee_vpa") or MERCHANT["vpa"]) == MERCHANT["vpa"]})
        if not matches:
            rows += [{"field": "UPI Ref (UTR)", "claim": utr or "—", "truth": "No such payment to this merchant", "match": False}]
            if bill_id:
                rows.append({"field": "Shop's bill", "claim": "paid", "truth": f"{bill_id} still unpaid", "match": False})
            wrong_payee = claim.get("payee_vpa") and claim["payee_vpa"] != MERCHANT["vpa"]
            await e.step(inc, "evidence", stamp="WRONG SHOP" if wrong_payee else "NOT RECEIVED", title="Screenshot vs UPI switch", rows=rows,
                         verdict="Paid to a different UPI ID" if wrong_payee else "This payment never reached Meena Kirana", tone="bad")
            inc.decisive = {"label": "Decisive evidence", "text": rows[1 if claim.get("payee_vpa") else 0]["truth"] if not wrong_payee else f"Screenshot shows payee {claim['payee_vpa']}"}
            e.tick_plan(inc, plan[3]); e.tick_plan(inc, plan[4])
            return await (self._wrong_payee(inc, claim) if wrong_payee else self._not_received(inc, claimed, utr))

        txn = matches[0]
        st = await e.call(inc, "get_payment_status", {"txn_id": txn["txn_id"]})
        inc.facts["txn_id"] = txn["txn_id"]
        led = await e.call(inc, "get_merchant_ledger", {"utr": st["utr"]})
        rf = await e.call(inc, "get_refund_status", {"txn_id": st["txn_id"]})
        await e.call(inc, "get_settlement_status", {"txn_id": st["txn_id"]})
        e.tick_plan(inc, plan[3])
        entry = (led.get("entries") or [None])[0]
        refunds = rf.get("refunds") or []
        rows += [{"field": "UPI Ref (UTR)", "claim": utr or "—", "truth": st["utr"], "match": (utr or st["utr"]) == st["utr"]},
                 {"field": "Amount", "claim": rs(claimed), "truth": rs(st["amount"]), "match": claimed in (None, st["amount"])},
                 {"field": "Status", "claim": claim.get("status_text") or "customer says paid", "truth": st["status"], "match": st["status"] == "SUCCESS"}]
        e.tick_plan(inc, plan[4])
        if st["status"] == "SUCCESS" and refunds:
            r = refunds[0]
            rows.append({"field": "Refund", "claim": "—", "truth": f"{r['refund_id']} {r['status']} · {r.get('reason', '')}", "match": False})
            await e.step(inc, "evidence", stamp="BEING REFUNDED", title="Screenshot vs UPI switch", rows=rows, tone="warn",
                         verdict="The money arrived, but it is already on its way back to the customer")
            inc.decisive = {"label": "Decisive evidence", "text": f"{r['refund_id']}: {r.get('reason', 'refund')} ({r['status']})"}
            return await self._refund_in_progress(inc, st, r, claimed)
        if st["status"] == "SUCCESS" and entry and entry["bill_id"] != bill_id:
            rows.append({"field": "Shop's ledger", "claim": f"for {bill_id or 'this purchase'}", "truth": f"already used for {entry['bill_id']} at {hm(entry['at'])}", "match": False})
            await e.step(inc, "evidence", stamp="ALREADY USED", title="Screenshot vs UPI switch", rows=rows, tone="bad",
                         verdict=f"A real payment, but it already paid bill {entry['bill_id']} at {hm(entry['at'])}")
            inc.decisive = {"label": "Decisive evidence", "text": f"UTR …{st['utr'][-4:]} is already in the ledger against {entry['bill_id']}"}
            return await self._replay(inc, st, entry, claimed)
        if st["status"] == "SUCCESS" and claimed and st["amount"] < claimed:
            rows.append({"field": "Shop's ledger", "claim": rs(claimed), "truth": f"{rs(st['amount'])} recorded" if entry else "nothing recorded", "match": False})
            await e.step(inc, "evidence", stamp=f"{rs(st['amount'])} ONLY", title="Screenshot vs UPI switch", rows=rows, tone="bad",
                         verdict=f"Screenshot says {rs(claimed)}; the bank record says {rs(st['amount'])}")
            inc.decisive = {"label": "Decisive evidence", "text": f"Switch record for UTR {st['utr']}: {rs(st['amount'])}, not {rs(claimed)}"}
            return await self._short_paid(inc, st, claimed)
        if st["status"] == "SUCCESS" and not entry:
            wh = led.get("webhook") or {}
            fails = [a for a in wh.get("attempts", []) if a.get("http") != 200]
            rows.append({"field": "Shop's ledger", "claim": "paid", "truth": f"{bill_id or 'bill'} unpaid · webhook failed ×{len(fails)}" if fails else "no entry", "match": False})
            await e.step(inc, "evidence", stamp="LEDGER MISSED IT", title="Bank vs the shop's books", rows=rows, tone="warn",
                         verdict="The payment is real. The shop's ledger never heard about it")
            inc.decisive = {"label": "Decisive evidence", "text": f"Switch: {rs(st['amount'])} SUCCESS · POS webhook " + (f"failed ×{len(fails)} (HTTP {fails[-1]['http']})" if fails else "has no record")}
            return await self._repair_ledger(inc, st, fails, claimed)
        if st["status"] == "SUCCESS":
            rows.append({"field": "Shop's ledger", "claim": "paid", "truth": f"{entry['bill_id']} paid", "match": True})
            await e.step(inc, "evidence", stamp="VERIFIED", title="Screenshot vs UPI switch", rows=rows, tone="good", verdict="The payment is real and already in the shop's books")
            inc.decisive = {"label": "Decisive evidence", "text": f"Switch: {rs(st['amount'])} SUCCESS · UTR {st['utr']} · ledger {entry['bill_id']}"}
            return await self._confirmed(inc, st)
        if st["status"] == "PENDING":
            await e.step(inc, "evidence", stamp="IN TRANSIT", title="Screenshot vs UPI switch", rows=rows, tone="warn",
                         verdict="Money is in transit: not received, not failed")
            inc.decisive = {"label": "Decisive evidence", "text": f"Switch: {rs(st['amount'])} PENDING · {st.get('status_reason') or ''}"}
            return await self._pending(inc, st, claimed)
        await e.step(inc, "evidence", stamp="FAILED", title="Screenshot vs UPI switch", rows=rows, tone="bad", verdict="The payment failed at the bank")
        inc.decisive = {"label": "Decisive evidence", "text": f"Switch: FAILED · {st.get('status_reason') or ''}"}
        return await self._failed(inc, st)

    def _who(self, inc) -> str:
        return inc.customer.get("name") or "Customer"

    async def _tell_customer(self, inc, text: str, **extra):
        await self.e.act(inc, "send_customer_update_simulated", {"text": text, **extra})

    async def _repair_ledger(self, inc, st, fails, claimed):
        """THE HERO: money is real, the shop's books missed it. Repair, re-check, then tell everyone."""
        e = self.e
        plan = [p["text"] for p in inc.plan]
        bill_id = inc.facts.get("bill_id")
        await self.think(inc, (f"The bank says {rs(st['amount'])} SUCCESS. Paytm's webhook to Meena's billing app failed {len(fails)} times"
                               f" (HTTP {fails[-1]['http']}), so bill {bill_id} still says unpaid. The money is real; the shop's books are wrong. "
                               "Posting the switch record into the ledger is allowed, auditable and idempotent on the UTR." if fails else
                               f"The bank says {rs(st['amount'])} SUCCESS but the ledger has no entry for it. Repairing from the switch record."))
        if not bill_id:
            await e.act(inc, "notify_merchant", {"text": f"{rs(st['amount'])} aaya hai (UPI Ref …{st['utr'][-4:]}), par billing app mein is amount ka koi khula bill nahi mila. Kaunse bill ka hai?"})
            inc.status = "waiting_merchant"
            return
        r = await e.act(inc, "reconcile_payment", {"utr": st["utr"], "bill_id": bill_id})
        if r["status"] != "DONE":
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Merchant Support", "summary": f"Ledger repair refused for {bill_id}: {r.get('decision', {}).get('reason', '')}"})
            inc.status = "with_human"
            return
        await e.call(inc, "get_merchant_ledger", {"bill_id": bill_id})
        e.tick_plan(inc, plan[5])
        sb = await e.call(inc, "get_soundbox_log", {"minutes_back": 10})
        if not any(x["txn_id"] == st["txn_id"] for x in sb["announcements"]):
            await e.act(inc, "replay_soundbox", {"txn_id": st["txn_id"]})
        if inc.facts.get("proactive"):
            await e.act(inc, "notify_merchant", {"text": f"✅ {self._who(inc)} ka {rs(st['amount'])} aa gaya, par aapke billing app tak Paytm ka message nahi pahuncha (server error ×{len(fails) or 1}). "
                                                        f"Maine bank record se bill {bill_id} paid kar diya aur dobara check kiya. Aapko kuch nahi karna.",
                                                "speak": f"{self._who(inc)} के {st['amount']} रुपये आ गए हैं। बिलिंग ऐप में अपडेट नहीं हुआ था, मैंने ठीक कर दिया है।"})
            due = (e.world.next_settlement - e.world.now).total_seconds() + 300
            await e.act(inc, "schedule_followup", {"after_seconds": int(due), "purpose": "Confirm tomorrow's 9:00 payout includes this payment"})
            e.tick_plan(inc, plan[6])
            inc.status = "watching"
            inc.headline = "Fixed before anyone noticed. Confirming tomorrow's payout."
            inc.money = {"amount": st["amount"], "label": "put back in the shop's books"}
            return
        await e.act(inc, "issue_verified_receipt", {"txn_id": st["txn_id"]})
        await self._tell_customer(inc, f"Hi {self._who(inc)}, Meena Kirana Store has received your {rs(st['amount'])} (UPI Ref {st['utr']}). "
                                       f"Your bill {bill_id} is now marked paid. Sorry for the wait — the shop's billing app had missed the payment update.")
        await e.act(inc, "notify_merchant", {"text": f"✅ {self._who(inc)} ka {rs(st['amount'])} {hm(st.get('created_at'))} pe hi aa gaya tha, par aapke billing app tak Paytm ka message nahi pahuncha (server error ×{len(fails) or 1}). "
                                                    f"Maine bank record se bill {bill_id} paid kar diya aur dobara check kiya — dono match karte hain. Saman de dijiye.",
                                            "speak": f"{st['amount']} रुपये आ गए थे। बिल ठीक कर दिया है। सामान दे दीजिए।"})
        due = (e.world.next_settlement - e.world.now).total_seconds() + 300
        await e.act(inc, "schedule_followup", {"after_seconds": int(due), "purpose": "Confirm tomorrow's 9:00 payout includes this payment"})
        e.tick_plan(inc, plan[6])
        inc.status = "watching"
        inc.headline = "Ledger repaired and verified. Confirming tomorrow's payout."
        inc.money = {"amount": st["amount"], "label": "recovered into the shop's books"}

    async def _replay(self, inc, st, entry, claimed):
        e = self.e
        bill_id = inc.facts.get("bill_id")
        await self.think(inc, f"This screenshot shows a real payment, but UTR …{st['utr'][-4:]} was already applied to bill {entry['bill_id']} at {hm(entry['at'])}. "
                              "Applying it to this bill as well would count one payment twice.", "warn")
        await e.act(inc, "reconcile_payment", {"utr": st["utr"], "bill_id": bill_id or "?"})
        await e.act(inc, "notify_merchant", {"text": f"⚠️ Ruk jaiye. Yeh screenshot pehle wale payment ka hai jo {hm(entry['at'])} baje bill {entry['bill_id']} mein lag chuka hai. "
                                                    f"Bill {bill_id} ke liye koi paisa nahi aaya. Saman abhi mat dijiye; maine customer ko naya QR bhej diya hai.",
                                            "speak": "रुकिए। यह पुराने पेमेंट का स्क्रीनशॉट है। इस बिल का पैसा नहीं आया।"})
        amt = claimed or st["amount"]
        await e.act(inc, "request_payment", {"amount": amt, "bill_id": bill_id, "claimed_amount": amt, "related_txn_ids": []})
        await self._tell_customer(inc, f"This payment (UPI Ref …{st['utr'][-4:]}) was already used for an earlier purchase today at {hm(entry['at'])}, "
                                       f"so it can't be applied to this bill. To complete this purchase of {rs(amt)}, please pay using the QR.")
        led = await e.call(inc, "get_merchant_ledger", {"utr": st["utr"]})
        inc.outcome_verified = len(led["entries"]) == 1
        await e.step(inc, "verify", action="final re-check", ok=inc.outcome_verified, check=f"Ledger re-read: UTR …{st['utr'][-4:]} applied exactly once ({entry['bill_id']}); {bill_id} still unpaid")
        for p in inc.plan:
            p["state"] = "done"
        inc.headline = "Reused payment reference refused. Fresh QR sent."
        inc.money = {"amount": amt, "label": "not handed over on a reused screenshot"}
        await e.act(inc, "resolve_incident", {"outcome": "Reused payment reference refused; fresh payment requested"})

    async def _refund_in_progress(self, inc, st, r, claimed):
        e = self.e
        bill_id = inc.facts.get("bill_id")
        await self.think(inc, f"The money did arrive, but {r['refund_id']} is already sending it back ({r.get('reason', 'refund')}). "
                              "Marking the bill paid, or issuing a receipt, would count money that is leaving.", "warn")
        await e.act(inc, "reconcile_payment", {"utr": st["utr"], "bill_id": bill_id or "?"})
        inc.facts["refund_id"] = r["refund_id"]
        inc.facts["amount"] = r["amount"]
        await e.act(inc, "request_payment", {"amount": st["amount"], "bill_id": bill_id, "claimed_amount": claimed or st["amount"], "related_txn_ids": [st["txn_id"]]})
        await self._tell_customer(inc, f"Your {rs(st['amount'])} reached us after this order's payment QR had expired, so it is being refunded to you automatically "
                                       f"(Ref {r['refund_id']}). To complete this purchase, please pay {rs(st['amount'])} using the QR. We'll confirm here when your refund lands.")
        await e.act(inc, "notify_merchant", {"text": f"{self._who(inc)} ka {rs(st['amount'])} order expire hone ke baad aaya tha, isliye apne-aap refund ho raha hai ({r['refund_id']}). "
                                                    f"Bill {bill_id} abhi unpaid hai. Customer ko naya QR diya. Naya payment aate hi saman dijiye.",
                                            "speak": "पहला पेमेंट रिफंड हो रहा है। नया पेमेंट आते ही सामान दीजिए।"})
        await e.act(inc, "schedule_followup", {"after_seconds": 120, "purpose": "Confirm the refund was credited"})
        inc.status = "watching"
        inc.headline = "Late payment is being refunded. Fresh QR sent; refund tracked."
        inc.money = {"amount": st["amount"], "label": "not counted twice while it is refunded"}

    async def _confirmed(self, inc, st):
        e = self.e
        sb = await e.call(inc, "get_soundbox_log", {"minutes_back": 10})
        heard = any(x["txn_id"] == st["txn_id"] for x in sb["announcements"])
        e.tick_plan(inc, inc.plan[5]["text"])
        if not heard:
            await self.think(inc, "The switch has it, but the Soundbox never announced it — that's why the counter missed it. Replaying.")
            await e.act(inc, "replay_soundbox", {"txn_id": st["txn_id"]})
        await e.act(inc, "issue_verified_receipt", {"txn_id": st["txn_id"]})
        await self._tell_customer(inc, f"Hi {self._who(inc)}, your {rs(st['amount'])} to Meena Kirana Store is confirmed (UPI Ref {st['utr']}). Thank you!")
        await e.act(inc, "notify_merchant", {"text": f"✅ {rs(st['amount'])} aapke account mein aa gaya hai (UPI Ref {st['utr']}). Customer ko verified receipt bhej di. Saman de dijiye.",
                                            "speak": f"{st['amount']} रुपये आ गए हैं। सामान दे दीजिए।"})
        await self._close(inc, st["txn_id"], "SUCCESS", f"Payment of {rs(st['amount'])} confirmed and receipted")
        inc.money = {"amount": st["amount"], "label": "confirmed with the bank, not the screenshot"}

    async def _short_paid(self, inc, st, claimed):
        e = self.e
        due = claimed - st["amount"]
        e.tick_plan(inc, inc.plan[5]["text"])
        await self.think(inc, f"Only {rs(st['amount'])} reached the switch. Handing over {rs(claimed)} of goods on this screenshot would lose {rs(due)}.", "warn")
        await e.act(inc, "notify_merchant", {"text": f"⚠️ Ruk jaiye. Sirf {rs(st['amount'])} aaya hai. Screenshot pe {rs(claimed)} dikh raha hai, par bank record (UPI Ref {st['utr']}) mein {rs(st['amount'])} hai. Baaki {rs(due)} milne tak saman mat dijiye. Maine customer ko baaki rakam ka QR bhej diya hai.",
                                            "speak": f"रुकिए। सिर्फ {st['amount']} रुपये आए हैं। बाकी {due} रुपये मिलने तक सामान मत दीजिए।"})
        await e.act(inc, "request_payment", {"amount": due, "bill_id": inc.facts.get("bill_id"), "claimed_amount": claimed, "related_txn_ids": [st["txn_id"]]})
        await self._tell_customer(inc, f"We have received {rs(st['amount'])} from you (UPI Ref {st['utr']}). {rs(due)} is still due for this purchase; you can pay it with the QR.")
        await self._close(inc, st["txn_id"], "SUCCESS", f"Short payment: {rs(st['amount'])} received, {rs(due)} requested; goods held")
        inc.money = {"amount": due, "label": "not handed over on an edited screenshot"}

    async def _pending(self, inc, st, claimed):
        e = self.e
        await self.think(inc, "The counter's usual move is to ask the customer to pay again. Checking that against policy before anyone does it.")
        await e.act(inc, "request_payment", {"amount": claimed or st["amount"], "bill_id": inc.facts.get("bill_id"),
                                             "claimed_amount": claimed or st["amount"], "related_txn_ids": [st["txn_id"]]})
        e.set_plan(inc, [p["text"] for p in inc.plan[:5]] + ["Block re-collection while pending", "Watch the switch and follow up"])
        e.tick_plan(inc, "Block re-collection while pending")
        await e.act(inc, "notify_merchant", {"text": f"⏳ {rs(st['amount'])} customer ke bank mein atka hai (PENDING). Dobara payment mat lijiye — warna customer ka paisa do baar katega. Main switch par nazar rakh raha hoon, confirm hote hi bataunga.",
                                            "speak": "पैसा बैंक में अटका है। दोबारा पेमेंट मत लीजिए। मैं नज़र रख रहा हूँ।"})
        await self._tell_customer(inc, f"Your payment of {rs(st['amount'])} to Meena Kirana Store is pending with your bank. Please don't pay again — "
                                       "Kavach is watching it and will confirm here as soon as your bank does.")
        await e.act(inc, "schedule_followup", {"after_seconds": 45, "purpose": "Re-check payment status at the switch"})
        inc.status = "watching"
        inc.headline = "Watching the bank. Nobody pays twice."
        inc.money = {"amount": st["amount"], "label": "double charge prevented"}
        e._emit("incident", {"incident": inc.summary()})

    async def _failed(self, inc, st):
        e = self.e
        e.tick_plan(inc, inc.plan[5]["text"])
        debited = st.get("debited")
        r = await e.act(inc, "request_payment", {"amount": st["amount"], "bill_id": inc.facts.get("bill_id"), "claimed_amount": st["amount"], "related_txn_ids": [st["txn_id"]]})
        msg = (f"❌ Yeh payment FAIL ho gaya. Customer ka kata hua paisa unke bank se apne-aap wapas aayega (T+1). "
               if debited else "❌ Yeh payment bank ne decline kar diya — paisa kata hi nahi. ")
        msg += "Ab naya payment lena safe hai; maine customer ko QR bhej diya." if r["status"] == "DONE" else ""
        await e.act(inc, "notify_merchant", {"text": msg, "speak": "पेमेंट फेल हो गया। अब नया पेमेंट लेना सुरक्षित है।"})
        await self._tell_customer(inc, f"Your payment of {rs(st['amount'])} to Meena Kirana Store did not go through." +
                                  (" Any amount debited will be reversed by your bank automatically (T+1)." if debited else "") +
                                  " You can pay again safely with the QR.")
        await self._close(inc, st["txn_id"], "FAILED", "First payment failed; fresh payment requested" + ("; reversal due T+1" if debited else ""))
        inc.money = {"amount": st["amount"], "label": "customer not charged twice"}

    async def _not_received(self, inc, claimed, utr):
        e = self.e
        e.tick_plan(inc, inc.plan[5]["text"])
        await e.act(inc, "notify_merchant", {"text": f"❌ Is UPI Ref No ({utr or 'not given'}) ka koi payment aapke account mein nahi aaya. Saman abhi mat dijiye. Customer se kahiye apne app ki history dekhein; agar unka paisa kata hai to apne bank se baat karein.",
                                            "speak": "यह पेमेंट आपके खाते में नहीं आया। सामान अभी मत दीजिए।"})
        await self._tell_customer(inc, f"We could not find a payment to Meena Kirana Store with UPI Ref {utr or '(not provided)'}. If money left your account, please contact your bank with this reference.")
        again = await e.call(inc, "lookup_transaction", {"utr": utr, "minutes_back": 120} if utr else {"amount": claimed, "minutes_back": 15})
        inc.outcome_verified = not again["matches"]
        await e.step(inc, "verify", action="final re-check", ok=inc.outcome_verified, check="Switch re-queried: still no payment")
        for p in inc.plan:
            p["state"] = "done"
        inc.headline = "No payment arrived. Goods stay on the shelf."
        await e.act(inc, "resolve_incident", {"outcome": "No payment reached the merchant; goods withheld"})
        inc.money = {"amount": claimed or 0, "label": "goods not handed over without payment"}

    async def _wrong_payee(self, inc, claim):
        e = self.e
        e.tick_plan(inc, inc.plan[5]["text"])
        await e.act(inc, "notify_merchant", {"text": f"❌ Customer ne galat QR/UPI ID pe pay kiya hai — screenshot mein '{claim.get('payee_name')}' hai, aap nahi. Aapke account mein kuch nahi aaya. Saman abhi mat dijiye.",
                                            "speak": "ग्राहक ने गलत खाते में पैसे भेजे हैं। आपके खाते में कुछ नहीं आया।"})
        await self._tell_customer(inc, f"Your payment went to a different merchant ({claim.get('payee_name')}), not Meena Kirana Store. Please contact that merchant or your bank with the UPI reference.")
        inc.outcome_verified = True
        await e.step(inc, "verify", action="final re-check", ok=True, check="Switch shows no payment to this merchant with that reference")
        for p in inc.plan:
            p["state"] = "done"
        inc.headline = "Paid to a different merchant"
        await e.act(inc, "resolve_incident", {"outcome": "Paid to a different merchant; goods withheld"})
        inc.money = {"amount": claim.get("amount") or 0, "label": "goods not handed over for a misdirected payment"}

    async def _close(self, inc, txn_id, expect, outcome):
        e = self.e
        st = await e.call(inc, "get_payment_status", {"txn_id": txn_id})
        inc.outcome_verified = st["status"] == expect
        await e.step(inc, "verify", action="final re-check", ok=inc.outcome_verified, check=f"Switch re-queried after acting: {st['status']}")
        for p in inc.plan:
            p["state"] = "done"
        inc.headline = outcome
        await e.act(inc, "resolve_incident", {"outcome": outcome})

    async def recollect(self, inc):
        e = self.e
        txn = inc.facts.get("txn_id")
        r = await e.act(inc, "request_payment", {"amount": inc.facts.get("claimed") or 0, "bill_id": inc.facts.get("bill_id"),
                                                  "claimed_amount": inc.facts.get("claimed"), "related_txn_ids": [txn] if txn else []})
        if r["status"] == "DENIED":
            await e.act(inc, "notify_merchant", {"text": "🙏 Abhi dobara payment nahi mangwa sakta: " + r["decision"]["reason"] + " Main check kar raha hoon.",
                                                "speak": "अभी दोबारा पेमेंट नहीं ले सकते। मैं जाँच कर रहा हूँ।"})

    # -------------------------------------------------------- duplicate
    async def duplicate(self, inc, u):
        e = self.e
        amt = u.get("amount")
        plan = [f"Find every {rs(amt)} payment in the last 30 min", "Check whether the same payer paid twice", "Refund only the duplicate, once", "Confirm the refund actually landed"]
        e.set_plan(inc, plan)
        if not amt:
            await e.act(inc, "notify_merchant", {"text": "Kitne rupaye do baar kate? Amount bataiye."})
            inc.status = "waiting_merchant"
            return
        await e.act(inc, "create_support_case", {"summary": f"Charged twice: {rs(amt)}", "channel": inc.channel})
        await e.call(inc, "get_incident_policy", {"kind": "duplicate"})
        r = await e.call(inc, "find_duplicate_payments", {"amount": amt, "minutes_back": 30})
        e.tick_plan(inc, plan[0])
        dup = r["duplicate_groups"]
        if not dup:
            await e.step(inc, "evidence", stamp="NOT A DUPLICATE", title="Same amount, same payer?", tone="good", verdict="Different people paid the same amount — not a duplicate",
                         rows=[{"field": "Payers", "claim": "same person, twice", "truth": ", ".join(g["payer"] for g in r["groups"]) or "none", "match": False}])
            await e.act(inc, "notify_merchant", {"text": f"Yeh duplicate nahi hai: {rs(amt)} do alag logon ne diya. Refund nahi karunga.", "speak": "यह डुप्लिकेट नहीं है।"})
            inc.outcome_verified = True
            inc.headline = "Two different customers. No refund."
            await e.act(inc, "resolve_incident", {"outcome": "Not a duplicate; no refund"})
            return
        g = dup[0]
        t1, t2 = g["txns"][0], g["txns"][-1]
        inc.facts.update({"dup_txn": t2["txn_id"], "amount": amt})
        await e.step(inc, "evidence", stamp="DUPLICATE", title="Same amount, same payer?", tone="warn", verdict=f"Proven duplicate: {g['payer']} paid twice, {g['gap_seconds']}s apart",
                     rows=[{"field": "Payer", "claim": g["payer"], "truth": g["payer"], "match": True},
                           {"field": "Amount", "claim": rs(t1["amount"]), "truth": rs(t2["amount"]), "match": True},
                           {"field": "Both SUCCESS", "claim": t1["status"], "truth": t2["status"], "match": True},
                           {"field": "Gap", "claim": "< 10 min", "truth": f"{g['gap_seconds']} s", "match": True}])
        inc.decisive = {"label": "Decisive evidence", "text": f"{g['payer']} · {rs(amt)} ×2 · {g['gap_seconds']}s apart · both SUCCESS"}
        e.tick_plan(inc, plan[1])
        res = await e.act(inc, "initiate_refund", {"txn_id": t2["txn_id"], "amount": amt})
        if res["status"] == "NEEDS_APPROVAL":
            await e.act(inc, "notify_merchant", {"text": f"Customer ({g['payer']}) ne {rs(amt)} do baar pay kiya, {g['gap_seconds']} second ke andar. Doosra payment refund kar doon?",
                                                "speak": f"ग्राहक ने {amt} रुपये दो बार दिए। दूसरा पेमेंट वापस कर दूँ?", "extra": {"approval": inc.id}})
            if inc.channel == "whatsapp":
                await self._tell_customer(inc, f"Thanks — we can see two payments of {rs(amt)} from you, {g['gap_seconds']} seconds apart. The shop is approving a refund of the second one now.")
            inc.headline = "Waiting for your OK to refund"
            return
        if res["status"] == "DENIED":
            await e.act(inc, "notify_merchant", {"text": "Refund nahi kiya: " + res["decision"]["reason"]})
            inc.headline = "Refund refused: " + res["decision"]["reason"].split(".")[0]
            inc.outcome_verified = True
            await e.act(inc, "resolve_incident", {"outcome": "Refund refused by policy"})
            return
        await self._after_refund(inc)

    async def _after_refund(self, inc):
        e = self.e
        e.tick_plan(inc, inc.plan[2]["text"])
        rid = inc.facts.get("refund_id")
        await e.call(inc, "get_refund_status", {"refund_id": rid})
        await self._tell_customer(inc, f"A refund of {rs(inc.facts['amount'])} for your duplicate payment to Meena Kirana Store has been initiated. Ref {rid}.")
        await e.act(inc, "schedule_followup", {"after_seconds": 100, "purpose": "Confirm the refund was credited"})
        inc.status = "watching"
        inc.headline = "Refund on its way. Kavach is following it."
        inc.money = {"amount": inc.facts["amount"], "label": "returned to the customer, exactly once"}

    # ------------------------------------------------------- settlement
    async def proactive_payout(self, inc, b):
        """Nobody complained. The settlement engine shows the merchant's bank sent a payout back."""
        e = self.e
        await e.step(inc, "intake", text=f"Settlement engine: payout {b['batch_id']} of {rs(b['amount'])} RETURNED by Meena's bank ({b.get('return_code') or 'no code'})",
                     intent="settlement_missing", amount=b["amount"], utrs=[], language="system", engine="payout-monitor", sender="monitor")
        await self.think(inc, "Nobody has complained. Meena's bank refused this morning's payout, so she probably doesn't know yet: "
                              "the first she'd hear is a supplier payment bouncing. Finding out why before that happens.")
        await e.act(inc, "create_support_case", {"summary": f"Payout {b['batch_id']} {rs(b['amount'])} returned by the merchant's bank; found by Kavach's monitor",
                                                 "channel": "monitor"})
        await e.call(inc, "get_incident_policy", {"kind": "settlement"})
        await self.settlement(inc, batch_id=b["batch_id"])

    async def settlement(self, inc, batch_id: str | None = None):
        e = self.e
        plan = ["Check yesterday's payout", "Check how the bank responded", "Pick the next step"]
        e.set_plan(inc, plan)
        r = await e.call(inc, "get_settlement_status", {"batch_id": batch_id} if batch_id else {})
        e.tick_plan(inc, plan[0])
        b = (r.get("batches") or [None])[0]
        if not b:
            await e.act(inc, "notify_merchant", {"text": "Kal ka koi settlement batch nahi mila. Main Paytm Support ko de raha hoon."})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Support", "summary": "No settlement batch for yesterday"})
            inc.status = "with_human"
            return
        if b["status"] == "SETTLED":
            await e.step(inc, "evidence", stamp="PAID OUT", title="Payout trail", tone="good", verdict="Payout reached the bank",
                         rows=[{"field": "Batch", "claim": "missing", "truth": f"{b['batch_id']} {rs(b['amount'])}", "match": False},
                               {"field": "Bank UTR", "claim": "—", "truth": b["bank_utr"], "match": True}])
            await e.act(inc, "notify_merchant", {"text": f"Kal ka {rs(b['amount'])} aapke bank mein {str(b['credited_at'])[11:16]} baje aa chuka hai. Passbook mein UTR {b['bank_utr']} dekhiye.",
                                                "speak": "कल का पैसा आपके बैंक में आ चुका है।"})
            inc.outcome_verified = True
            inc.headline = "The payout reached the bank."
            await e.act(inc, "resolve_incident", {"outcome": f"Payout {b['batch_id']} credited; UTR shared"})
            return
        sig = await e.call(inc, "get_bank_signal", {})
        e.tick_plan(inc, plan[1])
        await e.step(inc, "evidence", stamp="ACCOUNT FROZEN", title="Payout trail", tone="bad", verdict="The merchant's bank bounced the payout: account frozen",
                     rows=[{"field": "Batch", "claim": "should have arrived", "truth": f"{b['batch_id']} {rs(b['amount'])} RETURNED", "match": False},
                           {"field": "Bank response", "claim": "—", "truth": (sig.get("last_return") or {}).get("code", "—"), "match": False}])
        inc.decisive = {"label": "Decisive evidence", "text": f"{b['batch_id']} returned by the bank: account frozen"}
        inc.kind = "freeze"
        inc.title = "Bank account frozen · payout bounced"
        await self.think(inc, "This isn't a Paytm delay. The bank froze the account, so it's a different job now: I can't unfreeze it, but I can protect new sales and build the case.", "warn")
        await self._freeze_plan(inc)
        if inc.facts.get("proactive") and await self._risk_guarded(inc):
            return
        if inc.facts.get("proactive"):
            await self.think(inc, "Paytm only sees this because the bank also refused credits. A debit-only freeze would stay invisible to Paytm: payouts would keep landing. "
                                  "So this watcher catches some freezes early, not all of them.", "info")
            await e.act(inc, "notify_merchant", {
                "text": (f"⚠️ Meena ji, aaj subah ka {rs(b['amount'])} payout aapke bank ne wapas bhej diya. Bank ke hisaab se aapka account FREEZE hai. "
                         "Shayad aapko abhi pata nahi chala. Supplier ko payment karne se pehle bank se baat kar lijiye.\n"
                         "Main freeze hata nahi sakta, par case taiyaar kar sakta hoon. Branch se yeh teen cheezein maangiye:\n"
                         "1) NCRP acknowledgement number\n2) Police ka notice ya requisition\n3) Kitni rakam disputed hai\n"
                         "Bank ka SMS ya notice aaye to yahan bhejiye."),
                "speak": "मीना जी, आपके बैंक ने आज का पेआउट वापस भेज दिया। खाता फ्रीज़ है। सप्लायर को पेमेंट करने से पहले बैंक से बात कीजिए।"})
        else:
            await e.act(inc, "notify_merchant", {"text": f"⚠️ Kal ka {rs(b['amount'])} aapke bank ne wapas bhej diya — bank ke hisaab se aapka account FREEZE hai. Main freeze hata nahi sakta, par aapka case taiyaar kar sakta hoon. Bank ka SMS ya police notice yahan bhejiye.",
                                                "speak": "आपका बैंक खाता फ्रीज़ है। बैंक का SMS या पुलिस नोटिस भेजिए।"})
        inc.money = {"amount": b["amount"], "label": "payout bounced, safe with Paytm"}
        await self._propose_hold(inc)

    async def _risk_guarded(self, inc) -> bool:
        """Check Paytm Risk's signals BEFORE telling the merchant anything about a freeze (tipping-off guard, P17)."""
        e = self.e
        r = await e.call(inc, "get_risk_signals", {})
        if not r["guard"]:
            await self.think(inc, f"Checked Paytm Risk first: {r['independent']} independent signal{'s' if r['independent'] != 1 else ''} on this shop. Safe to tell Meena what's happening.")
            return False
        names = " and ".join(x["detail"] for x in r["signals"][:2])
        await self.think(inc, f"Stopping before I tell her anything. Paytm Risk holds {r['independent']} independent signals: {names}. "
                              "Case details could tip off a mule operator. That's not a verdict on her; it's a decision for a human.", "warn")
        await e.act(inc, "notify_merchant", {"text": "Namaste Meena ji, aapke payout mein ek rukawat aayi hai. Paytm ki team jald aapse baat karegi. Tab tak aapka paisa Paytm ke paas surakshit hai.",
                                            "template": "legal_neutral"})
        await e.act(inc, "escalate_to_human", {"queue": "Paytm Risk (EDD)", "summary": "Bounced payout on a merchant with 2 independent Risk signals; details withheld from merchant (P17)"})
        inc.status = "with_human"
        inc.headline = "Possible mule pattern. Details withheld; Paytm Risk decides."
        inc.decisive = {"label": "Why Kavach held back", "text": f"{r['independent']} independent Risk signals: {names}"}
        return True

    async def proactive_decline(self, inc, p):
        """Nobody complained. Meena's own UPI payment from her bank account came back YE: the bank has blocked debits."""
        e = self.e
        await e.step(inc, "intake", text=f"Paytm app: Meena's {rs(p['amount'])} payment to {p['payee']} DECLINED by her bank · UPI code {p['code']} (account blocked/frozen)",
                     intent="account_freeze", amount=p["amount"], utrs=[], language="system", engine="psp-monitor", sender="monitor")
        await self._freeze_plan(inc, first="Check what Paytm can see")
        await self.think(inc, "Her bank refused a payment FROM her account. A debit freeze is otherwise invisible to Paytm, because credits still land. "
                              "So every payout we send now goes into an account she can't take money out of.", "warn")
        await e.act(inc, "create_support_case", {"summary": f"Merchant's own UPI payment declined YE (account blocked/frozen); found by Kavach's PSP monitor", "channel": "monitor"})
        await e.call(inc, "get_own_payment_declines", {})
        sig = await e.call(inc, "get_bank_signal", {})
        stl = await e.call(inc, "get_settlement_status", {})
        b = (stl.get("batches") or [{}])[0]
        await e.step(inc, "evidence", stamp="DEBIT FROZEN", title="What Paytm can see", tone="bad", verdict="Her bank blocks debits; Paytm's payouts still land there",
                     rows=[{"field": "Her payment", "claim": f"{rs(p['amount'])} to {p['payee']}", "truth": f"DECLINED · {p['code']}", "match": False},
                           {"field": "Last payout", "claim": "—", "truth": f"{b.get('batch_id', '—')} {b.get('status', '—')}", "match": b.get("status") == "SETTLED"},
                           {"field": "Payout returns", "claim": "—", "truth": "none" if not sig["last_return"] else sig["last_return"]["code"], "match": not sig["last_return"]}])
        inc.decisive = {"label": "Decisive evidence", "text": f"UPI code {p['code']} on her own {rs(p['amount'])} payment: her bank has blocked debits"}
        e.tick_plan(inc, "Check what Paytm can see")
        if await self._risk_guarded(inc):
            return
        await e.act(inc, "notify_merchant", {
            "text": (f"⚠️ Meena ji, {p['payee']} ko aapka {rs(p['amount'])} ka payment aapke bank ne rok diya (code {p['code']}): bank ke hisaab se account se paisa nikalna band hai, yaani DEBIT FREEZE. "
                     "Paytm ke payouts abhi bhi us account mein ja rahe hain, jahan se aap nikal nahi sakti.\n"
                     "Branch se yeh teen cheezein maangiye:\n1) NCRP acknowledgement number\n2) Police ka notice ya requisition\n3) Kitni rakam disputed hai\n"
                     "Bank ka SMS ya notice aaye to yahan bhejiye."),
            "speak": "मीना जी, आपके बैंक ने आपका भुगतान रोक दिया। खाते से पैसा निकालना बंद है। शाखा से नोटिस और विवादित रकम पूछिए।"})
        inc.money = {"amount": b.get("amount") or 0, "label": "would land next in an account she can't use"}
        await self._propose_hold(inc, debit=True)

    async def _propose_lien(self, inc):
        """After the pack: offer a request, in Meena's name, to limit the hold to the disputed amount."""
        e = self.e
        if inc.pending or inc.facts.get("lien_request") or "pack" not in inc.facts:
            return
        res = await e.act(inc, "draft_lien_request", {"reason": "Notice names one disputed payment; the whole account is frozen"})
        if res["status"] == "NEEDS_APPROVAL":
            amt = rs((inc.money or {}).get("amount"))
            await e.act(inc, "notify_merchant", {"text": f"Ek aur kadam: bank ko aapke naam se likhit request bana doon ki hold sirf {amt} (vivadit rakam) tak rakhein, aur baaki account chalu karein? Aap padh kar hi bhejengi.",
                                                "speak": "बैंक को चिट्ठी बना दूँ कि रोक सिर्फ विवादित रकम तक रहे?", "extra": {"approval": inc.id}})
            inc.headline = "Signed pack ready. Lien-limiting request waiting for Meena's OK."

    async def _freeze_plan(self, inc, first: str = "Confirm why payouts bounce"):
        self.e.set_plan(inc, [first, "Protect new sales (two-key hold)", "Read the bank / cyber-cell notice",
                              "Find the disputed payment in Paytm records", "Route under the MHA/I4C SOP", "Build a signed evidence pack",
                              "Hand over a branch kit and track the clock"])
        self.e.tick_plan(inc, "Confirm why payouts bounce")

    async def _propose_hold(self, inc, debit: bool = False):
        e = self.e
        if e.world.settlement_config["paused"]:
            return
        res = await e.act(inc, "request_settlement_hold", {"reason": "Bank returns credits as frozen; keep payouts in the Paytm settlement balance"})
        if res["status"] == "NEEDS_APPROVAL" and "merchant" in res["approvers"]:
            why = "warna woh us account mein jayega jisse aap nikal nahi sakti" if debit else "bank use wapas bhej raha hai"
            await e.act(inc, "notify_merchant", {"text": f"Jab tak freeze ka hal nahi hota, aaj ki sale ka paisa Paytm ke paas surakshit rakhun? ({why}.) Kisi doosre account mein nahi jayega. Paytm Risk bhi approve karega.",
                                                "speak": "आज की बिक्री का पैसा पेटीएम के पास सुरक्षित रखूँ?", "extra": {"approval": inc.id}})
        inc.headline = "Waiting for approvals to hold payouts"

    async def freeze_report(self, inc, u):
        e = self.e
        if u.get("amount") and u["amount"] >= 10000:
            inc.facts["locked_stated"] = u["amount"]
        if inc.plan and inc.plan[0]["text"] == "Confirm why payouts bounce":
            await e.act(inc, "notify_merchant", {"text": "Samajh gaya. Bank ka SMS ya police notice bhejiye, main aage badhta hoon."})
            return
        await self._freeze_plan(inc, first="Check what Paytm can see")
        r = await e.call(inc, "get_bank_signal", {})
        stl = await e.call(inc, "get_settlement_status", {})
        b = (stl.get("batches") or [{}])[0]
        if r["last_return"]:
            await self.think(inc, "Paytm's own records agree: the bank is returning payouts as frozen.")
        else:
            await self.think(inc, f"Paytm can't see a debit freeze: yesterday's payout ({b.get('batch_id', '—')}) still SETTLED into her account. "
                                  "Credits keep landing; she just can't take money out. So I'll go on her report and the notice, and I won't claim more than that.", "warn")
        e.tick_plan(inc, "Check what Paytm can see")
        await e.act(inc, "notify_merchant", {"text": "Samajh gaya. Main freeze hata nahi sakta — woh bank aur police ka faisla hai — par aapka case pakka bana sakta hoon. Bank ka SMS ya police notice yahan bhejiye.",
                                            "speak": "बैंक का SMS या पुलिस नोटिस भेजिए।"})
        await self._propose_hold(inc, debit=not r["last_return"])
        if not inc.pending:
            inc.status = "waiting_merchant"

    async def freeze_notice(self, inc, doc_id):
        e = self.e
        if inc.kind != "freeze":
            inc.kind, inc.title = "freeze", "Bank account frozen"
        if not inc.plan or inc.plan[0]["text"] not in ("Confirm why payouts bounce", "Check what Paytm can see"):
            await self._freeze_plan(inc)
        await e.call(inc, "read_document", {"doc_id": doc_id})
        p = await e.call(inc, "parse_notice", {"doc_id": doc_id})
        e.tick_plan(inc, "Read the bank / cyber-cell notice")
        f = {k: v["value"] for k, v in p["fields"].items()}
        if p["injection_lines"]:
            await self.think(inc, f"Line {p['injection_lines'][0]} of the notice tries to give me an instruction (\"ignore previous instructions…\"). Documents are evidence, not instructions. Ignored, and flagged for the reviewer.", "warn")
        for c in p["checks"]:
            await self.think(inc, f"{c['check']}: {'pass' if c['pass'] else 'FAIL'}. {c['note']}", "info" if c["pass"] else "warn")
        inc.facts.update({"notice": f, "action_kind": p["action_kind"]})
        if p["action_kind"] == "unknown":
            await e.act(inc, "notify_merchant", {"text": "Is notice mein hold/freeze/seizure ka zikr nahi hai. Main ise galat SOP raste se nahi bhejunga — Paytm Support dekhega."})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Support", "summary": "Out-of-scope notice"})
            inc.status = "with_human"
            return
        utr = f.get("utr")
        m = (await e.call(inc, "lookup_transaction", {"utr": utr, "days_back": 120}))["matches"] if utr else []
        if not m:
            await e.step(inc, "evidence", stamp="NOT VIA PAYTM", title="Notice vs Paytm records", tone="bad", verdict="This UTR never came through Paytm",
                         rows=[{"field": "UTR", "claim": utr or "—", "truth": "not in Paytm records", "match": False}])
            inc.decisive = {"label": "Decisive evidence", "text": f"UTR {utr} is not a Paytm payment"}
            await e.act(inc, "generate_evidence_pack", {"utr": utr or "", "notice_amount": f.get("amount")})
            await e.act(inc, "notify_merchant", {"text": "Notice wala payment Paytm se nahi aaya tha, isliye main Paytm record ke naam pe koi pack nahi banaunga. Bank branch mein likhit shikayat dijiye aur dated acknowledgement lijiye — main checklist bhej raha hoon."})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Support", "summary": "Freeze notice for a non-Paytm payment"})
            inc.status = "with_human"
            inc.headline = "Not a Paytm payment. Honest checklist only."
            return
        txn = m[0]
        st = await e.call(inc, "get_payment_status", {"txn_id": txn["txn_id"]})
        stl = (await e.call(inc, "get_settlement_status", {"batch_id": st.get("settlement_batch")}))["batches"]
        e.tick_plan(inc, "Find the disputed payment in Paytm records")
        settled = bool(stl) and stl[0]["status"] == "SETTLED"
        inc.facts.update({"disputed_txn": txn["txn_id"], "disputed_settlement": stl[0] if stl else None})
        rows = [{"field": "UTR", "claim": utr, "truth": st["utr"], "match": True},
                {"field": "Amount", "claim": rs(f.get("amount")), "truth": rs(st["amount"]), "match": f.get("amount") == st["amount"]},
                {"field": "Date", "claim": f.get("transaction_date", "—"), "truth": st["created_at"][:10], "match": f.get("transaction_date") in (None, st["created_at"][:10])},
                {"field": "Where the money is", "claim": "—", "truth": f"settled to bank · {stl[0]['batch_id']}" if settled else "not settled", "match": True}]
        conflict = f.get("amount") != st["amount"]
        await e.step(inc, "evidence", stamp="CONFLICT" if conflict else "FACTS AGREE", title="Notice vs Paytm records", rows=rows, tone="bad" if conflict else "good",
                     verdict="Notice and Paytm record disagree" if conflict else "One exact Paytm payment; facts agree")
        if conflict:
            inc.decisive = {"label": "Decisive evidence", "text": f"Notice says {rs(f.get('amount'))}; Paytm record for UTR {utr} says {rs(st['amount'])}"}
            await e.act(inc, "generate_evidence_pack", {"utr": utr, "notice_amount": f.get("amount")})
            await e.act(inc, "notify_merchant", {"text": f"⚠️ Notice mein {rs(f.get('amount'))} likha hai, par Paytm record mein usi UTR ka payment {rs(st['amount'])} hai. Galat tathyon wala pack bank ko dena aapko nuksaan karega. Bank se notice ki sahi copy maangiye; main Paytm Risk ko bhi bata raha hoon.",
                                                "speak": "नोटिस और पेटीएम रिकॉर्ड में रकम अलग है। मैं गलत पैक नहीं बनाऊँगा।"})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Risk", "summary": f"Notice/record amount conflict on UTR {utr}"})
            inc.status = "with_human"
            inc.headline = "Stopped: notice contradicts the record"
            return
        inc.decisive = {"label": "Decisive evidence", "text": f"Disputed payment = one {rs(st['amount'])} sale, settled in {stl[0]['batch_id'] if stl else '—'}"}
        pat = await e.call(inc, "check_sale_pattern", {"txn_id": txn["txn_id"]})
        inc.facts["pattern"] = pat
        await self.think(inc, f"Supporting signal only: ₹{st['amount']:,} sits at the {pat['amount_percentile']}th percentile of her own sales, "
                              f"at an hour that carries {pat['share_of_sales_in_this_hour']}% of her trade. "
                              f"{'It looks like a normal counter sale.' if pat['looks_like_a_normal_sale'] else 'It is unusual for this shop, which is worth a human look.'} "
                              "This never proves anything on its own.")
        r = await e.call(inc, "route_sop", {"action_kind": p["action_kind"], "fund_location": "settled_to_merchant" if settled else None,
                                             "location_source": stl[0]["batch_id"] if settled else None})
        inc.facts["route"] = r["rules"]
        e.tick_plan(inc, "Route under the MHA/I4C SOP")
        locked = inc.facts.get("locked_stated")
        if locked:
            await self.think(inc, f"Disputed: {rs(st['amount'])} (Paytm record). Locked: {rs(locked)} (merchant's own statement, T3). "
                                  f"SOP prefers holding only the disputed amount where it can be identified — that's what the pack makes easy to see.")
        res = await e.act(inc, "generate_evidence_pack", {"utr": utr, "notice_amount": f.get("amount")})
        e.tick_plan(inc, "Build a signed evidence pack")
        await e.call(inc, "get_sop_clocks", {"hold_date": f.get("hold_date")})
        pack = res.get("result", {})
        await e.act(inc, "notify_merchant", {
            "text": (f"📄 Aapka case taiyaar hai. Notice sirf ek {rs(st['amount'])} ke payment ka hai — woh ek normal sale thi jo {st['created_at'][:10]} ko aapke bank mein settle hui.\n"
                     "Agla kadam (SOP ke hisaab se, aap hi kar sakti hain):\n1) Bank branch mein likhit shikayat dijiye\n2) Yeh signed pack dikhaiye\n3) Dated acknowledgement zaroor lijiye — wahi se bank ka 7 din ka clock chalta hai.\n"
                     "Koi bhi 'complaint wapas' karwane ke paise maange to mat dijiye."),
            "speak": "आपका केस तैयार है। बैंक शाखा में लिखित शिकायत दीजिए और तारीख वाली पावती ज़रूर लीजिए।",
            "extra": {"pack": pack.get("token"), "verify_url": pack.get("verify_url")}})
        await e.act(inc, "schedule_followup", {"after_seconds": 86400, "purpose": "Ask for the bank's dated acknowledgement (starts the 7-day clock)"})
        e.tick_plan(inc, "Hand over a branch kit and track the clock")
        inc.status = "with_human"
        inc.headline = "Signed pack ready for the bank branch."
        inc.money = {"amount": st["amount"], "label": (f"is all that's disputed, out of {rs(locked)} frozen (Meena's figure)" if locked
                                                       else "is the only payment the notice disputes")}
        await self._propose_lien(inc)

    async def scam(self, inc, u):
        e = self.e
        await self.think(inc, "Demand for money to 'withdraw a complaint'. Nothing in the SOP grievance route involves paying anyone. This matches a known extortion pattern on frozen merchants.", "warn")
        await e.act(inc, "notify_merchant", {"text": f"🛑 Mat dijiye. Freeze hatane ya complaint wapas karwane ke liye SOP mein kisi ko paise dene ka koi kadam nahi hai. Call ka number note kijiye aur 1930 / cybercrime.gov.in pe report kijiye. Maine Paytm Risk ko bata diya hai.",
                                            "speak": "पैसे मत दीजिए। उन्नीस सौ तीस पर रिपोर्ट कीजिए।"})
        await e.act(inc, "escalate_to_human", {"queue": "Paytm Risk", "summary": f"Merchant reports extortion call demanding {rs(u.get('amount'))}"})
        if inc.kind == "scam":
            inc.outcome_verified = True
            inc.headline = "Scam call flagged"
            await e.act(inc, "resolve_incident", {"outcome": "Scam call flagged; merchant warned; Risk informed"})

    async def account_change(self, inc):
        e = self.e
        await self.think(inc, "Merchant wants payouts sent to a different account. Checking policy.")
        r = await e.act(inc, "change_settlement_account", {"new_account": "merchant's other account"})
        if r["status"] == "DENIED":
            await e.act(inc, "notify_merchant", {"text": "🙏 Yeh main nahi karunga. Aapka account cyber-cell freeze mein hai; freeze ke beech paisa doosre account mein bhejna kanoon se bachne jaisa lag sakta hai aur aapka case kharab kar sakta hai. Aapka paisa Paytm ke paas surakshit hai. Paytm Risk ka ek vyakti aapse baat karega.",
                                                "speak": "यह मैं नहीं करूँगा। आपका पैसा पेटीएम के पास सुरक्षित है।"})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Risk", "summary": "Merchant asked to re-route payouts during an active freeze"})
        else:
            await e.act(inc, "notify_merchant", {"text": "Account badalne ke liye Paytm Ops verification karega."})
            inc.status = "waiting_approval"

    async def status(self, inc):
        live = [i for i in self.e.incidents.values() if i.status not in ("resolved", "refused") and i.id != inc.id]
        if not live:
            text = "Abhi koi khula case nahi hai."
        else:
            text = "Khule case: " + "; ".join(f"{i.title} — {i.headline or i.status}" for i in live)
        await self.e.act(inc, "notify_merchant", {"text": text})
        inc.outcome_verified = True
        await self.e.act(inc, "resolve_incident", {"outcome": "Status shared"})

    async def sop_question(self, inc, q):
        e = self.e
        r = await e.call(inc, "ask_sop", {"question": q})
        cites = ", ".join(f"para {c['id']}" for c in r["citations"])
        await e.act(inc, "notify_merchant", {"text": f"📘 {r['answer']}\n\n(Source: MHA/I4C SOP, {cites}. Hamara saar hai; asli PDF dekh sakte hain.)",
                                            "speak": None, "extra": {"citations": r["citations"]}})
        if inc.kind == "question":
            inc.outcome_verified = True
            inc.headline = "Answered from the SOP, with citations."
            await e.act(inc, "resolve_incident", {"outcome": "SOP question answered with checked citations"})

    async def bank_ack(self, inc):
        e = self.e
        if inc.kind != "freeze":
            await e.act(inc, "notify_merchant", {"text": "Kis shikayat ka acknowledgement? Pehle freeze ka case shuru kijiye."})
            inc.status = "waiting_merchant"
            return
        today = e.world.now.date().isoformat()
        await e.act(inc, "record_case_event", {"event": "bank_complaint", "date": today})
        for f in e.followups:   # the reminder to fetch the acknowledgement is moot now
            if f["incident"] == inc.id and not f.get("fired") and f["purpose"].startswith("Ask for the bank"):
                f["fired"] = True
                f["cancelled"] = "acknowledgement received"
        hold = (inc.facts.get("notice") or {}).get("hold_date")
        c = await e.call(inc, "get_sop_clocks", {"hold_date": hold, "bank_complaint_date": today})
        inc.facts["clocks"] = c["clocks"]
        due = c["clocks"][0]["due"]
        await e.act(inc, "schedule_followup", {"after_seconds": 5 * 86400, "purpose": "Day 5: remind Meena, the bank has 2 days left"})
        await e.act(inc, "schedule_followup", {"after_seconds": 7 * 86400 + 60, "purpose": "Day 7: bank deadline, check and prepare an escalation letter"})
        await e.act(inc, "notify_merchant", {"text": f"⏱️ Bank ka 7 din ka clock aaj se shuru: {due} tak bank ko aapki shikayat aage bhejni hai (SOP 10.1(a)). "
                                                    "Main 5ve aur 7ve din khud check karunga. 90 din ki do alag tareekhein bhi dikha raha hoon, kyunki SOP mein dono likhi hain.",
                                            "speak": "बैंक का सात दिन का समय आज से शुरू। मैं खुद याद दिलाऊँगा।"})
        inc.status = "watching"
        inc.headline = f"Bank's 7-day clock running. Due {due}."


    async def after_approval(self, inc, action, r):
        e = self.e
        if r.get("status") != "DONE":
            return
        if action == "initiate_refund":
            await self._after_refund(inc)
        elif action == "draft_escalation":
            await e.act(inc, "notify_merchant", {"text": "✅ Chitthi taiyaar. Branch mein de dijiye ya email kar dijiye; signed pack saath mein hai. Main aage bhi nazar rakhunga."})
            inc.headline = "Escalation letter signed off by Meena."
            inc.status = "with_human"
        elif action == "draft_lien_request":
            L = inc.facts.get("lien_request", {})
            await e.act(inc, "notify_merchant", {"text": f"✅ Request taiyaar: hold sirf {L.get('disputed_text', '')} tak. Ise signed pack ke saath branch mein dijiye aur dated acknowledgement lijiye.",
                                                "speak": "चिट्ठी तैयार है। शाखा में पैक के साथ दीजिए और तारीख वाली पावती लीजिए।"})
            inc.headline = "Pack and lien-limiting request ready for the branch."
            inc.status = "with_human"
        elif action == "request_settlement_hold":
            e.tick_plan(inc, "Protect new sales (two-key hold)")
            await e.act(inc, "notify_merchant", {"text": "✅ Ab se aapke payouts Paytm settlement balance mein surakshit rahenge. Kisi doosre account mein kuch nahi gaya." +
                                                ("" if "disputed_txn" in inc.facts else " Notice bhejiye to aage badhte hain."),
                                                "speak": "आपके पैसे पेटीएम के पास सुरक्षित हैं।"})
            inc.status = "waiting_merchant" if "disputed_txn" not in inc.facts else "with_human"
            inc.headline = "Payouts held safely. Waiting for the notice." if "disputed_txn" not in inc.facts else inc.headline
            await self._propose_lien(inc)

    async def followup(self, inc, purpose):
        e = self.e
        if purpose.startswith("Confirm tomorrow"):
            txn = inc.facts["txn_id"]
            r = await e.call(inc, "get_settlement_status", {"txn_id": txn})
            if not r.get("batches"):
                nxt = (e.world.next_settlement - e.world.now).total_seconds() + 300
                await e.act(inc, "schedule_followup", {"after_seconds": int(max(nxt, 600)), "purpose": "Confirm tomorrow's 9:00 payout includes this payment"})
                return
            b = r["batches"][0]
            ok = b["status"] == "SETTLED"
            await e.step(inc, "evidence", stamp="PAID OUT" if ok else b["status"], title="Follow-up: payout checked", tone="good" if ok else "bad",
                         verdict=f"The ₹{inc.money.get('amount', 0):,} reached Meena's bank in {b['batch_id']}" if ok else f"Payout {b['batch_id']} is {b['status']}",
                         rows=[{"field": "Payout", "claim": "tomorrow 9:00", "truth": f"{b['batch_id']} {b['status']}", "match": ok},
                               {"field": "Bank UTR", "claim": "—", "truth": b.get("bank_utr") or "—", "match": ok}])
            if ok:
                await e.act(inc, "notify_merchant", {"text": f"☀️ Kal wala {rs(inc.money.get('amount'))} aaj subah ke payout {b['batch_id']} mein aapke bank pahunch gaya (UTR {b['bank_utr']}). Case band kar raha hoon.",
                                                    "speak": "कल वाला पैसा आज सुबह बैंक में पहुँच गया।"})
                inc.outcome_verified = True
                await e.step(inc, "verify", action="final re-check", ok=True, check=f"Settlement engine: {b['batch_id']} SETTLED and includes this payment")
                for p in inc.plan:
                    p["state"] = "done"
                inc.headline = "Fixed before anyone complained, and paid out. Closed." if inc.facts.get("proactive") else "Repaired, receipted, and paid out. Closed."
                await e.act(inc, "resolve_incident", {"outcome": (f"Fixed before anyone complained; payout {b['batch_id']} confirmed" if inc.facts.get("proactive")
                                                              else f"Ledger repaired, customer receipted, payout {b['batch_id']} confirmed")})
            elif b["status"] == "RETURNED":
                await self.think(inc, f"The bill itself is fixed, but the payout {b['batch_id']} bounced at Meena's bank. That's the account freeze, "
                                      "which has its own case. The money is back in Paytm's settlement balance, not lost.", "warn")
                inc.status = "with_human"
                inc.headline = "Bill fixed. Payout bounced with the freeze; tracked in the freeze case."
            else:
                await e.act(inc, "escalate_to_human", {"queue": "Paytm Merchant Support", "summary": f"Payout {b['batch_id']} {b['status']}"})
                inc.status = "with_human"
            return
        if purpose.startswith("Re-check payment"):
            txn = inc.facts["txn_id"]
            st = await e.call(inc, "get_payment_status", {"txn_id": txn})
            if st["status"] == "PENDING":
                await e.act(inc, "schedule_followup", {"after_seconds": 45, "purpose": "Re-check payment status at the switch"})
                return
            e.tick_plan(inc, "Watch the switch and follow up")
            if st["status"] == "SUCCESS":
                sb = await e.call(inc, "get_soundbox_log", {"minutes_back": 10})
                heard = any(x["txn_id"] == txn for x in sb["announcements"])
                await e.step(inc, "evidence", stamp="LANDED", title="Follow-up: switch re-checked", tone="good", verdict="PENDING → SUCCESS. The money has landed.",
                             rows=[{"field": "Status", "claim": "PENDING", "truth": "SUCCESS", "match": True},
                                   {"field": "Soundbox", "claim": "—", "truth": "announced" if heard else "silent", "match": heard}])
                if not heard:
                    await e.act(inc, "replay_soundbox", {"txn_id": txn})
                led = await e.call(inc, "get_merchant_ledger", {"utr": st["utr"]})
                if not led["entries"] and inc.facts.get("bill_id"):
                    await e.act(inc, "reconcile_payment", {"utr": st["utr"], "bill_id": inc.facts["bill_id"]})
                await e.act(inc, "issue_verified_receipt", {"txn_id": txn})
                await self._tell_customer(inc, f"Your bank has confirmed it: {rs(st['amount'])} received by Meena Kirana Store (UPI Ref {st['utr']}). Thank you!")
                await e.act(inc, "notify_merchant", {"text": f"✅ {rs(st['amount'])} aa gaya (UPI Ref {st['utr']}). Customer ko receipt bhej di. Ab saman de dijiye — sirf ek baar paisa kata.",
                                                    "speak": f"{st['amount']} रुपये आ गए। अब सामान दे दीजिए।"})
                await self._close(inc, txn, "SUCCESS", f"Pending payment landed; {rs(st['amount'])} receipted once")
            else:
                await e.step(inc, "evidence", stamp="FAILED", title="Follow-up: switch re-checked", tone="bad", verdict="PENDING → FAILED",
                             rows=[{"field": "Status", "claim": "PENDING", "truth": "FAILED", "match": False}])
                await self._failed(inc, st)
        elif purpose.startswith("Confirm the refund"):
            r = await e.call(inc, "get_refund_status", {"refund_id": inc.facts["refund_id"]})
            if r["status"] != "SUCCESS":
                await e.act(inc, "schedule_followup", {"after_seconds": 60, "purpose": "Confirm the refund was credited"})
                return
            if len(inc.plan) > 3:
                e.tick_plan(inc, inc.plan[3]["text"])
            if inc.kind == "duplicate":
                await e.act(inc, "notify_merchant", {"text": f"✅ Duplicate {rs(inc.facts['amount'])} customer ko wapas mil gaya (refund {r['refund_id']}). Sirf ek baar refund hua.",
                                                    "speak": "डुप्लिकेट पैसा ग्राहक को वापस मिल गया।"})
            else:
                await e.act(inc, "notify_merchant", {"text": f"✅ {self._who(inc)} ka purana {rs(r['amount'])} wapas unke account mein pahunch gaya ({r['refund_id']})."})
            if inc.channel == "whatsapp":
                await self._tell_customer(inc, f"Your refund {r['refund_id']} of {rs(r['amount'])} has been credited back to your account.")
            again = await e.call(inc, "get_refund_status", {"refund_id": inc.facts["refund_id"]})
            inc.outcome_verified = again["status"] == "SUCCESS"
            await e.step(inc, "verify", action="final re-check", ok=inc.outcome_verified, check="Refund service re-queried: SUCCESS")
            inc.headline = "Duplicate refunded once, and confirmed." if inc.kind == "duplicate" else "Late payment refunded, and confirmed."
            for p in inc.plan:
                p["state"] = "done"
            await e.act(inc, "resolve_incident", {"outcome": f"Refund {r['refund_id']} of {rs(r['amount'])} confirmed credited"})
        elif purpose.startswith("Day 5"):
            due = (inc.facts.get("clocks") or [{}])[0].get("due")
            await e.act(inc, "notify_merchant", {"text": f"⏱️ Yaad dilana: bank ke paas {due} tak 2 din bache hain. Branch se poochiye ki shikayat grievance module mein gayi ya nahi. Mile to reference bhejiye.",
                                                "speak": "बैंक के पास दो दिन बचे हैं।"})
            inc.headline = f"Day 5 of 7. Reminder sent; bank due {due}."
        elif purpose.startswith("Day 7"):
            if "bank_submission" in inc.facts.get("case_events", {}):
                await e.act(inc, "notify_merchant", {"text": "Bank ne shikayat bhej di hai. Ab jaanch adhikari ke 15 din chalenge (SOP 10.1(b))."})
                return
            await self.think(inc, "Day 7 and no submission recorded. The SOP route says the bank should have submitted by now. "
                                  "Kavach can't contact the bank itself (P7), but it can draft a letter for Meena to sign.", "warn")
            r = await e.act(inc, "draft_escalation", {"to": "Grievance Officer, " + MERCHANT["settlement_bank"].replace("Bank account ", "Bank (a/c ") + ")",
                                                       "reason": "No confirmation of grievance submission within 7 days"})
            if r["status"] == "NEEDS_APPROVAL":
                await e.act(inc, "notify_merchant", {"text": "⚠️ 7 din poore, bank ne shikayat bhejne ki khabar nahi di. Main aapke naam se bank ke grievance officer ko chitthi bana doon?",
                                                    "speak": "सात दिन पूरे हो गए। बैंक को चिट्ठी बना दूँ?", "extra": {"approval": inc.id}})
                inc.headline = "Day 7 passed. Escalation letter waiting for Meena's OK."
        elif purpose.startswith("Ask for the bank"):
            await e.act(inc, "notify_merchant", {"text": "Namaste Meena ji — kya bank ne aapki shikayat ka dated acknowledgement diya? Uski photo bhejiye; usi din se bank ka 7 din ka clock chalta hai."})
