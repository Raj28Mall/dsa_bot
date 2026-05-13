# DSA Tracker Discord Bot

A Discord bot to track daily Data Structures and Algorithms (DSA) problem-solving numbers. It encourages daily practice among friends or a community by holding a daily poll and tracking stats over time to build a leaderboard.

## Features
- **Daily Check-ins**: Sends a daily poll at a configurable time offering buttons for simple answers and a modal for custom input.
- **SQLite Database**: Uses `aiosqlite` for asynchronous and easy data persistence. 
- **Leaderboard**: Displays the top 10 users with the most problems solved across the server.
- **Reactions & Prompts**: Motivates users with fun, customized messages depending on the number of questions solved!

## Prerequisites
- Python 3.10+
- Discord Bot Token

## Installation

1. Clone the repository and navigate to the project directory.

2. Install the required dependencies using `uv`:
   ```bash
   uv sync
   ```

3. Copy the `.temp.env` file to `.env` and fill in your actual values:
   ```bash
   cp .temp.env .env
   ```
   *Edit `.env` to include your bot token and channel ID.*

## Usage

Run the bot using `uv`:
```bash
uv run bot.py
```

## Commands
- `!leaderboard` - Shows the current problem-solving leaderboard.
- `!testpoll` - Manually triggers the DSA check-in poll (useful for testing).
