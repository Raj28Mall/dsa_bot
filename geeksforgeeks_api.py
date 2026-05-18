import logging
from datetime import datetime, timezone
import httpx

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

async def fetch_total_ac(
    client: httpx.AsyncClient, username: str
) -> int | None:
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
                return None
                
            results = data["result"]
            total_solved = 0
            
            for difficulty, problems in results.items():
                if isinstance(problems, dict):
                    total_solved += len(problems)
                elif isinstance(problems, list):
                    total_solved += len(problems)
                    
            logger.info(f"GFG {username} -> total solved: {total_solved}")
            return total_solved
        else:
            logger.warning(f"Failed to fetch GFG API for {username}. Status: {r.status_code}")
    except Exception as e:
        logger.error(f"Error fetching GFG API for {username}: {e}", exc_info=True)
        
    return None
