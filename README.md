# DSA Tracker Discord Bot

A Discord bot for a small group that links each member’s **LeetCode** profile, pulls submission stats from LeetCode’s GraphQL API (same pattern as [alfa-leetcode-api](https://github.com/alfaarghya/alfa-leetcode-api)), and posts **IST**-scheduled reminders with **today** and **last 7 UTC calendar days** leaderboards.

## Features

- **LeetCode linking**: Slash group `/leetcode` — `set`, `clear`, and `show` (validated against LeetCode before saving).
- **SQLite**: Stores Discord `user_id` → `leetcode_username` with a unique constraint per LeetCode account.
- **Scheduled messages (Asia/Kolkata)**:
  - **06:00** — Morning message (no leaderboard).
  - **12:00, 18:00, 22:00** — Reminder plus leaderboard embed(s).
  - **00:00** — Goodnight message (no leaderboard).
- **`/leaderboard`** and **`!leaderboard`**: On-demand leaderboard (same data as reminders).
- **`!testschedule`**: Admin-only; posts a reminder + leaderboard in the current channel (set `ADMIN_USER_IDS` in `.env`).

Leaderboard **footer** explains that daily counts follow **LeetCode’s activity calendar (UTC days)**, not IST calendar days.

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

- `/leetcode set username` — Link your LeetCode username.
- `/leetcode clear` — Remove your link.
- `/leetcode show` — Show your linked username.
- `/leaderboard` — LeetCode today / 7-day stats for all linked members.
- `!leaderboard` — Same as `/leaderboard`.
- `!testschedule` — Admin-only test of reminder + leaderboard.
