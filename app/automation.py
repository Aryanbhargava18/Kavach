"""n8n automation hook.

Kavach decides; n8n delivers. Every follow-up, reminder, approval request, escalation draft and scam
report becomes an event. With N8N_WEBHOOK_URL set, events are POSTed to your n8n workflow
(integrations/n8n/kavach-followups.json: Webhook -> Switch -> email / WhatsApp / Slack). Without it they
are kept in a local log shown in the UI, so nothing pretends to have been delivered.
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any

import httpx

LOG: list[dict[str, Any]] = []


def n8n_configured() -> bool:
    return bool(os.environ.get("N8N_WEBHOOK_URL"))


def emit(event: str, payload: dict[str, Any], at: str | None = None) -> dict[str, Any]:
    rec = {"event": event, "at": at or datetime.now().isoformat(timespec="seconds"), "payload": payload,
           "delivery": "sending to n8n" if n8n_configured() else "local log (N8N_WEBHOOK_URL not set)"}
    LOG.append(rec)
    del LOG[:-200]
    if n8n_configured():
        try:
            asyncio.get_running_loop().create_task(_post(rec))
        except RuntimeError:
            rec["delivery"] = "not sent (no event loop)"
    return rec


async def _post(rec: dict[str, Any]) -> None:
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.post(os.environ["N8N_WEBHOOK_URL"], json={"source": "kavach", **rec})
            rec["delivery"] = f"n8n {r.status_code}"
    except Exception as ex:
        rec["delivery"] = f"n8n failed: {type(ex).__name__}"


def reset() -> None:
    LOG.clear()
