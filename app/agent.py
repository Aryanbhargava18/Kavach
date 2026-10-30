"""Kavach's incident engine.

Loop: interpret -> plan -> call tools -> inspect -> policy -> act -> verify -> follow up / escalate.

Two planners drive the same engine:
  * OfflinePlanner  - deterministic playbooks (no API key needed). Labelled 'offline rules' in the UI.
  * LLMPlanner      - Claude with tool use (llm.py), when ANTHROPIC_API_KEY is set.
Either way, every write goes through policy.evaluate() and is re-verified against the World.
"""
from __future__ import annotations

import asyncio
import itertools
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from . import policy, proof, tools
from .bus import Bus
from .understand import interpret
from .world import MERCHANT, World, mask_vpa

_ids = itertools.count(1)


@dataclass
class Incident:
    id: str
    kind: str
    title: str
    created_at: str
    status: str = "investigating"     # investigating | waiting_approval | watching | waiting_merchant | with_human | resolved | refused
    headline: str = ""
    planner: str = "offline"
    steps: list[dict[str, Any]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    approvals: dict = field(default_factory=dict)   # action -> set of approvers (an approval never carries over to another action)
    pending: dict[str, Any] | None = None
    followups_used: int = 0
    outcome: str | None = None
    outcome_verified: bool = False
    decisive: dict[str, Any] | None = None
    plan: list[dict[str, Any]] = field(default_factory=list)
    money: dict[str, Any] = field(default_factory=dict)
    channel: str = "merchant"          # whatsapp (customer wrote in) | merchant (Meena reported it)
    customer: dict[str, Any] = field(default_factory=dict)
    recon: dict[str, dict[str, Any]] = field(default_factory=dict)   # the reconciliation grid: one column per system
    updated_at: str = ""

    def summary(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "title": self.title, "status": self.status, "headline": self.headline,
                "planner": self.planner, "created_at": self.created_at, "updated_at": self.updated_at, "outcome": self.outcome,
                "outcome_verified": self.outcome_verified, "decisive": self.decisive, "plan": self.plan, "pending": _pending_public(self.pending),
                "money": self.money, "channel": self.channel, "customer": self.customer, "recon": self.recon,
                "facts": {k: v for k, v in self.facts.items() if not k.startswith("_")}, "steps": len(self.steps)}


def _nice(ts) -> str:
    from datetime import datetime
    try:
        d = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
        return d.strftime("%-d %b, %-I:%M %p")
    except Exception:
        return str(ts)


def _pending_public(p):
    if not p:
        return None
    return {k: p[k] for k in ("action", "args", "approvers", "ask", "approved") if k in p}


class Engine:
    def __init__(self, world: World, bus: Bus | None = None, pace: float = 0.0, base_url: str = "http://127.0.0.1:8000"):
        self.world = world
        self.bus = bus or Bus()
        self.pace = pace
        self.base_url = base_url
        self.incidents: dict[str, Incident] = {}
        self.followups: list[dict[str, Any]] = []
        self.chat: list[dict[str, Any]] = []
        self.locks: dict[str, asyncio.Lock] = {}
        self.seen_webhooks: set[str] = set()   # failed POS deliveries Kavach has already picked up
        self.seen_returns: set[str] = set()    # payout batches the merchant's bank sent back that Kavach has already picked up
        self.alive = True   # set False on reset so a run still in flight can't paint the new screen
        from .llm import make_planner
        self.planner = make_planner(self)

    # ------------------------------------------------------------ plumbing
    def _emit(self, kind: str, payload: dict[str, Any]) -> None:
        if self.alive:
            self.bus.publish({"type": kind, **payload})

    async def step(self, inc: Incident, kind: str, **data) -> dict[str, Any]:
        s = {"n": len(inc.steps) + 1, "kind": kind, "at": self.world.now.isoformat(), "incident": inc.id, **data}
        inc.steps.append(s)
        inc.updated_at = s["at"]
        self._emit("step", {"step": s})
        self._emit("incident", {"incident": inc.summary()})
        if self.pace:
            await asyncio.sleep(self.pace * (1.6 if kind in ("tool", "action", "policy") else 1))
        if not self.alive:
            raise asyncio.CancelledError("engine was reset")
        return s

    def set_plan(self, inc: Incident, items: list[str], replan: str | None = None) -> None:
        done = {p["text"] for p in inc.plan if p["state"] == "done"}
        inc.plan = [{"text": t, "state": "done" if t in done else "todo"} for t in items]
        self._emit("incident", {"incident": inc.summary()})

    def tick_plan(self, inc: Incident, text: str, state: str = "done") -> None:
        for p in inc.plan:
            if p["text"] == text:
                p["state"] = state
        self._emit("incident", {"incident": inc.summary()})

    async def call(self, inc: Incident, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """A real tool call: announced (running), executed against the world, timed, and recorded."""
        import time
        self._emit("tool_start", {"incident": inc.id, "tool": name, "args": args, "n": len(inc.steps) + 1})
        if self.pace:
            await asyncio.sleep(self.pace * 0.9)
        t0 = time.perf_counter()
        result, summary = await tools.run_read_async(self.world, name, args)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        self._recon(inc, name, args, result)
        await self.step(inc, "tool", tool=name, args=args, summary=summary, result=result, ms=ms)
        return result

    # ------------------------------------------------- reconciliation grid
    def _col(self, inc: Incident, key: str, **v) -> None:
        inc.recon[key] = {**inc.recon.get(key, {}), **{k: x for k, x in v.items() if x is not None}}

    def _recon(self, inc: Incident, name: str, args: dict[str, Any], r: dict[str, Any]) -> None:
        """Every tool result that speaks about the disputed payment lands in one column of the grid."""
        def t12(iso):
            return str(iso)[11:16] if iso else None
        if name == "read_screenshot":
            self._col(inc, "claim", label="Customer's screenshot", tier="Claim", ref=r.get("utr"), amount=r.get("amount"),
                      status=r.get("status_text") or "?", when=None, note="an image can be edited")
        elif name == "parse_notice":
            f = r.get("fields", {})
            self._col(inc, "claim", label="Police notice", tier="Claim", ref=(f.get("utr") or {}).get("value"),
                      amount=(f.get("amount") or {}).get("value"), status=str(r.get("action_kind") or "?").replace("_", " ").upper(), when=(f.get("transaction_date") or {}).get("value"))
        elif name == "get_bank_signal":
            lr = r.get("last_return") or {}
            self._col(inc, "bank", label="Her bank, as Paytm sees it", tier="T1", ref=lr.get("batch_id"), amount=None,
                      status="PAYOUTS RETURNED" if lr else "PAYOUTS LANDING", when=None,
                      note=(f"{lr.get('code')} · {lr.get('reason')}" if lr else "debit freeze is invisible to Paytm; credits still land"))
        elif name == "get_settlement_status" and not args.get("txn_id") and r.get("batches") and "settlement" not in inc.recon:
            b = r["batches"][0]
            self._col(inc, "settlement", label="Latest payout", tier="T1", ref=b["batch_id"], amount=b["amount"], status=b["status"],
                      when=t12(b.get("credited_at")), note=f"bank UTR {b['bank_utr']}" if b.get("bank_utr") else b.get("return_reason"))
        elif name == "get_payment_status" and r.get("txn_id"):
            self._col(inc, "switch", label="UPI switch", tier="T1", ref=r.get("utr"), amount=r.get("amount"), status=r.get("status"),
                      when=t12(r.get("created_at")), note=r.get("status_reason"))
        elif name == "lookup_transaction" and not r.get("matches") and "switch" not in inc.recon:
            self._col(inc, "switch", label="UPI switch", tier="T1", ref=args.get("utr"), amount=None, status="NOT FOUND", when=None,
                      note="no payment to this shop with that reference")
        elif name == "get_merchant_ledger" and (args.get("utr") or args.get("bill_id")):
            e = (r.get("entries") or [None])[0]
            bill = next((b for b in r.get("bills", []) if b["bill_id"] == (inc.facts.get("bill_id") or args.get("bill_id"))), None)
            if e and inc.facts.get("bill_id") and e["bill_id"] != inc.facts["bill_id"]:
                self._col(inc, "ledger", label="Shop's ledger", tier="T1", ref=e["utr"], amount=e["amount"], status=f"USED ON {e['bill_id']}",
                          when=t12(e["at"]), note=f"{inc.facts['bill_id']} still unpaid")
            elif e:
                self._col(inc, "ledger", label="Shop's ledger", tier="T1", ref=e["utr"], amount=e["amount"],
                          status=f"{bill['status'] if bill else 'RECORDED'} · {e['bill_id']}", when=t12(e["at"]),
                          note="repaired by Kavach" if e["source"].startswith("kavach") else "via Paytm webhook",
                          repaired=e["source"].startswith("kavach"))
            else:
                wh = r.get("webhook") or {}
                fails = [x for x in wh.get("attempts", []) if x.get("http") not in (200, 410)]
                rejected = [x for x in wh.get("attempts", []) if x.get("http") == 410]
                status = ("MISSING" if fails else "NOT APPLIED" if rejected else (f"{bill['status']} · {bill['bill_id']}" if bill else "NO ENTRY"))
                note = (f"webhook failed ×{len(fails)} (HTTP {fails[-1]['http']})" if fails else
                        "order had expired (HTTP 410)" if rejected else (f"bill {bill['bill_id']} ₹{bill['amount']:,}" if bill else None))
                self._col(inc, "ledger", label="Shop's ledger", tier="T1", ref=None, amount=bill["paid_amount"] if bill else None,
                          status=status, when=None, note=note)
        elif name == "get_merchant_ledger" and r.get("bills") and inc.facts.get("bill_id"):
            b = next((x for x in r["bills"] if x["bill_id"] == inc.facts["bill_id"]), None)
            if b and "ledger" not in inc.recon:
                self._col(inc, "ledger", label="Shop's ledger", tier="T1", ref=None, amount=b["paid_amount"], status=f"{b['status']} · {b['bill_id']}",
                          when=t12(b["created_at"]), note=f"bill for ₹{b['amount']:,}")
        elif name == "get_refund_status" and args.get("txn_id"):
            rf = (r.get("refunds") or [None])[0]
            if rf:
                self._col(inc, "refund", label="Refund service", tier="T1", ref=rf["refund_id"], amount=rf["amount"], status=rf["status"],
                          when=t12(rf.get("created_at")), note=rf.get("reason"))
        elif name == "get_refund_status" and r.get("refund_id"):
            self._col(inc, "refund", label="Refund service", tier="T1", ref=r["refund_id"], amount=r.get("amount"), status=r.get("status"),
                      when=t12(r.get("created_at")), note=r.get("reason"))
        elif name == "get_settlement_status" and args.get("txn_id"):
            b = (r.get("batches") or [None])[0]
            if b:
                mine = (inc.recon.get("switch") or {}).get("amount")
                tail = f"bank UTR {b['bank_utr']}" if b.get("bank_utr") else (b.get("return_reason") or "")
                self._col(inc, "settlement", label="Payout to Meena's bank", tier="T1", ref=b["batch_id"], amount=mine or b["amount"], status=b["status"],
                          when=t12(b.get("credited_at")), note=(f"inside a ₹{b['amount']:,} batch · " if mine else "") + tail)
            elif r.get("next_payout"):
                self._col(inc, "settlement", label="Payout to Meena's bank", tier="T1", ref=None, amount=None, status="NOT YET",
                          when=None, note="next payout " + _nice(r["next_payout"]))
        elif name == "find_duplicate_payments":
            g = (r.get("duplicate_groups") or r.get("groups") or [{}])[0]
            for i, t in enumerate((g.get("txns") or [])[:2]):
                self._col(inc, f"pay{i + 1}", label=f"Payment {i + 1}", tier="T1", ref=t["utr"], amount=t["amount"], status=t["status"],
                          when=t12(t["created_at"]), note=g.get("payer"))
        elif name == "lookup_transaction" and inc.kind == "freeze" and r.get("matches"):
            t = r["matches"][0]
            self._col(inc, "switch", label="UPI switch", tier="T1", ref=t["utr"], amount=t["amount"], status=t["status"], when=str(t["created_at"])[:10])

    async def act(self, inc: Incident, action: str, args: dict[str, Any], *, verify: bool = True) -> dict[str, Any]:
        """Policy-gate, execute, and re-verify a write action."""
        granted = inc.approvals.get(action, set())
        ctx = {"approvals": granted, "followups_used": inc.followups_used, "outcome_verified": inc.outcome_verified,
               "freeze_reported": any(i.kind == "freeze" and i.status not in ("resolved", "refused") for i in self.incidents.values())}
        with self.world.lock:
            d = policy.evaluate(self.world, action, args, ctx)
        await self.step(inc, "policy", action=action, args=_redact(args), **d.as_dict())
        if d.verdict == "DENY":
            return {"status": "DENIED", "decision": d.as_dict()}
        if d.verdict == "NEEDS_APPROVAL":
            missing = [a for a in d.approvers if a not in granted]
            inc.pending = {"action": action, "args": args, "approvers": missing, "approved": sorted(granted), "ask": d.reason}
            from . import automation
            self._automation("approval_needed", inc, {"action": action, "approvers": missing, "reason": d.reason})
            inc.status = "waiting_approval"
            await self.step(inc, "approval", action=action, approvers=missing, reason=d.reason)
            if "paytm_ops" in missing:
                with self.world.lock:
                    self.world.add_ops_ticket("approval", f"Approve: {action.replace('_', ' ')}", {"args": args, "reason": d.reason}, inc.id, True)
            return {"status": "NEEDS_APPROVAL", "decision": d.as_dict(), "approvers": missing}
        with self.world.lock:
            res = self._execute(inc, action, args)
        await self.step(inc, "action", action=action, args=_redact(args), summary=res.get("summary", ""), result=res)
        ev = {"schedule_followup": "followup_scheduled", "escalate_to_human": "escalated_to_human", "generate_evidence_pack": "evidence_pack_issued",
              "request_settlement_hold": "payouts_held", "draft_escalation": "escalation_letter_approved", "record_case_event": "case_event_recorded",
              "initiate_refund": "refund_initiated"}.get(action)
        if ev:
            self._automation(ev, inc, {"action": action, "args": _redact(args), "summary": res.get("summary", "")})
        if verify:
            ok, what = self._verify(inc, action, args, res)
            await self.step(inc, "verify", action=action, ok=ok, check=what)
            res["verified"] = ok
        return {"status": "DONE", "result": res}

    # --------------------------------------------------------- execution
    def _execute(self, inc: Incident, action: str, a: dict[str, Any]) -> dict[str, Any]:
        w = self.world
        if action == "notify_merchant":
            m = w.send_message("merchant", "app", a["text"], inc.id)
            self._phone("kavach", a["text"], inc.id, speak=a.get("speak"), extra=a.get("extra"))
            return {"msg_id": m["msg_id"], "summary": "Message delivered in Paytm for Business app (simulated)"}
        if action == "send_customer_update_simulated":
            ch = "whatsapp" if inc.channel == "whatsapp" else "counter card"
            m = w.send_message("customer", ch, a["text"], inc.id)
            self._phone("card", a["text"], inc.id, extra={"channel": ch})
            return {"msg_id": m["msg_id"], "channel": ch,
                    "summary": "WhatsApp to the customer (simulated, inside the 24-hour service window)" if ch == "whatsapp" else "Card on Meena's phone for the customer"}
        if action == "create_support_case":
            c = w.open_case(inc.id, a.get("channel") or inc.channel, a.get("summary", inc.title))
            inc.facts["case_id"] = c["case_id"]
            return {"case_id": c["case_id"], "summary": f"Support case {c['case_id']} opened"}
        if action == "reconcile_payment":
            t = next(x for x in w.transactions if x["utr"] == a["utr"])
            e = w.reconcile(t, a["bill_id"])
            self._col(inc, "ledger", label="Shop's ledger", tier="T1", ref=e["utr"], amount=e["amount"], status=f"PAID · {e['bill_id']}",
                      when=str(e["at"])[11:16], note="repaired by Kavach from the switch record", repaired=True)
            return {"entry_id": e["entry_id"], "bill_id": e["bill_id"], "summary": f"Ledger entry {e['entry_id']}: ₹{e['amount']:,} → {e['bill_id']} (UTR …{e['utr'][-4:]})"}
        if action == "replay_soundbox":
            e = w.replay_soundbox(w.txn_by_id(a["txn_id"]))
            return {"phrase": e["phrase"], "summary": f"Soundbox {MERCHANT['soundbox_id']}: “{e['phrase']}”"}
        if action == "issue_verified_receipt":
            t = w.txn_by_id(a["txn_id"])
            text = (f"Receipt: ₹{t['amount']:,} received by {MERCHANT['name']} on {t['updated_at'].strftime('%d %b, %I:%M %p')}. "
                    f"UPI Ref {t['utr']}. Verified with the UPI switch by Paytm Kavach.")
            ch = "whatsapp" if inc.channel == "whatsapp" else "counter card"
            m = w.send_message("customer", ch, text, inc.id)
            self._phone("card", text, inc.id, extra={"receipt": True, "amount": t["amount"], "channel": ch})
            return {"msg_id": m["msg_id"], "txn_id": t["txn_id"], "summary": f"Verified receipt shown for ₹{t['amount']:,} (UTR {t['utr']})"}
        if action == "request_payment":
            amt = int(a["amount"])
            uri = f"upi://pay?pa={MERCHANT['vpa']}&pn=Meena%20Kirana%20Store&am={amt}.00&cu=INR&tn={inc.id}"
            text = f"Scan to pay ₹{amt:,} to {MERCHANT['name']}"
            ch = "whatsapp" if inc.channel == "whatsapp" else "counter card"
            m = w.send_message("customer", ch, text, inc.id)
            self._phone("card", text, inc.id, extra={"qr": uri, "amount": amt, "channel": ch})
            return {"msg_id": m["msg_id"], "upi_uri": uri, "summary": f"Dynamic QR for exactly ₹{amt:,} on Meena's phone"}
        if action == "initiate_refund":
            t = w.txn_by_id(a["txn_id"])
            r = w.create_refund(t, int(a["amount"]), idempotency_key=f"dup:{t['txn_id']}")
            inc.facts["refund_id"] = r["refund_id"]
            return {"refund_id": r["refund_id"], "status": r["status"], "summary": f"Refund {r['refund_id']} ₹{r['amount']:,} created at refund service"}
        if action == "schedule_followup":
            due = w.now + timedelta(seconds=int(a["after_seconds"]))
            via = None
            watched = w.txn_by_id(inc.facts.get("txn_id", "")) if inc.facts.get("txn_id") else None
            if watched and watched["status"] != "PENDING" and a["purpose"].startswith("Re-check payment status"):
                due, via = w.now, "status already changed"      # the bank answered while Kavach was still setting up the watch
            f = {"incident": inc.id, "due": due, "purpose": a["purpose"], "id": f"FU-{len(self.followups) + 1}", **({"via": via} if via else {})}
            self.followups.append(f)
            inc.followups_used += 1
            return {"followup_id": f["id"], "due": due.isoformat(), "summary": f"Follow-up {f['id']} at {due.strftime('%I:%M:%S %p') if due.date() == w.now.date() else due.strftime('%d %b, %I:%M %p')} · {a['purpose']}"}
        if action == "request_settlement_hold":
            cfg = w.pause_settlement(a.get("reason", "Bank returning credits as frozen"))
            for tk in w.ops_queue:
                if tk["incident_id"] == inc.id and tk["status"] == "AWAITING_HUMAN" and "settlement" in tk["title"]:
                    tk["status"] = "APPROVED"
            return {"settlement_config": cfg, "summary": "Payouts held in Paytm settlement balance; nothing moved to another account"}
        if action == "generate_evidence_pack":
            case = self._pack_case(inc, a)
            iss = proof.issue(case, self.base_url)
            inc.facts["pack"] = iss
            return {"token": iss["token"], "verify_url": iss["verify_url"], "pdf_sha256": iss["pdf_sha256"],
                    "summary": f"Signed pack {iss['token']} · SHA-256 {iss['pdf_sha256'][:12]}…"}
        if action == "escalate_to_human":
            tk = w.add_ops_ticket("escalation", a.get("summary", "Escalation")[:90], {"queue": a.get("queue")}, inc.id, False)
            inc.facts["ticket"] = tk["ticket_id"]
            return {"ticket_id": tk["ticket_id"], "summary": f"{tk['ticket_id']} opened in {a.get('queue', 'Paytm Support')} queue"}
        if action == "record_case_event":
            inc.facts.setdefault("case_events", {})[a["event"]] = {"date": a["date"], "source": "Meena-reported (indicative)"}
            return {"summary": f"{a['event'].replace('_', ' ')} on {a['date']} recorded (Meena-reported)"}
        if action == "draft_escalation":
            letter = self._escalation_letter(inc, a)
            inc.facts["escalation_letter"] = letter
            m = w.send_message("merchant", "app", letter["en"], inc.id)
            self._phone("kavach", "✉️ Bank ke grievance officer ke liye chitthi taiyaar hai (aapke naam se). Neeche padh lijiye:\n\n" + letter["en"], inc.id)
            return {"msg_id": m["msg_id"], "summary": f"Escalation letter to {a['to']} approved by Meena; ready to hand in or email"}
        if action == "resolve_incident":
            inc.status = "resolved"
            inc.outcome = a["outcome"]
            return {"summary": f"Closed: {a['outcome']}"}
        return {"summary": "no-op"}

    def _verify(self, inc: Incident, action: str, a: dict[str, Any], res: dict[str, Any]) -> tuple[bool, str]:
        w = self.world
        with w.lock:
            if action == "create_support_case":
                return any(c["case_id"] == res.get("case_id") for c in w.support_cases), f"Case {res.get('case_id')} exists in the support system"
            if action == "reconcile_payment":
                entries = [x for x in w.ledger if x["utr"] == a["utr"]]
                t = next((x for x in w.transactions if x["utr"] == a["utr"]), None)
                bill = next((b for b in w.bills if b["bill_id"] == a["bill_id"]), None)
                ok = len(entries) == 1 and entries[0]["bill_id"] == a["bill_id"] and t and t["status"] == "SUCCESS" and bill and bill["status"] in ("PAID", "PARTIAL")
                return ok, (f"Re-read both systems: switch SUCCESS ₹{t['amount']:,}; ledger has exactly one entry for UTR …{a['utr'][-4:]} on {a['bill_id']} ({bill['status']}). They agree."
                            if ok else "Ledger and switch still disagree")
            if action in ("notify_merchant", "send_customer_update_simulated", "request_payment", "issue_verified_receipt"):
                ok = any(m["msg_id"] == res.get("msg_id") for m in w.outbox)
                if action == "issue_verified_receipt":
                    t = w.txn_by_id(a["txn_id"])
                    ok = ok and t["status"] == "SUCCESS"
                    return ok, f"Outbox has {res.get('msg_id')} and switch still shows SUCCESS for {a['txn_id']}"
                return ok, f"Outbox has {res.get('msg_id')} (simulated delivery)"
            if action == "replay_soundbox":
                ok = bool(w.soundbox_log) and w.soundbox_log[-1]["txn_id"] == a["txn_id"]
                return ok, "Soundbox log shows the replay"
            if action == "initiate_refund":
                r = next((x for x in w.refunds if x["refund_id"] == res.get("refund_id")), None)
                return bool(r), f"Refund service reports {r['refund_id']} {r['status']}" if r else "Refund not found"
            if action == "schedule_followup":
                return any(f["id"] == res.get("followup_id") for f in self.followups), "Follow-up is on the scheduler"
            if action == "request_settlement_hold":
                return w.settlement_config["paused"], "Settlement engine config shows payouts held"
            if action == "generate_evidence_pack":
                v = proof.verify(res["token"], None, w.now, inc.id)
                return v["result"] == "VALID", f"Independent verifier: {v['result']}"
            if action == "record_case_event":
                return a["event"] in inc.facts.get("case_events", {}), "Case event is on the incident record"
            if action == "draft_escalation":
                return bool(inc.facts.get("escalation_letter")), "Letter stored on the case"
            if action == "escalate_to_human":
                return any(t["ticket_id"] == res.get("ticket_id") for t in w.ops_queue), "Ticket present in ops queue"
            if action == "resolve_incident":
                return True, "Outcome had been re-verified before closing"
        return True, "n/a"

    def _automation(self, event: str, inc: Incident, payload: dict[str, Any]) -> None:
        from . import automation
        rec = automation.emit(event, {"incident": inc.id, "kind": inc.kind, "merchant": MERCHANT["name"], **payload}, at=self.world.now.isoformat())
        self._emit("automation", {"record": rec})

    def _phone(self, who: str, text: str, inc_id: str | None = None, speak: str | None = None, extra: dict | None = None) -> None:
        m = {"who": who, "text": text, "at": self.world.now.isoformat(), "incident": inc_id, "speak": speak, "extra": extra or {}}
        self.chat.append(m)
        self._emit("phone", {"message": m})

    def _escalation_letter(self, inc: Incident, a: dict[str, Any]) -> dict[str, str]:
        n = inc.facts.get("notice", {})
        ev = inc.facts.get("case_events", {}).get("bank_complaint", {})
        pack = inc.facts.get("pack", {})
        en = (f"To: {a['to']}\nFrom: {MERCHANT['owner']}, {MERCHANT['name']} ({MERCHANT['settlement_bank']})\n\n"
              f"I submitted a written complaint at the branch on {ev.get('date', '[date]')} about a debit freeze linked to NCRP "
              f"acknowledgement {n.get('ack_number', '[ack]')} (disputed amount ₹{n.get('amount', 0):,}, UTR {n.get('utr', '[utr]')}). "
              f"Under the MHA/I4C SOP para 10.1(a), the bank is to submit the grievance within 7 calendar days of the complaint. "
              f"I have not been told that it was submitted. Please confirm the submission date and reference. "
              f"A signed evidence pack is attached (verify at {pack.get('verify_url', '[link]')}).\n\n{MERCHANT['owner']}")
        return {"en": en, "reason": a.get("reason", "")}

    def _pack_case(self, inc: Incident, a: dict[str, Any]) -> dict[str, Any]:
        f = inc.facts
        t = self.world.txn_by_id(f["disputed_txn"])
        stl = f.get("disputed_settlement") or {}
        facts = [
            {"label": "UTR", "value": t["utr"], "source": "UPI switch record (synthetic)", "tier": "T1"},
            {"label": "Amount", "value": f"₹{t['amount']:,}", "source": "UPI switch record (synthetic)", "tier": "T1"},
            {"label": "Time", "value": t["created_at"].strftime("%d %b %Y, %I:%M:%S %p"), "source": "UPI switch record (synthetic)", "tier": "T1"},
            {"label": "Paid to", "value": MERCHANT["vpa"], "source": "UPI switch record (synthetic)", "tier": "T1"},
            {"label": "Payer", "value": mask_vpa(t["payer_vpa"]), "source": "Masked: payer may be a victim (SOP)", "tier": "T1"},
            {"label": "Settled", "value": f"{stl.get('batch_id', '—')} on {str(stl.get('credited_at') or '—')[:10]}", "source": "Settlement engine (synthetic)", "tier": "T1"},
            {"label": "Soundbox", "value": "Announcement logged at counter" if t["soundbox_announced"] else "No announcement logged",
             "source": "Device notification log — supporting only", "tier": "T2"},
            {"label": "Merchant says", "value": "Regular counter sale", "source": "Merchant's own statement", "tier": "T3"},
        ]
        return {"case_id": inc.id, "merchant": f"{MERCHANT['name']} ({MERCHANT['mid']})", "issued_at": self.world.now.strftime("%d %b %Y %I:%M %p"),
                "issued_at_iso": self.world.now.isoformat(), "facts": facts, "route": f.get("route", []),
                "disputed_amount_text": f"₹{t['amount']:,}"}

    # ------------------------------------------------------------ entrypoints
    def new_incident(self, kind: str, title: str) -> Incident:
        ctx = getattr(self, "_msg_ctx", {}) or {}
        inc = Incident(id=f"KVH-{1040 + next(_ids)}", kind=kind, title=title, created_at=self.world.now.isoformat(),
                       planner=self.planner.label, channel=ctx.get("channel", "merchant"), customer=ctx.get("customer") or {})
        inc.updated_at = inc.created_at
        self.incidents[inc.id] = inc
        self.locks[inc.id] = asyncio.Lock()
        self._emit("incident", {"incident": inc.summary()})
        return inc

    def open_incident(self, kind: str | None = None) -> Incident | None:
        live = [i for i in self.incidents.values() if i.status not in ("resolved", "refused")]
        if kind:
            live = [i for i in live if i.kind == kind]
        return live[-1] if live else None

    async def customer_message(self, text: str, shot_id: str | None = None, customer: dict[str, Any] | None = None) -> Incident:
        """A customer writes in on WhatsApp (simulated). Same engine, customer channel."""
        shot = self.world.screenshots.get(shot_id or "") or {}
        customer = customer or shot.get("customer") or {"name": "Customer", "wa": "+91 9•••• ••••"}
        self._msg_ctx = {"channel": "whatsapp", "customer": customer}
        try:
            open_ = next((i for i in reversed(list(self.incidents.values())) if i.channel == "whatsapp"
                          and i.customer.get("name") == customer.get("name") and i.status in ("waiting_customer", "watching")), None)
            u = interpret(text, has_screenshot=bool(shot_id))
            if open_ and not shot_id:
                inc = open_
                async with self.locks[inc.id]:
                    await self.step(inc, "intake", text=text, intent=u["intent"], amount=u.get("amount"), utrs=u.get("utrs"),
                                    language=u.get("language"), engine=u.get("engine"), sender="customer")
                    import re as _re
                    d = _re.findall(r"(?<!\d)(\d{4})(?!\d)", text)
                    if inc.facts.get("candidates") and d:
                        await self.planner.disambiguate(inc, d[-1])
                    else:
                        await self.act(inc, "notify_merchant", {"text": f"{customer.get('name')} ne likha: “{text}”. Main dekh raha hoon."})
                return inc
            if u["intent"] not in ("payment_claim", "duplicate_charge"):
                u["intent"] = "payment_claim" if shot_id or u.get("amount") else u["intent"]
            inc = await self.planner.handle(text, dict(u, sender="customer"), shot_id=shot_id)
            self._emit("incident", {"incident": inc.summary()})
            return inc
        finally:
            self._msg_ctx = {}

    async def merchant_message(self, text: str, shot_id: str | None = None, doc_id: str | None = None) -> Incident:
        self._phone("merchant", text, extra={"shot_id": shot_id, "doc_id": doc_id})
        shot = self.world.screenshots.get(shot_id or "") or {}
        self._msg_ctx = {"channel": "merchant", "customer": shot.get("customer") or {}}
        u = interpret(text, has_screenshot=bool(shot_id))
        if doc_id and u["intent"] not in ("scam_call", "change_settlement_account"):
            u["intent"] = "freeze_notice"
        try:
            inc = await self.planner.handle(text, dict(u, sender="merchant"), shot_id=shot_id, doc_id=doc_id)
        finally:
            self._msg_ctx = {}
        self._emit("incident", {"incident": inc.summary()})
        return inc

    async def approve(self, inc_id: str, approver: str, yes: bool = True) -> dict[str, Any]:
        inc = self.incidents[inc_id]
        async with self.locks[inc_id]:
            if not inc.pending:
                return {"ok": False, "error": "nothing pending"}
            if not yes:
                await self.step(inc, "approval_result", approver=approver, approved=False)
                action = inc.pending["action"]
                inc.pending = None
                inc.status = "with_human" if inc.kind == "freeze" else "resolved"
                inc.outcome = f"{approver} declined {action.replace('_', ' ')}"
                return {"ok": True}
            inc.approvals.setdefault(inc.pending["action"], set()).add(approver)
            if approver == "merchant":
                self._phone("merchant", "✅ Haan, approve", inc.id)
            await self.step(inc, "approval_result", approver=approver, approved=True)
            p = inc.pending
            p["approvers"] = [a for a in p["approvers"] if a != approver]
            p["approved"] = sorted(inc.approvals.get(p["action"], set()))
            if p["approvers"]:
                self._emit("incident", {"incident": inc.summary()})
                return {"ok": True, "waiting_for": p["approvers"]}
            inc.pending = None
            inc.status = "investigating"
            r = await self.act(inc, p["action"], p["args"])
            await self.planner.after_approval(inc, p["action"], r)
            self._emit("incident", {"incident": inc.summary()})
            return {"ok": True, "result": r.get("status")}

    async def run_due_followups(self) -> None:
        due = [f for f in self.followups if f["due"] <= self.world.now and not f.get("fired")]
        for f in due:
            f["fired"] = True          # claim all due follow-ups before awaiting anything (no double firing)
        for f in due:
            inc = self.incidents.get(f["incident"])
            if not inc or inc.status in ("resolved", "refused"):
                continue
            async with self.locks[inc.id]:
                await self.step(inc, "followup", purpose=f["purpose"], followup_id=f["id"], via=f.get("via", "scheduled time"))
                self._automation("followup_fired", inc, {"purpose": f["purpose"], "via": f.get("via", "scheduled time")})
                await self.planner.followup(inc, f["purpose"])
            self._emit("incident", {"incident": inc.summary()})

    async def tick(self, seconds: float, background: bool = False) -> None:
        with self.world.lock:
            happened = self.world.advance(seconds)
        returned = []
        for ev in happened:
            self._emit("world_event", {"event": ev})
            self._wake_on_callback(ev)
            if ev.get("kind") == "settlement" and ev.get("status") == "RETURNED" and ev["batch_id"] not in self.seen_returns:
                self.seen_returns.add(ev["batch_id"])
                returned.append(ev["batch_id"])
        self._emit("clock", {"now": self.world.now.isoformat()})
        for batch_id in returned:     # the payout watcher: the bank bounced a payout before Meena knows anything is wrong
            if background:
                asyncio.create_task(self._safe(self.proactive_payout(batch_id)))
            else:
                await self.proactive_payout(batch_id)
        for rec in self.world.failed_webhooks_due():     # the watcher: nobody has to complain first
            if rec["txn_id"] not in self.seen_webhooks:
                self.seen_webhooks.add(rec["txn_id"])
                if background:
                    asyncio.create_task(self._safe(self.proactive_webhook(rec["txn_id"])))
                else:
                    await self.proactive_webhook(rec["txn_id"])
        if background:   # live server: keep the clock running while the agent works
            if any(f["due"] <= self.world.now and not f.get("fired") for f in self.followups):
                asyncio.create_task(self._safe_followups())
        else:
            await self.run_due_followups()

    async def _safe(self, coro) -> None:
        try:
            await coro
        except Exception as ex:
            self._emit("error", {"text": f"watcher failed: {type(ex).__name__}: {ex}"})

    async def proactive_webhook(self, txn_id: str) -> Incident | None:
        """Kavach on duty: a payment the bank confirmed never reached the shop's billing app. Open the case itself."""
        t = self.world.txn_by_id(txn_id)
        if not t or any(i.facts.get("txn_id") == txn_id for i in self.incidents.values()):
            return None
        self._msg_ctx = {"channel": "merchant", "customer": {"name": t["payer_name"]}}
        try:
            inc = self.new_incident("payment_claim", f"Billing app missed ₹{t['amount']:,}")
        finally:
            self._msg_ctx = {}
        inc.facts["proactive"] = True
        async with self.locks[inc.id]:
            await self.planner.proactive_ledger(inc, t)
        self._emit("incident", {"incident": inc.summary()})
        return inc

    async def proactive_payout(self, batch_id: str) -> Incident | None:
        """Kavach on duty: the merchant's bank sent a payout back. Nobody has complained; she may not know yet."""
        b = next((s for s in self.world.settlements if s["batch_id"] == batch_id), None)
        if not b or any(i.facts.get("returned_batch") == batch_id for i in self.incidents.values()):
            return None
        live = self.open_incident("freeze")
        if live:        # a freeze case is already open: this bounce is more evidence for it, not a new case
            live.facts["returned_batch"] = batch_id
            async with self.locks[live.id]:
                await self.step(live, "followup", purpose=f"Payout {batch_id} ₹{b['amount']:,} returned by the bank", followup_id="watcher",
                                via="settlement-engine callback")
            return live
        self._msg_ctx = {"channel": "merchant", "customer": {}}
        try:
            inc = self.new_incident("settlement", f"Payout bounced · ₹{b['amount']:,}")
        finally:
            self._msg_ctx = {}
        inc.facts.update({"proactive": True, "returned_batch": batch_id})
        async with self.locks[inc.id]:
            await self.planner.proactive_payout(inc, b)
        self._emit("incident", {"incident": inc.summary()})
        return inc

    async def _safe_followups(self) -> None:
        try:
            await self.run_due_followups()
        except Exception as ex:  # never let a background follow-up die silently
            self._emit("error", {"text": f"follow-up failed: {type(ex).__name__}: {ex}"})

    def _wake_on_callback(self, ev: dict[str, Any]) -> None:
        """Status callbacks (switch / refund service / settlement run) wake the incident watching that record now,
        instead of waiting for its next scheduled poll. The poll stays as a backstop."""
        if ev.get("txn_ids"):
            for inc in self.incidents.values():
                if inc.status not in ("resolved", "refused") and inc.facts.get("txn_id") in ev["txn_ids"]:
                    for f in self.followups:
                        if f["incident"] == inc.id and not f.get("fired") and "payout" in f["purpose"]:
                            f["due"], f["via"] = self.world.now, "settlement-engine callback"
            return
        key, val = ("txn_id", ev.get("txn_id")) if ev.get("txn_id") else ("refund_id", ev.get("refund_id"))
        if not val:
            return
        for inc in self.incidents.values():
            if inc.status not in ("resolved", "refused") and inc.facts.get(key) == val:
                for f in self.followups:
                    if f["incident"] == inc.id and not f.get("fired"):
                        f["due"] = self.world.now
                        f["via"] = "switch callback" if key == "txn_id" else "refund-service callback"


def _redact(a: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in a.items() if k not in ("extra",)}


def planner_mode() -> str:
    """KAVACH_PLANNER=offline|sarvam|claude. Default: Sarvam if its key is set, else Claude if its key is set, else offline."""
    forced = os.environ.get("KAVACH_PLANNER", "").lower()
    if forced in ("offline", "sarvam", "claude"):
        return forced
    if os.environ.get("SARVAM_API_KEY"):
        return "sarvam"
    return "claude" if os.environ.get("ANTHROPIC_API_KEY") else "offline"
