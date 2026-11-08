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


def test_policy_unregistered_action_and_open_paths():
    w = World()
    d = policy.evaluate(w, "unregistered_custom_action", {}, {})
    assert d.verdict == "DENY" and d.rule == "P7"
    assert "not an action Kavach is permitted to take" in d.reason
    assert policy.evaluate(w, "escalate_to_human", {}, {}).verdict == "ALLOW"
    assert policy.evaluate(w, "create_support_case", {}, {}).verdict == "ALLOW"


def test_policy_constants_and_rules_registry():
    from datetime import timedelta
    assert policy.DUPLICATE_WINDOW == timedelta(minutes=10)
    assert policy.MAX_FOLLOWUPS == 8
    for code in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10",
                 "P11", "P12", "P13", "P14", "P15", "P16", "P17", "P18", "P19", "P20"):
        assert code in policy.RULES
        assert len(policy.RULES[code].strip()) > 10


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


def test_proof_unknown_token_and_fingerprint():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    res = proof.verify("nonexistent_demo_token", None, now)
    assert res["result"] == "UNKNOWN"
    fp = proof.fingerprint()
    assert isinstance(fp, str) and len(fp) == 64


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


def test_payout_watcher_catches_freeze_before_merchant_knows():
    """Total freeze lands today. Nobody tells Paytm or Kavach. The next 9:00 payout bounces and the watcher
    opens the case itself; the merchant's notice later joins the same case and over-hold facts are kept apart."""
    async def go():
        w = World(); e = Engine(w)
        r = w.inject_freeze(freeze_type="total", bounce_next=True)
        assert w.bank_signal()["last_return"] is None            # nothing visible to Paytm yet
        assert not e.incidents
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)
        inc = next(iter(e.incidents.values()))
        assert inc.facts.get("proactive") and inc.kind == "freeze"
        intake = steps(inc, "intake")[0]
        assert intake["sender"] == "monitor" and intake["engine"] == "payout-monitor"
        assert not any(s["kind"] == "intake" and s.get("sender") == "merchant" for s in inc.steps)
        warn = [s for s in steps(inc, "action") if s["action"] == "notify_merchant"][0]
        assert "NCRP" in warn["args"]["text"] and warn["args"].get("speak")
        assert inc.pending and set(inc.pending["approvers"]) == {"merchant", "paytm_ops"}
        assert not w.settlement_config["paused"]                   # nothing held until both keys turn
        await e.approve(inc.id, "merchant"); await e.approve(inc.id, "paytm_ops")
        assert w.settlement_config["paused"] and w.settlement_config["account"] == MERCHANT["settlement_bank"]
        same = await e.merchant_message("Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id=r["doc_id"])
        assert same.id == inc.id and "pack" in inc.facts
        assert inc.facts["locked_stated"] == 310000 and inc.money["amount"] == 2400
        assert len(e.incidents) == 1
        w.inject_live_payment(amount=640, webhook_fails=False)      # a normal sale today...
        await e.tick(86400)                                         # ...is held at the next payout, not bounced again
        assert w.settlements[-1]["status"] == "HELD" and len(e.incidents) == 1
    run(go())


def test_debit_freeze_stays_invisible_to_the_payout_watcher():
    async def go():
        w = World(); e = Engine(w)
        w.inject_freeze(freeze_type="debit", bounce_next=True)
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)
        assert w.settlements[-1]["status"] == "SETTLED" and not e.incidents   # honest limit: no signal, no case
    run(go())


