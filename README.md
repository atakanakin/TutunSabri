# Tütün Sabri

An async Telegram bot that monitors train availability and holds a seat the moment one opens up.

## How it works

1. A user submits a departure station, arrival station, date, and departure hour.
2. The bot creates a background task that polls for availability on a configurable interval.
3. When a seat becomes available the bot immediately attempts to hold it.
4. The user is notified and the seat is kept held for a configurable window (default 10 minutes) so they can complete the purchase manually.
5. The user can cancel a search or release a held seat at any time.

## Stack

| Layer | Technology |
|---|---|
| Bot framework | [aiogram](https://docs.aiogram.dev/) 3.x |
| Database | SQLite via SQLAlchemy (async) |
| Task queue | [TaskIQ](https://taskiq-python.github.io/) + Redis |
| HTTP client | [curl-cffi](https://github.com/yifeikong/curl-cffi) |
| Config | Pydantic Settings |

## Requirements

- Python 3.9+
- Redis

## Setup

```bash
# 1. Clone and install dependencies
uv sync

# 2. Copy and fill in the environment file
cp .env.example .env

# 3. Start Redis (if not already running)
redis-server

# 4. Run the bot
tutunsabri
```

## Configuration

All configuration is done through environment variables (or a `.env` file).

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Bot token from @BotFather |
| `TCDD_AUTHORIZATION` | Yes | — | Bearer token for the API |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./data/app.db` | SQLAlchemy database URL |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `TCDD_API_BASE_URL` | No | — | API base URL |
| `POLL_INTERVAL_SECONDS` | No | `30` | How often each task polls for availability |
| `MAX_POLL_ERRORS` | No | `3` | Consecutive errors before a task is marked failed |
| `YHT_HOLD_DURATION_MINUTES` | No | `10` | How long a held seat is kept before being released |
| `YHT_MAX_HOLD_ATTEMPTS` | No | `3` | Max retries when a hold expires |
| `YHT_BASIC_MAX_PARALLEL_TASKS` | No | `3` | Max concurrent searches for basic users |
| `YHT_PREMIUM_MAX_PARALLEL_TASKS` | No | `5` | Max concurrent searches for premium users |
| `DEFAULT_TIMEZONE` | No | `Europe/Istanbul` | Timezone used for date/time display |

## Access model

- New users have no access by default. They can send an access request through the bot, which notifies all admins.
- An admin approves or rejects requests via `/grant` and `/revoke`.
- Roles determine how many searches can run in parallel: **basic** (3), **premium** (5), **admin** (unlimited).

## Database migrations

The bot applies lightweight SQLite migrations automatically on startup, so there is no separate migration step when upgrading.

---

## Legal disclaimer

This project is developed strictly for **educational purposes**.

- It is not designed to cause harm, disrupt service availability, perform denial-of-service attacks, or interfere with any third-party system or infrastructure.
- Automated interaction with third-party services may violate their terms of service. **You are solely responsible** for ensuring your use complies with all applicable laws and the terms of service of any platform you interact with.

**Use at your own risk.** The author(s) accept no liability for any damages, account bans, legal consequences, or any other outcome arising from the use or misuse of this software.
