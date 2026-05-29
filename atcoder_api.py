"""AtCoder REST client for DSA tracker.

Uses the AtCoder Problems unofficial API — no auth required.
- User existence: GET /v3/user_info?user={handle}
- Submissions: GET /v3/user/submissions?user={handle}&from_second={7 days ago}
"""

from __future__ import annotations

import httpx

from leetcode_graphql import (
    utc_day_keys_last_7_including_today,
    utc_today_calendar_key,
    _count_ac_in_utc_day_keys,
)


ATCODER_USER_INFO_URL = "https://kenkoooo.com/atcoder/atcoder-api/v3/user_info"
ATCODER_SUBMISSIONS_URL = (
    "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions"
)


async def user_exists(client: httpx.AsyncClient, handle: str) -> bool:
    """Check whether an AtCoder handle exists via the unofficial AtCoder Problems API."""
    try:
        r = await client.get(
            ATCODER_USER_INFO_URL,
            params={"user": handle},
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("user_id") == handle
    except (httpx.HTTPError, ValueError):
        return False


async def fetch_stats_today_and_week(
    client: httpx.AsyncClient,
    handle: str,
) -> tuple[int | None, int | None]:
    """Return (today_ac_count, last_7_utc_days_ac_sum) for an AtCoder user."""
    import time

    week_ago = int(time.time()) - 7 * 86400

    try:
        r = await client.get(
            ATCODER_SUBMISSIONS_URL,
            params={"user": handle, "from_second": week_ago},
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None, None

    # Filter for AC verdicts only.
    # AtCoder result is typically "AC".
    timestamps: list[int] = []
    for sub in data:
        if sub.get("result") == "AC":
            epoch = sub.get("epoch_second")
            if epoch is not None:
                try:
                    timestamps.append(int(epoch))
                except (TypeError, ValueError):
                    continue

    week_keys_list = utc_day_keys_last_7_including_today()
    today_key = utc_today_calendar_key()
    day_keys = set(week_keys_list)

    counts = _count_ac_in_utc_day_keys(timestamps, day_keys)
    today_count = counts.get(today_key, 0)
    week_sum = sum(counts.get(k, 0) for k in week_keys_list)
    return today_count, week_sum