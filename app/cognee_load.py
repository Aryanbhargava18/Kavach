"""Load Kavach's SOP passages into Cognee once: make cognee-load (needs COGNEE_URL)."""
import asyncio
import os
import sys

import httpx

from .sop_kb import PASSAGES


async def main():
    url = os.environ.get("COGNEE_URL", "").rstrip("/")
    if not url:
        sys.exit("Set COGNEE_URL in .env first.")
    h = {"Content-Type": "application/json"}
    if os.environ.get("COGNEE_API_KEY"):
        h["X-Api-Key"] = os.environ["COGNEE_API_KEY"]
    async with httpx.AsyncClient(timeout=120) as c:
        for p in PASSAGES:
            r = await c.post(f"{url}/api/v1/add", headers=h, json={"data": f"[{p['id']}] {p['title']}. {p['text']}", "datasetName": "kavach_sop"})
            print(p["id"], r.status_code)
        r = await c.post(f"{url}/api/v1/cognify", headers=h, json={"datasets": ["kavach_sop"]})
        print("cognify", r.status_code, r.text[:200])


if __name__ == "__main__":
    asyncio.run(main())
