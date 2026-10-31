import asyncio
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("KAVACH_PLANNER", "offline")
os.environ["SARVAM_API_KEY"] = ""          # never spend credits in tests
os.environ["N8N_WEBHOOK_URL"] = ""

import pytest  # noqa: E402

from app import desk, sarvam, sop_kb, tools  # noqa: E402
from app.agent import Engine  # noqa: E402
from app.world import World  # noqa: E402


def run(c):
    return asyncio.run(c)


# ---------------------------------------------------------------- Paytm Risk desk
def test_desk_never_escalates_genuine_and_never_reads_truth():
    esc_genuine, mules, mules_esc = 0, 0, 0
    for seed in range(1, 31):
        f = desk.make_feed(seed)
        truth = {m["mid"]: m.pop("_truth") for m in f["merchants"]}      # Kavach must decide without it
        for m in f["merchants"]:
            r = desk.assess(m, f)
            if truth[m["mid"]] in ("genuine", "genuine_outlier") and r["outcome"] == "Escalate for EDD":
                esc_genuine += 1
            if truth[m["mid"]] == "mule_front":
                mules += 1; mules_esc += r["outcome"] == "Escalate for EDD"
    assert esc_genuine == 0
    assert mules_esc / mules > 0.85


def test_single_signal_is_never_enough():
    f = desk.make_feed(3)
    for m in f["merchants"]:
        r = desk.assess(m, f)
        if r["outcome"] == "Escalate for EDD":
            assert len(r["strong_hits"]) >= 2


# ---------------------------------------------------------------- approvals are per action
def test_approval_for_one_action_does_not_carry_to_another():
    os.environ["KAVACH_SIMULATE_AUTHORITIES"] = "0"     # the bank misses its deadline here: test the escalation path
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze()
        inc = await e.merchant_message("Supplier ko payment fail ho gaya, bank bol raha account freeze hai")
        await e.approve(inc.id, "merchant"); await e.approve(inc.id, "paytm_ops")
        await e.merchant_message("notice", doc_id=r["doc_id"])
        await e.merchant_message("Bank ne complaint le li, acknowledgement mil gaya")
        for _ in range(8):
            await e.tick(86400)
        assert inc.pending and inc.pending["action"] == "draft_escalation" and inc.pending["approvers"] == ["merchant"]
        assert "escalation_letter" not in inc.facts
    run(go())


def test_clock_starts_only_from_a_dated_event_and_fires_reminders():
    os.environ["KAVACH_SIMULATE_AUTHORITIES"] = "0"     # the bank misses its deadline here: test the escalation path
    async def go():
        w = World(); e = Engine(w); r = w.inject_freeze()
        inc = await e.merchant_message("account freeze ho gaya")
        await e.approve(inc.id, "merchant"); await e.approve(inc.id, "paytm_ops")
        await e.merchant_message("notice", doc_id=r["doc_id"])
        assert "clocks" not in inc.facts                       # no clock from messages alone
        await e.merchant_message("Bank ne complaint le li, acknowledgement mil gaya")
        c = inc.facts["clocks"][0]
        assert c["state"] == "running" and c["start"] == w.now.date().isoformat()
        await e.tick(5 * 86400 + 10)
        assert any("2 din bache" in m["text"] for m in w.outbox)
    run(go())


# ---------------------------------------------------------------- Ask the SOP
def teardown_function(_fn):
    os.environ.pop("KAVACH_SIMULATE_AUTHORITIES", None)


def test_sop_answer_is_cited_and_unknown_citations_are_stripped():
    r = run(sop_kb.ask("bank ko kitne din mein bhejna hota hai"))
    assert r["citations"] and r["citations"][0]["id"] == "10.1(a)"
    txt, bad = sop_kb.check_citations("Bank has 7 days [10.1(a)] and a court said so [99.9]", sop_kb.retrieve_local("bank days"))
    assert bad == ["99.9"] and "[99.9]" not in txt


# ---------------------------------------------------------------- two readers
def test_second_reader_disagreement_is_reported(monkeypatch):
    monkeypatch.setattr(sarvam, "available", lambda: True)

    async def fake_read(png, kind):
        return {"amount": 9999, "utr": None, "payee_vpa": None, "engine": "fake vision"}
    monkeypatch.setattr(sarvam, "read_image", fake_read)
    w = World(); shot = w.inject_customer_claim(mode="pending")
    r, summary = run(tools.run_read_async(w, "read_screenshot", {"shot_id": shot["shot_id"]}))
    assert r["readers_disagree"] == ["amount"] and "disagree" in summary


# ---------------------------------------------------------------- Sarvam planner path
def test_sarvam_planner_is_policy_gated(monkeypatch):
    from app import llm
    w = World(); shot = w.inject_customer_claim(mode="pending")
    txn = shot["truth_txn_id"]
    script = [
        {"content": None, "tool_calls": [{"id": "1", "type": "function", "function": {"name": "get_payment_status", "arguments": f'{{"txn_id": "{txn}"}}'}}]},
        {"content": None, "tool_calls": [{"id": "2", "type": "function", "function": {"name": "request_payment", "arguments": f'{{"amount": 4200, "related_txn_ids": ["{txn}"]}}'}}]},
        {"content": "Payment pending; watching.", "tool_calls": None},
    ]

    async def fake_chat(messages, tools_=None, **kw):
        return {"choices": [{"message": script.pop(0)}]}
    monkeypatch.setattr(sarvam, "chat", fake_chat)
    e = Engine(w); e.planner = llm.LLMPlanner(e, provider="sarvam")
    inc = run(e.merchant_message("customer ne 4200 bheja", shot["shot_id"]))
    assert any(s["kind"] == "policy" and s["verdict"] == "DENY" and s["rule"] == "P1" for s in inc.steps)
    assert inc.planner == "sarvam"


# ---------------------------------------------------------------- uploads + endpoints
def test_upload_real_image_then_read_it():
    from fastapi.testclient import TestClient
    from app import shots
    from app.main import app
    with TestClient(app) as c:
        w = World(); shot = w.inject_customer_claim(mode="fake_utr")
        png = shots.render(shot)
        r = c.post("/api/upload", data={"kind": "screenshot"}, files={"file": ("shot.png", io.BytesIO(png), "image/png")})
        assert r.status_code == 200 and r.json()["shot_id"]
        assert c.post("/api/voice", files={"file": ("v.webm", b"x", "audio/webm")}).status_code in (503, 502)
        assert c.get("/api/integrations").json()["ocr"] in (True, False)
        d = c.get("/api/desk").json()
        assert len(d["rows"]) == 10 and all("_truth" not in r for r in d["rows"])
