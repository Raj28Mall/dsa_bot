import logging
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

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
                return 0, 0
                
            results = data["result"]
            today = datetime.utcnow().date()
            seven_days_ago = today - timedelta(days=6)
            
            today_solved = 0
            week_solved = 0
            
            for difficulty, problems in results.items():
                for problem_id, problem_data in problems.items():
                    subtime_str = problem_data.get("user_subtime")
                    if subtime_str:
                        try:
                            sub_date = datetime.strptime(subtime_str, "%Y-%m-%d %H:%M:%S").date()
                            if sub_date == today:
                                today_solved += 1
                            if seven_days_ago <= sub_date <= today:
                                week_solved += 1
                        except ValueError as ve:
                            logger.error(f"Failed to parse date '{subtime_str}': {ve}")
                            
            logger.info(f"GFG {username} -> today: {today_solved}, week: {week_solved}")
            return today_solved, week_solved
        else:
            logger.warning(f"Failed to fetch GFG API for {username}. Status: {r.status_code}")
    except Exception as e:
        logger.error(f"Error fetching GFG API for {username}: {e}", exc_info=True)
        
    return None, None
