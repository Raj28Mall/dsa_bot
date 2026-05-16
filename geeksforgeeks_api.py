import logging
from datetime import datetime, timezone
import httpx

from leetcode_graphql import (
    utc_day_keys_last_7_including_today,
    utc_today_calendar_key,
    _count_ac_in_utc_day_keys,
)

logger = logging.getLogger(__name__)
UTC = timezone.utc

async def user_exists(client: httpx.AsyncClient, username: str) -> bool:
    url = "https://practiceapi.geeksforgeeks.org/api/v1/user/problems/submissions/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.geeksforgeeks.org",
        "Referer": f"https://www.geeksforgeeks.org/profile/{username}/",
        "Content-Type": "application/json" 
    }
    payload = {
        "handle": username,
        "requestType": "",
        "year": "",
        "month": ""
    }
    try:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code == 200:
            data = r.json()
            if "result" in data:
                return True
    except Exception as e:
        logger.error(f"Error checking GFG user {username}: {e}")
    return False

async def fetch_stats_today_and_week(
    client: httpx.AsyncClient, username: str
) -> tuple[int | None, int | None]:
    url = "https://practiceapi.geeksforgeeks.org/api/v1/user/problems/submissions/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://www.geeksforgeeks.org",
        "Referer": f"https://www.geeksforgeeks.org/profile/{username}/",
        "Content-Type": "application/json" 
    }
    payload = {
        "handle": username,
        "requestType": "",
        "year": "",
        "month": ""
    }
    try:
        r = await client.post(url, headers=headers, json=payload)
        logger.info(f"GFG API status code for {username}: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            if "result" not in data:
                logger.warning(f"GFG JSON fetched for {username}, but 'result' missing.")
                return None, None
                
            results = data["result"]
            timestamps: list[int] = []
            
            # Collect all submission timestamps
            for difficulty, problems in results.items():
                for problem_id, problem_data in problems.items():
                    subtime_str = problem_data.get("user_subtime")
                    if subtime_str:
                        try:
                            # Parse the timestamp string and convert to Unix timestamp
                            dt = datetime.strptime(subtime_str, "%Y-%m-%d %H:%M:%S")
                            # Assume the API returns UTC timestamps (or treat as UTC for consistency)
                            dt_utc = dt.replace(tzinfo=UTC)
                            timestamps.append(int(dt_utc.timestamp()))
                        except ValueError as ve:
                            logger.error(f"Failed to parse date '{subtime_str}': {ve}")
            
            # Use the same UTC day bucketing as LeetCode/Codeforces
            week_keys_list = utc_day_keys_last_7_including_today()
            today_key = utc_today_calendar_key()
            day_keys = set(week_keys_list)
            
            counts = _count_ac_in_utc_day_keys(timestamps, day_keys)
            today_count = counts.get(today_key, 0)
            week_sum = sum(counts.get(k, 0) for k in week_keys_list)
            
            logger.info(f"GFG {username} -> today: {today_count}, week: {week_sum}")
            return today_count, week_sum
        else:
            logger.warning(f"Failed to fetch GFG API for {username}. Status: {r.status_code}")
    except Exception as e:
        logger.error(f"Error fetching GFG API for {username}: {e}", exc_info=True)
        
    return None, None
