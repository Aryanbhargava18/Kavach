import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("KAVACH_PLANNER", "offline")
os.environ["SARVAM_API_KEY"] = ""          # never spend credits in tests
os.environ["N8N_WEBHOOK_URL"] = ""

from app import policy, proof, shots, sop  # noqa: E402
from app.agent import Engine  # noqa: E402
from app.understand import interpret  # noqa: E402
from app.world import MERCHANT, World  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def steps(inc, kind):
    return [s for s in inc.steps if s["kind"] == kind]


# ------------------------------------------------------------------ policy
def test_policy_blocks_pay_again_while_pending():
    w = World(); shot = w.inject_customer_claim(mode="pending")
    d = policy.evaluate(w, "request_payment", {"amount": 4200, "claimed_amount": 4200, "related_txn_ids": [shot["truth_txn_id"]]}, {})
    assert d.verdict == "DENY" and d.rule == "P1"


def test_policy_receipt_needs_switch_success_not_screenshot():
    w = World(); shot = w.inject_customer_claim(mode="pending")
    assert policy.evaluate(w, "issue_verified_receipt", {"txn_id": shot["truth_txn_id"]}, {}).verdict == "DENY"
    w.force_txn(shot["truth_txn_id"], "SUCCESS"); w.process()
    assert policy.evaluate(w, "issue_verified_receipt", {"txn_id": shot["truth_txn_id"]}, {}).verdict == "ALLOW"


def test_policy_refund_only_proven_duplicate_and_once():
    w = World(); d = w.inject_duplicate(amount=1180)
    ok = {"approvals": {"merchant"}}
    assert policy.evaluate(w, "initiate_refund", {"txn_id": d["txn_ids"][1], "amount": 1180}, ok).verdict == "ALLOW"
    w.create_refund(w.txn_by_id(d["txn_ids"][1]), 1180, "k")
    assert policy.evaluate(w, "initiate_refund", {"txn_id": d["txn_ids"][0], "amount": 1180}, ok).verdict == "DENY"
    w2 = World(); d2 = w2.inject_duplicate(amount=1180, genuine_duplicate=False)
    assert policy.evaluate(w2, "initiate_refund", {"txn_id": d2["txn_ids"][1], "amount": 1180}, ok).verdict == "DENY"


def test_policy_every_refund_needs_merchant():
    for amt in (150, 2450):
        w = World(); d = w.inject_duplicate(amount=amt)
        r = policy.evaluate(w, "initiate_refund", {"txn_id": d["txn_ids"][1], "amount": amt}, {"approvals": set()})
        assert r.verdict == "NEEDS_APPROVAL" and r.approvers == ["merchant"]


def test_asks_instead_of_guessing_between_two_payments():
    async def go():
        w = World(); e = Engine(w)
        a = w.inject_customer_claim(mode="pending", amount=500, payer="Aman")
        w.inject_customer_claim(mode="pending", amount=500, payer="Neha")
        inc = await e.merchant_message("customer bol raha hai 500 bhej diya")
        assert inc.status == "waiting_merchant" and "txn_id" not in inc.facts
        assert not [s for s in steps(inc, "tool") if s["tool"] == "get_payment_status"]
        await e.merchant_message(f"ref {a['utr'][-4:]}")
        assert inc.facts["txn_id"] == a["truth_txn_id"] and inc.status == "watching"
    run(go())


def test_debit_freeze_payouts_still_settle_and_hold_is_proposed():
    async def go():
        w = World(); e = Engine(w); w.inject_freeze()   # default: debit freeze
        assert w.bank_signal()["last_return"] is None and w.settlements[-1]["status"] == "SETTLED"
        inc = await e.merchant_message("Supplier ko payment fail ho gaya, bank bol raha hai account freeze hai")
        assert inc.kind == "freeze" and inc.pending and inc.pending["action"] == "request_settlement_hold"
    run(go())


