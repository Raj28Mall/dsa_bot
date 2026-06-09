"""LeetCode GraphQL client — same endpoint/headers pattern as alfa-leetcode-api fetchUserDetails."""

from __future__ import annotations

import json
import datetime
from datetime import timezone
from typing import Any

import httpx
import aiosqlite

UTC = timezone.utc
IST = None  # Placeholder, will be set when importing
try:
    import zoneinfo
    IST = zoneinfo.ZoneInfo("Asia/Kolkata")
except (ImportError, AttributeError):
    # Fallback for Python < 3.9 or systems without zoneinfo
    from datetime import timedelta
    IST = timezone(timedelta(hours=5, minutes=30))

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

# recentAcSubmissionList silently caps at ~20. Use with dedup accumulation per day.
RECENT_AC_QUERY = """
query RecentAc($username: String!, $limit: Int!) {
  matchedUser(username: $username) {
    username
  }
  recentAcSubmissionList(username: $username, limit: $limit) {
    id
    titleSlug
    timestamp
  }
}
"""


def _utc_midnight_ts_for_date(d: datetime.date) -> str:
    dt = datetime.datetime.combine(d, datetime.time.min, tzinfo=UTC)
    return str(int(dt.timestamp()))


def _ist_midnight_ts_for_date(d: datetime.date) -> str:
    dt = datetime.datetime.combine(d, datetime.time.min, tzinfo=IST)
    return str(int(dt.timestamp()))


def utc_today_calendar_key() -> str:
    return _utc_midnight_ts_for_date(datetime.datetime.now(UTC).date())


def utc_day_keys_last_7_including_today() -> list[str]:
    today = datetime.datetime.now(UTC).date()
    return [_utc_midnight_ts_for_date(today - datetime.timedelta(days=i)) for i in range(7)]


def ist_today_calendar_key() -> str:
    """Return the timestamp key for today's midnight in IST."""
    return _ist_midnight_ts_for_date(datetime.datetime.now(IST).date())


def ist_day_keys_last_7_including_today() -> list[str]:
    """Return list of IST day keys for the last 7 days (including today)."""
    today = datetime.datetime.now(IST).date()
    return [_ist_midnight_ts_for_date(today - datetime.timedelta(days=i)) for i in range(7)]


def _count_ac_in_ist_day_keys(timestamps: list[int], day_keys: set[str]) -> dict[str, int]:
    """Count AC submissions bucketed by IST days instead of UTC."""
    counts = {k: 0 for k in day_keys}
    for ts in timestamps:
        day = datetime.datetime.fromtimestamp(ts, tz=IST).date()
        k = _ist_midnight_ts_for_date(day)
        if k in day_keys:
            counts[k] += 1
    return counts


def _ist_today_date_str() -> str:
    """Return today's date in IST as 'YYYY-MM-DD'."""
    return datetime.datetime.now(IST).strftime("%Y-%m-%d")


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


async def accumulate_daily_ac_problems(
    client: httpx.AsyncClient,
    username: str,
    db_path: str,
) -> int | None:
    """
    Poll recentAcSubmissionList, deduplicate problems for today (IST), and persist.
    Returns the unique count of today's AC problems after accumulation.
    Returns None on fetch failure or unknown user.
    """
    today_str = _ist_today_date_str()

    data = await graphql_request(
        client,
        RECENT_AC_QUERY,
        {"username": username, "limit": 20},
    )
    if not data or not data.get("matchedUser"):
        return None

    rows = data.get("recentAcSubmissionList")
    if rows is None:
        return None

    # Collect slugs belonging to today (IST)
    today_slugs: set[str] = set()
    for row in rows:
        slug = row.get("titleSlug")
        ts = row.get("timestamp")
        if not slug or ts is None:
            continue
        try:
            ts = int(ts)
        except (TypeError, ValueError):
            continue
        sub_date = datetime.datetime.fromtimestamp(ts, tz=IST).strftime("%Y-%m-%d")
        if sub_date == today_str:
            today_slugs.add(str(slug))

    if today_slugs:
        async with aiosqlite.connect(db_path) as db:
            await db.executemany(
                "INSERT OR IGNORE INTO lc_daily_problems (leetcode_username, problem_slug, ist_date) VALUES (?, ?, ?)",
                [(username, slug, today_str) for slug in today_slugs],
            )
            await db.commit()

    # Return the current unique count for today
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT COUNT(DISTINCT problem_slug) FROM lc_daily_problems WHERE leetcode_username = ? AND ist_date = ?",
            (username, today_str),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def fetch_daily_unique_from_db(
    username: str,
    db_path: str,
) -> int:
    """Read the already-accumulated unique daily count from the database."""
    today_str = _ist_today_date_str()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT COUNT(DISTINCT problem_slug) FROM lc_daily_problems WHERE leetcode_username = ? AND ist_date = ?",
            (username, today_str),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def fetch_stats_today_and_week(
    client: httpx.AsyncClient,
    username: str,
    db_path: str = "dsa_tracker.db",
) -> tuple[int | None, int | None]:
    """
    Returns (today_unique_ac_count, last_7_calendar_days_sum).

    Today's count comes from the accumulated deduplicated problem set (lc_daily_problems).
    Week count comes from submissionCalendar (all submission runs, IST-bucketed).

    None means fetch/parse failure or unknown user.
    """
    # --- Daily: read from the accumulated dedup table ---
    today_str = _ist_today_date_str()
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT COUNT(DISTINCT problem_slug) FROM lc_daily_problems WHERE leetcode_username = ? AND ist_date = ?",
            (username, today_str),
        ) as cur:
            row = await cur.fetchone()
            daily = row[0] if row else 0

    # --- Weekly: use submissionCalendar ---
    year = datetime.datetime.now(UTC).year
    data = await graphql_request(
        client,
        USER_PROFILE_CALENDAR_QUERY,
        {"username": username, "year": year},
    )
    if not data or not data.get("matchedUser"):
        return None, None

    cal = data.get("matchedUser", {}).get("userCalendar", {}).get("submissionCalendar")
    if cal is None:
        return daily, None

    try:
        calendar: dict[str, int] = json.loads(cal)
    except (json.JSONDecodeError, TypeError):
        return daily, None

    week_keys_list = ist_day_keys_last_7_including_today()
    week_sum = sum(calendar.get(k, 0) for k in week_keys_list)

    return daily, week_sum


async def clear_yesterdays_problems(db_path: str) -> None:
    """Delete lc_daily_problems rows not from today (IST). Called at midnight."""
    today_str = _ist_today_date_str()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "DELETE FROM lc_daily_problems WHERE ist_date != ?",
            (today_str,),
        )
        await db.commit()