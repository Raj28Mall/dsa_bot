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


def _utc_midnight_ts_for_date(d: datetime.date) -> str:
    dt = datetime.datetime.combine(d, datetime.time.min, tzinfo=UTC)
    return str(int(dt.timestamp()))


def utc_today_calendar_key() -> str:
    return _utc_midnight_ts_for_date(datetime.datetime.now(UTC).date())


def utc_day_keys_last_7_including_today() -> list[str]:
    today = datetime.datetime.now(UTC).date()
    return [_utc_midnight_ts_for_date(today - datetime.timedelta(days=i)) for i in range(7)]


def years_covering_keys(keys: list[str]) -> set[int]:
    years: set[int] = set()
    for k in keys:
        try:
            ts = int(k)
        except (TypeError, ValueError):
            continue
        years.add(datetime.datetime.fromtimestamp(ts, tz=UTC).year)
    return years if years else {datetime.datetime.now(UTC).year}


def parse_submission_calendar(raw: str | None) -> dict[str, int]:
    if not raw or raw == "{}":
        return {}
    data = json.loads(raw)
    out: dict[str, int] = {}
    for k, v in data.items():
        try:
            out[str(k)] = int(v)
        except (TypeError, ValueError):
            continue
    return out


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


async def fetch_calendar_for_year(
    client: httpx.AsyncClient,
    username: str,
    year: int,
) -> dict[str, int] | None:
    data = await graphql_request(
        client,
        USER_PROFILE_CALENDAR_QUERY,
        {"username": username, "year": year},
    )
    if not data or not data.get("matchedUser"):
        return None
    uc = data["matchedUser"].get("userCalendar") or {}
    raw = uc.get("submissionCalendar")
    if raw is None:
        return {}
    if isinstance(raw, dict):
        out: dict[str, int] = {}
        for k, v in raw.items():
            try:
                out[str(k)] = int(v)
            except (TypeError, ValueError):
                pass
        return out
    if isinstance(raw, str):
        return parse_submission_calendar(raw)
    return {}


async def fetch_merged_calendar_for_years(
    client: httpx.AsyncClient,
    username: str,
    years: set[int],
) -> dict[str, int] | None:
    merged: dict[str, int] = {}
    saw_valid_user = False
    for y in sorted(years):
        cal = await fetch_calendar_for_year(client, username, y)
        if cal is None:
            if not saw_valid_user:
                return None
            continue
        saw_valid_user = True
        merged.update(cal)
    if not saw_valid_user:
        return None
    return merged


async def user_exists(client: httpx.AsyncClient, username: str) -> bool:
    y = datetime.datetime.now(UTC).year
    data = await graphql_request(
        client,
        USER_PROFILE_CALENDAR_QUERY,
        {"username": username, "year": y},
    )
    return bool(data and data.get("matchedUser"))


async def fetch_stats_today_and_week(
    client: httpx.AsyncClient,
    username: str,
) -> tuple[int | None, int | None]:
    """
    Returns (today_submissions, last_7_utc_days_submissions_sum) using LeetCode calendar (UTC days).
    None means fetch/parse failure or unknown user.
    """
    week_keys = utc_day_keys_last_7_including_today()
    today_key = utc_today_calendar_key()
    years = years_covering_keys(week_keys + [today_key])
    cal = await fetch_merged_calendar_for_years(client, username, years)
    if cal is None:
        return None, None
    today_count = cal.get(today_key, 0)
    week_sum = sum(cal.get(k, 0) for k in week_keys)
    return today_count, week_sum
