"""Kavach server: API, live event stream, verifier pages."""
from __future__ import annotations

import asyncio
import html
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import proof, sarvam, shots
from .agent import Engine, planner_mode
from .bus import Bus
from .world import World

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).parent / "static"
PUBLIC_URL = os.environ.get("KAVACH_PUBLIC_URL", "http://127.0.0.1:8000")
PACE = float(os.environ.get("KAVACH_PACE", "0.55"))
CLOCK_SPEED = float(os.environ.get("KAVACH_CLOCK_SPEED", "1"))

bus = Bus()
state: dict[str, Any] = {}


def fresh() -> None:
    if state.get("engine"):
        state["engine"].alive = False
    state["world"] = World()
    state["engine"] = Engine(state["world"], bus, pace=PACE, base_url=PUBLIC_URL)
    state["drafts"] = []
    from . import automation, desk
    automation.reset()
    state["desk"] = desk.make_feed(int(os.environ.get("KAVACH_DESK_SEED", "11")))
    state["desk_results"] = {}
    state["desk_assigned"] = set()
    bus.publish({"type": "reset"})


async def ticker() -> None:
    while True:
        await asyncio.sleep(1)
        try:
            await state["engine"].tick(1 * CLOCK_SPEED, background=True)
        except Exception as ex:  # keep the clock alive no matter what
            bus.publish({"type": "error", "text": f"tick: {ex}"})


@asynccontextmanager
async def lifespan(_app):
    fresh()
    proof.fingerprint()
    task = asyncio.create_task(ticker())
    yield
    task.cancel()


app = FastAPI(title="Kavach — payment incident autopilot (synthetic demo)", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def W() -> World:
    return state["world"]


def E() -> Engine:
    return state["engine"]


def run_bg(coro) -> None:
    async def wrap():
        try:
            await coro
        except Exception as ex:
            import traceback
            traceback.print_exc()
            bus.publish({"type": "error", "text": f"{type(ex).__name__}: {ex}"})
    asyncio.create_task(wrap())


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/state")
def api_state():
    e = E()
    return {"world": W().snapshot(), "incidents": [i.summary() for i in e.incidents.values()], "followups": _followups(),
            "steps": [s for i in e.incidents.values() for s in i.steps], "chat": e.chat, "drafts": state["drafts"],
            "planner": {"mode": e.planner.label, "label": e.planner.label_long}, "ocr": shots.ocr_available(),
            "fingerprint": proof.fingerprint(), "pace": PACE}


def _followups() -> list[dict[str, Any]]:
    return [{"incident": f["incident"], "id": f["id"], "due": f["due"].isoformat(), "purpose": f["purpose"], "fired": bool(f.get("fired")), "cancelled": f.get("cancelled")}
            for f in E().followups]


@app.get("/api/followups")
def followups():
    return _followups()


@app.post("/api/clock/skip-to-payout")
async def skip_to_payout():
    secs = (W().next_settlement - W().now).total_seconds() + 330
    await E().tick(secs, background=True)
    bus.publish({"type": "world", "world": W().snapshot()})
    return {"now": W().now.isoformat()}


@app.get("/api/integrations")
def integrations():
    from . import automation, sop_kb
    return {"planner": planner_mode(), "sarvam": sarvam.available(), "ocr": shots.ocr_available(),
            "n8n": automation.n8n_configured(), "cognee": sop_kb.cognee_configured(),
            "models": {"chat": sarvam.CHAT_MODEL, "stt": sarvam.STT_MODEL, "tts": sarvam.TTS_MODEL}}


@app.post("/api/voice")
async def voice(file: UploadFile = File(...), language: str = "unknown"):
    """Meena's voice note -> Sarvam Saaras transcript. The browser falls back to its own recogniser without a key."""
    if not sarvam.available():
        raise HTTPException(503, "SARVAM_API_KEY not set")
    audio = await file.read()
    if len(audio) > 6 * 1024 * 1024:
        raise HTTPException(413, "voice note too long")
    try:
        return await sarvam.stt(audio, file.filename or "voice.webm", file.content_type or "audio/webm", language)
    except Exception as ex:
        raise HTTPException(502, f"Sarvam STT failed: {type(ex).__name__}")


@app.get("/api/tts")
async def tts(text: str, voice: str = "kavach", lang: str = "hi-IN"):
    if not sarvam.available():
        raise HTTPException(503, "SARVAM_API_KEY not set")
    try:
        wav = await sarvam.tts(text[:600], lang, sarvam.SOUNDBOX_SPEAKER if voice == "soundbox" else sarvam.TTS_SPEAKER)
    except Exception as ex:
        raise HTTPException(502, f"Sarvam TTS failed: {type(ex).__name__}")
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "max-age=86400"})


