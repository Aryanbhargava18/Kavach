"""What Meena's app shows: a state, not a chat.

One deterministic view model, built from the same incident facts and world records the engine uses:
a status, where her money is, a case tracker, the one thing she should do next, her documents and her
clocks. The tipping-off guard (P17) applies here too: a guarded case renders only the neutral card.

Language: English by default, Hindi (Devanagari) on request, like Paytm's own apps. No Hinglish.
"""
from __future__ import annotations

from contextvars import ContextVar
from datetime import date, datetime, timedelta
from typing import Any

from .world import MERCHANT

LIVE = ("resolved", "refused")
_lang: ContextVar[str] = ContextVar("lang", default="en")


def t(en: str, hi: str) -> str:
    return hi if _lang.get() == "hi" else en


def trust() -> str:
    return t("This is inside your Paytm for Business app. Kavach never asks for your OTP, PIN or money.",
             "यह आपके पेटीएम फ़ॉर बिज़नेस ऐप के अंदर है। कवच कभी OTP, PIN या पैसे नहीं माँगता।")


def _guarded(inc) -> bool:
    return bool(inc.decisive and inc.decisive.get("label") == "Why Kavach held back")


def _safe_with_paytm(world) -> int:
    return sum(s["amount"] for s in world.settlements if s["status"] in ("RETURNED", "HELD"))


def clocks(world, engine) -> list[dict[str, Any]]:
    """Every deadline that silently costs Meena money, and who is watching it. Kavach is."""
    out = []
    unsettled = [x for x in world.transactions if x["status"] == "SUCCESS" and x["payee_vpa"] == MERCHANT["vpa"] and not x.get("settlement_batch")
                 and x["created_at"] < world.next_settlement - timedelta(hours=9)]
    netted = sum(d["amount"] for d in world.disputes if d["status"] in ("DEEMED_VALID", "ACCEPTED", "LOST") and not d.get("netted_in"))
    if unsettled:
        out.append({"key": "payout", "label": t("Next payout", "अगला पेआउट"), "due": world.next_settlement.isoformat(), "amount": sum(x["amount"] for x in unsettled) - netted,
                    "note": t("Kavach checks it reaches your bank", "कवच पक्का करेगा कि बैंक पहुँचा") if not world.settlement_config.get("paused")
                    else t("Stays safe with Paytm (hold)", "पेटीएम के पास सुरक्षित रहेगा (रोक)"), "tone": "ok"})
    for d in world.disputes:
        if d["status"] == "OPEN":
            out.append({"key": d["dispute_id"], "label": t("Chargeback reply", "चार्जबैक का जवाब"), "due": d["respond_by"], "amount": d["amount"],
                        "note": t("No reply means money is deducted", "जवाब नहीं तो पैसा कटेगा"), "tone": "bad"})
        elif d["status"] == "REPRESENTED":
            out.append({"key": d["dispute_id"], "label": t("Chargeback decision", "चार्जबैक का फ़ैसला"), "due": d["decide_at"], "amount": d["amount"],
                        "note": t("Replied on time", "जवाब समय पर गया"), "tone": "wait"})
    for r in world.refunds:
        if r["status"] == "PENDING":
            out.append({"key": r["refund_id"], "label": t("Refund to customer", "ग्राहक को रिफंड"), "due": r["resolve_at"].isoformat(), "amount": r["amount"],
                        "note": t("Kavach watches until it lands", "पहुँचने तक कवच देखेगा"), "tone": "wait"})
    for i in engine.incidents.values():
        ev = i.facts.get("case_events", {}) if i.status not in LIVE else {}
        at = lambda d0, days: datetime.combine(date.fromisoformat(d0) + timedelta(days=days), datetime.min.time()).isoformat()
        if ev.get("bank_complaint") and not ev.get("bank_submission"):
            out.append({"key": f"{i.id}-bank7", "label": t("Bank's 7 days", "बैंक के 7 दिन"), "due": at(ev["bank_complaint"]["date"], 7), "amount": None,
                        "note": t("SOP 10.1(a) · Kavach checks on day 5 and 7", "SOP 10.1(a) · 5वें और 7वें दिन कवच जाँचेगा"), "tone": "wait"})
        if ev.get("bank_submission") and not ev.get("io_decision"):
            out.append({"key": f"{i.id}-io15", "label": t("Officer's 15 days", "अधिकारी के 15 दिन"), "due": at(ev["bank_submission"]["date"], 15), "amount": None,
                        "note": t("SOP 10.1(b) · decision arrives on the bank desk", "SOP 10.1(b) · फ़ैसला बैंक डेस्क पर आएगा"), "tone": "wait"})
        if ev.get("io_decision"):
            lien = ev["io_decision"].get("lien")
            hold = ((i.facts.get("notice") or {}).get("hold_date"))
            if ev.get("bank_submission"):
                out.append({"key": f"{i.id}-90a", "label": t("90 days (from complaint)", "90 दिन (शिकायत से)"), "due": at(ev["bank_submission"]["date"], 90), "amount": lien,
                            "note": t("SOP 10.1(f) · two dates, both watched", "SOP 10.1(f) · दो तारीख़ें, दोनों पर नज़र"), "tone": "wait"})
            if hold:
                out.append({"key": f"{i.id}-90b", "label": t("90 days (from hold)", "90 दिन (रोक से)"), "due": at(hold, 90), "amount": lien,
                            "note": t("SOP Annexure I · two dates, both watched", "SOP अनुलग्नक I · दो तारीख़ें, दोनों पर नज़र"), "tone": "wait"})
    for c in out:
        c["secs_left"] = max(0, int((datetime.fromisoformat(c["due"]) - world.now).total_seconds()))
    return sorted(out, key=lambda c: c["secs_left"])


