"""Offline understanding of merchant messages (Hinglish, Devanagari Hindi, English).

This is the deterministic fallback used when no LLM key is configured. It is a keyword +
pattern interpreter, and the UI labels it as such. With an LLM configured, the model does
interpretation and planning; this module is then only used to sanity-check extracted numbers.
"""
from __future__ import annotations

import re
from typing import Any

INTENTS: list[tuple[str, list[str]]] = [
    ("scam_call", [r"call|phone|फोन|कॉल|banda|aadmi|कोई", r"maang|mang|demand|मांग|माँग|paise do|pay karo|withdraw|(complaint|case|शिकायत)\s*(wapas|वापस)|settle kar|\d[\d,]*\s*(do|de do|bhejo|दो)\b.*(khatam|band|hata)|case khatam"]),
    ("bank_ack", [r"acknowledg|\back\b|pavti|paavti|पावती|receiving|complaint (le li|de di|jama)|shikayat (le li|de di|jama)|शिकायत (ले ली|दे दी)"]),
    ("sop_question", [r"kitne din|kab tak|kaun (file|de|kar)|how many days|who can|niyam|\brule|\bsop\b|कितने दिन|कब तक|(beta|beti|bhai|papa).{0,20}(file|shikayat|complaint)"]),
    ("change_settlement_account", [r"(doosr|dusr|dusre|other|another|new|naya|दूसर|नया)\w*\s*(bank\s*)?(account|a/c|khata|खात)|account\s*(badal|change)|खाता\s*बदल"]),
    ("duplicate_charge", [r"do\s*baar|2\s*baar|twice|double|duplicate|दो\s*बार|dobara\s*kat|dubara\s*kat|charged\s*two"]),
    ("account_freeze", [r"freez|frozen|फ्रीज|hold|lien|cyber|साइबर|account\s*(band|block)|khata\s*band|खाता\s*बंद|debit\s*band|ब्लॉक"]),
    ("settlement_missing", [r"settlement|सेटलमेंट|payout|kal\s*ka\s*paisa|कल\s*का\s*पैसा|bank\s*(mein|me|में)\s*(nahi|nahin|नहीं)\s*(aaya|aya|आया)|account\s*(mein|me)\s*(nahi|nahin)\s*(aaya|aya)|paise\s*nahi\s*aaye"]),
    ("payment_claim", [r"bhej\s*diya|bheja|paid|pay\s*kar\s*diya|kar\s*diya|भेज\s*दिया|पे\s*कर|screenshot|स्क्रीनशॉट|soundbox|साउंडबॉक्स|nahi\s*bola|नहीं\s*बोला|payment\s*(aaya|aya|hua)"]),
    ("status_query", [r"kya\s*hua|status|update|क्या\s*हुआ|aage\s*kya"]),
]

HAZAAR = re.compile(r"(\d+(?:\.\d+)?)\s*(hazaar|hazar|हज़ार|हजार|k)\b\s*(\d+)?", re.I)
LAKH = re.compile(r"(\d+(?:\.\d+)?)\s*(lakh|lac|लाख)", re.I)
AMOUNT = re.compile(r"(?:₹|rs\.?|inr|rupay?e?s?|रुपये)?\s*(\d{1,3}(?:,\d{2,3})+|\d{2,7})(?!\d)", re.I)
UTR = re.compile(r"\b(\d{12})\b")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def interpret(text: str, has_screenshot: bool = False) -> dict[str, Any]:
    t = text.strip()
    low = t.lower()
    scores = []
    for intent, pats in INTENTS:
        if all(re.search(p, low) for p in pats) if intent == "scam_call" else any(re.search(p, low) for p in pats):
            scores.append(intent)
    if has_screenshot and "payment_claim" not in scores and not scores:
        scores.append("payment_claim")
    # precedence: specific > generic
    order = ["scam_call", "bank_ack", "sop_question", "change_settlement_account", "duplicate_charge", "account_freeze", "settlement_missing", "payment_claim", "status_query"]
    intent = next((i for i in order if i in scores), "unknown")
    utrs = UTR.findall(t)
    amount = None
    m = LAKH.search(low)
    if m:
        amount = int(float(m.group(1)) * 100000)
    m = HAZAAR.search(low)
    if amount is None and m:
        amount = int(float(m.group(1)) * 1000) + (int(m.group(3)) if m.group(3) else 0)
    if amount is None:
        stripped = UTR.sub(" ", t)
        cands = [int(x.replace(",", "")) for x in AMOUNT.findall(stripped)]
        cands = [c for c in cands if 1 <= c <= 10_00_000]
        amount = cands[0] if cands else None
    lang = "hi-Deva" if DEVANAGARI.search(t) else ("hinglish" if re.search(r"\b(hai|nahi|kya|bhej|diya|mera|kal|paisa|ho gaya|karo|bol)\b", low) else "en")
    return {"intent": intent, "candidates": scores, "amount": amount, "utrs": utrs, "language": lang, "engine": "offline-rules"}
