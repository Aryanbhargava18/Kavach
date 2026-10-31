"""Paytm Payments, for real: the read path Kavach runs against Paytm's own APIs.

Transaction Status (v3/order/status) and Refund Status (v2/refund/status), signed with Paytm's official checksum
library. Defaults to Paytm's staging environment. Everything this module returns is tagged
provenance=PAYTM_STAGING (or PAYTM_PRODUCTION) so the UI and the evidence pack can tell live data from the simulator.

Freeze signals (payout returns, PSP decline codes) and the dispute desk are not exposed to outside developers, so those
stay simulated; this module is the part a judge can check against Paytm today.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import httpx

HOSTS = {"staging": "https://securestage.paytmpayments.com", "production": "https://secure.paytmpayments.com"}
STATUS = {"TXN_SUCCESS": "SUCCESS", "PENDING": "PENDING", "TXN_FAILURE": "FAILED"}


def env() -> str:
    return "production" if os.environ.get("PAYTM_ENV", "staging").lower() == "production" else "staging"


def configured() -> bool:
    return bool(os.environ.get("PAYTM_MID") and os.environ.get("PAYTM_MERCHANT_KEY"))


def provenance() -> str:
    return "PAYTM_PRODUCTION" if env() == "production" else "PAYTM_STAGING"


def _base() -> str:
    return os.environ.get("PAYTM_BASE_URL", HOSTS[env()]).rstrip("/")


def _signed(body: dict[str, Any]) -> dict[str, Any]:
    from paytmchecksum import generateSignature      # Paytm's official library (pip install paytmchecksum)
    return {"body": body, "head": {"signature": generateSignature(json.dumps(body), os.environ["PAYTM_MERCHANT_KEY"])}}


async def _post(path: str, body: dict[str, Any], transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    payload = _signed(body)
    async with httpx.AsyncClient(timeout=12, transport=transport) as c:
        r = await c.post(f"{_base()}{path}", content=json.dumps(payload), headers={"Content-Type": "application/json"})
        r.raise_for_status()
        return r.json()


async def order_status(order_id: str, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    """Paytm Transaction Status API. Returns Kavach's transaction shape plus the raw Paytm fields it came from."""
    raw = await _post("/v3/order/status", {"mid": os.environ["PAYTM_MID"], "orderId": order_id}, transport)
    b = raw.get("body", {})
    ri = b.get("resultInfo", {})
    amt = b.get("txnAmount")
    try:
        amount = int(round(float(amt))) if amt is not None else None
    except ValueError:
        amount = None
    return {
        "found": ri.get("resultStatus") in STATUS,
        "status": STATUS.get(ri.get("resultStatus"), ri.get("resultStatus") or "UNKNOWN"),
        "result_code": ri.get("resultCode"), "result_msg": ri.get("resultMsg"),
        "order_id": b.get("orderId", order_id), "txn_id": b.get("txnId"), "bank_txn_id": b.get("bankTxnId"),
        "amount": amount, "amount_text": amt, "txn_date": b.get("txnDate"), "payment_mode": b.get("paymentMode"),
        "gateway": b.get("gatewayName"), "bank": b.get("bankName"), "mid": b.get("mid"),
        "refund_amount": b.get("refundAmt"),
        "provenance": provenance(), "endpoint": f"{_base()}/v3/order/status", "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "response_signed": bool((raw.get("head") or {}).get("signature")),
    }


async def refund_status(order_id: str, ref_id: str, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, Any]:
    raw = await _post("/v2/refund/status", {"mid": os.environ["PAYTM_MID"], "orderId": order_id, "refId": ref_id}, transport)
    b = raw.get("body", {})
    ri = b.get("resultInfo", {})
    return {"status": ri.get("resultStatus"), "result_code": ri.get("resultCode"), "result_msg": ri.get("resultMsg"),
            "order_id": b.get("orderId", order_id), "ref_id": b.get("refId", ref_id), "refund_id": b.get("refundId"),
            "refund_amount": b.get("refundAmount"), "txn_id": b.get("txnId"), "provenance": provenance(),
            "endpoint": f"{_base()}/v2/refund/status", "fetched_at": datetime.now().isoformat(timespec="seconds")}