def _chargeback(world, engine, inc) -> dict[str, Any]:
    f = inc.facts
    d = next(x for x in world.disputes if x["dispute_id"] == f["dispute_id"])
    pend = (inc.pending or {}).get("action") == "submit_dispute_response"
    proven = [{"label": e["label"], "tier": e["tier"], "ok": True} for e in f.get("dispute_evidence", [])]
    proven.append({"label": t("Goods handed over (no record can show this)", "सामान दिया गया (कोई रिकॉर्ड यह नहीं दिखा सकता)"), "tier": "Meena",
                   "ok": bool((d.get("response") or {}).get("merchant_attests_handover"))})
    state = d["status"]
    due = _hm(d["respond_by"], world.now)
    steps = [
        {"key": "detect", "label": t("Paytm caught it", "पेटीएम ने पकड़ा"), "sub": t(f"Chargeback on the dispute desk · {_hm(d['raised_at'])}", f"डिस्प्यूट डेस्क पर चार्जबैक · {_hm(d['raised_at'])}"), "state": "done"},
        {"key": "proof", "label": t("Proof gathered", "सबूत इकट्ठा"), "sub": t("Payment and bill, from Paytm's records", "भुगतान और बिल, पेटीएम रिकॉर्ड से"), "state": "done" if proven else "todo"},
        {"key": "ask", "label": t("Your answer", "आपका जवाब"), "sub": t("Did you hand over the goods?", "क्या आपने सामान दिया था?"), "state": "now" if pend else "done"},
        {"key": "reply", "label": t("Reply before the deadline", "समय-सीमा से पहले जवाब"), "sub": t(f"by {due}", f"{due} तक"),
         "state": "done" if state in ("REPRESENTED", "WON", "LOST") else ("blocked" if state == "DEEMED_VALID" else "todo")},
        {"key": "decision", "label": t("Bank's decision", "बैंक का फ़ैसला"),
         "sub": {"WON": t("In your favour", "आपके पक्ष में"), "LOST": t("For the customer", "ग्राहक के पक्ष में")}.get(state, t("Kavach is watching", "कवच नज़र रखेगा")),
         "state": "done" if state in ("WON", "LOST") else ("now" if state == "REPRESENTED" else "todo")},
    ]
    action = None
    if pend:
        action = {"kind": "approve", "incident": inc.id, "title": t("Did you hand over the goods?", "क्या आपने सामान दिया था?"),
                  "body": t("Kavach has proof of the payment and the bill. Only you can say the goods were handed over, and it goes in your name. If you didn't, Kavach accepts the chargeback.",
                            "भुगतान और बिल का सबूत कवच के पास है। सामान देने की बात सिर्फ़ आप कह सकती हैं, और वह आपके नाम से जाएगी। नहीं दिया, तो कवच चार्जबैक मान लेगा।"),
                  "cta": t("Yes, I handed them over", "हाँ, सामान दिया था"), "secondary": t("No, I didn't", "नहीं दिया")}
    titles = {"OPEN": f"{t('Chargeback', 'चार्जबैक')} · {_rs(d['amount'])}", "REPRESENTED": t("Reply sent", "जवाब चला गया"),
              "WON": t(f"{_rs(d['amount'])} stays yours", f"{_rs(d['amount'])} आपके रहे"), "ACCEPTED": t("Chargeback accepted", "चार्जबैक माना"),
              "DEEMED_VALID": t("Deadline missed", "समय-सीमा निकल गई")}
    subs = {"OPEN": t(f"The customer's bank says \"{d['reason']}\". If nobody replies by {due}, {_rs(d['amount'])} comes out of your next payout. Kavach caught it at {_hm(d['raised_at'])}.",
                      f"ग्राहक के बैंक का कहना है: \"सामान नहीं मिला\"। {due} तक जवाब नहीं दिया तो {_rs(d['amount'])} अगले पेआउट से कटेंगे। कवच ने {_hm(d['raised_at'])} पर पकड़ा।"),
            "REPRESENTED": t("The payment record, the bill and your statement went in before the deadline. Kavach will tell you as soon as the bank decides.",
                             "भुगतान का रिकॉर्ड, बिल और आपकी बात समय-सीमा से पहले चली गई। बैंक का फ़ैसला आते ही कवच बताएगा।"),
            "WON": t("Replied on time, and the decision went your way.", "जवाब समय पर गया और फ़ैसला आपके पक्ष में आया।"),
            "ACCEPTED": t("You said the goods weren't handed over. Kavach didn't file a false reply; the customer gets the money back.",
                          "आपने बताया सामान नहीं दिया था। कवच ने गलत जवाब नहीं दिया; पैसा ग्राहक को वापस।"),
            "DEEMED_VALID": t("No reply went in before the deadline, so the chargeback was accepted.", "समय-सीमा तक जवाब नहीं गया, इसलिए चार्जबैक माना गया।")}
    return {"mode": "case", "case": "chargeback", "incident": inc.id, "lang": _lang.get(),
            "shield": {"tone": "bad" if state == "OPEN" else "ok", "title": titles.get(state, "Chargeback"), "account": d["dispute_id"], "sub": subs.get(state, ""), "trust": trust()},
            "stake": {"amount": d["amount"], "due": d["respond_by"], "replied": state in ("REPRESENTED", "WON", "LOST"),
                      "secs_left": max(0, int((datetime.fromisoformat(d["respond_by"]) - world.now).total_seconds()))},
            "proof": proven, "money": [], "ratio": None, "steps": steps, "action": action, "docs": [], "clocks": clocks(world, engine), "headline": inc.headline}


