"""In-process pub/sub feeding the Server-Sent Events stream."""
from __future__ import annotations

import asyncio
from typing import Any


class Bus:
    def __init__(self) -> None:
        self.subs: set[asyncio.Queue] = set()
        self.history: list[dict[str, Any]] = []

    def publish(self, event: dict[str, Any]) -> None:
        self.history.append(event)
        self.history = self.history[-800:]
        for q in list(self.subs):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=2000)
        self.subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subs.discard(q)
