"""Kavach at Paytm scale: triage a whole day's settlement return file.

Paytm settles every merchant's payout once a day. Banks send back the ones they refuse, each with a reason.
Most returns are NOT freezes: closed accounts, dormant/inoperative accounts (KYC lapsed), wrong account numbers
and name mismatches are far more common, and treating them as freezes would frighten merchants for nothing.
So each reason gets its own route, the tipping-off guard runs per merchant, opening is idempotent per
(merchant, batch), and every alert is queued in that merchant's own language.

The input is a CSV with one row per returned payout (or a synthetic day generated here). Reason codes are
SYNTHETIC, modelled on how NEFT/IMPS returns are described; a real integration maps the bank's codes onto these.
"""
from __future__ import annotations

import csv
import io
import random
import time
from datetime import date
from typing import Any

FIELDS = ["merchant_id", "merchant_name", "city", "lang", "batch_id", "business_date", "amount", "return_code", "return_reason", "risk_signals"]

# reason code -> route. Only one of these is a freeze.
ROUTES = {
    "R-FRZ": {"route": "freeze", "label": "Account blocked/frozen", "action": "Open a freeze case: warn the merchant, propose a two-key payout hold, build the SOP case",
              "msg_en": "Your bank returned today's payout: it says your account is frozen. Kavach has opened your case. Kavach never asks for OTP or money.",
              "msg_hi": "आपके बैंक ने आज का पेआउट लौटा दिया: बैंक के अनुसार आपका खाता फ्रीज़ है। कवच ने आपका केस खोल दिया है। कवच कभी OTP या पैसे नहीं माँगता।"},
    "R-DOR": {"route": "dormant", "label": "Dormant / inoperative account", "action": "Hold the payout safely; ask the merchant to re-do KYC at the branch to reactivate the account",
              "msg_en": "Your bank says your account is inoperative (often a lapsed KYC). Your payout is safe with Paytm. Visit your branch to update KYC; Kavach will retry automatically.",
              "msg_hi": "आपके बैंक के अनुसार आपका खाता निष्क्रिय है (अक्सर KYC पुराना होने से)। आपका पेआउट पेटीएम के पास सुरक्षित है। शाखा जाकर KYC अपडेट कीजिए; कवच अपने-आप दोबारा भेजेगा।"},
    "R-CLS": {"route": "bank_details", "label": "Account closed", "action": "Hold the payout safely; ask the merchant to add a new settlement account (Paytm Ops verifies)",
              "msg_en": "Your bank says this account is closed. Your payout is safe with Paytm. Add your new bank account in the app; Paytm will verify it and send the money.",
              "msg_hi": "आपके बैंक के अनुसार यह खाता बंद है। आपका पेआउट पेटीएम के पास सुरक्षित है। ऐप में नया बैंक खाता जोड़िए; पेटीएम जाँच कर पैसा भेज देगा।"},
    "R-INV": {"route": "bank_details", "label": "Invalid account number / IFSC", "action": "Hold the payout safely; ask the merchant to correct the account number or IFSC (Paytm Ops verifies)",
              "msg_en": "Your bank couldn't find this account number or IFSC. Your payout is safe with Paytm. Please check and correct your bank details in the app.",
              "msg_hi": "बैंक को यह खाता नंबर या IFSC नहीं मिला। आपका पेआउट पेटीएम के पास सुरक्षित है। ऐप में अपनी बैंक जानकारी जाँचकर ठीक कीजिए।"},
    "R-NAM": {"route": "kyc_name", "label": "Beneficiary name mismatch", "action": "Hold the payout safely; route to KYC to match the account holder's name",
              "msg_en": "The name on your bank account doesn't match your Paytm profile. Your payout is safe with Paytm. Kavach has asked the KYC team to help you fix it.",
              "msg_hi": "आपके बैंक खाते का नाम पेटीएम प्रोफ़ाइल से मेल नहीं खाता। आपका पेआउट पेटीएम के पास सुरक्षित है। कवच ने KYC टीम से मदद माँगी है।"},
}
NEUTRAL = {"en": "There's a delay with your payout. The Paytm team will contact you soon. Until then your money is safe with Paytm.",
           "hi": "आपके पेआउट में थोड़ी देरी है। पेटीएम की टीम जल्द आपसे बात करेगी। तब तक आपका पैसा पेटीएम के पास सुरक्षित है।"}

CITIES = ["Lucknow", "Patna", "Jaipur", "Indore", "Kanpur", "Varanasi", "Bhopal", "Surat", "Nagpur", "Agra", "Ranchi", "Pune", "Delhi", "Noida", "Bengaluru", "Chennai"]
NAMES = ["Kirana Store", "General Store", "Medical", "Sweets", "Mobile Centre", "Dairy", "Hardware", "Tea Stall", "Fruits & Veg", "Garments", "Pan Shop", "Bakery"]
OWNERS = ["Meena", "Ramesh", "Sunita", "Imran", "Kavita", "Arjun", "Farah", "Deepak", "Pooja", "Sanjay", "Asha", "Manoj", "Neha", "Vikas", "Ritu", "Salim"]
LANGS = ["hi"] * 6 + ["en"] * 3 + ["ta", "te", "mr", "bn", "gu", "kn"]   # merchants' chosen app language