@app.post("/api/upload")
async def upload(kind: str = Form(...), file: UploadFile = File(...)):
    """Upload any real image: a customer's screenshot, or a bank SMS / police notice photo."""
    if kind not in ("screenshot", "notice"):
        raise HTTPException(400, "kind must be screenshot or notice")
    raw = await file.read()
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "image too large")
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im.thumbnail((1600, 2400))
        buf = io.BytesIO(); im.save(buf, "PNG"); png = buf.getvalue()
    except Exception:
        raise HTTPException(400, "not an image")
    rec = W().add_upload(kind, png, file.filename or "upload")
    draft = ({"text": "Customer ne yeh screenshot dikhaya, check karo.", "shot_id": rec["shot_id"]} if kind == "screenshot"
             else {"text": "Yeh notice aaya hai, dekho.", "doc_id": rec["doc_id"]})
    state["drafts"] = [draft]
    return draft


@app.get("/api/stream")
async def stream(request: Request):
    q = bus.subscribe()

    async def gen():
        try:
            yield "retry: 1500\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(ev, default=str, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(q)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


class Msg(BaseModel):
    text: str
    shot_id: str | None = None
    doc_id: str | None = None


@app.post("/api/merchant/message")
async def merchant_message(m: Msg):
    if not m.text.strip():
        raise HTTPException(400, "empty")
    state["drafts"] = []
    run_bg(E().merchant_message(m.text.strip(), m.shot_id, m.doc_id))
    return {"ok": True}


class Approval(BaseModel):
    incident_id: str
    approver: str
    yes: bool = True


@app.post("/api/approve")
async def approve(a: Approval):
    if a.incident_id not in E().incidents:
        raise HTTPException(404)
    run_bg(E().approve(a.incident_id, a.approver, a.yes))
    return {"ok": True}


class Scenario(BaseModel):
    amount: int | None = None
    shown_amount: int | None = None
    mode: str | None = None
    notice_amount: int | None = None
    paytm_record: bool = True
    genuine: bool = True
    freeze_type: str = "debit"
    mule: bool = False


CUSTOMER_LINES = {
    "success_missed": ("Rahul", "I paid ₹4,200, but the shop says they haven't received it."),
    "fake_amount": ("Priya", "Paid ₹4,200 for my groceries, shop is saying payment not received. Screenshot attached."),
    "pending": ("Imran", "Bhaiya maine ₹4,200 bhej diya, paisa kat gaya hai, shop wale bol rahe nahi aaya"),
    "pending_fail": ("Imran", "Bhaiya maine ₹4,200 bhej diya, paisa kat gaya hai, shop wale bol rahe nahi aaya"),
    "fake_utr": ("Deepak", "I paid ₹4,200 at Meena Kirana just now. Here is the screenshot."),
    "refund_initiated": ("Farah", "I paid ₹4,200 but the shop says it didn't come. Please check."),
    "replay": ("Vikas", "Payment done ₹4,200, see screenshot. Shop is not giving the items."),
    "failed_debited": ("Kavita", "₹4,200 deducted from my account but the shop says not received!"),
    "failed": ("Kavita", "I paid ₹4,200, shop says not received."),
    "wrong_merchant": ("Sanjay", "Paid ₹4,200 to Meena Kirana, they say not received."),
    "success_missed_counter": ("Rahul", ""),
}


@app.post("/api/customer/message")
async def customer_message(m: Msg):
    if not m.text.strip():
        raise HTTPException(400, "empty")
    shot = W().screenshots.get(m.shot_id or "") or {}
    run_bg(E().customer_message(m.text.strip(), m.shot_id, shot.get("customer") or {"name": "Customer", "wa": "+91 9•••• ••••"}))
    return {"ok": True}