def _payout(world) -> dict[str, Any]:
    """The money tracker: today's collections on their way to her bank, and the step Kavach adds (confirming it landed)."""
    pend = [x for x in world.transactions if x["status"] == "SUCCESS" and x["payee_vpa"] == MERCHANT["vpa"] and not x.get("settlement_batch")
            and x["created_at"] < world.next_settlement - timedelta(hours=9)]
    last = max(world.settlements, key=lambda b: str(b.get("business_date")), default=None)
    acct = str(world.settlement_config.get("account") or "").split("XX")[-1]
    return {"amount": sum(x["amount"] for x in pend), "count": len(pend), "at": world.next_settlement.isoformat(), "account": f"••{acct}" if acct else "",
            "last": {"amount": last["amount"], "status": last["status"], "at": str(last.get("credited_at") or last.get("due_at") or "")} if last else None}


def _home(world, engine) -> dict[str, Any]:
    today = world.now.date()
    sales = [x for x in world.transactions if x["status"] == "SUCCESS" and x["payee_vpa"] == MERCHANT["vpa"] and x["created_at"].date() == today]
    fixes = [i for i in engine.incidents.values() if i.kind not in ("freeze", "chargeback") and not _guarded(i)
             and not (i.kind == "live_check" and not i.facts.get("pack"))]
    return {
        "mode": "home", "lang": _lang.get(),
        "shield": {"tone": "ok", "title": t("All good", "सब ठीक है"), "sub": t("Kavach is watching every payment, refund and payout for you.", "कवच आपके हर भुगतान, रिफंड और पेआउट पर नज़र रख रहा है।")},
        "today": {"sales": sum(x["amount"] for x in sales), "count": len(sales), "next_payout": world.next_settlement.isoformat(),
                  "next_payout_day": t("Tomorrow", "कल") if (world.next_settlement.date() - world.now.date()).days == 1 else (t("Today", "आज") if world.next_settlement.date() == world.now.date() else world.next_settlement.strftime("%-d %b"))},
        "payout": _payout(world),
        "payments": [{"amount": x["amount"], "name": x.get("payer_name") or "Customer", "at": x["created_at"].isoformat(),
                      "vpa": (x.get("payer_vpa") or "")[:3] + "•••@" + (x.get("payer_vpa") or "@").split("@")[-1]}
                     for x in sorted(sales, key=lambda x: x["created_at"], reverse=True)[:5]],
        "disputes_open": sum(1 for d in world.disputes if d["status"] == "OPEN"),
        "clocks": clocks(world, engine),
        "feed": [{"title": i.title, "text": i.headline or "", "state": "done" if i.status == "resolved" else "working", "at": i.updated_at}
                 for i in sorted(fixes, key=lambda i: i.updated_at, reverse=True)[:4]],
    }


