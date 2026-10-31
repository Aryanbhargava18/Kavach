"""Deterministic playbooks (offline mode).

These are explicit rules, not an LLM, and the UI says so. They still drive the same engine:
every branch is chosen from what the tools return, every write passes policy, every action is
re-verified, and follow-ups run on the clock.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
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
        if intent == "money_question":
            return (e.open_incident("freeze") or e.open_incident("chargeback") or e.new_incident("question", "Where is my money?")), intent
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
        if intent == "money_question":
            return await self.money(inc)
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
        return await self.money(inc, unclear=True)   # never a menu: answer from what Kavach already knows, then invite the rest

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
            await e.act(inc, "notify_merchant", {"text": f"I found {len(near)} payments of {rs(claimed)}: {listing}. One may be another customer's, so I won't guess. Ask the customer for the last 4 digits of their UPI Ref and type them here.", "hi": f"{rs(claimed)} के {len(near)} भुगतान मिले: {listing}। यह किसी और ग्राहक का भी हो सकता है, इसलिए मैं अंदाज़ा नहीं लगाऊँगा। ग्राहक से UPI Ref के आख़िरी 4 अंक पूछकर यहाँ लिखिए।", "speak": "ग्राहक से यूपीआई रेफ़रेंस के आख़िरी चार अंक पूछिए।", "speak_en": "Ask the customer for the last four digits of the UPI reference."})
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
            await e.act(inc, "notify_merchant", {"text": f"{rs(st['amount'])} has arrived (UPI Ref …{st['utr'][-4:]}), but your billing app has no open bill for this amount. Which bill is it for?", "hi": f"{rs(st['amount'])} आ गए हैं (UPI Ref …{st['utr'][-4:]}), पर बिलिंग ऐप में इस रकम का कोई खुला बिल नहीं मिला। यह किस बिल का है?"})
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
            await e.act(inc, "notify_merchant", {"text": f"✅ {self._who(inc)}'s {rs(st['amount'])} arrived, but Paytm's update never reached your billing app (server error ×{len(fails) or 1}). "
                                                        f"I marked bill {bill_id} paid from the bank's record and checked it again. Nothing for you to do.",
                                                "hi": f"✅ {self._who(inc)} के {rs(st['amount'])} आ गए, पर पेटीएम का संदेश आपके बिलिंग ऐप तक नहीं पहुँचा (सर्वर एरर ×{len(fails) or 1})। मैंने बैंक के रिकॉर्ड से बिल {bill_id} पेड कर दिया और दोबारा जाँचा। आपको कुछ नहीं करना है।",
                                                "speak": f"{self._who(inc)} के {st['amount']} रुपये आ गए हैं। बिलिंग ऐप में अपडेट नहीं हुआ था, मैंने ठीक कर दिया है।",
                                                "speak_en": f"{st['amount']} rupees from {self._who(inc)} arrived. Your billing app missed it, and I've fixed it."})
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
        await e.act(inc, "notify_merchant", {"text": f"✅ {self._who(inc)}'s {rs(st['amount'])} arrived at {hm(st.get('created_at'))}, but Paytm's update never reached your billing app (server error ×{len(fails) or 1}). "
                                                    f"I marked bill {bill_id} paid from the bank's record and checked both again; they match. You can hand over the goods.",
                                            "hi": f"✅ {self._who(inc)} के {rs(st['amount'])} {hm(st.get('created_at'))} पर ही आ गए थे, पर पेटीएम का संदेश आपके बिलिंग ऐप तक नहीं पहुँचा। मैंने बैंक के रिकॉर्ड से बिल {bill_id} पेड कर दिया और दोबारा जाँचा — दोनों मेल खाते हैं। सामान दे दीजिए।",
                                            "speak": f"{st['amount']} रुपये आ गए थे। बिल ठीक कर दिया है। सामान दे दीजिए।", "speak_en": f"{st['amount']} rupees had arrived. The bill is fixed. You can hand over the goods."})
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
        await e.act(inc, "notify_merchant", {"text": f"⚠️ Wait. This screenshot is of an earlier payment already used for bill {entry['bill_id']} at {hm(entry['at'])}. " f"No money has come in for bill {bill_id}. Don't hand over the goods yet; I've sent the customer a fresh QR.", "hi": f"⚠️ रुकिए। यह स्क्रीनशॉट पुराने भुगतान का है जो {hm(entry['at'])} बजे बिल {entry['bill_id']} में लग चुका है। बिल {bill_id} के लिए कोई पैसा नहीं आया। अभी सामान मत दीजिए; मैंने ग्राहक को नया QR भेज दिया है।", "speak": "रुकिए। यह पुराने पेमेंट का स्क्रीनशॉट है। इस बिल का पैसा नहीं आया।", "speak_en": "Wait. This screenshot is of an old payment. Nothing has come in for this bill."})
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
        await e.act(inc, "notify_merchant", {"text": f"{self._who(inc)}'s {rs(st['amount'])} arrived after the order expired, so it's being refunded automatically ({r['refund_id']}). "
                                                    f"Bill {bill_id} is still unpaid. I've given the customer a fresh QR; hand over the goods once the new payment lands.",
                                            "hi": f"{self._who(inc)} के {rs(st['amount'])} ऑर्डर की समय-सीमा के बाद आए, इसलिए अपने-आप रिफंड हो रहे हैं ({r['refund_id']})। बिल {bill_id} अभी अनपेड है। ग्राहक को नया QR दिया है; नया भुगतान आते ही सामान दीजिए।",
                                            "speak": "पहला पेमेंट रिफंड हो रहा है। नया पेमेंट आते ही सामान दीजिए।", "speak_en": "The first payment is being refunded. Hand over the goods once the new payment arrives."})
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
        await e.act(inc, "notify_merchant", {"text": f"✅ {rs(st['amount'])} is in your account (UPI Ref {st['utr']}). I've sent the customer a verified receipt. You can hand over the goods.",
                                            "hi": f"✅ {rs(st['amount'])} आपके खाते में आ गए हैं (UPI Ref {st['utr']})। ग्राहक को सत्यापित रसीद भेज दी। सामान दे दीजिए।",
                                            "speak": f"{st['amount']} रुपये आ गए हैं। सामान दे दीजिए।", "speak_en": f"{st['amount']} rupees received. You can hand over the goods."})
        await self._close(inc, st["txn_id"], "SUCCESS", f"Payment of {rs(st['amount'])} confirmed and receipted")
        inc.money = {"amount": st["amount"], "label": "confirmed with the bank, not the screenshot"}

    async def _short_paid(self, inc, st, claimed):
        e = self.e
        due = claimed - st["amount"]
        e.tick_plan(inc, inc.plan[5]["text"])
        await self.think(inc, f"Only {rs(st['amount'])} reached the switch. Handing over {rs(claimed)} of goods on this screenshot would lose {rs(due)}.", "warn")
        await e.act(inc, "notify_merchant", {"text": f"⚠️ Wait. Only {rs(st['amount'])} has arrived. The screenshot shows {rs(claimed)}, but the bank record (UPI Ref {st['utr']}) says {rs(st['amount'])}. Hold the goods until the remaining {rs(due)} arrives. I've sent the customer a QR for it.",
                                            "hi": f"⚠️ रुकिए। सिर्फ़ {rs(st['amount'])} आए हैं। स्क्रीनशॉट पर {rs(claimed)} दिख रहा है, पर बैंक रिकॉर्ड (UPI Ref {st['utr']}) में {rs(st['amount'])} है। बाकी {rs(due)} मिलने तक सामान मत दीजिए। मैंने ग्राहक को बाकी रकम का QR भेज दिया है।",
                                            "speak": f"रुकिए। सिर्फ {st['amount']} रुपये आए हैं। बाकी {due} रुपये मिलने तक सामान मत दीजिए।", "speak_en": f"Wait. Only {st['amount']} rupees arrived. Hold the goods until the remaining {due} rupees come in."})
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
        await e.act(inc, "notify_merchant", {"text": f"⏳ {rs(st['amount'])} is stuck at the customer's bank (PENDING). Don't take the payment again, or the customer will be charged twice. I'm watching it and will tell you the moment it confirms.", "hi": f"⏳ {rs(st['amount'])} ग्राहक के बैंक में अटके हैं (PENDING)। दोबारा भुगतान मत लीजिए, वरना ग्राहक का पैसा दो बार कटेगा। मैं नज़र रख रहा हूँ, पुष्टि होते ही बताऊँगा।", "speak": "पैसा बैंक में अटका है। दोबारा पेमेंट मत लीजिए। मैं नज़र रख रहा हूँ।", "speak_en": "The money is stuck at the bank. Don't take the payment again. I'm watching it."})
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
        msg = (f"❌ This payment FAILED. Any money taken from the customer goes back to them automatically (T+1). "
               if debited else "❌ The bank declined this payment; no money was taken. ")
        msg += "It's safe to take a new payment; I've sent the customer a QR." if r["status"] == "DONE" else ""
        msg_hi = ("❌ यह भुगतान फ़ेल हो गया। ग्राहक का कटा हुआ पैसा उनके बैंक से अपने-आप वापस आएगा (T+1)। " if debited else "❌ बैंक ने यह भुगतान अस्वीकार कर दिया; पैसा कटा ही नहीं। ")
        msg_hi += "अब नया भुगतान लेना सुरक्षित है; मैंने ग्राहक को QR भेज दिया है।" if r["status"] == "DONE" else ""
        await e.act(inc, "notify_merchant", {"text": msg, "hi": msg_hi, "speak": "पेमेंट फेल हो गया। अब नया पेमेंट लेना सुरक्षित है।", "speak_en": "The payment failed. It's safe to take a new one."})
        await self._tell_customer(inc, f"Your payment of {rs(st['amount'])} to Meena Kirana Store did not go through." +
                                  (" Any amount debited will be reversed by your bank automatically (T+1)." if debited else "") +
                                  " You can pay again safely with the QR.")
        await self._close(inc, st["txn_id"], "FAILED", "First payment failed; fresh payment requested" + ("; reversal due T+1" if debited else ""))
        inc.money = {"amount": st["amount"], "label": "customer not charged twice"}

    async def _not_received(self, inc, claimed, utr):
        e = self.e
        e.tick_plan(inc, inc.plan[5]["text"])
        await e.act(inc, "notify_merchant", {"text": f"❌ No payment with UPI Ref {utr or '(not given)'} reached your account. Don't hand over the goods yet. Ask the customer to check their app history; if money left their account, they should contact their bank.",
                                            "hi": f"❌ इस UPI Ref ({utr or 'नहीं दिया'}) का कोई भुगतान आपके खाते में नहीं आया। अभी सामान मत दीजिए। ग्राहक से कहिए अपने ऐप की हिस्ट्री देखें; अगर पैसा कटा है तो अपने बैंक से बात करें।",
                                            "speak": "यह पेमेंट आपके खाते में नहीं आया। सामान अभी मत दीजिए।", "speak_en": "This payment did not reach your account. Don't hand over the goods yet."})
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
        await e.act(inc, "notify_merchant", {"text": f"❌ The customer paid a different QR/UPI ID: the screenshot shows '{claim.get('payee_name')}', not you. Nothing reached your account. Don't hand over the goods yet.", "hi": f"❌ ग्राहक ने गलत QR/UPI ID पर भुगतान किया है — स्क्रीनशॉट में '{claim.get('payee_name')}' है, आप नहीं। आपके खाते में कुछ नहीं आया। अभी सामान मत दीजिए।", "speak": "ग्राहक ने गलत खाते में पैसे भेजे हैं। आपके खाते में कुछ नहीं आया।", "speak_en": "The customer paid someone else. Nothing reached your account."})
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
            await e.act(inc, "notify_merchant", {"text": "🙏 I can't ask for the payment again right now: " + r["decision"]["reason"] + " I'm checking.", "hi": "🙏 अभी दोबारा भुगतान नहीं माँग सकता: ग्राहक का पैसा दो बार कट सकता है। मैं जाँच कर रहा हूँ।", "speak": "अभी दोबारा पेमेंट नहीं ले सकते। मैं जाँच कर रहा हूँ।", "speak_en": "We can't take the payment again right now. I'm checking."})

    # -------------------------------------------------------- duplicate
    async def duplicate(self, inc, u):
        e = self.e
        amt = u.get("amount")
        plan = [f"Find every {rs(amt)} payment in the last 30 min", "Check whether the same payer paid twice", "Refund only the duplicate, once", "Confirm the refund actually landed"]
        e.set_plan(inc, plan)
        if not amt:
            await e.act(inc, "notify_merchant", {"text": "How much was charged twice? Tell me the amount.", "hi": "कितने रुपये दो बार कटे? रकम बताइए।"})
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
            await e.act(inc, "notify_merchant", {"text": f"This isn't a duplicate: two different people each paid {rs(amt)}. I won't refund it.", "hi": f"यह डुप्लिकेट नहीं है: {rs(amt)} दो अलग लोगों ने दिए। मैं रिफंड नहीं करूँगा।", "speak": "यह डुप्लिकेट नहीं है।", "speak_en": "This is not a duplicate."})
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
            await e.act(inc, "notify_merchant", {"text": f"The customer ({g['payer']}) paid {rs(amt)} twice, {g['gap_seconds']} seconds apart. Shall I refund the second payment?",
                                                "hi": f"ग्राहक ({g['payer']}) ने {rs(amt)} दो बार दिए, {g['gap_seconds']} सेकंड के अंदर। दूसरा भुगतान वापस कर दूँ?",
                                                "speak": f"ग्राहक ने {amt} रुपये दो बार दिए। दूसरा पेमेंट वापस कर दूँ?", "speak_en": f"The customer paid {amt} rupees twice. Shall I refund the second payment?", "extra": {"approval": inc.id}})
            if inc.channel == "whatsapp":
                await self._tell_customer(inc, f"Thanks — we can see two payments of {rs(amt)} from you, {g['gap_seconds']} seconds apart. The shop is approving a refund of the second one now.")
            inc.headline = "Waiting for your OK to refund"
            return
        if res["status"] == "DENIED":
            await e.act(inc, "notify_merchant", {"text": "Refund not made: " + res["decision"]["reason"], "hi": "रिफंड नहीं किया: यह साबित डुप्लिकेट नहीं है।"})
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
            await e.act(inc, "notify_merchant", {"text": "I couldn't find yesterday's payout batch. I'm handing this to Paytm Support.", "hi": "कल का कोई पेआउट बैच नहीं मिला। मैं इसे पेटीएम सपोर्ट को दे रहा हूँ।"})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Support", "summary": "No settlement batch for yesterday"})
            inc.status = "with_human"
            return
        if b["status"] == "SETTLED":
            await e.step(inc, "evidence", stamp="PAID OUT", title="Payout trail", tone="good", verdict="Payout reached the bank",
                         rows=[{"field": "Batch", "claim": "missing", "truth": f"{b['batch_id']} {rs(b['amount'])}", "match": False},
                               {"field": "Bank UTR", "claim": "—", "truth": b["bank_utr"], "match": True}])
            await e.act(inc, "notify_merchant", {"text": f"Yesterday's {rs(b['amount'])} reached your bank at {str(b['credited_at'])[11:16]}. Look for UTR {b['bank_utr']} in your passbook.", "hi": f"कल के {rs(b['amount'])} आपके बैंक में {str(b['credited_at'])[11:16]} बजे आ चुके हैं। पासबुक में UTR {b['bank_utr']} देखिए।", "speak": "कल का पैसा आपके बैंक में आ चुका है।", "speak_en": "Yesterday's money has reached your bank."})
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
                "text": (f"⚠️ Meena ji, your bank sent back this morning's {rs(b['amount'])} payout. It says your account is FROZEN. "
                         "You may not know yet. Talk to your bank before you pay any supplier.\n"
                         "I can't lift a freeze, but I can build your case. Ask your branch for three things:\n"
                         "1) The NCRP acknowledgement number\n2) The police notice or requisition\n3) How much is disputed\n"
                         "Send me the bank's SMS or notice when you get it."),
                "hi": (f"⚠️ मीना जी, आपके बैंक ने आज सुबह का {rs(b['amount'])} का पेआउट वापस भेज दिया। बैंक के अनुसार आपका खाता फ्रीज़ है। "
                       "शायद आपको अभी पता नहीं चला। सप्लायर को भुगतान करने से पहले बैंक से बात कर लीजिए।\n"
                       "मैं फ्रीज़ हटा नहीं सकता, पर आपका केस तैयार कर सकता हूँ। शाखा से ये तीन चीज़ें माँगिए:\n"
                       "1) NCRP पावती नंबर\n2) पुलिस का नोटिस या अनुरोध-पत्र\n3) कितनी रकम विवादित है\n"
                       "बैंक का SMS या नोटिस आए तो यहाँ भेजिए।"),
                "speak": "मीना जी, आपके बैंक ने आज का पेआउट वापस भेज दिया। खाता फ्रीज़ है। सप्लायर को पेमेंट करने से पहले बैंक से बात कीजिए।",
                "speak_en": "Meena ji, your bank returned today's payout. Your account is frozen. Talk to your bank before paying any supplier."})
        else:
            await e.act(inc, "notify_merchant", {"text": f"⚠️ Your bank sent back yesterday's {rs(b['amount'])}: it says your account is FROZEN. I can't lift a freeze, but I can build your case. Send me the bank's SMS or the police notice.",
                                                "hi": f"⚠️ कल के {rs(b['amount'])} आपके बैंक ने वापस भेज दिए — बैंक के अनुसार आपका खाता फ्रीज़ है। मैं फ्रीज़ हटा नहीं सकता, पर आपका केस तैयार कर सकता हूँ। बैंक का SMS या पुलिस नोटिस यहाँ भेजिए।",
                                                "speak": "आपका बैंक खाता फ्रीज़ है। बैंक का SMS या पुलिस नोटिस भेजिए।", "speak_en": "Your bank account is frozen. Send me the bank's SMS or the police notice."})
        inc.money = {"amount": b["amount"], "label": "payout bounced, safe with Paytm"}
        await self._propose_hold(inc)

    # ------------------------------------------------------- live Paytm check
    async def live_check(self, inc, order_id):
        """The read path on Paytm's real API: ask, re-ask before acting, sign only what Paytm said."""
        e = self.e
        plan = ["Ask Paytm's Transaction Status API", "Re-check before acting", "Sign only what Paytm returned", "Tell Meena"]
        e.set_plan(inc, plan)
        await e.step(inc, "intake", text=f"Order {order_id}: checking with Paytm's real Transaction Status API", intent="live_check",
                     amount=None, utrs=[], language="system", engine="paytm-live", sender="monitor")
        r = await e.call(inc, "paytm_order_status", {"order_id": order_id})
        if not r.get("configured"):
            await self.think(inc, "No Paytm keys on this machine (PAYTM_MID, PAYTM_MERCHANT_KEY). I won't fake a live answer.", "warn")
            inc.status, inc.headline = "with_human", "Paytm keys not set. Nothing faked."
            return
        if r.get("error"):
            await self.think(inc, f"Paytm's API didn't answer ({r['error']}). I won't guess the status.", "warn")
            inc.status, inc.headline = "with_human", "Paytm API unreachable. Nothing guessed."
            return
        e.tick_plan(inc, plan[0])
        if r["status"] != "SUCCESS":
            await e.step(inc, "evidence", stamp=r["status"], title="Paytm, live", tone="bad" if r["status"] == "FAILED" else "warn",
                         verdict=f"Paytm says {r['status']}: {r.get('result_msg') or ''}", rows=[{"field": "Status", "claim": "—", "truth": r["status"], "match": False}])
            await e.act(inc, "notify_merchant", {"text": f"Paytm's record for order {order_id}: {r['status']} ({r.get('result_msg') or ''}). Hold the goods for now.", "hi": f"पेटीएम के रिकॉर्ड में ऑर्डर {order_id}: {r['status']}। सामान देने से पहले रुकिए।"})
            inc.status, inc.headline = "with_human", f"Paytm says {r['status']}. Nothing receipted."
            return
        again = await e.call(inc, "paytm_order_status", {"order_id": order_id})
        e.tick_plan(inc, plan[1])
        same = again.get("status") == "SUCCESS" and again.get("txn_id") == r.get("txn_id") and again.get("amount") == r.get("amount")
        await e.step(inc, "evidence", stamp="PAYTM CONFIRMS" if same else "CHANGED", title="Paytm, live (asked twice)", tone="good" if same else "bad",
                     verdict=f"Paytm's own API: SUCCESS ₹{r['amount_text']}, asked twice" if same else "Paytm's answer changed between calls",
                     rows=[{"field": "Status", "claim": "—", "truth": f"{r['status']} → {again.get('status')}", "match": same},
                           {"field": "Amount", "claim": "—", "truth": f"₹{r['amount_text']}", "match": same},
                           {"field": "Paytm txnId", "claim": "—", "truth": str(r.get("txn_id")), "match": same},
                           {"field": "Bank txn ID", "claim": "—", "truth": str(r.get("bank_txn_id")), "match": True}])
        if not same:
            inc.status, inc.headline = "with_human", "Paytm's answer changed. Not signing."
            return
        inc.decisive = {"label": "Decisive evidence", "text": f"Paytm Transaction Status API (live): SUCCESS ₹{r['amount_text']} · txnId {r.get('txn_id')}"}
        res = await e.act(inc, "issue_live_pack", {"order_id": order_id})
        e.tick_plan(inc, plan[2])
        pack = (res.get("result") or {})
        await e.act(inc, "notify_merchant", {"text": f"✅ Paytm itself confirmed it: order {order_id}, ₹{r['amount_text']} SUCCESS (bank ref {r.get('bank_txn_id') or '—'}). Your signed pack is ready.",
                                            "hi": f"✅ पेटीएम ने ख़ुद पुष्टि की: ऑर्डर {order_id}, ₹{r['amount_text']} सफल (बैंक रेफ़ {r.get('bank_txn_id') or '—'})। हस्ताक्षरित पैक तैयार है।",
                                            "speak": "पेटीएम ने पुष्टि की, भुगतान सफल है।", "speak_en": "Paytm confirmed it. The payment was successful.", "extra": {"pack": pack.get("token"), "verify_url": pack.get("verify_url")}})
        e.tick_plan(inc, plan[3])
        inc.outcome_verified = True
        inc.money = {"amount": r.get("amount"), "label": "confirmed by Paytm's live API"}
        inc.headline = "Confirmed live by Paytm's own API, asked twice, and signed."
        await e.act(inc, "resolve_incident", {"outcome": f"Order {order_id} confirmed SUCCESS by Paytm's Transaction Status API; signed pack {pack.get('token')}"})

    # ------------------------------------------------------- chargeback clock
    async def proactive_dispute(self, inc, d):
        """A chargeback landed. If nobody replies by the deadline, it is deemed valid and netted from her payout."""
        e = self.e
        due = due_en = hm(d["respond_by"])
        if datetime.fromisoformat(d["respond_by"]).date() != e.world.now.date():
            due, due_en = "कल " + due, "tomorrow " + due_en
        plan = ["Notice the chargeback", "Gather what Paytm's records prove", "Say what they don't prove", "Ask Meena one question", "Reply before the deadline", "Watch the outcome"]
        e.set_plan(inc, plan)
        await e.step(inc, "intake", text=f"Dispute desk: chargeback {d['dispute_id']} on {rs(d['amount'])} · \"{d['reason']}\" · reply by {due_en} or it is deemed valid",
                     intent="chargeback", amount=d["amount"], utrs=[d["utr"]], language="system", engine="dispute-monitor", sender="monitor")
        await self.think(inc, f"Nobody has told Meena. If nobody replies by {due_en}, the chargeback is deemed valid and {rs(d['amount'])} comes out of her next payout. "
                              "She doesn't watch the dispute desk. I do.", "warn")
        e.tick_plan(inc, plan[0])
        await e.act(inc, "create_support_case", {"summary": f"Chargeback {d['dispute_id']} {rs(d['amount'])} ({d['reason']}); found by Kavach's dispute monitor", "channel": "monitor"})
        await e.call(inc, "get_disputes", {})
        st = await e.call(inc, "get_payment_status", {"txn_id": d["txn_id"]})
        led = await e.call(inc, "get_merchant_ledger", {"utr": d["utr"]})
        sb = await e.call(inc, "get_soundbox_log", {"minutes_back": 600})
        entry = (led.get("entries") or [None])[0]
        bill = next((b for b in led.get("bills", []) if entry and b["bill_id"] == entry["bill_id"]), None)
        heard = any(x["txn_id"] == d["txn_id"] for x in sb.get("announcements", []))
        if bill:
            inc.facts["bill_id"] = bill["bill_id"]
        ev = [{"kind": "switch", "label": f"UPI switch: SUCCESS {rs(st['amount'])} to {MERCHANT['vpa']} at {hm(st['created_at'])}", "tier": "T1"}]
        if entry:
            ev.append({"kind": "ledger", "label": f"Shop's bill {entry['bill_id']} marked paid by this UTR" + (f" ({', '.join(bill['items'])})" if bill else ""), "tier": "T1"})
        if heard:
            ev.append({"kind": "soundbox", "label": "Soundbox announced the payment at the counter", "claim": "payment notification played", "tier": "T2"})
        inc.facts["dispute_evidence"] = ev
        e.tick_plan(inc, plan[1])
        await e.step(inc, "evidence", stamp="PAYMENT PROVEN", title="What Paytm's records prove", tone="good",
                     verdict="The payment and the bill are proven. Handing over the goods is not.",
                     rows=[{"field": "Payment", "claim": d["reason"], "truth": f"SUCCESS {rs(st['amount'])}", "match": True},
                           {"field": "Bill", "claim": "—", "truth": f"{entry['bill_id']} paid" if entry else "no bill", "match": bool(entry)},
                           {"field": "Soundbox", "claim": "—", "truth": "announced" if heard else "silent", "match": heard},
                           {"field": "Goods handed over", "claim": "not received", "truth": "no record can show this", "match": False}])
        await self.think(inc, "The Soundbox proves the notification played, not that the goods changed hands, and no Paytm record can prove a handover. "
                              "I won't invent delivery proof. Only Meena can say it, and her answer goes in labelled as hers.", "warn")
        e.tick_plan(inc, plan[2])
        inc.decisive = {"label": "Decisive evidence", "text": f"Payment and bill proven; handover only Meena can state"}
        inc.money = {"amount": d["amount"], "label": f"at stake · reply by {due_en}"}
        res = await e.act(inc, "submit_dispute_response", {"dispute_id": d["dispute_id"], "evidence": ev, "merchant_attests_handover": True})
        if res["status"] == "NEEDS_APPROVAL":
            await e.act(inc, "notify_merchant", {
                "text": (f"⏱️ A {rs(d['amount'])} chargeback has come in: the customer's bank says \"{d['reason']}\" (bill {inc.facts.get('bill_id', '')}). "
                         f"If nobody replies by {due_en}, it comes out of your next payout.\n"
                         "I have proof of the payment and the bill. Only you can answer one thing: did you hand over the goods?"),
                "hi": (f"⏱️ {rs(d['amount'])} का चार्जबैक आया है: ग्राहक के बैंक का कहना है \"सामान नहीं मिला\" (बिल {inc.facts.get('bill_id', '')})। "
                       f"{due} तक जवाब नहीं दिया तो यह पैसा आपके अगले पेआउट से कट जाएगा।\n"
                       "भुगतान और बिल का सबूत मेरे पास है। सिर्फ़ एक बात आप बता सकती हैं: क्या आपने सामान दिया था?"),
                "speak": f"{d['amount']} रुपये का चार्जबैक आया है। क्या आपने सामान दिया था?", "speak_en": f"A {d['amount']} rupee chargeback has come in. Did you hand over the goods?", "extra": {"approval": inc.id}})
            e.tick_plan(inc, plan[3])
            await e.act(inc, "schedule_followup", {"after_seconds": max(600, int((datetime.fromisoformat(d["respond_by"]) - e.world.now).total_seconds()) - 6 * 3600),
                                                  "purpose": "Remind Meena: chargeback reply due in 6 hours"})
            inc.status = "waiting_approval"
            inc.headline = f"Chargeback {rs(d['amount'])}: waiting for Meena's one answer before {due_en}."

    async def after_decline(self, inc, action) -> bool:
        """Meena said no. For a chargeback that means the goods were not handed over: accept it, don't fight it."""
        e = self.e
        if action == "request_settlement_hold":   # her money, her call: say so, keep helping
            await self.think(inc, "Meena said not now. Nothing is held; her payouts keep going to her bank. Respect it and keep building the case.")
            await e.act(inc, "notify_merchant", {"text": "Okay, nothing is held. Your payouts keep going to your bank; if it sends them back, they return safely to Paytm. You can change your mind any time. Next: send me the bank's SMS or notice.",
                                                 "hi": "ठीक है, कुछ नहीं रोका। आपके पेआउट बैंक जाते रहेंगे; बैंक लौटाएगा तो पैसा सुरक्षित पेटीएम के पास लौट आएगा। आप कभी भी मन बदल सकते हैं। अगला कदम: बैंक का SMS या नोटिस भेजिए।",
                                                 "speak": "ठीक है, कुछ नहीं रोका।", "speak_en": "Okay, nothing is held."})
            inc.status = "waiting_merchant"
            inc.headline = "Meena chose not to hold payouts. Waiting for the bank's notice."
            return True
        if action == "draft_lien_request":
            await e.act(inc, "notify_merchant", {"text": "Okay, I won't send the request. Your signed case is ready whenever you want it.", "hi": "ठीक है, अनुरोध नहीं भेजूँगा। आपका केस जब चाहें तैयार है।"})
            inc.status = "waiting_merchant"
            return True
        if action != "submit_dispute_response":
            return False
        await self.think(inc, "Meena says she didn't hand over the goods. Fighting it would mean a false reply in her name. Accepting is the honest outcome.")
        inc.approvals.setdefault("accept_chargeback", set()).add("merchant")
        d = inc.facts["dispute_id"]
        await e.act(inc, "accept_chargeback", {"dispute_id": d})
        await e.act(inc, "notify_merchant", {"text": "Okay. I've accepted the chargeback; the customer gets the money back. A false reply would have hurt you more.", "hi": "ठीक है। चार्जबैक मान लिया, ग्राहक को पैसा वापस जाएगा। गलत जवाब देना आपके लिए और नुकसानदेह होता।", "speak": "ठीक है, चार्जबैक मान लिया।", "speak_en": "Okay. I've accepted the chargeback."})
        inc.outcome_verified = True
        inc.headline = "Chargeback accepted honestly on Meena's word."
        await e.act(inc, "resolve_incident", {"outcome": f"{d} accepted: merchant says goods were not handed over"})
        return True

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
        await e.act(inc, "notify_merchant", {"text": "Namaste Meena ji, there's a delay with your payout. The Paytm team will contact you soon. Until then your money is safe with Paytm.", "hi": "नमस्ते मीना जी, आपके पेआउट में थोड़ी देरी है। पेटीएम की टीम जल्द आपसे बात करेगी। तब तक आपका पैसा पेटीएम के पास सुरक्षित है।", "template": "legal_neutral"})
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
            "text": (f"⚠️ Meena ji, your bank stopped your {rs(p['amount'])} payment to {p['payee']} (code {p['code']}): money can't leave your account. That's a DEBIT FREEZE. "
                     "Paytm's payouts are still landing in that account, where you can't use them.\n"
                     "Ask your branch for three things:\n1) The NCRP acknowledgement number\n2) The police notice or requisition\n3) How much is disputed\n"
                     "Send me the bank's SMS or notice when you get it."),
            "hi": (f"⚠️ मीना जी, {p['payee']} को आपका {rs(p['amount'])} का भुगतान आपके बैंक ने रोक दिया (कोड {p['code']}): खाते से पैसा निकालना बंद है, यानी डेबिट फ्रीज़। "
                   "पेटीएम के पेआउट अभी भी उसी खाते में जा रहे हैं, जहाँ से आप निकाल नहीं सकतीं।\n"
                   "शाखा से ये तीन चीज़ें माँगिए:\n1) NCRP पावती नंबर\n2) पुलिस का नोटिस या अनुरोध-पत्र\n3) कितनी रकम विवादित है\n"
                   "बैंक का SMS या नोटिस आए तो यहाँ भेजिए।"),
            "speak_en": "Meena ji, your bank stopped your payment. Money can't leave your account. Ask your branch for the notice and the disputed amount.",
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
            await e.act(inc, "notify_merchant", {"text": f"One more step: shall I write to your bank, in your name, asking them to hold only {amt} (the disputed amount) and free the rest of your account? You'll read it before it goes.", "hi": f"एक और कदम: बैंक को आपके नाम से लिखित अनुरोध बना दूँ कि रोक सिर्फ़ {amt} (विवादित रकम) तक रहे, और बाकी खाता चालू हो? आप पढ़कर ही भेजेंगी।", "speak": "बैंक को चिट्ठी बना दूँ कि रोक सिर्फ विवादित रकम तक रहे?", "speak_en": "Shall I write to your bank asking them to hold only the disputed amount?", "extra": {"approval": inc.id}})
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
            why_en = "otherwise it lands in an account you can't withdraw from" if debit else "your bank is sending it back"
            why_hi = "वरना वह उस खाते में जाएगा जहाँ से आप निकाल नहीं सकतीं" if debit else "बैंक उसे वापस भेज रहा है"
            await e.act(inc, "notify_merchant", {"text": f"Until the freeze is sorted, shall I keep today's sales safe with Paytm? ({why_en}.) Nothing goes to any other account. Paytm Risk approves too.",
                                                "hi": f"जब तक फ्रीज़ का हल नहीं होता, आज की बिक्री का पैसा पेटीएम के पास सुरक्षित रखूँ? ({why_hi}।) किसी दूसरे खाते में नहीं जाएगा। पेटीएम रिस्क भी मंज़ूरी देगा।",
                                                "speak": "आज की बिक्री का पैसा पेटीएम के पास सुरक्षित रखूँ?", "speak_en": "Shall I keep today's sales safe with Paytm?", "extra": {"approval": inc.id}})
        inc.headline = "Waiting for approvals to hold payouts"

    async def freeze_report(self, inc, u):
        e = self.e
        if u.get("amount") and u["amount"] >= 10000:
            inc.facts["locked_stated"] = u["amount"]
        if inc.plan and inc.plan[0]["text"] == "Confirm why payouts bounce":
            await e.act(inc, "notify_merchant", {"text": "Understood. Send me the bank's SMS or the police notice and I'll take it from there.", "hi": "समझ गया। बैंक का SMS या पुलिस नोटिस भेजिए, मैं आगे बढ़ता हूँ।"})
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
        await e.act(inc, "notify_merchant", {"text": "Understood. I can't lift a freeze (that's for the bank and the police to decide), but I can build a solid case. Send me the bank's SMS or the police notice.",
                                            "hi": "समझ गया। मैं फ्रीज़ हटा नहीं सकता — वह बैंक और पुलिस का फ़ैसला है — पर आपका केस पक्का बना सकता हूँ। बैंक का SMS या पुलिस नोटिस यहाँ भेजिए।",
                                            "speak": "बैंक का SMS या पुलिस नोटिस भेजिए।", "speak_en": "Send me the bank's SMS or the police notice."})
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
            await e.act(inc, "notify_merchant", {"text": "This notice doesn't mention a hold, freeze or seizure. I won't send it down the wrong SOP route; Paytm Support will look at it.", "hi": "इस नोटिस में रोक, फ्रीज़ या ज़ब्ती का ज़िक्र नहीं है। मैं इसे गलत SOP रास्ते से नहीं भेजूँगा — पेटीएम सपोर्ट देखेगा।"})
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
            await e.act(inc, "notify_merchant", {"text": "The payment in the notice didn't come through Paytm, so I won't build a pack in Paytm's name. File a written complaint at your branch and get a dated acknowledgement; I'm sending you a checklist.", "hi": "नोटिस वाला भुगतान पेटीएम से नहीं आया था, इसलिए मैं पेटीएम रिकॉर्ड के नाम पर कोई पैक नहीं बनाऊँगा। बैंक शाखा में लिखित शिकायत दीजिए और तारीख़ वाली पावती लीजिए — मैं चेकलिस्ट भेज रहा हूँ।"})
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
            await e.act(inc, "notify_merchant", {"text": f"⚠️ The notice says {rs(f.get('amount'))}, but Paytm's record for that UTR says {rs(st['amount'])}. A pack with wrong facts would hurt you at the bank. Ask the bank for a correct copy of the notice; I'm telling Paytm Risk too.",
                                                "hi": f"⚠️ नोटिस में {rs(f.get('amount'))} लिखा है, पर पेटीएम रिकॉर्ड में उसी UTR का भुगतान {rs(st['amount'])} है। गलत तथ्यों वाला पैक बैंक को देना आपको नुकसान करेगा। बैंक से नोटिस की सही कॉपी माँगिए; मैं पेटीएम रिस्क को भी बता रहा हूँ।",
                                                "speak": "नोटिस और पेटीएम रिकॉर्ड में रकम अलग है। मैं गलत पैक नहीं बनाऊँगा।", "speak_en": "The notice and Paytm's record show different amounts. I won't build a wrong pack."})
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
        if any(x["id"] == "PA-SETTLED-9.5.ii" for x in r["rules"]):
            # Paytm's own SOP duty as the payment aggregator: upload the settlement trail for the reported payment.
            await e.act(inc, "prepare_pa_upload", {"txn_id": txn["txn_id"]})
        locked = inc.facts.get("locked_stated")
        if locked:
            await self.think(inc, f"Disputed: {rs(st['amount'])} (Paytm record). Locked: {rs(locked)} (merchant's own statement, T3). "
                                  f"SOP prefers holding only the disputed amount where it can be identified — that's what the pack makes easy to see.")
        res = await e.act(inc, "generate_evidence_pack", {"utr": utr, "notice_amount": f.get("amount")})
        e.tick_plan(inc, "Build a signed evidence pack")
        await e.call(inc, "get_sop_clocks", {"hold_date": f.get("hold_date")})
        pack = res.get("result", {})
        await e.act(inc, "notify_merchant", {
            "text": (f"📄 Your case is ready. The notice is about one {rs(st['amount'])} payment, a normal sale that settled to your bank on {st['created_at'][:10]}.\n"
                     "Next (under the SOP, only you can do this):\n1) File a written complaint at your branch\n2) Show them this signed pack\n3) Get a dated acknowledgement; the bank's 7-day clock starts from it.\n"
                     "If anyone asks for money to 'withdraw the complaint', don't pay."),
            "hi": (f"📄 आपका केस तैयार है। नोटिस सिर्फ़ एक {rs(st['amount'])} के भुगतान का है — वह एक सामान्य बिक्री थी जो {st['created_at'][:10]} को आपके बैंक में सेटल हुई।\n"
                   "अगला कदम (SOP के अनुसार, सिर्फ़ आप कर सकती हैं):\n1) बैंक शाखा में लिखित शिकायत दीजिए\n2) यह हस्ताक्षरित पैक दिखाइए\n3) तारीख़ वाली पावती ज़रूर लीजिए — वहीं से बैंक के 7 दिन गिने जाते हैं।\n"
                   "कोई 'शिकायत वापस' करवाने के पैसे माँगे तो मत दीजिए।"),
            "speak": "आपका केस तैयार है। बैंक शाखा में लिखित शिकायत दीजिए और तारीख वाली पावती ज़रूर लीजिए।", "speak_en": "Your case is ready. File a written complaint at your branch and get a dated acknowledgement.",
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
        await e.act(inc, "notify_merchant", {"text": f"🛑 Don't pay. Nothing in the SOP involves paying anyone to lift a freeze or withdraw a complaint. Note the caller's number and report it on 1930 or cybercrime.gov.in. I've told Paytm Risk.", "hi": "🛑 पैसे मत दीजिए। फ्रीज़ हटाने या शिकायत वापस करवाने के लिए SOP में किसी को पैसे देने का कोई कदम नहीं है। कॉल का नंबर नोट कीजिए और 1930 / cybercrime.gov.in पर रिपोर्ट कीजिए। मैंने पेटीएम रिस्क को बता दिया है।", "speak": "पैसे मत दीजिए। उन्नीस सौ तीस पर रिपोर्ट कीजिए।", "speak_en": "Don't pay. Report it on nineteen thirty."})
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
            await e.act(inc, "notify_merchant", {"text": "🙏 I won't do that. Your account is under a cyber-cell freeze; moving money to another account now could look like evading the law and hurt your case. Your money is safe with Paytm. Someone from Paytm Risk will call you.",
                                                "hi": "🙏 यह मैं नहीं करूँगा। आपका खाता साइबर-सेल फ्रीज़ में है; फ्रीज़ के बीच पैसा दूसरे खाते में भेजना कानून से बचने जैसा लग सकता है और आपका केस बिगाड़ सकता है। आपका पैसा पेटीएम के पास सुरक्षित है। पेटीएम रिस्क से कोई आपसे बात करेगा।",
                                                "speak": "यह मैं नहीं करूँगा। आपका पैसा पेटीएम के पास सुरक्षित है।", "speak_en": "I won't do that. Your money is safe with Paytm."})
            await e.act(inc, "escalate_to_human", {"queue": "Paytm Risk", "summary": "Merchant asked to re-route payouts during an active freeze"})
        else:
            await e.act(inc, "notify_merchant", {"text": "Paytm Ops will verify before any account change.", "hi": "खाता बदलने के लिए पेटीएम ऑप्स सत्यापन करेगा।"})
            inc.status = "waiting_approval"

    async def money(self, inc, unclear: bool = False):
        """'When will it come?' Answered from her real money position, not a menu."""
        e = self.e
        r = await e.call(inc, "get_money_position", {})
        nxt = datetime.fromisoformat(r["next_payout"])
        day_en = "today" if nxt.date() == e.world.now.date() else "tomorrow" if (nxt.date() - e.world.now.date()).days == 1 else nxt.strftime("%-d %b")
        day_hi = "आज" if day_en == "today" else "कल" if day_en == "tomorrow" else nxt.strftime("%-d %b")
        acct = (r.get("account") or "your bank account").replace("Bank account ", "bank account ")
        if r["paused"] or r["held_amount"]:
            amt = r["held_amount"] + (r["pending_amount"] if r["paused"] else 0)
            text = (f"{rs(amt)} is safe with Paytm right now. Your bank is refusing payouts, so nothing is sent until the freeze is limited. "
                    "Then it goes to your own account, after a ₹1 check. Nothing ever goes to any other account.")
            hi = (f"{rs(amt)} अभी पेटीएम के पास सुरक्षित है। आपका बैंक पेआउट लौटा रहा है, इसलिए फ्रीज़ सीमित होने तक कुछ नहीं भेजा जाएगा। "
                  "फिर ₹1 की जाँच के बाद यह आपके ही खाते में जाएगा। किसी और खाते में कभी नहीं।")
            speak, speak_en = f"{amt} रुपये पेटीएम के पास सुरक्षित हैं।", f"{amt} rupees are safe with Paytm."
        elif r["pending_amount"]:
            text = (f"{rs(r['pending_amount'])} from today's {r['pending_count']} payments reaches your {acct} {day_en} at {hm(r['next_payout'])}. "
                    "I'll check that it actually lands and tell you if the bank sends anything back.")
            hi = (f"आज के {r['pending_count']} भुगतानों के {rs(r['pending_amount'])} {day_hi} {hm(r['next_payout'])} बजे आपके खाते में पहुँचेंगे। "
                  "मैं देखूँगा कि पैसा सच में पहुँचा, और बैंक ने कुछ लौटाया तो बताऊँगा।")
            speak = f"{r['pending_amount']} रुपये {day_hi} सुबह आपके खाते में पहुँचेंगे।"
            speak_en = f"{r['pending_amount']} rupees reach your bank {day_en} at {hm(r['next_payout'])}."
        else:
            lb = r.get("last_batch") or {}
            text = f"Nothing is waiting right now. Your last payout of {rs(lb.get('amount'))} was {str(lb.get('status', 'sent')).lower()}." if lb else "Nothing is waiting for a payout right now."
            hi = f"अभी कोई पैसा बाकी नहीं है। पिछला पेआउट {rs(lb.get('amount'))} का था।" if lb else "अभी कोई पेआउट बाकी नहीं है।"
            speak, speak_en = None, None
        if unclear:
            text += " You can also ask about a customer's payment, or send a screenshot."
            hi += " आप किसी ग्राहक के भुगतान के बारे में भी पूछ सकते हैं, या स्क्रीनशॉट भेज सकते हैं।"
        await e.act(inc, "notify_merchant", {"text": text, "hi": hi, "speak": speak, "speak_en": speak_en, "extra": {"money": r}})
        if inc.kind in ("question", "unknown"):
            inc.outcome_verified = True
            await e.act(inc, "resolve_incident", {"outcome": "Told her where her money is, from Paytm's records"})

    async def status(self, inc):
        live = [i for i in self.e.incidents.values() if i.status not in ("resolved", "refused") and i.id != inc.id]
        if not live:
            text, hi = "No open cases right now.", "अभी कोई खुला केस नहीं है।"
        else:
            text = "Open cases: " + "; ".join(f"{i.title} — {i.headline or i.status}" for i in live)
            hi = f"खुले केस: {len(live)}"
        await self.e.act(inc, "notify_merchant", {"text": text, "hi": hi})
        inc.outcome_verified = True
        await self.e.act(inc, "resolve_incident", {"outcome": "Status shared"})

    async def sop_question(self, inc, q):
        e = self.e
        r = await e.call(inc, "ask_sop", {"question": q})
        cites = ", ".join(f"para {c['id']}" for c in r["citations"])
        await e.act(inc, "notify_merchant", {"text": f"📘 {r['answer']}\n\n(Source: MHA/I4C SOP, {cites}. Our summary; you can read the original PDF.)", "speak": None, "extra": {"citations": r["citations"]}})
        if inc.kind == "question":
            inc.outcome_verified = True
            inc.headline = "Answered from the SOP, with citations."
            await e.act(inc, "resolve_incident", {"outcome": "SOP question answered with checked citations"})

    async def bank_ack(self, inc):
        e = self.e
        if inc.kind != "freeze":
            await e.act(inc, "notify_merchant", {"text": "Acknowledgement for which complaint? Start a freeze case first.", "hi": "किस शिकायत की पावती? पहले फ्रीज़ का केस शुरू कीजिए।"})
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
        await e.act(inc, "notify_merchant", {"text": f"⏱️ The bank's 7-day clock starts today: it must forward your complaint by {due} (SOP 10.1(a)). "
                                                    "I'll check on day 5 and day 7 myself. I'm also showing both 90-day dates, because the SOP mentions both.",
                                            "hi": f"⏱️ बैंक के 7 दिन आज से शुरू: {due} तक बैंक को आपकी शिकायत आगे भेजनी है (SOP 10.1(a))। मैं 5वें और 7वें दिन ख़ुद जाँचूँगा। 90 दिन की दोनों तारीख़ें भी दिखा रहा हूँ, क्योंकि SOP में दोनों लिखी हैं।",
                                            "speak": "बैंक का सात दिन का समय आज से शुरू। मैं खुद याद दिलाऊँगा।", "speak_en": "The bank's seven days start today. I'll remind you myself."})
        inc.status = "watching"
        inc.headline = f"Bank's 7-day clock running. Due {due}."


    async def after_approval(self, inc, action, r):
        e = self.e
        if r.get("status") != "DONE":
            return
        if action == "initiate_refund":
            await self._after_refund(inc)
        elif action == "draft_escalation":
            await e.act(inc, "notify_merchant", {"text": "✅ Letter ready. Hand it in at the branch or email it; the signed pack goes with it. I'll keep watching.", "hi": "✅ चिट्ठी तैयार। शाखा में दे दीजिए या ईमेल कर दीजिए; हस्ताक्षरित पैक साथ में है। मैं आगे भी नज़र रखूँगा।"})
            inc.headline = "Escalation letter signed off by Meena."
            inc.status = "with_human"
        elif action == "release_settlement_hold":
            rel = inc.facts.get("released", {})
            lien = (inc.facts.get("case_events", {}).get("io_decision") or {}).get("lien")
            await e.act(inc, "notify_merchant", {"text": f"🎉 Your account is working again. I've sent the {rs(rel.get('released'))} Paytm was holding to your account. Only {rs(lien)} stays held for the police case.", "hi": f"🎉 आपका खाता फिर से चालू है। पेटीएम के पास रुके {rs(rel.get('released'))} आपके खाते में भेज दिए। सिर्फ़ {rs(lien)} पुलिस केस तक रुके रहेंगे।", "speak": "आपका खाता फिर से चालू है। रुका हुआ पैसा आपके खाते में भेज दिया।", "speak_en": "Your account is working again. Your held money has been sent to your account."})
            await e.act(inc, "schedule_followup", {"after_seconds": 76 * 86400, "purpose": "90-day review: both SOP anchors for the remaining hold"})
            for p in inc.plan:
                p["state"] = "done"
            inc.status = "watching"
            inc.money = {"amount": rel.get("released"), "label": f"paid back to her account; only {rs(lien)} still held"}
            inc.headline = f"Account working again. Only {rs(lien)} held."
        elif action == "submit_dispute_response":
            for f in e.followups:
                if f["incident"] == inc.id and not f.get("fired") and f["purpose"].startswith("Remind Meena: chargeback"):
                    f["fired"], f["cancelled"] = True, "replied"
            dd = next(x for x in e.world.disputes if x["dispute_id"] == inc.facts["dispute_id"])
            left = datetime.fromisoformat(dd["respond_by"]) - e.world.now
            e.tick_plan(inc, "Ask Meena one question"); e.tick_plan(inc, "Reply before the deadline")
            await e.act(inc, "notify_merchant", {"text": f"✅ Reply sent, {int(left.total_seconds() // 3600)} hours before the deadline: the payment record, the bill, and your statement (in your name). I'll tell you as soon as there's a decision.", "hi": f"✅ जवाब चला गया, समय-सीमा से {int(left.total_seconds() // 3600)} घंटे पहले: भुगतान का रिकॉर्ड, बिल, और आपकी बात (आपके नाम से)। फ़ैसला आते ही बताऊँगा।", "speak": "जवाब चला गया। फैसला आते ही बताऊँगा।", "speak_en": "Reply sent. I'll tell you when there's a decision."})
            await e.act(inc, "schedule_followup", {"after_seconds": 8 * 3600, "purpose": "Check the chargeback outcome"})
            inc.status = "watching"
            inc.headline = f"Replied {int(left.total_seconds() // 3600)} h before the deadline. Watching the outcome."
        elif action == "draft_lien_request":
            L = inc.facts.get("lien_request", {})
            await e.act(inc, "notify_merchant", {"text": f"✅ Request ready: hold only {L.get('disputed_text', '')}. Take it to your branch with the signed pack and get a dated acknowledgement.", "hi": f"✅ अनुरोध तैयार: रोक सिर्फ़ {L.get('disputed_text', '')} तक। इसे हस्ताक्षरित पैक के साथ शाखा में दीजिए और तारीख़ वाली पावती लीजिए।", "speak": "चिट्ठी तैयार है। शाखा में पैक के साथ दीजिए और तारीख वाली पावती लीजिए।", "speak_en": "Your request is ready. Take it to the branch with the pack and get a dated acknowledgement."})
            inc.headline = "Pack and lien-limiting request ready for the branch."
            inc.status = "with_human"
        elif action == "request_settlement_hold":
            e.tick_plan(inc, "Protect new sales (two-key hold)")
            await e.act(inc, "notify_merchant", {"text": "✅ From now on your payouts stay safe in your Paytm settlement balance. Nothing went to any other account." + ("" if "disputed_txn" in inc.facts else " Send the notice and we'll take the next step."),
                                                "hi": "✅ अब से आपके पेआउट पेटीएम सेटलमेंट बैलेंस में सुरक्षित रहेंगे। किसी दूसरे खाते में कुछ नहीं गया।" + ("" if "disputed_txn" in inc.facts else " नोटिस भेजिए तो आगे बढ़ते हैं।"),
                                                "speak": "आपके पैसे पेटीएम के पास सुरक्षित हैं।", "speak_en": "Your money is safe with Paytm."})
            inc.status = "waiting_merchant" if "disputed_txn" not in inc.facts else "with_human"
            inc.headline = "Payouts held safely. Waiting for the notice." if "disputed_txn" not in inc.facts else inc.headline
            await self._propose_lien(inc)

    async def followup(self, inc, purpose):
        e = self.e
        if purpose.startswith("Remind Meena: chargeback"):
            await e.act(inc, "notify_merchant", {"text": f"⏱️ Reminder: the reply to the {rs(inc.money.get('amount'))} chargeback is due in 6 hours. Did you hand over the goods?",
                                                "hi": f"⏱️ याद दिलाना: {rs(inc.money.get('amount'))} के चार्जबैक का जवाब 6 घंटे में देना है। क्या आपने सामान दिया था?",
                                                "speak": "चार्जबैक का जवाब छह घंटे में देना है।", "speak_en": "The chargeback reply is due in six hours.", "extra": {"approval": inc.id}})
            return
        if purpose.startswith("Check the chargeback outcome"):
            r = await e.call(inc, "get_disputes", {})
            dd = next(x for x in r["disputes"] if x["dispute_id"] == inc.facts["dispute_id"])
            if dd["status"] == "REPRESENTED":
                await e.act(inc, "schedule_followup", {"after_seconds": 3600, "purpose": "Check the chargeback outcome"})
                return
            won = dd["status"] == "WON"
            await e.step(inc, "evidence", stamp="KEPT" if won else dd["status"], title="Follow-up: dispute desk re-checked", tone="good" if won else "bad",
                         verdict=f"{rs(dd['amount'])} stays with Meena" if won else f"Decided for the payer ({dd['status']})",
                         rows=[{"field": "Decision", "claim": "replied in time", "truth": dd["status"], "match": won}])
            await e.act(inc, "notify_merchant", {"text": f"✅ Chargeback won: the {rs(dd['amount'])} stays yours." if won else "The chargeback was decided for the customer. Kavach had replied on time.",
                                                "hi": f"✅ चार्जबैक जीत गए: {rs(dd['amount'])} आपके ही रहे।" if won else "चार्जबैक का फ़ैसला ग्राहक के पक्ष में गया। कवच ने समय पर जवाब दिया था।",
                                                "speak": "चार्जबैक जीत गए, पैसा आपका रहा।" if won else None, "speak_en": "Chargeback won. The money stays yours." if won else None})
            inc.outcome_verified = True
            for p in inc.plan:
                p["state"] = "done"
            inc.headline = f"Replied before the deadline and kept {rs(dd['amount'])}." if won else "Replied in time; decided for the payer."
            await e.act(inc, "resolve_incident", {"outcome": f"{dd['dispute_id']} {dd['status']} after a reply filed before the deadline"})
            return
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
                await e.act(inc, "notify_merchant", {"text": f"☀️ Yesterday's {rs(inc.money.get('amount'))} reached your bank in this morning's payout {b['batch_id']} (UTR {b['bank_utr']}). Closing the case.",
                                                    "hi": f"☀️ कल वाले {rs(inc.money.get('amount'))} आज सुबह के पेआउट {b['batch_id']} में आपके बैंक पहुँच गए (UTR {b['bank_utr']})। केस बंद कर रहा हूँ।",
                                                    "speak": "कल वाला पैसा आज सुबह बैंक में पहुँच गया।", "speak_en": "Yesterday's money reached your bank this morning."})
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
                await e.act(inc, "notify_merchant", {"text": f"✅ {rs(st['amount'])} has arrived (UPI Ref {st['utr']}). I've sent the customer a receipt. You can hand over the goods; they were charged only once.",
                                                    "hi": f"✅ {rs(st['amount'])} आ गए (UPI Ref {st['utr']})। ग्राहक को रसीद भेज दी। अब सामान दे दीजिए — पैसा सिर्फ़ एक बार कटा।",
                                                    "speak": f"{st['amount']} रुपये आ गए। अब सामान दे दीजिए।", "speak_en": f"{st['amount']} rupees arrived. You can hand over the goods."})
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
                await e.act(inc, "notify_merchant", {"text": f"✅ The duplicate {rs(inc.facts['amount'])} is back with the customer (refund {r['refund_id']}). Refunded exactly once.",
                                                    "hi": f"✅ डुप्लिकेट {rs(inc.facts['amount'])} ग्राहक को वापस मिल गए (रिफंड {r['refund_id']})। सिर्फ़ एक बार रिफंड हुआ।",
                                                    "speak": "डुप्लिकेट पैसा ग्राहक को वापस मिल गया।", "speak_en": "The duplicate money is back with the customer."})
            else:
                await e.act(inc, "notify_merchant", {"text": f"✅ {self._who(inc)}'s earlier {rs(r['amount'])} is back in their account ({r['refund_id']}).", "hi": f"✅ {self._who(inc)} के पुराने {rs(r['amount'])} वापस उनके खाते में पहुँच गए ({r['refund_id']})।"})
            if inc.channel == "whatsapp":
                await self._tell_customer(inc, f"Your refund {r['refund_id']} of {rs(r['amount'])} has been credited back to your account.")
            again = await e.call(inc, "get_refund_status", {"refund_id": inc.facts["refund_id"]})
            inc.outcome_verified = again["status"] == "SUCCESS"
            await e.step(inc, "verify", action="final re-check", ok=inc.outcome_verified, check="Refund service re-queried: SUCCESS")
            inc.headline = "Duplicate refunded once, and confirmed." if inc.kind == "duplicate" else "Late payment refunded, and confirmed."
            for p in inc.plan:
                p["state"] = "done"
            await e.act(inc, "resolve_incident", {"outcome": f"Refund {r['refund_id']} of {rs(r['amount'])} confirmed credited"})
        elif purpose.startswith("Bank desk update: bank_submission"):
            ev = inc.facts["case_events"]
            filed = ev.get("bank_complaint", {}).get("date")
            days = (e.world.now.date() - datetime.fromisoformat(filed).date()).days if filed else None
            for f in e.followups:      # the day-5 nudge and day-7 escalation are moot now
                if f["incident"] == inc.id and not f.get("fired") and (f["purpose"].startswith("Day 5") or f["purpose"].startswith("Day 7")):
                    f["fired"], f["cancelled"] = True, "bank submitted"
            await e.step(inc, "evidence", stamp="BANK FILED", title="Bank desk", tone="good", verdict=f"The bank filed in {days} days, inside the SOP's 7",
                         rows=[{"field": "Grievance module", "claim": "within 7 days", "truth": f"{ev['bank_submission'].get('ref')} · day {days}", "match": True}])
            await e.act(inc, "notify_merchant", {"text": f"✅ Your bank filed your complaint on the grievance module in {days} days (ref {ev['bank_submission'].get('ref')}), inside the SOP's 7. Next is the investigating officer's decision; Kavach is watching.",
                                                "hi": f"✅ बैंक ने आपकी शिकायत {days} दिन में ग्रीवेंस मॉड्यूल पर भेज दी (रेफ़ {ev['bank_submission'].get('ref')})। SOP के 7 दिन से पहले। अब जाँच अधिकारी का फ़ैसला आएगा; कवच नज़र रखेगा।",
                                                "speak": "बैंक ने आपकी शिकायत आगे भेज दी।", "speak_en": "Your bank has forwarded your complaint."})
            inc.headline = f"Bank filed on day {days}. Waiting for the officer."
        elif purpose.startswith("Bank desk update: io_decision"):
            lien = inc.facts["case_events"]["io_decision"].get("lien")
            await self.think(inc, f"The bank desk says the officer limited the hold to {rs(lien)}. I won't take that on trust before moving her money: "
                                  "sending Paytm's ₹1 validation credit to see if her bank accepts credits again.")
            v = await e.act(inc, "validate_settlement_account", {})
            st = (v.get("result") or {}).get("status")
            await e.step(inc, "evidence", stamp="CREDITS LAND" if st == "CREDITED" else "STILL FROZEN", title="₹1 validation", tone="good" if st == "CREDITED" else "bad",
                         verdict="Her bank accepts credits again" if st == "CREDITED" else "Her bank still returns credits",
                         rows=[{"field": "Officer's decision", "claim": "—", "truth": f"hold limited to {rs(lien)} (bank desk)", "match": True},
                               {"field": "₹1 credit", "claim": "—", "truth": st or "—", "match": st == "CREDITED"}])
            if st != "CREDITED":
                await e.act(inc, "escalate_to_human", {"queue": "Paytm Risk", "summary": "Bank desk shows a decision but the ₹1 validation still bounces"})
                inc.status = "with_human"
                return
            res = await e.act(inc, "release_settlement_hold", {"reason": "Officer limited the hold; ₹1 validation credited"})
            if res["status"] == "NEEDS_APPROVAL":
                await e.act(inc, "notify_merchant", {"text": f"Good news: the investigating officer has limited the hold to {rs(lien)}, and your bank is accepting money again. As soon as Paytm Risk approves, I'll send your held money to your account.",
                                                    "hi": f"अच्छी ख़बर: जाँच अधिकारी ने रोक सिर्फ़ {rs(lien)} तक सीमित कर दी है, और आपका बैंक अब पैसा ले रहा है। पेटीएम रिस्क की मंज़ूरी मिलते ही आपका रुका हुआ पैसा आपके खाते में भेज दूँगा।",
                                                    "speak": "अच्छी खबर। रोक सिर्फ विवादित रकम तक है।", "speak_en": "Good news. The hold is now only on the disputed amount."})
                inc.headline = "Officer limited the hold. Release waiting for Paytm Risk."
        elif purpose.startswith("90-day review"):
            await e.act(inc, "notify_merchant", {"text": "⏱️ Both 90-day dates are coming up (the SOP mentions both). Ask your bank how long the remaining hold lasts; Kavach is watching both dates.", "hi": "⏱️ 90 दिन की दोनों तारीख़ें पास हैं (SOP में दोनों लिखी हैं)। बैंक से पूछिए कि बची हुई रोक कब तक है; कवच दोनों तारीख़ों पर नज़र रख रहा है।"})
        elif purpose.startswith("Day 5"):
            if "bank_submission" in inc.facts.get("case_events", {}):
                return
            due = (inc.facts.get("clocks") or [{}])[0].get("due")
            await e.act(inc, "notify_merchant", {"text": f"⏱️ Reminder: the bank has 2 days left, until {due}. Ask your branch whether your complaint has gone to the grievance module, and send me the reference if you get it.", "hi": f"⏱️ याद दिलाना: बैंक के पास {due} तक 2 दिन बचे हैं। शाखा से पूछिए कि शिकायत ग्रीवेंस मॉड्यूल में गई या नहीं। रेफ़रेंस मिले तो भेजिए।", "speak": "बैंक के पास दो दिन बचे हैं।", "speak_en": "The bank has two days left."})
            inc.headline = f"Day 5 of 7. Reminder sent; bank due {due}."
        elif purpose.startswith("Day 7"):
            if "bank_submission" in inc.facts.get("case_events", {}):
                await e.act(inc, "notify_merchant", {"text": "The bank has forwarded your complaint. The investigating officer now has 15 days (SOP 10.1(b)).", "hi": "बैंक ने शिकायत भेज दी है। अब जाँच अधिकारी के 15 दिन चलेंगे (SOP 10.1(b))।"})
                return
            await self.think(inc, "Day 7 and no submission recorded. The SOP route says the bank should have submitted by now. "
                                  "Kavach can't contact the bank itself (P7), but it can draft a letter for Meena to sign.", "warn")
            r = await e.act(inc, "draft_escalation", {"to": "Grievance Officer, " + MERCHANT["settlement_bank"].replace("Bank account ", "Bank (a/c ") + ")",
                                                       "reason": "No confirmation of grievance submission within 7 days"})
            if r["status"] == "NEEDS_APPROVAL":
                await e.act(inc, "notify_merchant", {"text": "⚠️ 7 days are up and the bank hasn't confirmed forwarding your complaint. Shall I draft a letter to the bank's grievance officer in your name?", "hi": "⚠️ 7 दिन पूरे, बैंक ने शिकायत भेजने की ख़बर नहीं दी। मैं आपके नाम से बैंक के ग्रीवेंस अधिकारी को चिट्ठी बना दूँ?", "speak": "सात दिन पूरे हो गए। बैंक को चिट्ठी बना दूँ?", "speak_en": "Seven days are up. Shall I draft a letter to the bank?", "extra": {"approval": inc.id}})
                inc.headline = "Day 7 passed. Escalation letter waiting for Meena's OK."
        elif purpose.startswith("Ask for the bank"):
            await e.act(inc, "notify_merchant", {"text": "Namaste Meena ji, did the bank give you a dated acknowledgement for your complaint? Send me a photo of it; the bank's 7-day clock starts from that date.", "hi": "नमस्ते मीना जी — क्या बैंक ने आपकी शिकायत की तारीख़ वाली पावती दी? उसकी फ़ोटो भेजिए; उसी दिन से बैंक के 7 दिन गिने जाते हैं।"})