def test_policy_no_reroute_during_freeze_and_human_only_filing():
    w = World(); w.inject_freeze(freeze_type="total")                       # visible to Paytm: payouts bounce
    assert policy.evaluate(w, "change_settlement_account", {"new_account": "x"}, {}).verdict == "DENY"
    w = World(); w.inject_freeze()                                          # debit freeze: invisible to Paytm...
    assert policy.evaluate(w, "change_settlement_account", {"new_account": "x"}, {}).verdict == "NEEDS_APPROVAL"
    assert policy.evaluate(w, "change_settlement_account", {"new_account": "x"}, {"freeze_reported": True}).verdict == "DENY"  # ...until reported
    assert policy.evaluate(w, "file_grievance", {}, {}).verdict == "DENY"
    assert policy.evaluate(w, "made_up_action", {}, {}).verdict == "DENY"


def test_policy_customer_messages_never_accuse_or_expose():
    w = World()
    assert policy.evaluate(w, "send_customer_update_simulated", {"text": "Your screenshot looks fake"}, {}).verdict == "DENY"
    assert policy.evaluate(w, "send_customer_update_simulated", {"text": "Paid to rahul42@okaxis"}, {}).verdict == "DENY"


def test_two_key_hold():
    w = World(); w.inject_freeze()
    assert policy.evaluate(w, "request_settlement_hold", {}, {"approvals": {"merchant"}}).approvers == ["paytm_ops"]
    assert policy.evaluate(w, "request_settlement_hold", {}, {"approvals": {"merchant", "paytm_ops"}}).verdict == "ALLOW"


# ------------------------------------------------------------------ OCR
def test_ocr_reads_edited_screenshot_as_shown():
    w = World(); shot = w.inject_customer_claim(mode="fake_amount", amount=4200)
    r = shots.extract(shots.render(shot))
    assert r["amount"] == 4200 and r["utr"] == shot["utr"]          # the image claims 4,200 ...
    assert w.txn_by_id(shot["truth_txn_id"])["amount"] == 2400      # ... the switch says 2,400


# ------------------------------------------------------------------ agent flows
def test_pending_flow_blocks_recollect_then_closes_itself():
    async def go():
        w = World(); e = Engine(w); shot = w.inject_customer_claim(mode="pending", resolve_after_s=100)
        inc = await e.merchant_message("Customer bol raha hai 4200 bhej diya", shot["shot_id"])
        assert inc.status == "watching"
        assert any(s["verdict"] == "DENY" and s["rule"] == "P1" for s in steps(inc, "policy"))
        for _ in range(6):
            await e.tick(30)
        assert inc.status == "resolved" and inc.outcome_verified
        receipts = [m for m in w.outbox if m["text"].startswith("Receipt:")]
        assert len(receipts) == 1
        assert not [s for s in steps(inc, "action") if s["action"] == "request_payment"]
        assert any(s.get("via") == "switch callback" for s in steps(inc, "followup"))
    run(go())


def test_edited_screenshot_withholds_goods_and_never_receipts():
    async def go():
        w = World(); e = Engine(w); shot = w.inject_customer_claim(mode="fake_amount", amount=4200)
        inc = await e.merchant_message("Customer bol raha hai 4200 bhej diya", shot["shot_id"])
        assert not [m for m in w.outbox if m["text"].startswith("Receipt:")]
        assert any("1,800" in m["text"] for m in w.outbox)
        assert inc.money["amount"] == 1800
    run(go())


def test_every_executed_action_is_verified():
    async def go():
        w = World(); e = Engine(w); d = w.inject_duplicate(amount=2450)
        inc = await e.merchant_message("ek customer ka 2450 do baar kat gaya")
        assert inc.pending and inc.pending["approvers"] == ["merchant"]
        await e.approve(inc.id, "merchant")
        for _ in range(6):
            await e.tick(30)
        for i, s in enumerate(inc.steps):
            if s["kind"] == "action" and s["action"] != "resolve_incident":
                v = next(x for x in inc.steps[i + 1:] if x["kind"] == "verify" and x["action"] == s["action"])
                assert v["ok"]
        assert inc.status == "resolved" and len(w.refunds) == 1 and w.refunds[0]["status"] == "SUCCESS"
    run(go())


