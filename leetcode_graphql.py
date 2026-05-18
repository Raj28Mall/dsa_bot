"""LeetCode GraphQL client — same endpoint/headers pattern as alfa-leetcode-api fetchUserDetails."""

from __future__ import annotations

import json
from typing import Any

import httpx

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

GET_USER_STATS_QUERY = """
query getUserStats($username: String!) {
    matchedUser(username: $username) {
        submitStats {
            acSubmissionNum {
                count
            }
        }
    }
}
"""

async def graphql_request(
    client: httpx.AsyncClient,
    query: str,
    variables: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        r = await client.post(
            LEETCODE_GRAPHQL_URL,
            headers={
                "Content-Type": "application/json",
                "Referer": "https://leetcode.com",
            },
            json={"query": query, "variables": variables},
            timeout=30.0,
        )
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return None
    if body.get("errors"):
        return None
    return body.get("data")

async def user_exists(client: httpx.AsyncClient, username: str) -> bool:
    data = await graphql_request(
        client,
        GET_USER_STATS_QUERY,
        {"username": username},
    )
    return bool(data and data.get("matchedUser"))

async def fetch_total_ac(
    client: httpx.AsyncClient,
    username: str,
) -> int | None:
    """
    Returns the sum of the total accepted submissions counts.
    None means fetch/parse failure or unknown user.
    """
    data = await graphql_request(
        client,
        GET_USER_STATS_QUERY,
        {"username": username},
    )
    if not data:
        return None
    
    matched_user = data.get("matchedUser")
    if not matched_user:
        return None
        
    stats = matched_user.get("submitStats", {}).get("acSubmissionNum", [])
    if not stats:
        return None
        
    total_ac = sum(item.get("count", 0) for item in stats)
    return total_ac


async def fetch_stats_today_and_week(
    client: httpx.AsyncClient,
    username: str,
) -> tuple[int | None, int | None]:
    """
    Returns (today_ac_count, last_7_utc_days_ac_sum) from recent AC submissions (UTC days).
    None means fetch/parse failure or unknown user.

    Uses recentAcSubmissionList (accepted only). Counts can be capped if a user exceeds
    RECENT_AC_FETCH_LIMIT recent AC submissions returned by the API for the window.
    """
    week_keys_list = utc_day_keys_last_7_including_today()
    today_key = utc_today_calendar_key()
    day_keys = set(week_keys_list)

    data = await graphql_request(
        client,
        AC_STATS_FOR_LEADERBOARD_QUERY,
        {"username": username, "limit": RECENT_AC_FETCH_LIMIT},
    )
    if not data:
        return None, None
    if not data.get("matchedUser"):
        return None, None
    rows = data.get("recentAcSubmissionList")
    if rows is None:
        return None, None

    timestamps: list[int] = []
    for row in rows:
        ts = row.get("timestamp")
        try:
            timestamps.append(int(ts))
        except (TypeError, ValueError):
            continue

    counts = _count_ac_in_utc_day_keys(timestamps, day_keys)
    today_count = counts.get(today_key, 0)
    week_sum = sum(counts.get(k, 0) for k in week_keys_list)
    return today_count, week_sum
