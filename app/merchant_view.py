"""What Meena's app shows: a state, not a chat.

One deterministic view model, built from the same incident facts and world records the engine uses:
a status, where her money is, a case tracker, the one thing she should do next, her documents and her
clocks. The tipping-off guard (P17) applies here too: a guarded case renders only the neutral card.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .world import MERCHANT

LIVE = ("resolved", "refused")


def _guarded(inc) -> bool:
    return bool(inc.decisive and inc.decisive.get("label") == "Why Kavach held back")


def _done_step(inc, kind: str, action: str | None = None, ok: bool | None = None):
    for s in inc.steps:
        if s["kind"] == kind and (action is None or s.get("action") == action) and (ok is None or s.get("ok") == ok):
            return s
    return None


def _safe_with_paytm(world) -> int:
    return sum(s["amount"] for s in world.settlements if s["status"] in ("RETURNED", "HELD"))


def clocks(world, engine) -> list[dict[str, Any]]:
    """Every deadline that silently costs Meena money, and who is watching it. Kavach is."""
    out = []
    today = world.now.date()
    unsettled = [t for t in world.transactions if t["status"] == "SUCCESS" and t["payee_vpa"] == MERCHANT["vpa"] and not t.get("settlement_batch")
                 and t["created_at"] < world.next_settlement - timedelta(hours=9)]
    netted = sum(d["amount"] for d in world.disputes if d["status"] in ("DEEMED_VALID", "ACCEPTED", "LOST") and not d.get("netted_in"))
    if unsettled:
        out.append({"key": "payout", "label": "Agla payout", "due": world.next_settlement.isoformat(), "amount": sum(t["amount"] for t in unsettled) - netted,
                    "note": "T+1 · Kavach confirm karega ki bank mein pahuncha" if not world.settlement_config.get("paused") else "Paytm ke paas surakshit rahega (hold)", "tone": "ok"})
    for d in world.disputes:
        if d["status"] == "OPEN":
            out.append({"key": d["dispute_id"], "label": "Chargeback ka jawab", "due": d["respond_by"], "amount": d["amount"],
                        "note": "Jawab nahi to paisa katega", "tone": "bad"})
        elif d["status"] == "REPRESENTED":
            out.append({"key": d["dispute_id"], "label": "Chargeback ka faisla", "due": d["decide_at"], "amount": d["amount"], "note": "Jawab waqt par gaya", "tone": "wait"})
    for r in world.refunds:
        if r["status"] == "PENDING":
            out.append({"key": r["refund_id"], "label": "Refund customer tak", "due": r["resolve_at"].isoformat(), "amount": r["amount"], "note": "Kavach pahunchne tak dekhega", "tone": "wait"})
    for i in engine.incidents.values():
        ev = i.facts.get("case_events", {}) if i.status not in LIVE else {}
        if ev.get("bank_complaint"):
            due = date.fromisoformat(ev["bank_complaint"]["date"]) + timedelta(days=7)
            out.append({"key": f"{i.id}-bank7", "label": "Bank ke 7 din", "due": datetime.combine(due, datetime.min.time()).isoformat(), "amount": None,
                        "note": "SOP 10.1(a) · 5ve aur 7ve din Kavach check karega", "tone": "wait"})
    for c in out:
        secs = (datetime.fromisoformat(c["due"]) - world.now).total_seconds()
        c["secs_left"] = max(0, int(secs))
    return sorted(out, key=lambda c: c["secs_left"])


def _chargeback(world, engine, inc) -> dict[str, Any]:
    f = inc.facts
    d = next(x for x in world.disputes if x["dispute_id"] == f["dispute_id"])
    pend = (inc.pending or {}).get("action") == "submit_dispute_response"
    proven = [{"label": e["label"], "tier": e["tier"], "ok": True} for e in f.get("dispute_evidence", [])]
    proven.append({"label": "Saman diya gaya (koi record yeh nahi dikha sakta)", "tier": "Meena", "ok": bool((d.get("response") or {}).get("merchant_attests_handover"))})
    state = d["status"]
    steps = [
        {"key": "detect", "label": "Paytm ne pakda", "sub": f"Dispute desk par chargeback · {_hm(d['raised_at'])}", "state": "done"},
        {"key": "proof", "label": "Saboot ikattha", "sub": "Payment aur bill, Paytm record se", "state": "done" if proven else "todo"},
        {"key": "ask", "label": "Aapka jawab", "sub": "Kya aapne saman diya tha?", "state": "now" if pend else "done"},
        {"key": "reply", "label": "Deadline se pehle jawab", "sub": f"{_hm(d['respond_by'], world.now)} tak", "state": "done" if state in ("REPRESENTED", "WON", "LOST") else ("blocked" if state == "DEEMED_VALID" else "todo")},
        {"key": "decision", "label": "Bank ka faisla", "sub": {"WON": "Aapke haq mein", "LOST": "Customer ke haq mein"}.get(state, "Kavach nazar rakhega"),
         "state": "done" if state in ("WON", "LOST") else ("now" if state == "REPRESENTED" else "todo")},
    ]
    action = None
    if pend:
        action = {"kind": "approve", "incident": inc.id, "title": "Kya aapne saman diya tha?",
                  "body": f"Payment aur bill ka saboot Kavach ke paas hai. Saman dene ka saboot sirf aapki baat hai, aur woh aapke naam se jayegi. Nahi diya, to Kavach chargeback maan lega.",
                  "cta": "Haan, saman diya tha", "secondary": "Nahi diya"}
    titles = {"OPEN": f"Chargeback · {_rs(d['amount'])}", "REPRESENTED": "Jawab chala gaya", "WON": f"{_rs(d['amount'])} aapka raha", "ACCEPTED": "Chargeback maana", "DEEMED_VALID": "Deadline nikal gayi"}
    return {"mode": "case", "case": "chargeback", "incident": inc.id,
            "shield": {"tone": "bad" if state == "OPEN" else "ok", "title": titles.get(state, "Chargeback"), "account": d["dispute_id"],
                       "sub": {"OPEN": f"Customer ke bank ka kehna hai: \"{d['reason']}\". {_hm(d['respond_by'], world.now)} tak jawab nahi diya to {_rs(d['amount'])} agle payout se katega. Kavach ne {_hm(d['raised_at'])} par pakda.",
                               "REPRESENTED": f"Payment ka record, bill aur aapki baat, deadline se pehle chali gayi. Bank ka faisla aate hi Kavach batayega.",
                               "WON": "Jawab waqt par gaya aur faisla aapke haq mein aaya.",
                               "ACCEPTED": "Aapne bataya saman nahi diya tha. Kavach ne galat jawab nahi diya; paisa customer ko wapas.",
                               "DEEMED_VALID": "Jawab deadline tak nahi gaya, isliye chargeback maana gaya."}.get(state, "")},
            "stake": {"amount": d["amount"], "due": d["respond_by"], "replied": state in ("REPRESENTED", "WON", "LOST"),
                      "secs_left": max(0, int((datetime.fromisoformat(d["respond_by"]) - world.now).total_seconds()))},
            "proof": proven, "money": [], "ratio": None, "steps": steps, "action": action, "docs": [], "clocks": clocks(world, engine), "headline": inc.headline}


def _home(world, engine) -> dict[str, Any]:
    today = world.now.date()
    sales = [t for t in world.transactions if t["status"] == "SUCCESS" and t["payee_vpa"] == MERCHANT["vpa"] and t["created_at"].date() == today]
    fixes = [i for i in engine.incidents.values() if i.kind not in ("freeze", "chargeback") and not _guarded(i)]
    return {
        "mode": "home",
        "shield": {"tone": "ok", "title": "Sab theek hai", "sub": "Kavach har payment, refund aur payout par nazar rakh raha hai."},
        "today": {"sales": sum(t["amount"] for t in sales), "count": len(sales), "next_payout": world.next_settlement.isoformat()},
        "clocks": clocks(world, engine),
        "feed": [{"title": i.title, "text": i.headline or "", "state": "done" if i.status == "resolved" else "working", "at": i.updated_at}
                 for i in sorted(fixes, key=lambda i: i.updated_at, reverse=True)[:4]],
    }


def _neutral(inc) -> dict[str, Any]:
    """P17: nothing about a freeze, a notice or a report. The same words Legal approved for the message."""
    return {"mode": "neutral", "incident": inc.id,
            "shield": {"tone": "wait", "title": "Payout mein rukawat", "sub": "Paytm ki team jald aapse baat karegi. Tab tak aapka paisa Paytm ke paas surakshit hai."}}


def _needs_meena(i) -> bool:
    return "merchant" in ((i.pending or {}).get("approvers") or [])


def build(world, engine) -> dict[str, Any]:
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
        money.append({"key": "locked", "label": "Bank mein ruka hua", "en": "Frozen at your bank", "amount": locked, "source": "aapka bataya hua · unverified", "tone": "bad"})
    if disputed_txn:
        money.append({"key": "disputed", "label": "Police ka vivadit", "en": "Disputed by police", "amount": disputed_txn["amount"], "source": "Paytm record", "tone": "warn"})
    safe = _safe_with_paytm(world)
    if safe:
        money.append({"key": "safe", "label": "Paytm ke paas surakshit", "en": "Safe with Paytm", "amount": safe, "source": "held payouts", "tone": "good"})
    ratio = round(locked / disputed_txn["amount"]) if locked and disputed_txn and locked > disputed_txn["amount"] else None

    # ---- the tracker
    intake = next((s for s in inc.steps if s["kind"] == "intake"), None)
    pend = inc.pending or {}
    pend_action = pend.get("action") if "merchant" in (pend.get("approvers") or []) else None
    ev = f.get("case_events", {})
    complaint = (ev.get("bank_complaint") or {}).get("date")
    due = (date.fromisoformat(complaint) + timedelta(days=7)).isoformat() if complaint else None
    notice_in = bool(f.get("notice"))
    steps = [
        {"key": "detect", "label": "Paytm ne pakda", "sub": ("Aapka apna payment bank ne roka (YE)" if own else "Bank ne payout wapas bheja") if f.get("proactive") else "Aapne bataya",
         "state": "done", "at": intake["at"] if intake else inc.created_at},
        {"key": "protect", "label": "Nayi sale surakshit", "sub": "Aap + Paytm Risk ki manzoori se payouts Paytm ke paas",
         "state": "done" if held else ("now" if pend.get("action") == "request_settlement_hold" else "todo")},
        {"key": "notice", "label": "Notice padha", "sub": "Chhupa hua nirdesh nazarandaaz; ek payment mila" if notice_in else "Bank ka SMS ya notice bhejiye",
         "state": "done" if notice_in else ("now" if held or not pend else "todo")},
        {"key": "case", "label": "Signed case taiyaar", "sub": "SOP ke hisaab se, Paytm record se", "state": "done" if f.get("pack") else "todo"},
        {"key": "request", "label": "Hold kam karne ki request", "sub": f"Sirf vivadit rakam tak" if f.get("lien_request") else "Aapke naam se, aapki manzoori se",
         "state": "done" if f.get("lien_request") else ("now" if pend.get("action") == "draft_lien_request" else "todo")},
        {"key": "branch", "label": "Branch mein shikayat", "sub": f"Mili {complaint}" if complaint else "Dated acknowledgement zaroor lijiye",
         "state": "done" if complaint else ("now" if f.get("pack") and not pend_action else "todo")},
        {"key": "bank7", "label": "Bank 7 din mein aage bheje", "sub": f"{due} tak · SOP 10.1(a)" if due else "Shikayat ki tareekh se ginti",
         "state": "now" if due else "todo"},
        {"key": "officer", "label": "Jaanch adhikari ka faisla", "sub": "15 din · bank aur police tay karte hain", "state": "todo"},
    ]
    if f.get("conflict") or (inc.decisive or {}).get("text", "").startswith("Notice says"):
        for s in steps:
            if s["key"] == "case":
                s.update({"state": "blocked", "sub": "Notice aur Paytm record mein rakam alag. Galat pack nahi banega."})

    # ---- the one thing to do next
    action: dict[str, Any] | None = None
    if pend_action == "request_settlement_hold":
        action = {"kind": "approve", "incident": inc.id, "title": "Aaj ki sale Paytm ke paas surakshit rakhein?",
                  "body": ("Payouts us account mein ja rahe hain jahan se aap nikal nahi sakti." if debit else "Aapka bank payouts wapas bhej raha hai.") +
                          " Kisi doosre account mein kuch nahi jayega. Paytm Risk bhi manzoori dega.",
                  "cta": "Haan, surakshit rakho", "secondary": "Abhi nahi"}
    elif pend_action == "draft_lien_request":
        action = {"kind": "approve", "incident": inc.id, "title": f"Bank ko request: hold sirf {_rs(disputed_txn['amount']) if disputed_txn else 'vivadit rakam'} tak",
                  "body": "Aapke naam se. Paytm record ki rakam, SOP aur High Court ke faisle saath mein. Aap padh kar hi bhejengi.",
                  "cta": "Request taiyaar karo", "secondary": "Abhi nahi"}
    elif not notice_in and not _guarded(inc):
        action = {"kind": "notice", "incident": inc.id, "title": "Bank ka SMS ya notice bhejiye",
                  "body": "Branch se teen cheezein maangiye: NCRP number, police ka notice, aur kitni rakam vivadit hai.", "cta": "Photo bhejo"}
    elif f.get("pack") and not complaint:
        action = {"kind": "branch", "incident": inc.id, "title": "Kal branch jaiye",
                  "body": "Likhit shikayat, signed pack aur request saath le jaiye. Dated acknowledgement zaroor lijiye: wahi se bank ke 7 din chalte hain.",
                  "cta": "Bank ne complaint le li ✓"}
    elif due:
        left = (date.fromisoformat(due) - world.now.date()).days
        action = {"kind": "wait", "incident": inc.id, "title": f"Bank ke paas {max(left, 0)} din",
                  "body": f"{due} tak bank ko aapki shikayat aage bhejni hai. Kavach 5ve aur 7ve din khud check karega.", "days_left": left}

    docs = []
    if f.get("pack"):
        docs.append({"kind": "pack", "label": "Signed evidence pack", "sub": "Bank ise 10 second mein verify kar sakta hai",
                     "href": f"/pack/{f['pack']['token']}.pdf", "verify": f["pack"]["verify_url"]})
    if f.get("lien_request"):
        docs.append({"kind": "letter", "label": "Hold kam karne ki request", "sub": f"Sirf {f['lien_request']['disputed_text']} tak · aapke naam se", "text": f["lien_request"]["en"]})

    title = "Account freeze" + (" · debit" if debit else "")
    sub = (f"{'Aapka bank paisa nikalne nahi de raha' if debit else 'Aapke bank ne payout lauta diya'}. Kavach ne {_hm(inc.created_at)} par pakda"
           + (", aapke kisi ko batane se pehle." if f.get("proactive") else "."))
    return {"mode": "case", "incident": inc.id,
            "shield": {"tone": "bad", "title": title, "sub": sub, "account": "XX4471"},
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
    t = d.strftime("%-I:%M %p").lower()
    if now and d.date() != now.date():
        return ("kal " if d.date() == now.date() + timedelta(days=1) else d.strftime("%-d %b ")) + t
    return t