@app.post("/api/scenario/{name}")
async def scenario(name: str, s: Scenario):
    """Judge controls. Each changes the WORLD (what really happened), then the complaint arrives the way it
    would in real life. Kavach has to find out the rest on its own."""
    w = W()
    if name == "customer_claim":
        mode = s.mode or "success_missed"
        who, line = CUSTOMER_LINES.get(mode, ("Rahul", "I paid ₹4,200 but the shop says not received."))
        shot = w.inject_customer_claim(amount=s.amount or 4200, mode=mode, payer=who, shown_amount=s.shown_amount)
        await asyncio.sleep(0.4)
        run_bg(E().customer_message(line.replace("₹4,200", f"₹{shot['amount']:,}"), shot["shot_id"], shot["customer"]))
        bus.publish({"type": "world", "world": w.snapshot()})
        return {"ok": True, "shot_id": shot["shot_id"], "customer": shot["customer"]}
    if name == "live_payment":
        r = w.inject_live_payment(amount=s.amount or 4200, payer="Rahul")
        bus.publish({"type": "world_event", "event": r["event"]})
        bus.publish({"type": "world", "world": w.snapshot()})
        return {"ok": True, **{k: v for k, v in r.items() if k != "event"}}
    if name == "counter_claim":
        shot = w.inject_customer_claim(amount=s.amount or 4200, mode=s.mode or "pending")
        draft = {"text": f"Customer bol raha hai ₹{shot['amount']:,} bhej diya, par Soundbox nahi bola. Screenshot dikha raha hai.", "shot_id": shot["shot_id"]}
    elif name == "duplicate":
        d = w.inject_duplicate(amount=s.amount or 2450, genuine_duplicate=s.genuine)
        cust = {"name": "Sunita", "wa": "+91 98•• ••418"}
        run_bg(E().customer_message(f"I was charged twice for ₹{d['amount']:,} at Meena Kirana. Please refund one.", None, cust))
        return {"ok": True}
    elif name == "supplier_declined":
        # Debit-only freeze: credits still land, so payouts tell Paytm nothing. Meena pays her supplier through the Paytm app;
        # her bank declines it with YE. Kavach's PSP watcher has to notice on its own.
        r = w.inject_freeze(notice_amount=s.notice_amount, paytm_record=s.paytm_record, freeze_type="debit")
        if s.mule:
            w.inject_mule_signals()
        w.merchant_pays(s.amount or 18000, "Gupta Traders")
        draft = {"text": "", "next_doc": None if s.mule else r["doc_id"]}
        state["drafts"] = [draft]
        bus.publish({"type": "world", "world": w.snapshot()})
        return draft
    elif name == "payout_bounce":
        # The bank freezes Meena's account (debit AND credit) today. Nobody tells Paytm. Skip to the next 9:00 payout run:
        # the bank sends it back, and Kavach's settlement watcher has to notice on its own.
        r = w.inject_freeze(notice_amount=s.notice_amount, paytm_record=s.paytm_record, freeze_type="total", bounce_next=True)
        if s.mule:
            w.inject_mule_signals()
        secs = (w.next_settlement - w.now).total_seconds() + 60
        await E().tick(secs, background=True)
        draft = {"text": "", "next_doc": None if s.mule else r["doc_id"]}
        state["drafts"] = [draft]
        bus.publish({"type": "draft", "draft": draft})
        bus.publish({"type": "world", "world": w.snapshot()})
        return draft
    elif name == "freeze":
        r = w.inject_freeze(notice_amount=s.notice_amount, paytm_record=s.paytm_record, freeze_type=s.freeze_type)
        draft = ({"text": "Kal ka paisa bank mein nahi aaya. Kya hua?", "next_doc": r["doc_id"]} if s.freeze_type == "total" else
                 {"text": "Supplier ko payment fail ho gaya. Bank bol raha hai account freeze hai, 3.1 lakh atak gaye.", "next_doc": r["doc_id"]})
    else:
        raise HTTPException(404, "unknown scenario")
    state["drafts"] = [draft]
    bus.publish({"type": "draft", "draft": draft})
    bus.publish({"type": "world", "world": w.snapshot()})
    return draft


class Edit(BaseModel):
    amount: int


@app.post("/api/shot/{shot_id}/edit")
def edit_shot(shot_id: str, e: Edit):
    shot = W().edit_screenshot(shot_id, e.amount)
    if not shot:
        raise HTTPException(404)
    draft = {"text": f"I paid ₹{e.amount:,}. Screenshot attached.", "shot_id": shot["shot_id"], "as": "customer"}
    state["drafts"] = [draft]
    bus.publish({"type": "draft", "draft": draft})
    return draft


@app.get("/api/shot/{shot_id}.png")
def shot_png(shot_id: str):
    shot = W().screenshots.get(shot_id)
    if not shot:
        raise HTTPException(404)
    return Response(shots.screenshot_png(shot), media_type="image/png")


@app.get("/api/doc/{doc_id}.png")
def doc_png(doc_id: str):
    d = W().documents.get(doc_id)
    if not d or not d.get("png"):
        raise HTTPException(404)
    return Response(d["png"], media_type="image/png")


@app.get("/api/qr")
def qr(data: str):
    import io, qrcode
    if not data.startswith("upi://pay?") or len(data) > 300:
        raise HTTPException(400, "only UPI payment URIs")
    buf = io.BytesIO(); qrcode.make(data, box_size=6, border=2).save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png")


@app.get("/api/doc/{doc_id}")
def doc(doc_id: str):
    d = W().documents.get(doc_id)
    if not d:
        raise HTTPException(404)
    return {"doc_id": doc_id, "text": d["text"], "sms": d["sms"]}


class Adv(BaseModel):
    seconds: int = 60


@app.post("/api/clock/advance")
async def advance(a: Adv):
    await E().tick(a.seconds, background=True)
    bus.publish({"type": "world", "world": W().snapshot()})
    return {"now": W().now.isoformat()}


