"""Ask the SOP: cited answers about the MHA/I4C SOP for NCRP-CFCFRMS (02.01.2026).

Passages are the team's paraphrases of SOP paragraphs, each tied to its paragraph id (and PDF page
where recorded). They are not the SOP's verbatim text; the UI says "paraphrase, check the PDF".

Retrieval: Cognee (if COGNEE_URL is set: POST /api/v1/search over the 'kavach_sop' dataset), else a
local keyword retriever. Answering: Sarvam (if SARVAM_API_KEY) constrained to the retrieved passages,
else the top passage's own Hinglish line. Every citation in the answer is checked against the passages
that were actually retrieved; anything else is stripped and flagged.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

from . import sarvam
from .sop import SOP_SOURCE

PASSAGES: list[dict[str, Any]] = [
    {"id": "6.1", "page": 16, "title": "Portal complaint acknowledgement",
     "text": "A complaint registered on the cybercrime portal gets a 14-digit acknowledgement number beginning with 2.",
     "hi": "Portal par shikayat ka 14 ank ka acknowledgement number 2 se shuru hota hai.",
     "kw": "acknowledgement ack number portal ncrp 14 digit complaint number"},
    {"id": "6.2", "page": 19, "title": "1930 helpline acknowledgement",
     "text": "A complaint made through the 1930 helpline gets a 14-digit acknowledgement number beginning with 3.",
     "hi": "1930 helpline wali shikayat ka acknowledgement number 3 se shuru hota hai.",
     "kw": "1930 helpline acknowledgement number 14 digit call"},
    {"id": "9.5(i)", "page": 30, "title": "Funds still with the payment aggregator",
     "text": "If the reported amount is still in the payment aggregator's escrow or pool account and not settled, the PA holds only the reported amount and updates beneficiary details on CFCFRMS.",
     "hi": "Agar paisa abhi Paytm jaise PA ke escrow mein hai, to sirf utni hi rakam roki jaati hai jitni report hui.",
     "kw": "escrow pool aggregator pa not settled hold reported amount beneficiary"},
    {"id": "9.5(ii)", "page": 31, "title": "Funds already settled to the merchant",
     "text": "If the amount was already settled to the merchant's bank account after goods or services were delivered, the PA uploads the settlement transaction details; the account holder follows the bank-side grievance route.",
     "hi": "Agar paisa aapke bank mein settle ho chuka hai, to Paytm settlement ki details deta hai aur aap bank wala raasta lete hain.",
     "kw": "settled settlement merchant bank account delivered goods upload details"},
    {"id": "9.5(iv)", "page": 32, "title": "Same UPI ID in several reports",
     "text": "When one UPI ID or account is reported in multiple CFCFRMS complaints, the TPAP/PA carries out enhanced due diligence; the account may be suspended and the UPI ID escalated to the linked bank.",
     "hi": "Ek hi UPI ID kai shikayaton mein aaye to uski gehri jaanch (EDD) hoti hai.",
     "kw": "repeated multiple reports same upi id edd enhanced due diligence mule suspend"},
    {"id": "10.1(a)", "page": 38, "title": "Complain at your bank; bank submits in 7 days",
     "text": "The aggrieved account holder complains to their bank. The bank does CDD/EDD and, if satisfied, submits the grievance to the grievance module no later than 7 calendar days from the day of the complaint to the bank.",
     "hi": "Aap apne bank ki branch mein likhit shikayat dijiye. Bank ko 7 din ke andar use aage bhejna hota hai, aapki shikayat ke din se.",
     "kw": "7 seven days bank complaint branch submit grievance module cdd edd how many days kitne din"},
    {"id": "10.1(b)", "page": 39, "title": "Investigating officer decides in 15 days",
     "text": "For a hold on a reported amount, the investigating officer is to decide on the grievance within 15 days of receiving it.",
     "hi": "Bank ke bhejne ke baad, jaanch adhikari (IO) ko 15 din mein faisla lena hota hai.",
     "kw": "15 fifteen days io investigating officer police decide decision"},
    {"id": "10.1(f)", "page": 40, "title": "90 days from the bank's submission",
     "text": "A contested hold can be removed by the bank after 90 calendar days counted from the grievance submitted by the bank, absent an extension request.",
     "hi": "Bank ke grievance bhejne ke 90 din baad, extension na mile to, rok hatayi ja sakti hai.",
     "kw": "90 ninety days remove hold lift release extension"},
    {"id": "Annexure I", "page": 61, "title": "90 days from the hold date (notice template)",
     "text": "The notice template in Annexure I counts 90 calendar days from the date the amount was put on hold, a different starting point from 10.1(f).",
     "hi": "Notice ke template mein 90 din hold lagne ki tareekh se gine jaate hain. Yeh 10.1(f) se alag hai, isliye dono tareekhein dikhaate hain.",
     "kw": "90 days hold date annexure notice template anchor"},
    {"id": "10.2", "page": 40, "title": "Suspension or seizure: the escalation ladder",
     "text": "For suspension of digital banking or seizure, the grievance goes from the investigating officer (15 days) to the district officer (15 days) to the state officer (15 days), and then to court.",
     "hi": "Poora khata band (suspension/seizure) ho to IO, phir district officer, phir state officer — har ek ke 15 din.",
     "kw": "suspension seizure whole account district state officer ladder escalate court"},
    {"id": "10 (third party)", "page": 38, "title": "Who can file",
     "text": "The account holder files personally; a third party may file only for senior citizens, specially-abled or terminally ill holders.",
     "hi": "Shikayat khud khatadhaarak deta hai. Sirf buzurg, divyang ya gambhir bimar logon ke liye koi aur de sakta hai.",
     "kw": "third party family son daughter senior citizen specially abled who can file someone else beta beti"},
    {"id": "10 (no payment)", "page": 38, "title": "No fees in the grievance route",
     "text": "The grievance route runs through the bank and the grievance module. Nothing in it involves paying anyone to withdraw a complaint or release a hold.",
     "hi": "Is poore raaste mein kisi ko paise dene ka koi kadam nahi hai. Koi paise maange to woh fraud hai, 1930 par report kijiye.",
     "kw": "pay money fee withdraw complaint caller demand bribe scam paise maang"},
]

SYN = {"din": "days", "kitne": "how many", "shikayat": "complaint", "khata": "account", "rok": "hold", "freeze": "hold",
       "band": "suspension", "paise": "money pay", "maang": "demand", "beta": "son family", "beti": "daughter family",
       "buzurg": "senior", "papa": "family", "police": "officer io", "saat": "7", "nabbe": "90", "pandrah": "15",
       "कितने": "how many", "दिन": "days", "शिकायत": "complaint", "बैंक": "bank", "पैसे": "money"}


def cognee_configured() -> bool:
    return bool(os.environ.get("COGNEE_URL"))


def _tok(s: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+|[ऀ-ॿ]+", s.lower())
    out = []
    for t in toks:
        out.append(t)
        if t in SYN:
            out += SYN[t].split()
    return out


def retrieve_local(q: str, k: int = 3) -> list[dict[str, Any]]:
    qt = set(_tok(q))
    scored = []
    for p in PASSAGES:
        kw = set(_tok(p["kw"])); tx = set(_tok(p["text"]))
        score = 3 * len(qt & kw) + len(qt & tx)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:k]]


async def retrieve(q: str, k: int = 3) -> tuple[list[dict[str, Any]], str]:
    if cognee_configured():
        try:
            h = {"Content-Type": "application/json"}
            if os.environ.get("COGNEE_API_KEY"):
                h["X-Api-Key"] = os.environ["COGNEE_API_KEY"]
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(os.environ["COGNEE_URL"].rstrip("/") + "/api/v1/search", headers=h,
                                 json={"query": q, "search_type": "CHUNKS", "datasets": ["kavach_sop"]})
                r.raise_for_status()
                blob = str(r.json())
            ids = [p for p in PASSAGES if p["id"] in blob or p["title"] in blob]
            if ids:
                return ids[:k], "cognee"
        except Exception:
            pass
    return retrieve_local(q, k), "local keyword retrieval"


CITE = re.compile(r"\[([^\]]{1,24})\]")


def check_citations(answer: str, passages: list[dict[str, Any]]) -> tuple[str, list[str]]:
    allowed = {p["id"] for p in passages}
    bad = [c for c in CITE.findall(answer) if c not in allowed]
    for c in bad:
        answer = answer.replace(f"[{c}]", "")
    return answer.strip(), bad


async def ask(q: str) -> dict[str, Any]:
    passages, retriever = await retrieve(q)
    if not passages:
        return {"answer": "Yeh sawaal SOP ke jin hisson ko main jaanta hoon unmein nahi aata. Bank ya Paytm Support se poochiye.",
                "citations": [], "retriever": retriever, "answerer": "none", "passages": []}
    answerer = "offline: top passage"
    answer = f"{passages[0]['hi']} [{passages[0]['id']}]"
    if sarvam.available():
        try:
            ctx = "\n".join(f"[{p['id']}] {p['text']}" for p in passages)
            j = await sarvam.chat([
                {"role": "system", "content": "You answer a small shopkeeper's question in 1-2 short Hinglish sentences using ONLY the passages given. "
                                              "Cite each fact with its passage id in square brackets exactly as given, e.g. [10.1(a)]. "
                                              "If the passages don't answer it, say so. Never give legal opinions."},
                {"role": "user", "content": f"Passages:\n{ctx}\n\nQuestion: {q}"}], max_tokens=300, reasoning="none")
            text = (j["choices"][0]["message"].get("content") or "").strip()
            if text:
                answer, answerer = text, f"sarvam {sarvam.CHAT_MODEL}"
        except Exception:
            pass
    answer, stripped = check_citations(answer, passages)
    return {"answer": answer, "citations": [{"id": p["id"], "title": p["title"], "page": p.get("page"), "text": p["text"]} for p in passages
                                            if f"[{p['id']}]" in answer] or [{"id": passages[0]["id"], "title": passages[0]["title"], "page": passages[0].get("page"), "text": passages[0]["text"]}],
            "stripped_citations": stripped, "retriever": retriever, "answerer": answerer, "source": SOP_SOURCE,
            "note": "Passages are the team's paraphrases of the SOP; check the PDF."}