def _neutral(inc) -> dict[str, Any]:
    """P17: nothing about a freeze, a notice or a report. The same words Legal approved for the message."""
    return {"mode": "neutral", "incident": inc.id, "lang": _lang.get(),
            "shield": {"tone": "wait", "title": t("Payout delayed", "पेआउट में देरी"),
                       "sub": t("The Paytm team will contact you soon. Until then your money is safe with Paytm.", "पेटीएम की टीम जल्द आपसे बात करेगी। तब तक आपका पैसा पेटीएम के पास सुरक्षित है।")}}


def _needs_meena(i) -> bool:
    return "merchant" in ((i.pending or {}).get("approvers") or [])


def build(world, engine, lang: str = "en") -> dict[str, Any]:
    tok = _lang.set("hi" if lang == "hi" else "en")
    try:
        return _build(world, engine)
    finally:
        _lang.reset(tok)


def _build(world, engine) -> dict[str, Any]:
    # Whatever is waiting on Meena comes first; otherwise the most serious open case (a freeze), then a chargeback.
    waiting = [i for i in engine.incidents.values() if i.kind == "chargeback" and i.status not in LIVE and _needs_meena(i)]
    live = [i for i in engine.incidents.values() if i.kind in ("freeze", "settlement") and i.status not in LIVE]
    if waiting and not (live and _needs_meena(live[-1])):
        return _chargeback(world, engine, waiting[-1])
    inc = live[-1] if live else None
    if inc is None:
        cb = [i for i in engine.incidents.values() if i.kind == "chargeback" and (i.status not in LIVE or i.updated_at >= world.now.isoformat()[:13])]
        if cb:
            return _chargeback(world, engine, cb[-1])
        return _home(world, engine)
    if _guarded(inc):
        return _neutral(inc)
    f = inc.facts
    held = bool(world.settlement_config.get("paused"))
    locked = f.get("locked_stated")
    disputed_txn = world.txn_by_id(f["disputed_txn"]) if f.get("disputed_txn") else None
    debit = world.bank_account.get("state") == "DEBIT_FROZEN"
    own = (inc.recon or {}).get("own")

    # ---- where the money is
    money = []
    if locked:
        money.append({"key": "locked", "label": t("Frozen at your bank", "बैंक में रुका हुआ"), "amount": locked, "source": t("your figure · unverified", "आपका बताया हुआ · असत्यापित"), "tone": "bad"})
    if disputed_txn:
        money.append({"key": "disputed", "label": t("Disputed by police", "पुलिस द्वारा विवादित"), "amount": disputed_txn["amount"], "source": t("Paytm record", "पेटीएम रिकॉर्ड"), "tone": "warn"})
    safe = _safe_with_paytm(world)
    if safe:
        money.append({"key": "safe", "label": t("Safe with Paytm", "पेटीएम के पास सुरक्षित"), "amount": safe, "source": t("held payouts", "रोके गए पेआउट"), "tone": "good"})
    ratio = round(locked / disputed_txn["amount"]) if locked and disputed_txn and locked > disputed_txn["amount"] else None

    # ---- the tracker
    intake = next((s for s in inc.steps if s["kind"] == "intake"), None)
    pend = inc.pending or {}
    pend_action = pend.get("action") if "merchant" in (pend.get("approvers") or []) else None
    ev = f.get("case_events", {})
    complaint = (ev.get("bank_complaint") or {}).get("date")
    sub_ev, dec_ev, released = ev.get("bank_submission"), ev.get("io_decision"), f.get("released")
    due = (date.fromisoformat(complaint) + timedelta(days=7)).isoformat() if complaint else None
    notice_in = bool(f.get("notice"))
    steps = [
        {"key": "detect", "label": t("Paytm caught it", "पेटीएम ने पकड़ा"),
         "sub": ((t("Your bank stopped your own payment (YE)", "बैंक ने आपका अपना भुगतान रोका (YE)") if own else t("Your bank sent a payout back", "बैंक ने पेआउट वापस भेजा"))
                 if f.get("proactive") else t("You reported it", "आपने बताया")),
         "state": "done", "at": intake["at"] if intake else inc.created_at},
        {"key": "protect", "label": t("New sales protected", "नई बिक्री सुरक्षित"), "sub": t("Payouts held with Paytm, approved by you and Paytm Risk", "आपकी और पेटीएम रिस्क की मंज़ूरी से पेआउट पेटीएम के पास"),
         "state": "done" if held or released else ("now" if pend.get("action") == "request_settlement_hold" else "todo")},
        {"key": "notice", "label": t("Notice read", "नोटिस पढ़ा"),
         "sub": t("Hidden instruction ignored; one payment matched", "छिपा निर्देश अनदेखा; एक भुगतान मिला") if notice_in else t("Send the bank's SMS or notice", "बैंक का SMS या नोटिस भेजिए"),
         "state": "done" if notice_in else ("now" if held or not pend else "todo")},
        {"key": "case", "label": t("Signed case ready", "हस्ताक्षरित केस तैयार"), "sub": t("Per the SOP, from Paytm's records", "SOP के अनुसार, पेटीएम रिकॉर्ड से"), "state": "done" if f.get("pack") else "todo"},
        {"key": "request", "label": t("Request to reduce the hold", "रोक घटाने का अनुरोध"),
         "sub": t("Only the disputed amount", "सिर्फ़ विवादित रकम") if f.get("lien_request") else t("In your name, with your approval", "आपके नाम से, आपकी मंज़ूरी से"),
         "state": "done" if f.get("lien_request") else ("now" if pend.get("action") == "draft_lien_request" else "todo")},
        {"key": "branch", "label": t("Complaint at the branch", "शाखा में शिकायत"),
         "sub": t(f"Received {complaint}", f"मिली {complaint}") if complaint else t("Always get a dated acknowledgement", "तारीख़ वाली पावती ज़रूर लीजिए"),
         "state": "done" if complaint else ("now" if f.get("pack") and not pend_action else "todo")},
        {"key": "bank7", "label": t("Bank forwards it within 7 days", "बैंक 7 दिन में आगे भेजे"),
         "sub": (t(f"Filed · {sub_ev.get('ref')} · bank desk", f"भेजा · {sub_ev.get('ref')} · बैंक डेस्क") if sub_ev
                 else (t(f"by {due} · SOP 10.1(a)", f"{due} तक · SOP 10.1(a)") if due else t("Counted from your complaint date", "शिकायत की तारीख़ से गिनती"))),
         "state": "done" if sub_ev else ("now" if due else "todo")},
        {"key": "officer", "label": t("Investigating officer decides", "जाँच अधिकारी का फ़ैसला"),
         "sub": (t(f"Hold limited to {_rs(dec_ev.get('lien'))}", f"रोक सिर्फ़ {_rs(dec_ev.get('lien'))} तक") if dec_ev else t("15 days · decided by the bank and police", "15 दिन · बैंक और पुलिस तय करते हैं")),
         "state": "done" if dec_ev else ("now" if sub_ev else "todo")},
        {"key": "release", "label": t("Held money back in your account", "रुका पैसा आपके खाते में"),
         "sub": (t(f"{_rs(released['released'])} sent · after a ₹1 check", f"{_rs(released['released'])} भेजे · ₹1 जाँच के बाद") if released
                 else t("After a ₹1 check and Paytm Risk's approval", "₹1 जाँच और पेटीएम रिस्क की मंज़ूरी के बाद")),
         "state": "done" if released else ("now" if pend.get("action") == "release_settlement_hold" else "todo")},
    ]
    if (inc.decisive or {}).get("text", "").startswith("Notice says"):
        for s in steps:
            if s["key"] == "case":
                s.update({"state": "blocked", "sub": t("The notice and Paytm's record disagree. No wrong pack will be made.", "नोटिस और पेटीएम रिकॉर्ड में रकम अलग है। गलत पैक नहीं बनेगा।")})

    # ---- the one thing to do next
    action: dict[str, Any] | None = None
    if pend_action == "request_settlement_hold":
        action = {"kind": "approve", "incident": inc.id, "title": t("Keep today's sales safe with Paytm?", "आज की बिक्री पेटीएम के पास सुरक्षित रखें?"),
                  "body": (t("Payouts are landing in an account you can't withdraw from.", "पेआउट उस खाते में जा रहे हैं जहाँ से आप निकाल नहीं सकतीं।") if debit
                           else t("Your bank is sending payouts back.", "आपका बैंक पेआउट वापस भेज रहा है।")) + " " +
                          t("Nothing goes to any other account. Paytm Risk approves too.", "किसी दूसरे खाते में कुछ नहीं जाएगा। पेटीएम रिस्क भी मंज़ूरी देगा।"),
                  "cta": t("Yes, keep it safe", "हाँ, सुरक्षित रखो"), "secondary": t("Not now", "अभी नहीं")}
    elif pend_action == "draft_lien_request":
        amt = _rs(disputed_txn["amount"]) if disputed_txn else t("the disputed amount", "विवादित रकम")
        action = {"kind": "approve", "incident": inc.id, "title": t(f"Ask the bank to hold only {amt}", f"बैंक से अनुरोध: रोक सिर्फ़ {amt} तक"),
                  "body": t("In your name, with Paytm's record, the SOP and High Court rulings attached. You'll read it before it goes.",
                            "आपके नाम से, पेटीएम रिकॉर्ड, SOP और हाई कोर्ट के फ़ैसलों के साथ। आप पढ़कर ही भेजेंगी।"),
                  "cta": t("Prepare the request", "अनुरोध तैयार करो"), "secondary": t("Not now", "अभी नहीं")}
    elif not notice_in:
        action = {"kind": "notice", "incident": inc.id, "title": t("Send the bank's SMS or notice", "बैंक का SMS या नोटिस भेजिए"),
                  "body": t("Ask your branch for three things: the NCRP number, the police notice, and how much is disputed.",
                            "शाखा से तीन चीज़ें माँगिए: NCRP नंबर, पुलिस का नोटिस, और कितनी रकम विवादित है।"), "cta": t("Send photo", "फ़ोटो भेजो")}
    elif f.get("pack") and not complaint:
        action = {"kind": "branch", "incident": inc.id, "title": t("Visit your branch", "शाखा जाइए"),
                  "body": t("Take a written complaint, the signed pack and the request. Always get a dated acknowledgement: the bank's 7 days start from it.",
                            "लिखित शिकायत, हस्ताक्षरित पैक और अनुरोध साथ ले जाइए। तारीख़ वाली पावती ज़रूर लीजिए: बैंक के 7 दिन वहीं से गिने जाते हैं।"),
                  "cta": t("The bank took my complaint ✓", "बैंक ने शिकायत ले ली ✓")}
    elif released:
        action = {"kind": "done", "incident": inc.id, "title": t("Nothing for you to do", "अब आपको कुछ नहीं करना"),
                  "body": t(f"Only {_rs((dec_ev or {}).get('lien'))} stays held for the police case. Kavach watches both 90-day dates in the SOP.",
                            f"सिर्फ़ {_rs((dec_ev or {}).get('lien'))} पुलिस केस तक रुके हैं। SOP की 90 दिन वाली दोनों तारीख़ों पर कवच नज़र रखेगा।")}
    elif pend.get("action") == "release_settlement_hold":
        action = {"kind": "info", "incident": inc.id, "title": t("Paytm Risk is approving", "पेटीएम रिस्क मंज़ूरी दे रहा है"),
                  "body": t("The officer's decision is on the bank desk, and a ₹1 check reached your account. Your held money follows once approved.",
                            "अधिकारी का फ़ैसला बैंक डेस्क पर आ गया, और ₹1 की जाँच आपके खाते में पहुँच गई। मंज़ूरी मिलते ही रुका पैसा आपके खाते में।")}
    elif sub_ev:
        left = 15 - (world.now.date() - date.fromisoformat(sub_ev["date"])).days
        action = {"kind": "wait", "incident": inc.id, "title": t("Investigating officer's decision", "जाँच अधिकारी का फ़ैसला"), "days_left": left,
                  "body": t(f"Your bank filed the complaint ({sub_ev.get('ref')}). The officer has 15 days (SOP 10.1(b)). Kavach tells you as soon as it's decided.",
                            f"बैंक ने शिकायत भेज दी ({sub_ev.get('ref')})। अधिकारी के पास 15 दिन हैं (SOP 10.1(b))। फ़ैसला आते ही कवच बताएगा।")}
    elif due:
        left = (date.fromisoformat(due) - world.now.date()).days
        action = {"kind": "wait", "incident": inc.id, "title": t(f"Bank has {max(left, 0)} days", f"बैंक के पास {max(left, 0)} दिन"), "days_left": left,
                  "body": t(f"Your bank must forward the complaint by {due}. Kavach checks on day 5 and 7.", f"{due} तक बैंक को शिकायत आगे भेजनी है। कवच 5वें और 7वें दिन जाँचेगा।")}

    docs = []
    if f.get("pack"):
        docs.append({"kind": "pack", "label": t("Signed evidence pack", "हस्ताक्षरित सबूत पैक"), "sub": t("Your bank can verify it in 10 seconds", "बैंक इसे 10 सेकंड में जाँच सकता है"),
                     "href": f"/pack/{f['pack']['token']}.pdf", "verify": f["pack"]["verify_url"]})
    if f.get("lien_request"):
        docs.append({"kind": "letter", "label": t("Request to reduce the hold", "रोक घटाने का अनुरोध"),
                     "sub": t(f"Only {f['lien_request']['disputed_text']} · in your name", f"सिर्फ़ {f['lien_request']['disputed_text']} · आपके नाम से"), "text": f["lien_request"]["en"]})

    if released:
        lien = (dec_ev or {}).get("lien")
        money = [{"key": "back", "label": t("Paid back to your account", "आपके खाते में वापस"), "amount": released["released"], "source": t("was held with Paytm", "पेटीएम के पास रुका था"), "tone": "good"},
                 {"key": "still", "label": t("Still held (police case)", "अभी भी रुका (पुलिस केस)"), "amount": lien, "source": t("officer's decision · bank desk", "अधिकारी का फ़ैसला · बैंक डेस्क"), "tone": "warn"}]
        if locked:
            money.append({"key": "was", "label": t("Was frozen", "पहले रुका था"), "amount": locked, "source": t("your figure", "आपका बताया हुआ"), "tone": "muted"})
        return {"mode": "case", "incident": inc.id, "released": True, "lang": _lang.get(),
                "shield": {"tone": "ok", "title": t("Your account works again", "आपका खाता फिर से चालू"), "account": "XX4471",
                           "sub": t(f"The hold is now only {_rs(lien)} (police case). The {_rs(released['released'])} Paytm was holding is in your account.",
                                    f"रोक अब सिर्फ़ {_rs(lien)} की है (पुलिस केस)। पेटीएम के पास रुके {_rs(released['released'])} आपके खाते में भेज दिए।"), "trust": trust()},
                "money": money, "ratio": None, "steps": steps, "action": action, "docs": docs, "clocks": clocks(world, engine), "headline": inc.headline}
    title = t("Account frozen", "खाता फ्रीज़") + (t(" · debit", " · डेबिट") if debit else "")
    sub = (t("Your bank is blocking withdrawals." if debit else "Your bank sent a payout back.", "आपका बैंक पैसा निकालने नहीं दे रहा।" if debit else "आपके बैंक ने पेआउट लौटा दिया।") + " "
           + (t(f"Kavach caught it at {_hm(inc.created_at)}, before anyone told you.", f"कवच ने {_hm(inc.created_at)} पर पकड़ा, आपको किसी के बताने से पहले।") if f.get("proactive")
              else t(f"Kavach opened your case at {_hm(inc.created_at)}.", f"कवच ने {_hm(inc.created_at)} पर आपका केस खोला।")))
    return {"mode": "case", "incident": inc.id, "lang": _lang.get(),
            "shield": {"tone": "bad", "title": title, "sub": sub, "account": "XX4471", "trust": trust()},
            "money": money, "ratio": ratio, "steps": steps, "action": action, "docs": docs,
            "clocks": clocks(world, engine), "headline": inc.headline}


def _rs(n: int | None) -> str:
    from .planner_offline import rs
    return rs(n)


def _hm(iso: str, now: datetime | None = None) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    tm = d.strftime("%-I:%M %p").lower()
    if now and d.date() != now.date():
        return (t("tomorrow ", "कल ") if d.date() == now.date() + timedelta(days=1) else d.strftime("%-d %b ")) + tm
    return tm
