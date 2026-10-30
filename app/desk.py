"""Paytm Risk / PA desk: enhanced due diligence on merchants named in CFCFRMS reports (SOP 9.5(iv)).

Two parts, kept apart on purpose:
  * make_feed(seed)  SIMULATOR. A synthetic queue of frozen merchants. Each carries hidden ground truth
                     (`_truth`: genuine | mule_front | genuine_outlier) used only by the evaluation.
  * assess(m, feed)  KAVACH. Deterministic signals computed from the feed's observable fields. Outcome is
                     Consistent / Insufficient / Escalate for EDD. Escalation needs two or more independent
                     strong signals. It is a review queue for a human, never a guilt finding.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

CITIES = ["Lucknow", "Patna", "Jaipur", "Indore", "Nagpur", "Surat", "Kanpur", "Bhopal", "Agra", "Ranchi", "Varanasi", "Meerut"]
SHOPS = ["Kirana Store", "Mobile Point", "Medical Hall", "Jewellers", "Sweets", "Electronics", "Garments", "Hardware", "Dairy", "Stationers"]
FIRST = ["Raju", "Sharma", "Gupta", "Ansari", "Verma", "Khan", "Patel", "Yadav", "Singh", "Jain", "Mishra", "Das", "Rao"]


def _tok(s: str) -> str:
    return "pyr_" + hashlib.sha256(s.encode()).hexdigest()[:8]     # opaque payer token: payer may be a victim (SOP)


def make_feed(seed: int = 11, n: int = 10, mules: int = 2, outliers: int = 1, include_meena: bool = True) -> dict[str, Any]:
    rng = random.Random(seed)
    merchants: list[dict[str, Any]] = []
    shared_acct = f"XX{rng.randint(1000, 9999)}"
    mule_payers = [_tok(f"mule-payer-{seed}-{i}") for i in range(6)]
    kinds = ["mule_front"] * mules + ["genuine_outlier"] * outliers
    kinds += ["genuine"] * (n - len(kinds) - (1 if include_meena else 0))
    rng.shuffle(kinds)
    if include_meena:
        kinds = ["meena"] + kinds
    for i, kind in enumerate(kinds):
        genuine = kind in ("genuine", "genuine_outlier", "meena")
        name = "Meena Kirana Store" if kind == "meena" else f"{rng.choice(FIRST)} {rng.choice(SHOPS)}"
        typical_payers = rng.randint(25, 70)
        m = {
            "mid": "MEENAKIRANA0417" if kind == "meena" else f"MID{rng.randint(10**7, 10**8 - 1)}",
            "name": name, "city": "Lucknow" if kind == "meena" else rng.choice(CITIES),
            "months_on_paytm": 79 if kind == "meena" else (rng.randint(5, 96) if genuine else rng.choice([1, 2, 3, 14, 26, 40])),
            "typical_daily_payers": typical_payers,
            "settlement_account": f"XX{rng.randint(1000, 9999)}" if genuine else (shared_acct if rng.random() < .6 else f"XX{rng.randint(1000, 9999)}"),
            "frozen_amount": rng.choice([42000, 86000, 125000, 310000, 64000, 198000]) if kind != "meena" else 310000,
        }
        if genuine:
            k = 1 if kind != "genuine_outlier" else rng.randint(1, 2)
            disputed = [{"amount": rng.choice([2400, 560, 1180, 3150, 780, 1999]) if kind != "meena" else 2400,
                         "payer": _tok(f"victim-{seed}-{i}-{j}"), "announced": rng.random() < .93} for j in range(k)]
            payers_24h = int(typical_payers * (rng.uniform(0.8, 1.3) if kind != "genuine_outlier" else rng.uniform(5.5, 8)))  # wedding-season spike
        else:
            # mule fronts vary: careful ones use fresh payers, odd amounts, a quiet day; few trip every signal
            k = rng.randint(3, 7)
            careful_payers, odd_amounts, quiet = rng.random() < .35, rng.random() < .35, rng.random() < .3
            disputed = [{"amount": (rng.choice([9850, 18640, 23710, 12480, 31260]) if odd_amounts else rng.choice([10000, 20000, 25000, 49000, 50000, 15000])),
                         "payer": (_tok(f"fresh-{seed}-{i}-{j}") if careful_payers else rng.choice(mule_payers)),
                         "announced": rng.random() < .35} for j in range(k)]
            payers_24h = int(typical_payers * (rng.uniform(1.5, 4) if quiet else rng.uniform(6, 14)))
        m["disputed"] = disputed
        m["distinct_payers_24h_before_hold"] = payers_24h
        m["disputed_amount"] = sum(d["amount"] for d in disputed)
        m["_truth"] = "genuine" if kind == "meena" else kind
        merchants.append(m)
    # cross-report index: how many CFCFRMS reports each payer token appears in, across the whole feed
    reports: dict[str, int] = {}
    for m in merchants:
        for d in m["disputed"]:
            reports[d["payer"]] = reports.get(d["payer"], 0) + 1
    return {"seed": seed, "merchants": merchants, "payer_reports": reports}


STRONG = ("repeat_reports", "fan_in", "round_amounts", "shared_settlement_account", "new_account")


def assess(m: dict[str, Any], feed: dict[str, Any]) -> dict[str, Any]:
    """Deterministic EDD signals from observable fields only (never reads `_truth`)."""
    sig: list[dict[str, Any]] = []
    rep = max(feed["payer_reports"].get(d["payer"], 0) for d in m["disputed"])
    sig.append({"id": "repeat_reports", "strong": True, "hit": rep >= 2, "para": "9.5(iv)",
                "label": "Same payer in several CFCFRMS reports", "value": f"payer seen in {rep} report{'s' if rep != 1 else ''}"})
    ratio = m["distinct_payers_24h_before_hold"] / max(1, m["typical_daily_payers"])
    sig.append({"id": "fan_in", "strong": True, "hit": ratio >= 5, "label": "Fan-in from unrelated payers before the hold",
                "value": f"{m['distinct_payers_24h_before_hold']} payers in 24 h vs {m['typical_daily_payers']} usual ({ratio:.1f}×)"})
    rounds = sum(1 for d in m["disputed"] if d["amount"] % 1000 == 0 or d["amount"] % 1000 == 999) / len(m["disputed"])
    sig.append({"id": "round_amounts", "strong": True, "hit": rounds >= .6 and len(m["disputed"]) >= 3,
                "label": "Disputed credits mostly round sums", "value": f"{round(100 * rounds)}% of {len(m['disputed'])} credits"})
    shared = [x["mid"] for x in feed["merchants"] if x is not m and x["settlement_account"] == m["settlement_account"]]
    sig.append({"id": "shared_settlement_account", "strong": True, "hit": bool(shared), "label": "Settlement account shared with other merchants",
                "value": f"shared with {len(shared)} other MID{'s' if len(shared) != 1 else ''}" if shared else "not shared"})
    sig.append({"id": "new_account", "strong": True, "hit": m["months_on_paytm"] < 4, "label": "Merchant onboarded recently",
                "value": f"{m['months_on_paytm']} months on Paytm"})
    ann = sum(1 for d in m["disputed"] if d["announced"]) / len(m["disputed"])
    sig.append({"id": "no_counter_activity", "strong": False, "hit": ann < .3, "label": "Few Soundbox announcements on disputed credits",
                "value": f"{round(100 * ann)}% announced (weak signal: a Soundbox is easy to own)"})
    strong = [s for s in sig if s["strong"] and s["hit"]]
    if len(strong) >= 2:
        outcome, action = "Escalate for EDD", "Send to a Paytm Risk reviewer for enhanced due diligence (SOP 9.5(iv)). No guilt is implied."
    elif strong or any(s["hit"] for s in sig):
        outcome, action = "Insufficient", "One signal only. Ask for records; do not escalate on a single signal."
    else:
        outcome, action = "Consistent", "Records agree with an ordinary shop. The merchant can take the bank route with a signed pack."
    return {"mid": m["mid"], "outcome": outcome, "action": action, "signals": sig, "strong_hits": [s["id"] for s in strong]}


def score(feed: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Evaluation only: compare Kavach's outcomes with the simulator's hidden labels."""
    out = {"mules": 0, "mules_escalated": 0, "genuine": 0, "genuine_escalated": 0, "outliers": 0, "outliers_escalated": 0}
    for m in feed["merchants"]:
        esc = results[m["mid"]]["outcome"] == "Escalate for EDD"
        t = m["_truth"]
        if t == "mule_front":
            out["mules"] += 1; out["mules_escalated"] += esc
        elif t == "genuine_outlier":
            out["outliers"] += 1; out["outliers_escalated"] += esc
        else:
            out["genuine"] += 1; out["genuine_escalated"] += esc
    return out


def public(m: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in m.items() if not k.startswith("_")} | {"disputed_count": len(m["disputed"])}
