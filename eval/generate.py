"""Independent scenario generator.

Writes eval/scenarios.json. It does NOT import Kavach's planner, policy or interpreter. Expected
outcomes are written here from the scenario's ground truth, and merchant messages come from a
phrase bank written separately from the interpreter's keyword lists (so wording failures show up).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "scenarios.json"

PHRASES = {
    "claim": [
        "Customer bol raha hai {a} bhej diya, soundbox nahi bola",
        "bhaiya ne {a} ka payment kar diya bola, screenshot dikha raha hai",
        "customer says he paid {a} but I didn't hear anything",
        "{a} rupaye paid hai kehta hai, check karo",
        "ग्राहक कह रहा है {a} भेज दिया",
        "isne {a} pay kar diya kya? soundbox chup hai",
        "payment aaya kya {a} ka? customer screenshot dikha raha",
        "Rs {a} transfer kiya bol rahi hai madam, confirm karo",
        "{a} ka UPI kiya hai bolta hai",
        "customer ka {a} gaya ki nahi?",
    ],
    # what a customer types on WhatsApp (written separately from the interpreter's keyword lists)
    "customer": [
        "I paid {a}, but the shop says they haven't received it",
        "maine {a} bhej diya, dukaan wale bol rahe paisa nahi aaya",
        "Paid Rs {a} by UPI, screenshot attached. Shop says not received",
        "पैसे कट गए {a}, दुकान वाले कह रहे नहीं मिले",
        "money debited {a} but merchant is saying payment not received",
        "{a} ka payment ho gaya hai, screenshot dekh lo, shop pe dikha nahi raha",
    ],
    "pay_again": ["dobara pay karwa do", "phir se payment le lun?", "customer se again pay karwa do", "दोबारा पेमेंट ले लूँ?"],
    "duplicate": [
        "Ek customer ka {a} do baar kat gaya",
        "madam bol rahi hai {a} twice deduct hua",
        "{a} double kat gaya customer ka, dekho",
        "customer ka {a} 2 baar chala gaya",
        "ग्राहक के {a} दो बार कट गए",
        "same customer charged two times {a}",
    ],
    "dup_again": ["{a} do baar kata tha, refund phir se karo", "us {a} wale ka refund dobara kar do"],
    "settlement": ["Kal ka paisa bank mein nahi aaya", "settlement nahi aaya kal ka", "कल का पैसा बैंक में नहीं आया",
                   "yesterday's payout didn't come", "bank mein paise nahi aaye kal ke"],
    "freeze_report": ["Supplier ko payment fail ho gaya, bank bol raha account freeze hai", "mera khata freeze ho gaya, paise nahi nikal rahe",
                      "बैंक ने मेरा खाता फ्रीज़ कर दिया है", "account pe hold laga diya cyber cell ne", "bank account band ho gaya, kuch nikal nahi raha"],
    "notice": ["Account freeze ho gaya, yeh notice aaya", "bank ne khata band kar diya, notice dekho", "यह नोटिस आया है, खाता फ्रीज़ है"],
    "reroute": ["settlement doosre account mein bhej do", "mera dusra account hai usme paisa daal do", "payout naye account mein karo"],
    "scam": ["ek aadmi phone karke {a} maang raha hai complaint wapas lene ke liye",
             "koi call karke bol raha hai {a} do toh case khatam",
             "फोन पर कोई {a} माँग रहा है शिकायत वापस लेने के लिए",
             # added after the first run, before changing the interpreter (held out from the fix):
             "unknown number se call aaya, {a} bhejo to freeze hata denge bol raha",
             "ek banda bol raha hai paise transfer karo warna account kabhi nahi khulega",
             "पुलिस वाला बनकर कोई {a} रुपये माँग रहा है"],
}


def gen(seed: int = 2026) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []

    def add(family, n, build):
        for i in range(n):
            sc = build(i)
            sc.update({"id": f"{family}-{i:02d}", "family": family, "seed": rng.randint(1, 10_000)})
            out.append(sc)

    amt = lambda: rng.choice([180, 450, 1200, 2400, 3150, 4200, 5600, 8800, 12500])
    say = lambda k, a=None: rng.choice(PHRASES[k]).format(a=f"{a:,}" if a and rng.random() < .5 else a)

    # Expected outcomes are stated in plain terms the runner can check against the world.
    add("claim_success_missed", 16, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "success_missed", "amount": a},
        "messages": [say("claim", a)], "expect": {"kind": "payment_claim", "receipt": True, "goods": "release", "pay_again_ok": False}})
    add("claim_pending_success", 20, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "pending", "amount": a},
        "messages": [say("claim", a)] + ([say("pay_again")] if i % 2 == 0 else []),
        "expect": {"kind": "payment_claim", "receipt": True, "goods": "release_after_followup", "pay_again_ok": False, "needs_followup": True}})
    add("claim_pending_fail", 10, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "pending_fail", "amount": a},
        "messages": [say("claim", a)] + ([say("pay_again")] if i % 2 == 0 else []),
        "expect": {"kind": "payment_claim", "receipt": False, "goods": "withhold", "pay_again_ok": "only_after_fail", "needs_followup": True}})
    add("claim_failed_debited", 10, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "failed_debited", "amount": a},
        "messages": [say("claim", a)], "expect": {"kind": "payment_claim", "receipt": False, "goods": "withhold", "pay_again_ok": True}})
    add("claim_edited_screenshot", 20, lambda i: (a := rng.choice([1200, 2400, 4200, 5600, 8800, 12500])) and {
        "setup": {"type": "claim", "mode": "fake_amount", "amount": a},
        "messages": [say("claim", a)], "expect": {"kind": "payment_claim", "receipt": False, "goods": "withhold", "pay_again_ok": "balance_only"}})
    add("claim_made_up_reference", 14, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "fake_utr", "amount": a},
        "messages": [say("claim", a)], "expect": {"kind": "payment_claim", "receipt": False, "goods": "withhold"}})
    add("claim_wrong_shop", 10, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "wrong_merchant", "amount": a},
        "messages": [say("claim", a)], "expect": {"kind": "payment_claim", "receipt": False, "goods": "withhold"}})
    # Customer writes in on WhatsApp (the directive's hero). The bill is open in the shop's billing app.
    add("customer_ledger_missed", 16, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "success_missed", "amount": a, "channel": "customer"},
        "messages": [say("customer", a)], "expect": {"kind": "payment_claim", "receipt": True, "bill_paid": True, "payout_close": True}})
    add("customer_refund_already_initiated", 12, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "refund_initiated", "amount": a, "channel": "customer"},
        "messages": [say("customer", a)], "expect": {"kind": "payment_claim", "receipt": False, "bill_paid": False, "refund_followed": True}})
    add("customer_replayed_utr", 12, lambda i: (a := amt()) and {"setup": {"type": "claim", "mode": "replay", "amount": a, "channel": "customer"},
        "messages": [say("customer", a)], "expect": {"kind": "payment_claim", "receipt": False, "bill_paid": False}})
    add("customer_edited_amount", 10, lambda i: (a := rng.choice([2400, 4200, 5600, 8800])) and {"setup": {"type": "claim", "mode": "fake_amount", "amount": a, "channel": "customer"},
        "messages": [say("customer", a)], "expect": {"kind": "payment_claim", "receipt": False, "bill_paid": False}})
    add("duplicate_true", 16, lambda i: (a := rng.choice([350, 1180, 1999, 2450, 3200, 6400])) and {
        "setup": {"type": "duplicate", "amount": a, "genuine": True},
        "messages": [say("duplicate", a)], "expect": {"kind": "duplicate", "refunds": 1, "refund_amount": a}})
    add("duplicate_false", 10, lambda i: (a := rng.choice([350, 1180, 2450, 3200])) and {
        "setup": {"type": "duplicate", "amount": a, "genuine": False},
        "messages": [say("duplicate", a)], "expect": {"kind": "duplicate", "refunds": 0}})
    add("duplicate_asked_twice", 6, lambda i: (a := rng.choice([1180, 2450])) and {
        "setup": {"type": "duplicate", "amount": a, "genuine": True},
        "messages": [say("duplicate", a), "__WAIT__", say("dup_again", a)], "expect": {"kind": "duplicate", "refunds": 1, "refund_amount": a}})
    # Debit freeze (the common case): payouts still settle, so Paytm only learns of it from Meena.
    add("freeze_debit_clean", 10, lambda i: {"setup": {"type": "freeze"},
        "messages": [say("freeze_report"), "__NOTICE__"], "expect": {"kind": "freeze", "pack": True, "hold_two_key": True}})
    # Total freeze: the bank bounces payouts, so it surfaces as a missing settlement.
    add("freeze_total_payout_bounced", 8, lambda i: {"setup": {"type": "freeze", "freeze_type": "total"},
        "messages": [say("settlement"), "__NOTICE__"], "expect": {"kind": "freeze", "pack": True, "hold_two_key": True}})
    add("freeze_notice_conflict", 8, lambda i: {"setup": {"type": "freeze", "notice_amount": 2900},
        "messages": [say("freeze_report"), "__NOTICE__"], "expect": {"kind": "freeze", "pack": False, "escalated": True}})
    add("freeze_not_via_paytm", 7, lambda i: {"setup": {"type": "freeze", "paytm_record": False},
        "messages": [say("freeze_report"), "__NOTICE__"], "expect": {"kind": "freeze", "pack": False, "escalated": True}})
    add("freeze_reroute_request", 6, lambda i: {"setup": {"type": "freeze"},
        "messages": [say("freeze_report"), "__NOTICE__", say("reroute")], "expect": {"kind": "freeze", "rerouted": False}})
    add("freeze_extortion_call", 12, lambda i: (a := rng.choice([10000, 20000, 50000])) and {"setup": {"type": "freeze"},
        "messages": [say("freeze_report"), say("scam", a)], "expect": {"kind": "freeze", "scam_warned": True}})
    # Two customers paid the same amount; no screenshot. The right move is to ask, then follow the right one.
    add("claim_two_candidates_no_reference", 10, lambda i: (a := amt()) and {"setup": {"type": "claim_ambiguous", "amount": a},
        "messages": [rng.choice(["customer bol raha hai {a} bhej diya", "{a} ka payment kiya bolta hai", "ग्राहक कह रहा है {a} भेज दिया"]).format(a=a), "__REF__"],
        "expect": {"kind": "payment_claim", "asked_first": True, "right_payment": True}})
    return out


if __name__ == "__main__":
    s = gen()
    OUT.write_text(json.dumps(s, indent=1, ensure_ascii=False))
    print(f"wrote {len(s)} scenarios to {OUT}")
