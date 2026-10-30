"""One-shot check of every Sarvam call Kavach makes. Run: make sarvam-check (needs SARVAM_API_KEY)."""
from __future__ import annotations

import asyncio
import sys
import time

from . import sarvam, shots, sop_kb, tools
from .world import World


async def step(name, coro):
    t = time.time()
    try:
        r = await coro
        print(f"PASS  {name:<34} {time.time() - t:5.1f}s  {r}")
        return True
    except Exception as ex:
        print(f"FAIL  {name:<34} {time.time() - t:5.1f}s  {type(ex).__name__}: {str(ex)[:160]}")
        return False


async def main():
    if not sarvam.available():
        sys.exit("Set SARVAM_API_KEY in .env first.")
    print(f"chat={sarvam.CHAT_MODEL}  stt={sarvam.STT_MODEL}  tts={sarvam.TTS_MODEL} ({sarvam.TTS_SPEAKER})\n")
    ok = []

    async def chat():
        j = await sarvam.chat([{"role": "user", "content": "Reply with exactly: Kavach ready"}], max_tokens=20, reasoning="none")
        return j["choices"][0]["message"].get("content")
    ok.append(await step("chat completions", chat()))

    async def toolcall():
        j = await sarvam.chat([{"role": "user", "content": "Check the status of transaction T123."}],
                              sarvam.openai_tools([s for s in tools.llm_tool_specs() if s["name"] == "get_payment_status"]), max_tokens=200)
        tc = j["choices"][0]["message"].get("tool_calls") or []
        assert tc, "model did not call the tool"
        return f"{tc[0]['function']['name']}({tc[0]['function']['arguments']})"
    ok.append(await step("tool calling", toolcall()))

    wav = {}

    async def speak():
        wav["b"] = await sarvam.tts("Customer ne do baar payment kar diya hai. Main ek refund kar raha hoon.", "hi-IN")
        return f"{len(wav['b']) // 1024} KB WAV"
    ok.append(await step("text-to-speech (Bulbul)", speak()))

    async def listen():
        r = await sarvam.stt(wav["b"], "check.wav", "audio/wav", "hi-IN")
        return repr(r["transcript"])
    if wav.get("b"):
        ok.append(await step("speech-to-text (Saaras) round trip", listen()))

    w = World()
    shot = w.inject_customer_claim(mode="fake_amount")

    async def vision():
        r = await sarvam.read_image(shots.render(shot), "screenshot")
        return {k: r.get(k) for k in ("amount", "utr", "payee_vpa")}
    ok.append(await step("vision: screenshot", vision()))

    async def sopq():
        r = await sop_kb.ask("bank ko kitne din mein shikayat aage bhejni hoti hai?")
        return f"{r['answer'][:90]}… cites {[c['id'] for c in r['citations']]} via {r['answerer']}"
    ok.append(await step("ask the SOP", sopq()))
    print(f"\n{sum(ok)}/{len(ok)} passed. Next: make llm-check runs the full scenarios on the Sarvam planner.")


if __name__ == "__main__":
    asyncio.run(main())
