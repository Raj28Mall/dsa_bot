"""LeetCode stats via self-hosted alfa-leetcode-api."""

from __future__ import annotations

import os
import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://leetcode-api:3000"

LEETCODE_API_BASE_URL = os.getenv("LEETCODE_API_BASE_URL", DEFAULT_BASE_URL)


async def fetch_solved(client: httpx.AsyncClient, username: str) -> dict[str, Any] | None:
    url = f"{LEETCODE_API_BASE_URL}/{username}/solved"
    try:
        r = await client.get(url, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, Exception):
        log.warning("alfa-leetcode-api request failed for %s", username)
        return None


async def fetch_total_solved(client: httpx.AsyncClient, username: str) -> int | None:
    data = await fetch_solved(client, username)
    if not data:
        return None
    total = data.get("solvedProblem")
    if total is None:
        return None
    try:
        return int(total)
    except (TypeError, ValueError):
        return None


async def user_exists(client: httpx.AsyncClient, username: str) -> bool:
    data = await fetch_solved(client, username)
    return data is not None and "solvedProblem" in data
