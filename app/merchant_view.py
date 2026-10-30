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


def _home(world, engine) -> dict[str, Any]:
    today = world.now.date()
    sales = [t for t in world.transactions if t["status"] == "SUCCESS" and t["payee_vpa"] == MERCHANT["vpa"] and t["created_at"].date() == today]
    fixes = [i for i in engine.incidents.values() if i.kind != "freeze" and not _guarded(i)]
    return {
        "mode": "home",
        "shield": {"tone": "ok", "title": "Sab theek hai", "sub": "Kavach har payment, refund aur payout par nazar rakh raha hai."},
        "today": {"sales": sum(t["amount"] for t in sales), "count": len(sales), "next_payout": world.next_settlement.isoformat()},
        "feed": [{"title": i.title, "text": i.headline or "", "state": "done" if i.status == "resolved" else "working", "at": i.updated_at}
                 for i in sorted(fixes, key=lambda i: i.updated_at, reverse=True)[:4]],
    }


def _neutral(inc) -> dict[str, Any]:
    """P17: nothing about a freeze, a notice or a report. The same words Legal approved for the message."""
    return {"mode": "neutral", "incident": inc.id,
            "shield": {"tone": "wait", "title": "Payout mein rukawat", "sub": "Paytm ki team jald aapse baat karegi. Tab tak aapka paisa Paytm ke paas surakshit hai."}}


def build(world, engine) -> dict[str, Any]:
    live = [i for i in engine.incidents.values() if i.kind in ("freeze", "settlement") and i.status not in LIVE]
    inc = live[-1] if live else None
    if inc is None:
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
            "headline": inc.headline}


def _rs(n: int | None) -> str:
    from .planner_offline import rs
    return rs(n)


def _hm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%-I:%M %p").lower()
    except ValueError:
        return iso
