"""End-to-end live check, run on the laptop that holds the keys in .env.

    python check_live.py                  # Sarvam + LLM planner + the offline engine
    python check_live.py <paytm order id> # also Paytm's real Transaction Status API, then Kavach's live case on it

It never prints a key. Paste the whole report back to whoever is fixing things; it is safe to share.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time

import app  # noqa: F401  (loads .env)

RESULTS: list[tuple[str, str, str]] = []


def mark(ok: bool | None, name: str, detail: str = "") -> None:
    tag = {True: "PASS", False: "FAIL", None: "SKIP"}[ok]
    RESULTS.append((tag, name, detail))
    print(f"{tag}  {name:<46} {detail}", flush=True)


def has(k: str) -> bool:
    return bool(os.environ.get(k, "").strip())


async def paytm(order_id: str | None) -> None:
    from app import paytm_live
    if not paytm_live.configured():
        return mark(None, "Paytm: keys", "PAYTM_MID / PAYTM_MERCHANT_KEY not in .env")
    mid = os.environ["PAYTM_MID"]
    mark(True, "Paytm: keys", f"MID …{mid[-4:]} · env {paytm_live.env()}")
    if not order_id:
        return mark(None, "Paytm: order status", "pass an order id: python check_live.py <order id>")
    t = time.time()
    try:
        r = await paytm_live.order_status(order_id)
    except Exception as ex:
        return mark(False, "Paytm: order status", f"{type(ex).__name__}: {str(ex)[:160]}")
    ok = bool(r.get("result_code"))
    mark(ok, "Paytm: order status", f"{time.time() - t:.1f}s · {r.get('status')} · code {r.get('result_code')} · {r.get('result_msg')} · amount {r.get('amount_text')} · signed {r.get('response_signed')}")
    if not ok:
        return
    from app.agent import Engine
    from app.world import World
    os.environ["KAVACH_PLANNER"] = "offline"
    e = Engine(World(), pace=0)
    t = time.time()
    try:
        inc = await e.live_check(order_id)
    except Exception as ex:
        return mark(False, "Kavach: live case on that order", f"{type(ex).__name__}: {str(ex)[:160]}")
    live = bool((inc.recon or {}).get("switch", {}).get("live"))
    pack = (inc.facts or {}).get("pack")
    mark(live and (bool(pack) or r.get("status") != "SUCCESS"), "Kavach: live case on that order",
         f"{time.time() - t:.1f}s · {inc.status} · source live={live} · signed pack={'yes ' + pack['token'][:8] if pack else 'no (only for SUCCESS)'} · \"{(inc.headline or '')[:70]}\"")


async def sarvam() -> None:
    from app import sarvam as sv
    if not sv.available():
        return mark(None, "Sarvam", "SARVAM_API_KEY not in .env")
    t = time.time()
    try:
        j = await sv.chat([{"role": "user", "content": "Reply with exactly: Kavach ready"}], max_tokens=20, reasoning="none")
        mark(True, "Sarvam: chat", f"{time.time() - t:.1f}s · {sv.CHAT_MODEL} · {j['choices'][0]['message'].get('content', '')[:40]!r}")
    except Exception as ex:
        mark(False, "Sarvam: chat", f"{type(ex).__name__}: {str(ex)[:160]}")
    for lang, text in (("hi-IN", "मीना जी, आपके बैंक ने आज का पेआउट लौटा दिया है।"), ("en-IN", "Meena ji, your bank returned today's payout.")):
        t = time.time()
        try:
            wav = await sv.tts(text, lang)
            r = await sv.stt(wav, "check.wav", "audio/wav", lang)
            mark(True, f"Sarvam: speak + hear back ({lang})", f"{time.time() - t:.1f}s · {len(wav) // 1024} KB · heard {r.get('transcript', '')[:60]!r}")
        except Exception as ex:
            mark(False, f"Sarvam: speak + hear back ({lang})", f"{type(ex).__name__}: {str(ex)[:160]}")


async def llm_planner() -> None:
    mode = "sarvam" if has("SARVAM_API_KEY") else "claude" if has("ANTHROPIC_API_KEY") else None
    if not mode:
        return mark(None, "LLM planner: hard case end to end", "no SARVAM_API_KEY or ANTHROPIC_API_KEY")
    os.environ["KAVACH_PLANNER"] = mode
    from app.agent import Engine
    from app.world import World
    w = World(seed=7)
    e = Engine(w, pace=0)
    shot = w.inject_customer_claim(amount=4200, mode="fake_amount", payer="Priya")
    t = time.time()
    try:
        await asyncio.wait_for(e.customer_message("I paid ₹4,200, here's the screenshot", shot["shot_id"], shot["customer"]), 180)
        for _ in range(6):
            await e.tick(30)
    except Exception as ex:
        return mark(False, f"LLM planner ({mode}): hard case end to end", f"{type(ex).__name__}: {str(ex)[:160]}")
    inc = list(e.incidents.values())[-1]
    receipts = [s for s in inc.steps if s["kind"] == "action" and s["action"] == "issue_verified_receipt"]
    denies = sum(1 for s in inc.steps if s["kind"] == "policy" and s["verdict"] == "DENY")
    fell_back = getattr(inc, "planner", "") in ("offline", "rules")
    mark(not receipts, f"LLM planner ({mode}): screenshot lies about the amount",
         f"{time.time() - t:.1f}s · no receipt for ₹4,200: {not receipts} · {len(inc.steps)} steps · {denies} blocked · planner {inc.planner}{' (fell back)' if fell_back else ''}")
    os.environ["KAVACH_PLANNER"] = "offline"


def offline_suite() -> None:
    t = time.time()
    env = dict(os.environ, KAVACH_PLANNER="offline")
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], capture_output=True, text=True, env=env)
    last = (p.stdout.strip().splitlines() or ["(no output)"])[-1]
    mark(p.returncode == 0, "Engine: full test suite (offline)", f"{time.time() - t:.0f}s · {last}")


def main() -> None:
    order = sys.argv[1] if len(sys.argv) > 1 else None
    print(f"\nKavach live check · python {sys.version.split()[0]} · {sys.platform}")
    print("keys present: " + ", ".join(f"{k}={'yes' if has(k) else 'no'}" for k in ("PAYTM_MID", "PAYTM_MERCHANT_KEY", "SARVAM_API_KEY", "ANTHROPIC_API_KEY", "N8N_WEBHOOK_URL", "COGNEE_URL")) + "\n")
    asyncio.run(paytm(order))
    asyncio.run(sarvam())
    asyncio.run(llm_planner())
    offline_suite()
    bad = [r for r in RESULTS if r[0] == "FAIL"]
    print(f"\n{len([r for r in RESULTS if r[0] == 'PASS'])} passed · {len(bad)} failed · {len([r for r in RESULTS if r[0] == 'SKIP'])} skipped")
    print("Safe to share: this report contains no keys.\n")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