def test_debit_freeze_caught_from_her_own_declined_payment():
    """Debit-only freeze: payouts still SETTLE, so the payout watcher is blind. Her own UPI payment through the
    Paytm app comes back YE, and the PSP watcher opens the case before she reports anything."""
    async def go():
        w = World(); e = Engine(w)
        w.inject_freeze(freeze_type="debit")
        assert w.bank_signal()["last_return"] is None
        p = w.merchant_pays(18000, "Gupta Traders")
        assert p["status"] == "DECLINED" and p["code"] == "YE"
        await e.tick(1)
        inc = next(iter(e.incidents.values()))
        assert inc.kind == "freeze" and inc.facts["proactive"] and steps(inc, "intake")[0]["engine"] == "psp-monitor"
        assert any(s["tool"] == "get_risk_signals" for s in steps(inc, "tool"))
        assert any(s["action"] == "notify_merchant" and "DEBIT FREEZE" in s["args"]["text"] for s in steps(inc, "action"))
        assert inc.pending and inc.pending["action"] == "request_settlement_hold"
        ok = World(); ok_e = Engine(ok)
        assert ok.merchant_pays(500, "Gupta Traders")["status"] == "SUCCESS"
        await ok_e.tick(1)
        assert not ok_e.incidents                                   # a healthy account raises nothing
    run(go())


def test_tipping_off_guard_withholds_case_details():
    async def go():
        w = World(); e = Engine(w)
        w.inject_freeze(freeze_type="total", bounce_next=True); w.inject_mule_signals()
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)
        inc = next(iter(e.incidents.values()))
        msgs = [s for s in steps(inc, "action") if s["action"] == "notify_merchant"]
        assert len(msgs) == 1 and msgs[0]["args"]["template"] == "legal_neutral"
        assert not policy.CASE_DETAIL.search(msgs[0]["args"]["text"])
        assert inc.status == "with_human" and not inc.pending and not w.settlement_config["paused"]
        assert any(s["action"] == "escalate_to_human" and "Risk" in s["args"]["queue"] for s in steps(inc, "action"))
        # backstop: even if a planner tries, the policy refuses case details under the guard
        d = policy.evaluate(w, "notify_merchant", {"text": "Aapka account freeze hai, police notice aaya"}, {})
        assert d.verdict == "DENY" and d.rule == "P17"
    run(go())