def test_freeze_flow_pack_and_injection_ignored():
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze(freeze_type="total")
        inc = await e.merchant_message("Kal ka paisa bank mein nahi aaya")
        assert inc.kind == "freeze" and inc.pending and set(inc.pending["approvers"]) == {"merchant", "paytm_ops"}
        await e.approve(inc.id, "merchant"); await e.approve(inc.id, "paytm_ops")
        assert w.settlement_config["paused"] and w.settlement_config["account"] == MERCHANT["settlement_bank"]
        await e.merchant_message("Notice aaya", doc_id=r["doc_id"])
        assert "pack" in inc.facts
        assert [x["id"] for x in inc.facts["route"]] == ["PA-SETTLED-9.5.ii", "BANK-HOLD-10.1"]
        assert not any("cleared" in m["text"].lower() for m in w.outbox)
        await e.merchant_message("settlement doosre account mein bhej do")
        assert any(s["verdict"] == "DENY" and s["rule"] == "P6" for s in steps(inc, "policy"))
    run(go())


def test_freeze_conflict_refuses_pack():
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze(notice_amount=2900)
        inc = await e.merchant_message("Notice aaya, account freeze", doc_id=r["doc_id"])
        assert "pack" not in inc.facts
        assert any(s["verdict"] == "DENY" and s["rule"] == "P10" for s in steps(inc, "policy"))
    run(go())


# ------------------------------------------------------------------ proof
def test_proof_valid_then_tamper_detected():
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze()
        inc = await e.merchant_message("notice", doc_id=r["doc_id"])
        tok = inc.facts["pack"]["token"]
        assert proof.verify(tok, None, w.now)["result"] == "VALID"
        assert proof.verify(tok, proof.tampered_copy(tok), w.now)["result"] == "TAMPERED"
        assert proof.verify(tok, None, w.now, expected_case="KVH-0000")["result"] == "WRONG_CASE"
        from datetime import timedelta
        assert proof.verify(tok, None, w.now + timedelta(days=200))["result"] == "EXPIRED"
    run(go())


# ------------------------------------------------------------------ sop / nlu
def test_sop_unknown_without_system_record_and_clock_semantics():
    assert sop.route("amount_hold", "settled_to_merchant", None)["status"] == "UNKNOWN"
    c = sop.clocks({"hold_date": "2026-10-30"})
    assert c[0]["state"] == "needs_confirmation" and c[0]["due"] is None   # a message to Kavach never starts the 7-day clock


def test_interpreter_basics():
    assert interpret("मेरा खाता फ्रीज हो गया")["intent"] == "account_freeze"
    assert interpret("4 hazaar 200 bhej diya")["amount"] == 4200
    assert interpret("3.1 lakh atak gaye, account freeze")["amount"] == 310000


# ------------------------------------------------------------------ LLM planner path (scripted fake API)
def test_llm_planner_tools_are_policy_gated(monkeypatch):
    from app import llm
    async def go():
        w = World(); shot = w.inject_customer_claim(mode="pending")
        e = Engine(w)
        p = llm.LLMPlanner(e); e.planner = p
        txn = shot["truth_txn_id"]
        script = [
            [{"type": "tool_use", "id": "a", "name": "get_payment_status", "input": {"txn_id": txn}}],
            [{"type": "tool_use", "id": "b", "name": "request_payment", "input": {"amount": 4200, "related_txn_ids": [txn]}}],
            [{"type": "tool_use", "id": "c", "name": "issue_verified_receipt", "input": {"txn_id": txn}}],
            [{"type": "text", "text": "Waiting for the bank."}],
        ]
        async def fake(msgs):
            content = script.pop(0)
            return {"content": content, "stop_reason": "tool_use" if content[0]["type"] == "tool_use" else "end_turn"}
        monkeypatch.setattr(p, "_messages", fake)
        inc = await e.merchant_message("customer ne 4200 bheja", shot["shot_id"])
        denials = [s for s in steps(inc, "policy") if s["verdict"] == "DENY"]
        assert {d["rule"] for d in denials} == {"P1", "P2"}     # the model tried both; policy stopped both
        assert not [m for m in w.outbox if m["text"].startswith("Receipt:")]
    run(go())


