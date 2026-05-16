# DSA Tracker Discord Bot

A Discord bot for a small group that links each member's **LeetCode**, **Codeforces**, and **GeeksforGeeks** profiles, pulls submission stats from their respective APIs, and posts **IST**-scheduled reminders with **today** and **last 7 UTC calendar days** leaderboards.

## Features

- **Multi-platform linking**: Slash command groups for `/leetcode`, `/codeforces`, and `/geeksforgeeks` — each with `set`, `clear`, and `show` subcommands (validated against respective platforms before saving).
- **SQLite**: Stores Discord `user_id` → platform handles with unique constraints per platform account.
- **Scheduled messages (Asia/Kolkata)**:
  - **06:00** — Morning message with leaderboard.
  - **12:00, 18:00, 22:00** — Reminder plus leaderboard embed(s).
  - **00:00** — Goodnight message with leaderboard.
- **`/leaderboard`** and **`!leaderboard`**: On-demand leaderboard (same data as reminders).
- **`!testschedule`**: Admin-only; posts a reminder + leaderboard in the current channel (set `ADMIN_USER_IDS` in `.env`).

Leaderboard **footer** explains that daily counts are aggregated per **UTC calendar day** across all linked platforms (LeetCode, Codeforces, and GeeksforGeeks).


## Prerequisites

- Python 3.10+
- Discord bot token and the **Message Content** intent enabled (for `!` commands).
- **Applications commands** scope when generating the invite URL (for slash commands).

## Installation

1. Clone the repository and open the project directory.

2. Install dependencies:

   ```bash
   uv sync
   ```

3. Copy `.temp.env` to `.env` and fill in values:

   ```bash
   cp .temp.env .env
   ```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_ID` | Yes | Discord bot token (name kept for backward compatibility). |
| `MAIN_CHANNEL_ID` | Yes | Text channel ID where scheduled messages are sent. |
| `GUILD_ID` | No | If set, slash commands sync to that server only (faster while developing). If unset, global sync is used (can take up to ~1 hour to appear). |
| `ADMIN_USER_IDS` | No | Comma-separated Discord user IDs allowed to use `!testschedule`. |

## Usage

```bash
uv run python bot.py
```

Or:

```bash
python bot.py
```

(with your virtualenv activated after `uv sync`).

Docker: `docker compose up --build` (same env file; SQLite persists via the mounted project directory).

## Commands

### Platform Linking
- `/leetcode set username` — Link your LeetCode username.
- `/leetcode clear` — Remove your LeetCode link.
- `/leetcode show` — Show your linked LeetCode username.
- `/codeforces set handle` — Link your Codeforces handle.
- `/codeforces clear` — Remove your Codeforces link.
- `/codeforces show` — Show your linked Codeforces handle.
- `/geeksforgeeks set handle` — Link your GeeksforGeeks handle.
- `/geeksforgeeks clear` — Remove your GeeksforGeeks link.
- `/geeksforgeeks show` — Show your linked GeeksforGeeks handle.

### Leaderboard
- `/leaderboard` — Show today / 7-day stats for all linked members across all platforms.
- `!leaderboard` — Same as `/leaderboard`.

### Admin
- `!testschedule` — Admin-only test of reminder + leaderboard.
