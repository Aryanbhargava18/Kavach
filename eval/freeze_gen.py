"""Independent scenario generator for the freeze watchers.

Writes eval/freeze_scenarios.json. Like generate.py it imports nothing from Kavach's planner, policy or
interpreter; each expected outcome is written from the scenario's ground truth alone.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "freeze_scenarios.json"


def gen(seed: int = 3107) -> list[dict]:
    rng = random.Random(seed)
    out: list[dict] = []

    def add(family: str, n: int, build):
        for i in range(n):
            sc = build()
            sc.update({"id": f"{family}-{i:02d}", "family": family, "seed": rng.randint(1, 10_000)})
            out.append(sc)

    disputed = lambda: rng.choice([450, 999, 1800, 2400, 3150, 6200, 9800])
    locked = lambda: rng.choice([48_000, 1_25_000, 3_10_000, 7_40_000])
    supplier = lambda: rng.choice([3_500, 12_000, 18_000, 26_500])

    # Signal reaches Paytm: total freeze bounces the next payout. Expect a case, a warning, a two-key hold request.
    add("total_freeze_bounce", 30, lambda: {"setup": {"freeze": "total", "bounce_next": True, "disputed": disputed(), "days_ago": rng.randint(5, 60)},
                                             "expect": {"case": True, "warn": True, "hold_proposed": True, "guard": False}})
    # Signal reaches Paytm: debit freeze, her own payment through the Paytm app comes back YE.
    add("debit_freeze_own_payment", 30, lambda: {"setup": {"freeze": "debit", "own_payment": supplier(), "disputed": disputed(), "days_ago": rng.randint(5, 60)},
                                                  "expect": {"case": True, "warn": True, "hold_proposed": True, "guard": False}})
    # No signal reaches Paytm: debit freeze and she hasn't paid anyone through Paytm. Honest blind spot: expect NO case.
    add("debit_freeze_no_signal", 20, lambda: {"setup": {"freeze": "debit", "disputed": disputed(), "days_ago": rng.randint(5, 60), "advance_to_payout": True},
                                                "expect": {"case": False}})
    # Healthy account: payouts settle, her own payment succeeds. Expect no case (false-alarm check).
    add("healthy_account", 30, lambda: {"setup": {"freeze": None, "own_payment": supplier(), "advance_to_payout": True},
                                         "expect": {"case": False}})
    # Risk already holds two independent signals: expect a case but NO case details to the merchant, Risk escalation, no hold request.
    add("mule_flagged", 30, lambda: {"setup": {"freeze": rng.choice(["total", "debit"]), "bounce_next": True, "own_payment": supplier(), "mule": True,
                                               "disputed": disputed(), "days_ago": rng.randint(5, 60)},
                                     "expect": {"case": True, "warn": False, "hold_proposed": False, "guard": True}})
    # Merchant forwards the notice; the notice amount agrees with the Paytm record. Expect pack + lien request for exactly that amount.
    add("notice_agrees", 20, lambda: (d := disputed()) and {"setup": {"freeze": "debit", "disputed": d, "notice": d, "locked": locked(), "days_ago": rng.randint(5, 60)},
                                                            "expect": {"pack": True, "lien_amount": d}})
    # The notice amount disagrees with the record. Expect no pack and no lien request.
    add("notice_conflicts", 20, lambda: (d := disputed()) and {"setup": {"freeze": "debit", "disputed": d, "notice": d + rng.choice([100, 500, 1000]), "days_ago": rng.randint(5, 60)},
                                                               "expect": {"pack": False}})
    # Chargeback clock. Silence past the deadline = deemed valid. Expected outcomes depend only on Meena's answer.
    add("chargeback_handed_over", 20, lambda: {"setup": {"chargeback": True, "hours": rng.choice([6, 12, 22, 40]), "answer": "yes"},
                                               "expect": {"replied_before_deadline": True, "attested_only_by_meena": True}})
    add("chargeback_not_handed_over", 20, lambda: {"setup": {"chargeback": True, "hours": rng.choice([6, 12, 22, 40]), "answer": "no"},
                                                   "expect": {"accepted": True, "no_reply_filed": True}})
    add("chargeback_no_answer", 20, lambda: {"setup": {"chargeback": True, "hours": rng.choice([8, 12, 22]), "answer": None},
                                             "expect": {"no_reply_filed": True, "reminded": True}})
    return out


if __name__ == "__main__":
    sc = gen()
    OUT.write_text(json.dumps(sc, indent=1))
    print(f"wrote {len(sc)} freeze scenarios to {OUT}")