def test_llm_failure_falls_back_to_offline(monkeypatch):
    from app import llm
    async def go():
        w = World(); shot = w.inject_customer_claim(mode="success_missed")
        e = Engine(w); p = llm.LLMPlanner(e); e.planner = p
        async def boom(msgs):
            raise ConnectionError("offline venue wifi")
        monkeypatch.setattr(p, "_messages", boom)
        inc = await e.merchant_message("customer ne 4200 bheja", shot["shot_id"])
        assert inc.status == "watching" and inc.planner == "offline (fallback)" and inc.recon["ledger"].get("repaired")
    run(go())


# ------------------------------------------------------------------ the directive's hero + judge challenges
def _claim(mode, **kw):
    w = World(); e = Engine(w)
    shot = w.inject_customer_claim(mode=mode, **kw)
    inc = run(e.customer_message("I paid ₹4,200, but the shop says they haven't received it.", shot["shot_id"], shot.get("customer")))
    return w, e, shot, inc


def _settle(w, e, inc):
    for _ in range(4):
        run(e.tick(60))
    if inc.status == "watching":
        run(e.tick((w.next_settlement - w.now).total_seconds() + 600))
        for _ in range(3):
            run(e.tick(60))


def test_hero_ledger_repaired_verified_and_closed_only_after_payout():
    w, e, shot, inc = _claim("success_missed")
    assert inc.channel == "whatsapp"
    names = [s["tool"] for s in steps(inc, "tool")]
    assert names[:2] == ["get_incident_policy", "read_screenshot"] or "create_support_case" in [s["action"] for s in steps(inc, "action")]
    assert {"lookup_transaction", "get_merchant_ledger", "get_refund_status", "get_settlement_status"} <= set(names)
    assert inc.recon["ledger"].get("repaired") and inc.recon["ledger"]["status"].startswith("PAID")
    bill = next(b for b in w.bills if b["bill_id"] == inc.facts["bill_id"])
    assert bill["status"] == "PAID"
    assert sum(1 for x in w.ledger if x["utr"] == inc.recon["switch"]["ref"]) == 1          # exactly one entry
    assert inc.status == "watching"                                                          # not closed yet
    _settle(w, e, inc)
    assert inc.status == "resolved" and inc.outcome_verified
    assert any(s.get("via") == "settlement-engine callback" for s in steps(inc, "followup"))


def test_reconcile_is_idempotent_and_needs_switch_success():
    w = World(); shot = w.inject_customer_claim(mode="success_missed")
    t = w.txn_by_id(shot["truth_txn_id"]); bill = shot["bill_id"]
    assert policy.evaluate(w, "reconcile_payment", {"utr": t["utr"], "bill_id": bill}, {}).verdict == "ALLOW"
    w.reconcile(t, bill)
    d = policy.evaluate(w, "reconcile_payment", {"utr": t["utr"], "bill_id": bill}, {})
    assert d.verdict == "DENY" and d.rule == "P15"
    w2 = World(); s2 = w2.inject_customer_claim(mode="pending")
    t2 = w2.txn_by_id(s2["truth_txn_id"])
    assert policy.evaluate(w2, "reconcile_payment", {"utr": t2["utr"], "bill_id": s2["bill_id"]}, {}).verdict == "DENY"


