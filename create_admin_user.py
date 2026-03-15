from __future__ import annotations

import asyncio
import sys
from typing import Any, Dict

import httpx

from core.config import settings
from core.database import SessionFactory, init_database
from core.models import UserRole
from core.repositories import upsert_user


def _parse_chat_id(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: uv run python create_admin_user.py <telegram_chat_id>")
    try:
        return int(argv[1])
    except ValueError as exc:
        raise SystemExit("telegram_chat_id must be an integer.") from exc


async def _fetch_chat(chat_id: int) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getChat"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params={"chat_id": chat_id})
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        description = payload.get("description", "Telegram API request failed.")
        raise RuntimeError(description)
    result = payload["result"]
    if result.get("type") != "private":
        raise RuntimeError("Chat ID must belong to a private user chat.")
    return result


async def _run(chat_id: int) -> None:
    await init_database()
    chat = await _fetch_chat(chat_id)
    async with SessionFactory() as session:
        user = await upsert_user(
            session,
            telegram_user_id=chat["id"],
            username=chat.get("username"),
            first_name=chat.get("first_name"),
            last_name=chat.get("last_name"),
            force_role=UserRole.admin,
            force_active=True,
        )
    print(f"Admin user ready: telegram_user_id={user.telegram_user_id} username={user.username!r}")


def main() -> None:
    asyncio.run(_run(_parse_chat_id(sys.argv)))


if __name__ == "__main__":
    main()