def sample_file(payouts: int = 5000, seed: int = 31) -> tuple[str, dict[str, Any]]:
    """One synthetic day: N payouts, of which ~1.5% come back, with a realistic mix of reasons (freezes are a minority)."""
    rng = random.Random(seed)
    today = date(2026, 10, 31).isoformat()
    mix = [("R-DOR", 34), ("R-CLS", 18), ("R-INV", 16), ("R-NAM", 12), ("R-FRZ", 20)]
    n_ret = max(1, round(payouts * 0.015))
    codes = [c for c, w in mix for _ in range(w)]
    rows = [{"merchant_id": "MEENAKIRANA0417", "merchant_name": "Meena Kirana Store", "city": "Lucknow", "lang": "hi", "batch_id": "STL-20261031-046",
             "business_date": today, "amount": 4580, "return_code": "R-FRZ", "return_reason": ROUTES["R-FRZ"]["label"], "risk_signals": 0}]
    seen = {"MEENAKIRANA0417"}
    while len(rows) < n_ret:
        mid = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(6)) + str(rng.randint(1000, 9999))
        if mid in seen:
            continue
        seen.add(mid)
        code = rng.choice(codes)
        rows.append({"merchant_id": mid, "merchant_name": f"{rng.choice(OWNERS)} {rng.choice(NAMES)}", "city": rng.choice(CITIES), "lang": rng.choice(LANGS),
                     "batch_id": f"STL-20261031-{rng.randint(100, 999)}", "business_date": today, "amount": rng.choice([380, 760, 1240, 2150, 3480, 5600, 8900, 14200, 26500]),
                     "return_code": code, "return_reason": ROUTES[code]["label"],
                     "risk_signals": (2 if rng.random() < 0.15 else rng.choice([0, 0, 0, 1])) if code == "R-FRZ" else 0})
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue(), {"payouts": payouts, "returns": len(rows), "business_date": today}


def triage(csv_text: str, seen: set | None = None, payouts: int | None = None) -> dict[str, Any]:
    """Route every returned payout. Pure and deterministic: same file in, same decisions out; reprocessing a file opens nothing twice."""
    t0 = time.perf_counter()
    seen = seen if seen is not None else set()
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = [f for f in ("merchant_id", "batch_id", "amount", "return_code") if f not in (reader.fieldnames or [])]
    if missing:
        return {"error": f"missing columns: {', '.join(missing)}"}
    cases, skipped, unknown, alerts = [], 0, [], {}
    for row in reader:
        key = (row["merchant_id"], row["batch_id"])
        if key in seen:                       # idempotent: the same return never opens two cases
            skipped += 1
            continue
        seen.add(key)
        code = (row.get("return_code") or "").strip().upper()
        r = ROUTES.get(code)
        if not r:
            unknown.append(row["merchant_id"])
            cases.append({**_base(row), "route": "human", "label": f"Unrecognised code {code or '—'}", "action": "Hand to Paytm Ops: unknown return code", "guarded": False, "message": None})
            continue
        guarded = r["route"] == "freeze" and int(row.get("risk_signals") or 0) >= 2     # P17, per merchant
        lang = (row.get("lang") or "en").strip()
        msg_lang = "hi" if lang == "hi" else "en"          # this build ships English and Hindi; other languages queue with English until translated
        message = NEUTRAL[msg_lang] if guarded else r["msg_" + msg_lang]
        alerts[lang] = alerts.get(lang, 0) + 1
        cases.append({**_base(row), "route": "risk_edd" if guarded else r["route"], "label": r["label"], "guarded": guarded,
                      "action": "Neutral message only; Paytm Risk EDD decides (P17)" if guarded else r["action"],
                      "message": message, "message_lang": msg_lang})
    ms = round((time.perf_counter() - t0) * 1000, 1)
    by = {}
    for c in cases:
        by[c["route"]] = by.get(c["route"], 0) + 1
    held = sum(c["amount"] for c in cases if c["route"] != "human")
    return {"cases": cases, "summary": {"returns": len(cases) + skipped, "opened": len(cases), "skipped_duplicates": skipped, "by_route": by,
                                         "freezes": by.get("freeze", 0) + by.get("risk_edd", 0), "not_freezes": sum(v for k, v in by.items() if k not in ("freeze", "risk_edd")),
                                         "guarded": by.get("risk_edd", 0), "unknown_codes": len(unknown), "amount_held_safe": held,
                                         "alerts_by_language": alerts, "payouts_in_file": payouts, "ms": ms,
                                         "per_return_ms": round(ms / max(1, len(cases)), 3)}}


def _base(row: dict[str, str]) -> dict[str, Any]:
    try:
        amt = int(float(row.get("amount") or 0))
    except ValueError:
        amt = 0
    return {"merchant_id": row["merchant_id"], "merchant_name": row.get("merchant_name") or row["merchant_id"], "city": row.get("city") or "",
            "lang": row.get("lang") or "en", "batch_id": row["batch_id"], "amount": amt, "return_code": row.get("return_code")}
