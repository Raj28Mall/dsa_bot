"""Codeforces REST client for DSA tracker."""

from __future__ import annotations

import httpx
import json

from leetcode_graphql import (
    utc_day_keys_last_7_including_today,
    utc_today_calendar_key,
    _count_ac_in_utc_day_keys,
)


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


async def fetch_stats_today_and_week(
    client: httpx.AsyncClient,
    handle: str,
) -> tuple[int | None, int | None]:
    try:
        r = await client.get(
            f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=500",
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return None, None

    if data.get("status") != "OK":
        return None, None

    submissions = data.get("result", [])
    timestamps: list[int] = []
    
    for row in submissions:
        if row.get("verdict") == "OK":
            ts = row.get("creationTimeSeconds")
            if ts is not None:
                try:
                    timestamps.append(int(ts))
                except (TypeError, ValueError):
                    continue

    week_keys_list = utc_day_keys_last_7_including_today()
    today_key = utc_today_calendar_key()
    day_keys = set(week_keys_list)

    counts = _count_ac_in_utc_day_keys(timestamps, day_keys)
    today_count = counts.get(today_key, 0)
    week_sum = sum(counts.get(k, 0) for k in week_keys_list)
    return today_count, week_sum
