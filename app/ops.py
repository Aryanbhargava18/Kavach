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
import re
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

# Banks and ops teams never send the same file twice: headers change case, columns get renamed, Excel adds a BOM,
# amounts arrive as "₹1,240.00", and many banks send a sentence instead of a code. All of that lands here.
ALIASES = {
    "merchant_id": ["merchant_id", "mid", "merchant", "merchant_code", "merchantid", "mer_id", "beneficiary_id", "id"],
    "merchant_name": ["merchant_name", "name", "beneficiary_name", "bene_name", "shop", "shop_name", "business_name"],
    "city": ["city", "town", "location"],
    "lang": ["lang", "language", "app_language", "preferred_language"],
    "batch_id": ["batch_id", "batch", "settlement_id", "utr", "payout_id", "reference", "ref", "ref_no", "txn_ref"],
    "business_date": ["business_date", "date", "settlement_date", "value_date"],
    "amount": ["amount", "amt", "payout_amount", "value", "settlement_amount", "rs", "inr"],
    "return_code": ["return_code", "code", "reason_code", "rc", "status_code"],
    "return_reason": ["return_reason", "reason", "remarks", "description", "bank_remarks", "narration", "status"],
    "risk_signals": ["risk_signals", "risk", "risk_score", "signals"],
}
# Free-text reason -> code. Order matters: "closed" must win over "account", "inoperative" over "invalid".
KEYWORDS = [
    ("R-FRZ", r"freez|frozen|block|debit\s*freeze|lien|attach|hold\s*by\s*(police|court|order)|cyber|lea\b|1930"),
    ("R-DOR", r"dormant|inoperat|inactive|kyc\s*(expir|lapse|pending|not\s*updated)|re-?kyc"),
    ("R-CLS", r"closed|close\b|account\s*clos"),
    ("R-NAM", r"name\s*mismatch|name\s*does\s*not\s*match|beneficiary\s*name|name\s*not\s*match"),
    ("R-INV", r"invalid|incorrect|wrong|does\s*not\s*exist|no\s*such|not\s*found|ifsc"),
]
LANG_NAMES = {"hindi": "hi", "english": "en", "tamil": "ta", "telugu": "te", "marathi": "mr", "bengali": "bn", "bangla": "bn",
              "gujarati": "gu", "kannada": "kn", "हिंदी": "hi", "हिन्दी": "hi"}


def _key(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (h or "").replace("\ufeff", "").strip().lower()).strip("_")


def _columns(fieldnames: list[str]) -> dict[str, str]:
    """Map each canonical field to the header the file actually used."""
    norm = {_key(h): h for h in fieldnames if h}
    out = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in norm and norm[n] not in out.values():
                out[field] = norm[n]
                break
    return out


def _reader(text: str) -> csv.DictReader:
    text = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return csv.DictReader(io.StringIO(text), dialect=dialect)


def amount(v: Any) -> int:
    """"₹1,240.00", "Rs. 1240", "1 240", "1240/-" -> 1240. Unreadable -> 0 (and the row goes to a human)."""
    s = re.sub(r"(?i)rs\.?|inr|₹|/-|\s", "", str(v or "")).replace(",", "")
    m = re.search(r"-?\d+(\.\d+)?", s)
    return int(float(m.group())) if m else 0


def code_for(code: str, reason: str) -> tuple[str, str]:
    """A known code wins; otherwise read the bank's words. Returns (code, how) where how is 'code', 'text' or ''."""
    c = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    for k in ROUTES:
        if c and c == k.replace("-", ""):
            return k, "code"
    text = f"{code or ''} {reason or ''}".lower()
    for k, pat in KEYWORDS:
        if re.search(pat, text):
            return k, "text"
    return (code or "").strip().upper(), ""


def _lang(v: str) -> str:
    v = (v or "").strip().lower()
    return LANG_NAMES.get(v, v[:2] if v else "en")


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
    reader = _reader(csv_text)
    col = _columns(reader.fieldnames or [])
    if "merchant_id" not in col or ("return_code" not in col and "return_reason" not in col):
        need = [n for n, ok in (("merchant ID", "merchant_id" in col), ("return code or reason", "return_code" in col or "return_reason" in col)) if not ok]
        return {"error": f"Couldn't find a column for: {', '.join(need)}. Columns seen: {', '.join(h for h in (reader.fieldnames or []) if h) or 'none'}"}
    cases, skipped, unknown, alerts, blank, read_text = [], 0, [], {}, 0, 0
    for raw in reader:
        row = {f: str(raw.get(h) or "").strip() for f, h in col.items()}
        if not row.get("merchant_id"):
            if any(str(v or "").strip() for v in raw.values() if not isinstance(v, list)):
                cases.append({**_base(row), "merchant_id": "—", "route": "human", "label": "No merchant ID on this row", "action": "Hand to Paytm Ops: row has no merchant ID", "guarded": False, "message": None})
            else:
                blank += 1
            continue
        row.setdefault("batch_id", "")
        key = (row["merchant_id"].upper(), row["batch_id"].upper() or row.get("business_date", ""))
        if key in seen:                       # idempotent: the same return never opens two cases
            skipped += 1
            continue
        seen.add(key)
        code, how = code_for(row.get("return_code", ""), row.get("return_reason", ""))
        read_text += how == "text"
        row["return_code"] = code
        r = ROUTES.get(code)
        if not r:
            unknown.append(row["merchant_id"])
            cases.append({**_base(row), "route": "human", "label": f"Unrecognised: {(row.get('return_reason') or code or '—')[:60]}", "action": "Hand to Paytm Ops: reason not recognised", "guarded": False, "message": None})
            continue
        try:
            risk = int(float(row.get("risk_signals") or 0))
        except ValueError:
            risk = 0
        guarded = r["route"] == "freeze" and risk >= 2     # P17, per merchant
        lang = _lang(row.get("lang", ""))
        msg_lang = "hi" if lang == "hi" else "en"          # this build ships English and Hindi; other languages queue with English until translated
        message = NEUTRAL[msg_lang] if guarded else r["msg_" + msg_lang]
        alerts[lang] = alerts.get(lang, 0) + 1
        cases.append({**_base(row), "lang": lang, "route": "risk_edd" if guarded else r["route"], "label": r["label"], "guarded": guarded,
                      "read_from": how, "action": "Neutral message only; Paytm Risk EDD decides (P17)" if guarded else r["action"],
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
                                         "blank_rows": blank, "read_from_text": read_text,
                                         "per_return_ms": round(ms / max(1, len(cases)), 3)}}


def _base(row: dict[str, str]) -> dict[str, Any]:
    return {"merchant_id": row.get("merchant_id") or "—", "merchant_name": row.get("merchant_name") or row.get("merchant_id") or "—", "city": row.get("city") or "",
            "lang": row.get("lang") or "en", "batch_id": row.get("batch_id") or "", "amount": amount(row.get("amount")), "return_code": row.get("return_code")}