def test_refund_initiated_is_not_counted_as_paid():
    w, e, shot, inc = _claim("refund_initiated")
    denies = [s for s in steps(inc, "policy") if s["verdict"] == "DENY"]
    assert any(s["action"] == "reconcile_payment" and s["rule"] == "P14" for s in denies)
    assert not any(s["action"] == "issue_verified_receipt" for s in steps(inc, "action"))
    assert any(s["action"] == "request_payment" for s in steps(inc, "action"))
    assert next(b for b in w.bills if b["bill_id"] == shot["bill_id"])["status"] != "PAID"


def test_replayed_utr_is_refused_by_ledger():
    w, e, shot, inc = _claim("replay")
    assert "USED ON" in inc.recon["ledger"]["status"]
    assert any(s["action"] == "reconcile_payment" and s["rule"] == "P15" for s in steps(inc, "policy") if s["verdict"] == "DENY") \
        or not any(s["action"] == "reconcile_payment" for s in steps(inc, "action"))
    assert not any(s["action"] == "issue_verified_receipt" for s in steps(inc, "action"))
    assert next(b for b in w.bills if b["bill_id"] == shot["bill_id"])["status"] != "PAID"


def test_fake_amount_and_no_such_txn_never_receipt():
    for mode in ("fake_amount", "fake_utr", "failed_debited"):
        w, e, shot, inc = _claim(mode)
        assert not any(s["action"] in ("issue_verified_receipt", "reconcile_payment") for s in steps(inc, "action")), mode
        msgs = [m["text"] for m in w.outbox if m["to"] == "customer"]
        assert msgs and not any(word in " ".join(msgs).lower() for word in ("fake", "fraud", "forged")), mode


def test_customer_followup_routes_to_open_incident():
    w, e, shot, inc = _claim("pending")
    n = len(e.incidents)
    run(e.customer_message("Any update on my payment?", None, shot.get("customer")))
    assert len(e.incidents) == n and steps(inc, "intake")[-1]["sender"] == "customer"


def test_tool_steps_are_timed_and_announced():
    w = World(); e = Engine(w); seen = []
    e.bus.subscribe = getattr(e.bus, "subscribe", None)
    orig = e._emit
    e._emit = lambda kind, payload: (seen.append(kind), orig(kind, payload))
    shot = w.inject_customer_claim(mode="success_missed")
    inc = run(e.customer_message("I paid", shot["shot_id"], shot.get("customer")))
    assert seen.count("tool_start") == len(steps(inc, "tool"))
    assert all("ms" in s for s in steps(inc, "tool"))


def test_proactive_watcher_fixes_before_anyone_complains():
    w = World(); e = Engine(w)
    r = w.inject_live_payment(amount=4200, payer="Rahul")
    assert not e.incidents                                   # nothing yet: retries still running
    for _ in range(12):
        run(e.tick(1))
    assert len(e.incidents) == 1
    inc = next(iter(e.incidents.values()))
    assert inc.facts.get("proactive") and steps(inc, "intake")[0]["sender"] == "monitor"
    assert inc.recon["ledger"].get("repaired")
    assert next(b for b in w.bills if b["bill_id"] == r["bill_id"])["status"] == "PAID"
    assert not [m for m in w.outbox if m["to"] == "customer"]   # nobody complained, so nobody is messaged
    assert any(s["action"] == "notify_merchant" and s["args"].get("speak") for s in steps(inc, "action"))
    for _ in range(5):
        run(e.tick(1))
    assert len(e.incidents) == 1                             # the same failure is never picked up twice
    run(e.tick((w.next_settlement - w.now).total_seconds() + 600))
    for _ in range(3):
        run(e.tick(30))
    assert inc.status == "resolved" and inc.outcome_verified


def test_watcher_ignores_failures_from_before_it_was_on_duty():
    w = World(); e = Engine(w)
    w.inject_customer_claim(mode="success_missed")
    for _ in range(30):
        run(e.tick(1))
    assert not e.incidents
