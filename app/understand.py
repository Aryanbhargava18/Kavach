"""Offline understanding of merchant messages (Hinglish, Devanagari Hindi, English).

This is the deterministic fallback used when no LLM key is configured. It is a keyword +
pattern interpreter, and the UI labels it as such. With an LLM configured, the model does
interpretation and planning; this module is then only used to sanity-check extracted numbers.
"""
from __future__ import annotations

import difflib
import re
from typing import Any

# People type fast, on small keyboards, in whatever spelling comes to mind. Fix the spelling first, then match.
SHORT = {"acc": "account", "acct": "account", "accnt": "account", "ac": "account", "a/c": "account", "pymt": "payment", "pmt": "payment",
         "paymnt": "payment", "nhi": "nahi", "nai": "nahi", "nahin": "nahi", "ni": "nahi", "aya": "aaya", "ayega": "aayega", "pls": "", "plz": "", "pls.": "",
         "frozed": "frozen", "blokd": "block", "blockd": "block", "blokced": "block", "credted": "credited", "recived": "received", "recieved": "received", "freezed": "frozen", "blocked": "block", "blok": "block", "blck": "block", "stlmt": "settlement", "u": "you", "r": "are",
         "ss": "screenshot", "scrnsht": "screenshot", "2wice": "twice", "dbl": "double", "y'day": "yesterday", "yday": "yesterday", "ystrday": "yesterday"}
VOCAB = ["account", "payment", "settlement", "payout", "freeze", "frozen", "block", "money", "screenshot", "complaint", "acknowledgement", "twice",
         "double", "duplicate", "status", "yesterday", "deducted", "received", "change", "another", "cyber", "police", "someone", "asking", "withdraw",
         "soundbox", "nahi", "aaya", "paisa", "khata", "bheja", "shikayat", "settle", "update", "how", "many", "days"]

# Real words people type in Roman Hindi: never "correct" these into something else (bhejo != bheja).
KEEP = {"bhejo", "bhejna", "bheje", "maang", "maange", "dijiye", "dedo", "hatao", "hata", "hatado", "karo", "kardo", "kariye", "aayega", "aayenge",
        "nikal", "nikla", "paise", "paisa", "khate", "khaata", "kaise", "kitna", "kitne", "abhi", "bolo", "bataiye", "batao", "wapas", "denge", "lenge"}


def normalise(text: str) -> str:
    low = re.sub(r"(.)\1{2,}", r"\1\1", text.lower())          # "pleaseeee" -> "pleasee", "frozzzen" -> "frozzen"
    low = re.sub(r"\bscreen\s+shot\b", "screenshot", low)

    def fix(m: re.Match) -> str:
        w = m.group(0)
        if w in SHORT:
            return SHORT[w]
        if len(w) >= 5 and w.isalpha() and w not in VOCAB and w not in KEEP:
            c = difflib.get_close_matches(w, VOCAB, n=1, cutoff=0.85)
            return c[0] if c else w
        return w
    return re.sub(r"(?<![\w/'])[a-z0-9][a-z0-9/']*(?![\w/'])", fix, low)    # ASCII words only; Devanagari passes through untouched

INTENTS: list[tuple[str, list[str]]] = [
    ("scam_call", [r"call|phone|फोन|कॉल|banda|aadmi|कोई|someone|somebody|caller|a man|a person|asking", r"maang|mang|demand|asking for|wants|मांग|माँग|paise do|pay karo|withdraw|(complaint|case|शिकायत)\s*(wapas|वापस)|asking\s*(for\s*)?(₹|rs\.?)?\s*\d|(paise|paisa|money|payment|\d)\s*(transfer|bhejo|send|do|de\s*do)\b.{0,30}(warna|nahi\s*to|otherwise|or\s*else)|(remove|withdraw|close|drop)\s*(the\s*)?(complaint|case)|settle kar|\d[\d,]*\s*(do|de do|bhejo|दो)\b.*(khatam|band|hata)|case khatam"]),
    ("bank_ack", [r"acknowledg|\back\b|pavti|paavti|पावती|receiving|complaint (le li|de di|jama)|shikayat (le li|de di|jama)|शिकायत (ले ली|दे दी)"]),
    ("sop_question", [r"kitne din|kab tak|kaun (file|de|kar)|how many days|who can|what is an? \w+|niyam|\brule|\bsop\b|क्या होता है|कितने दिन|कब तक|(beta|beti|bhai|papa).{0,20}(file|shikayat|complaint)"]),
    ("change_settlement_account", [r"(doosr|dusr|dusre|other|another|new|naya|दूसर|नया)\S*\s*(bank\s*)?(account|a/c|khata|खात)|account\s*(badal|change)|खाता\s*बदल"]),
    ("duplicate_charge", [r"do\s*baar|2\s*baar|twice|double|duplicate|दो\s*बार|dobara\s*kat|dubara\s*kat|charged\s*two"]),
    ("account_freeze", [r"freez|frozen|फ्रीज|hold|lien|cyber|साइबर|account\s*(band|block)|(account|khata)\s+(\w+\s+){0,3}(block|seiz|band)|khata\s*band|खाता\s*बंद|debit\s*band|ब्लॉक"]),
    ("settlement_missing", [r"settlement|सेटलमेंट|payout|पेआउट|yesterday'?s?\s*money|when will (my|the)?\s*(money|payment|payout)|kal\s*ka\s*paisa|कल\s*का\s*पैसा|bank\s*(mein|me|में)\s*(nahi|nahin|नहीं)\s*(aaya|aya|आया)|account\s*(mein|me)\s*(nahi|nahin)\s*(aaya|aya)|paise\s*nahi\s*aaye|(payment|money|paisa|payout|settlement)\S*\s+(\w+\s+){0,2}(nahi|not)\s*(aaya|received|credited|come|came|arrived)|not\s*(credited|received)"]),
    ("payment_claim", [r"bhej\s*diya|bheja|paid|pay\s*kar\s*diya|kar\s*diya|भेज\s*दिया|पे\s*कर|screenshot|स्क्रीनशॉट|soundbox|साउंडबॉक्स|nahi\s*bola|नहीं\s*बोला|payment\s*(aaya|aya|hua)"]),
    ("status_query", [r"kya\s*hua|status|update|what\s*(happened|now|next)|any\s*news|क्या\s*हुआ|aage\s*kya"]),
]

HAZAAR = re.compile(r"(\d+(?:\.\d+)?)\s*(hazaar|hazar|हज़ार|हजार|k)\b\s*(\d+)?", re.I)
LAKH = re.compile(r"(\d+(?:\.\d+)?)\s*(lakh|lac|लाख)", re.I)
AMOUNT = re.compile(r"(?:₹|rs\.?|inr|rupay?e?s?|रुपये)?\s*(\d{1,3}(?:,\d{2,3})+|\d{2,7})(?!\d)", re.I)
UTR = re.compile(r"\b(\d{12})\b")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def interpret(text: str, has_screenshot: bool = False) -> dict[str, Any]:
    t = text.strip()
    low = normalise(t)
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
