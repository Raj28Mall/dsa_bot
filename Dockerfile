FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency specifications first to leverage Docker cache
COPY pyproject.toml uv.lock* ./

# Sync dependencies using uv, creating a virtual environment automatically
RUN uv sync

# Copy the rest of the application code
COPY . .

# Run the bot using uv
CMD ["uv", "run", "python3", "-u", "bot.py"]