class Force(BaseModel):
    txn_id: str
    status: str


@app.post("/api/world/force")
def force(f: Force):
    t = W().force_txn(f.txn_id, f.status.upper())
    if not t:
        raise HTTPException(400, "not a pending transaction")
    return {"ok": True, "note": "Resolves on the next clock tick (≤1 s)."}


@app.post("/api/reset")
def reset():
    fresh()
    return {"ok": True}


@app.get("/api/world")
def world():
    return W().snapshot()


# ------------------------------------------------------------ Paytm Risk / PA desk
def _desk_view() -> dict[str, Any]:
    from . import desk
    feed = state["desk"]
    pack = next((i.facts["pack"] for i in E().incidents.values() if i.facts.get("pack")), None)
    rows = []
    for m in feed["merchants"]:
        r = state["desk_results"].get(m["mid"])
        row = desk.public(m) | {"result": r, "assigned": m["mid"] in state["desk_assigned"]}
        if m["mid"] == "MEENAKIRANA0417" and pack:
            row["pack"] = {"token": pack["token"], "verify": proof.verify(pack["token"], None, W().now)["result"]}
        rows.append(row)
    done = list(state["desk_results"].values())
    return {"rows": rows, "running": state.get("desk_running", False),
            "summary": {o: sum(1 for x in done if x["outcome"] == o) for o in ("Consistent", "Insufficient", "Escalate for EDD")}}


@app.get("/api/desk")
def desk_get():
    return _desk_view()


@app.post("/api/desk/run")
async def desk_run():
    from . import desk
    if state.get("desk_running"):
        return {"ok": False, "error": "already running"}
    state["desk_running"] = True
    state["desk_results"] = {}

    async def go():
        feed = state["desk"]
        try:
            for m in feed["merchants"]:
                bus.publish({"type": "desk", "phase": "checking", "mid": m["mid"]})
                r = desk.assess(m, feed)
                for sig in r["signals"]:
                    bus.publish({"type": "desk", "phase": "signal", "mid": m["mid"], "signal": sig})
                    await asyncio.sleep(PACE * 0.35)
                state["desk_results"][m["mid"]] = r
                bus.publish({"type": "desk", "phase": "done", "mid": m["mid"], "result": r})
                await asyncio.sleep(PACE * 0.6)
        finally:
            state["desk_running"] = False
            bus.publish({"type": "desk", "phase": "finished", "view": _desk_view()})
    run_bg(go())
    return {"ok": True}


class Assign(BaseModel):
    mid: str


@app.post("/api/desk/assign")
def desk_assign(a: Assign):
    m = next((x for x in state["desk"]["merchants"] if x["mid"] == a.mid), None)
    r = state["desk_results"].get(a.mid)
    if not m or not r or r["outcome"] != "Escalate for EDD":
        raise HTTPException(400, "only escalated merchants go to an EDD reviewer")
    state["desk_assigned"].add(a.mid)
    W().add_ops_ticket("edd", f"EDD review: {m['name']} ({a.mid})", {"signals": r["strong_hits"]}, "DESK", False)
    from . import automation
    rec = automation.emit("edd_assigned", {"mid": a.mid, "merchant": m["name"], "signals": r["strong_hits"]}, at=W().now.isoformat())
    bus.publish({"type": "automation", "record": rec})
    return _desk_view()


@app.get("/api/automation")
def automation_log():
    from . import automation
    return {"n8n": automation.n8n_configured(), "log": automation.LOG[-60:][::-1]}


@app.get("/api/eval")
def eval_results():
    p = ROOT / "eval" / "results.json"
    return json.loads(p.read_text()) if p.exists() else {"error": "Run `python -m eval.run` first."}


# ------------------------------------------------------------ verifier
@app.get("/pack/{token}.pdf")
def pack_pdf(token: str):
    _rec, pdf = proof.load(token)
    if not pdf:
        raise HTTPException(404)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="kavach-{token}.pdf"'})


@app.get("/pack/{token}/tampered.pdf")
def pack_tampered(token: str):
    pdf = proof.tampered_copy(token)
    if not pdf:
        raise HTTPException(404)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="kavach-{token}-EDITED.pdf"'})


@app.get("/api/verify/{token}")
def api_verify(token: str, tampered: bool = False):
    pdf = proof.tampered_copy(token) if tampered else None
    return proof.verify(token, pdf, W().now)


@app.post("/api/verify/{token}")
async def api_verify_upload(token: str, file: UploadFile = File(...)):
    body = await file.read()
    return proof.verify(token, body[: 8 * 1024 * 1024], W().now)


@app.get("/verify/{token}", response_class=HTMLResponse)
def verify_page(token: str):
    return HTMLResponse((STATIC / "verify.html").read_text().replace("__TOKEN__", html.escape(token)))