def test_lien_request_after_pack_needs_meena_and_matches_record():
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze()
        inc = await e.merchant_message("Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id=r["doc_id"])
        # nothing else is pending here, so the lien request is offered straight after the pack
        assert inc.pending and inc.pending["action"] == "draft_lien_request" and inc.pending["approvers"] == ["merchant"]
        assert "lien_request" not in inc.facts
        await e.approve(inc.id, "merchant")
        L = inc.facts["lien_request"]
        t = w.txn_by_id(inc.facts["disputed_txn"])
        assert L["disputed"] == t["amount"] == 2400 and t["utr"] in L["en"] and "my own figure" in L["en"]
        assert "proposed, not yet in force" in L["en"] and "Not legal advice" in L["en"]
        assert any(s["kind"] == "verify" and s["action"] == "draft_lien_request" and s["ok"] for s in inc.steps)
    run(go())


def test_paytm_nodal_upload_and_bank_desk():
    async def go():
        from fastapi.testclient import TestClient
        from app import main
        with TestClient(main.app) as c:
            w, e = main.W(), main.E()
            r = w.inject_freeze()
            inc = await e.merchant_message("Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id=r["doc_id"])
            pa = inc.facts["pa_upload"]
            tk = next(t for t in w.ops_queue if t["ticket_id"] == pa["ticket_id"])
            assert tk["status"] == "AWAITING_HUMAN" and pa["row"]["sop_para"] == "9.5(ii)"
            assert pa["row"]["reported_utr"] == w.txn_by_id(inc.facts["disputed_txn"])["utr"]
            await e.approve(inc.id, "merchant")                     # lien request
            d = c.get(f"/api/bankdesk/{inc.facts['pack']['token']}").json()
            st = {x["item"]: x["status"] for x in d["checklist"]}
            assert st["Disputed transaction identified"] == "signed" and st["CDD/EDD on the account holder"] == "bank"
            assert st["Hold scope requested by the account holder"] == "requested" and d["lien_request"]
    run(go())


def test_merchant_view_is_a_tracker_and_respects_the_guard():
    import json as _json
    from app import merchant_view as mv
    async def go():
        w = World(); e = Engine(w)
        assert mv.build(w, e)["mode"] == "home"
        r = w.inject_freeze(freeze_type="total", bounce_next=True)
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)
        v = mv.build(w, e)
        assert v["mode"] == "case" and v["action"]["kind"] == "approve"
        st = {s["key"]: s["state"] for s in v["steps"]}
        assert st["detect"] == "done" and st["protect"] == "now"
        inc = next(iter(e.incidents.values()))
        await e.approve(inc.id, "merchant"); await e.approve(inc.id, "paytm_ops")
        assert mv.build(w, e)["action"]["kind"] == "notice"
        await e.merchant_message("Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id=r["doc_id"])
        v = mv.build(w, e)
        assert v["ratio"] == 129 and {m["key"] for m in v["money"]} == {"locked", "disputed", "safe"}
        assert v["action"]["kind"] == "approve" and "2,400" in v["action"]["title"]
        await e.approve(inc.id, "merchant")
        v = mv.build(w, e)
        assert v["action"]["kind"] == "branch" and {d["kind"] for d in v["docs"]} == {"pack", "letter"}
        await e.merchant_message("Bank ne complaint le li, acknowledgement mil gaya.")
        v = mv.build(w, e)
        assert v["action"]["kind"] == "wait" and v["action"]["days_left"] == 7
        # guarded merchant: the whole screen is the neutral card
        g = World(); ge = Engine(g); g.inject_freeze(freeze_type="total", bounce_next=True); g.inject_mule_signals()
        await ge.tick((g.next_settlement - g.now).total_seconds() + 60)
        gv = mv.build(g, ge)
        assert gv["mode"] == "neutral" and not policy.CASE_DETAIL.search(_json.dumps(gv, ensure_ascii=False))
    run(go())


def test_chargeback_clock_reply_in_time_and_honest_accept():
    async def go():
        # yes: she handed over the goods -> reply with record-backed evidence before the deadline, then win
        w = World(); e = Engine(w); d = w.inject_chargeback()
        await e.tick(1)
        inc = next(iter(e.incidents.values()))
        assert inc.kind == "chargeback" and inc.pending["action"] == "submit_dispute_response" and inc.pending["approvers"] == ["merchant"]
        kinds = {x["kind"] for x in inc.facts["dispute_evidence"]}
        assert {"switch", "ledger"} <= kinds and all("deliver" not in x["label"].lower() for x in inc.facts["dispute_evidence"])
        await e.approve(inc.id, "merchant")
        assert d["status"] == "REPRESENTED" and d["response"]["merchant_attests_handover"]
        await e.tick(8 * 3600 + 5)
        assert d["status"] == "WON" and inc.status == "resolved"
        # no: she didn't -> accept, never a false reply
        w2 = World(); e2 = Engine(w2); d2 = w2.inject_chargeback()
        await e2.tick(1); inc2 = next(iter(e2.incidents.values()))
        await e2.approve(inc2.id, "merchant", yes=False)
        assert d2["status"] == "ACCEPTED" and d2["response"] is None and inc2.status == "resolved"
        # silence: past the deadline it is deemed valid and netted from the next payout
        w3 = World(); d3 = w3.inject_chargeback(hours=2)
        w3.advance(3 * 3600); assert d3["status"] == "DEEMED_VALID"
        w3.advance((w3.next_settlement - w3.now).total_seconds() + 60)
        assert d3.get("netted_in") and d3["dispute_id"] in w3.settlements[-1]["chargebacks_netted"]
        # P18: no invented evidence, no reply after the deadline
        w4 = World(); d4 = w4.inject_chargeback()
        bad = policy.evaluate(w4, "submit_dispute_response", {"dispute_id": d4["dispute_id"], "evidence": [{"kind": "soundbox", "claim": "goods delivered"}]}, {"approvals": {"merchant"}})
        assert bad.verdict == "DENY" and bad.rule == "P18"
        w4.advance(23 * 3600)
        late = policy.evaluate(w4, "submit_dispute_response", {"dispute_id": d4["dispute_id"], "evidence": []}, {"approvals": {"merchant"}})
        assert late.verdict == "DENY"
    run(go())


def test_merchant_view_surfaces_whatever_needs_meena():
    from app import merchant_view as mv
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze()
        inc = await e.merchant_message("Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id=r["doc_id"])
        await e.approve(inc.id, "merchant")                         # lien done; freeze now waits on the branch
        assert mv.build(w, e).get("case") is None
        w.inject_chargeback(); await e.tick(1)
        v = mv.build(w, e)
        assert v.get("case") == "chargeback" and v["action"]["kind"] == "approve"   # the question that needs her now
        cb = next(i for i in e.incidents.values() if i.kind == "chargeback")
        await e.approve(cb.id, "merchant")
        assert mv.build(w, e).get("case") is None                    # back to the freeze case, chargeback in the clocks row
        assert any(c["label"].startswith("Chargeback") for c in mv.build(w, e)["clocks"])
    run(go())


def test_chargeback_after_the_clock_moved_to_a_new_day():
    async def go():
        w = World(); e = Engine(w)
        w.inject_freeze(freeze_type="total", bounce_next=True)
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)   # next morning, no sales yet today
        d = w.inject_chargeback()
        assert d["amount"] > 0 and w.txn_by_id(d["txn_id"])["bill_id"]
        await e.tick(1)
        assert any(i.kind == "chargeback" for i in e.incidents.values())
    run(go())


def test_full_arc_detect_protect_prove_release():
    """Total freeze -> bounced payout caught -> two-key hold -> notice -> pack + lien request -> branch complaint ->
    (simulated) bank files via the bank desk -> (simulated) officer limits the hold -> ₹1 validation -> Risk releases."""
    async def go():
        w = World(); e = Engine(w)
        r = w.inject_freeze(freeze_type="total", bounce_next=True)
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)
        inc = next(iter(e.incidents.values()))
        await e.approve(inc.id, "merchant"); await e.approve(inc.id, "paytm_ops")
        await e.merchant_message("Bank ka SMS aur police ka notice yeh hai. Account mein 3.1 lakh atak gaye.", doc_id=r["doc_id"])
        await e.approve(inc.id, "merchant")                                   # lien request
        await e.merchant_message("Bank ne complaint le li, acknowledgement mil gaya.")
        held = sum(b["amount"] for b in w.settlements if b["status"] in ("HELD", "RETURNED"))
        assert held > 0
        # P19 backstop: no release before a decision
        assert policy.evaluate(w, "release_settlement_hold", {}, {"approvals": {"paytm_ops"}}).verdict == "DENY"
        for _ in range(13):
            await e.tick(86400)
        ev = inc.facts["case_events"]
        assert "bank_submission" in ev and "io_decision" in ev
        assert not any(s["kind"] == "action" and s["action"] == "draft_escalation" for s in inc.steps)   # bank filed in time: no escalation letter
        assert inc.facts["validation"]["status"] == "CREDITED"
        assert inc.pending and inc.pending["action"] == "release_settlement_hold" and inc.pending["approvers"] == ["paytm_ops"]
        await e.approve(inc.id, "paytm_ops")
        assert not w.settlement_config["paused"] and inc.facts["released"]["released"] == held
        assert not [b for b in w.settlements if b["status"] in ("HELD", "RETURNED")]
        assert inc.status == "watching" and "2,400" in inc.headline
    run(go())


def test_paytm_live_client_signs_like_paytm_and_maps_the_response():
    import json as _json, httpx
    from paytmchecksum import verifySignature
    from app import paytm_live
    os.environ.update({"PAYTM_MID": "TESTMID12345", "PAYTM_MERCHANT_KEY": "abcd1234EFGH5678", "PAYTM_ENV": "staging"})
    seen = {}

    def handler(req: httpx.Request):
        p = _json.loads(req.content)
        seen["url"] = str(req.url)
        seen["sig_ok"] = verifySignature(_json.dumps(p["body"]), "abcd1234EFGH5678", p["head"]["signature"])
        seen["body"] = p["body"]
        return httpx.Response(200, json={"head": {"signature": "x"}, "body": {"resultInfo": {"resultStatus": "TXN_SUCCESS", "resultCode": "01", "resultMsg": "Txn Success"},
            "txnId": "20261031111212800110168123456789", "bankTxnId": "777001234567", "orderId": "KVH-ORD-1", "txnAmount": "1.00",
            "txnDate": "2026-10-31 10:12:33.0", "paymentMode": "UPI", "mid": "TESTMID12345", "gatewayName": "PPBLC"}})
    try:
        r = run(paytm_live.order_status("KVH-ORD-1", transport=httpx.MockTransport(handler)))
        assert seen["url"] == "https://securestage.paytmpayments.com/v3/order/status"
        assert seen["sig_ok"] and seen["body"] == {"mid": "TESTMID12345", "orderId": "KVH-ORD-1"}
        assert r["status"] == "SUCCESS" and r["amount"] == 1 and r["bank_txn_id"] == "777001234567" and r["provenance"] == "PAYTM_STAGING"
    finally:
        for k in ("PAYTM_MID", "PAYTM_MERCHANT_KEY", "PAYTM_ENV"):
            os.environ.pop(k, None)


def test_live_check_flow_signs_only_what_paytm_said(monkeypatch):
    from app import paytm_live
    async def go(status):
        calls = []
        async def fake(order_id, transport=None):
            calls.append(order_id)
            return {"found": True, "status": status, "result_msg": "x", "order_id": order_id, "txn_id": "T1", "bank_txn_id": "B1", "amount": 1,
                    "amount_text": "1.00", "txn_date": "2026-10-31 10:12:33", "payment_mode": "UPI", "mid": "TESTMID", "provenance": "PAYTM_STAGING",
                    "fetched_at": "2026-10-31T10:12:40", "endpoint": "mock", "response_signed": True}
        monkeypatch.setattr(paytm_live, "configured", lambda: True)
        monkeypatch.setattr(paytm_live, "order_status", fake)
        w = World(); e = Engine(w)
        inc = await e.live_check("ORD-9")
        return w, inc, calls
    w, inc, calls = run(go("SUCCESS"))
    assert len(calls) == 2 and "pack" in inc.facts and inc.status == "resolved"                 # asked twice, then signed
    assert proof.verify(inc.facts["pack"]["token"], None, w.now, inc.id)["result"] == "VALID"
    w2, inc2, _ = run(go("PENDING"))
    assert "pack" not in inc2.facts and inc2.status == "with_human"
    assert policy.evaluate(w2, "issue_live_pack", {"order_id": "ORD-9"}, {}).verdict == "DENY"   # P20
    monkeypatch.setattr(paytm_live, "configured", lambda: False)
    async def nokeys():
        w3 = World(); e3 = Engine(w3); return await e3.live_check("ORD-1")
    inc3 = run(nokeys())
    assert "pack" not in inc3.facts and "not set" in inc3.headline


def test_english_by_default_hindi_on_request_no_hinglish():
    import re as _re
    from app import merchant_view as mv
    async def go():
        w = World(); e = Engine(w)
        w.inject_freeze(freeze_type="total", bounce_next=True)
        await e.tick((w.next_settlement - w.now).total_seconds() + 60)
        en, hi = mv.build(w, e), mv.build(w, e, "hi")
        assert en["shield"]["title"] == "Account frozen" and en["action"]["cta"] == "Yes, keep it safe"
        assert _re.search(r"[ऀ-ॿ]", hi["shield"]["title"]) and _re.search(r"[ऀ-ॿ]", hi["action"]["cta"])
        msgs = [m for m in e.chat if m["who"] == "kavach"]
        assert msgs and all(m.get("hi") and _re.search(r"[ऀ-ॿ]", m["hi"]) for m in msgs)
        hinglish = _re.compile(r"\b(aapke|aapka|dijiye|kijiye|bhejiye|surakshit|nahi|hai)\b", _re.I)
        assert not any(hinglish.search(m["text"]) for m in msgs)                 # English text is English
        assert not hinglish.search(str(en))
    run(go())


def test_ops_return_file_routes_by_reason_idempotent_and_scales():
    from app import ops
    text, meta = ops.sample_file(5000)
    seen = set()
    r = ops.triage(text, seen, meta["payouts"])
    s = r["summary"]
    assert s["opened"] == meta["returns"] and s["not_freezes"] > s["freezes"]          # most returns are NOT freezes
    meena = next(c for c in r["cases"] if c["merchant_id"] == "MEENAKIRANA0417")
    assert meena["route"] == "freeze" and meena["message_lang"] == "hi"
    for c in r["cases"]:
        if c["guarded"]:
            assert c["route"] == "risk_edd" and not policy.CASE_DETAIL.search(c["message"])    # P17 per merchant
        if c["route"] in ("dormant", "bank_details", "kyc_name"):
            assert not policy.CASE_DETAIL.search(c["message"])                            # no freeze scare for a closed or dormant account
    again = ops.triage(text, seen, meta["payouts"])
    assert again["summary"]["opened"] == 0 and again["summary"]["skipped_duplicates"] == meta["returns"]   # idempotent
    big, bmeta = ops.sample_file(1_000_000)
    br = ops.triage(big, set(), bmeta["payouts"])
    assert br["summary"]["opened"] == bmeta["returns"] == 15000 and br["summary"]["ms"] < 5000   # a crore-merchant day is a 15k-row job
    assert "error" in ops.triage("foo,bar\n1,2\n")


def test_ops_reads_a_messy_real_world_return_file():
    """Renamed headers, BOM, semicolons, rupee amounts, lowercase codes, sentences instead of codes, blank and broken rows."""
    from app import ops
    messy = ("\ufeff MID ; Shop Name ;Language; UTR ; Amt ; Reason Code ; Bank Remarks \n"
             "meena0417; Meena Kirana ;Hindi;UTR881; ₹4,580.00 ;r-frz;\n"
             "AB1234;Ramesh Dairy;english;UTR882;Rs. 1,240/-;;Account is DORMANT - KYC not updated\n"
             "CD5678;Asha Sweets;hi;UTR883;760;;A/c closed by customer\n"
             "EF9012;Imran Mobiles;en;UTR884;2150;;Beneficiary name mismatch\n"
             "GH3456;Pooja Medical;ta;UTR885;380;;Invalid IFSC code\n"
             "JK7890;Salim Hardware;en;UTR886;5600;;Debit freeze on account by LEA\n"
             ";;;;;;\n"
             ";Nameless;en;UTR887;900;R-CLS;\n"
             "LM1111;Odd Shop;en;UTR888;abc;;Technical error at beneficiary bank\n"
             "AB1234;Ramesh Dairy;english;utr882;1240;;dormant\n")
    r = ops.triage(messy, set())
    assert "error" not in r
    by = {c["merchant_id"]: c for c in r["cases"]}
    assert by["meena0417"]["route"] == "freeze" and by["meena0417"]["amount"] == 4580 and by["meena0417"]["message_lang"] == "hi"
    assert by["AB1234"]["route"] == "dormant" and by["AB1234"]["amount"] == 1240 and by["AB1234"]["read_from"] == "text"
    assert by["CD5678"]["route"] == "bank_details" and by["EF9012"]["route"] == "kyc_name" and by["GH3456"]["route"] == "bank_details"
    assert by["JK7890"]["route"] == "freeze"
    assert by["LM1111"]["route"] == "human"                                  # never guess: unknown words go to a person
    assert any(c["route"] == "human" and c["merchant_id"] == "—" for c in r["cases"])   # a row with no merchant ID is surfaced, not dropped
    s = r["summary"]
    assert s["blank_rows"] == 1 and s["skipped_duplicates"] == 1           # same UTR in a different case is still the same return
    assert "Couldn't find" in ops.triage("foo,bar\n1,2\n")["error"]
    tabbed = "merchant\treason\nZZ1\tAccount frozen\n"
    assert ops.triage(tabbed, set())["cases"][0]["route"] == "freeze"
