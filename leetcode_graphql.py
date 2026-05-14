"""LeetCode GraphQL client — same endpoint/headers pattern as alfa-leetcode-api fetchUserDetails."""

from __future__ import annotations

import json
import datetime
from datetime import timezone
from typing import Any

import httpx

UTC = timezone.utc

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

USER_PROFILE_CALENDAR_QUERY = """
query UserProfileCalendar($username: String!, $year: Int!) {
  matchedUser(username: $username) {
    userCalendar(year: $year) {
      submissionCalendar
    }
  }
}
"""

# submissionCalendar counts every run (WA/TLE/etc.). Leaderboards use recent AC only.
AC_STATS_FOR_LEADERBOARD_QUERY = """
query AcStatsLeaderboard($username: String!, $limit: Int!) {
  matchedUser(username: $username) {
    username
  }
  recentAcSubmissionList(username: $username, limit: $limit) {
    timestamp
  }
}
"""


def _utc_midnight_ts_for_date(d: datetime.date) -> str:
    dt = datetime.datetime.combine(d, datetime.time.min, tzinfo=UTC)
    return str(int(dt.timestamp()))


def utc_today_calendar_key() -> str:
    return _utc_midnight_ts_for_date(datetime.datetime.now(UTC).date())


def utc_day_keys_last_7_including_today() -> list[str]:
    today = datetime.datetime.now(UTC).date()
    return [_utc_midnight_ts_for_date(today - datetime.timedelta(days=i)) for i in range(7)]


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
    y = datetime.datetime.now(UTC).year
    data = await graphql_request(
        client,
        USER_PROFILE_CALENDAR_QUERY,
        {"username": username, "year": y},
    )
    return bool(data and data.get("matchedUser"))


# Large enough for very active weekly AC volume; API has no pagination on this list.
RECENT_AC_FETCH_LIMIT = 1000


def _count_ac_in_utc_day_keys(timestamps: list[int], day_keys: set[str]) -> dict[str, int]:
    counts = {k: 0 for k in day_keys}
    for ts in timestamps:
        day = datetime.datetime.fromtimestamp(ts, tz=UTC).date()
        k = _utc_midnight_ts_for_date(day)
        if k in day_keys:
            counts[k] += 1
    return counts


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
