"""Codeforces REST client for DSA tracker."""

from __future__ import annotations

import httpx
import json
import logging

logger = logging.getLogger(__name__)

async def user_exists(client: httpx.AsyncClient, handle: str) -> bool:
    try:
        r = await client.get(
            f"https://codeforces.com/api/user.info?handles={handle}", timeout=30.0
        )
        r.raise_for_status()
        data = r.json()
        return data.get("status") == "OK"
    except (httpx.HTTPError, json.JSONDecodeError):
        return False

async def fetch_total_ac(client: httpx.AsyncClient, handle: str) -> int | None:
    url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=10000"
    try:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "OK":
            submissions = data.get("result", [])
            ac_count = sum(1 for sub in submissions if sub.get("verdict") == "OK")
            return ac_count
        else:
            logger.error(f"Codeforces API returned error for {handle}: {data.get('comment')}")
            return None
    except Exception as e:
        logger.error(f"Failed to fetch Codeforces stats for {handle}: {e}")
        return None
