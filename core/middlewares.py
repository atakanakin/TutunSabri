from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from core.database import SessionFactory
from core.repositories import upsert_user


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event_from_user = data.get("event_from_user")
        logger.info(
            "telegram_update event=%s user_id=%s",
            type(event).__name__,
            getattr(event_from_user, "id", None),
        )
        return await handler(event, data)


class ActiveUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event_from_user = data.get("event_from_user")
        if event_from_user is None:
            return await handler(event, data)

        async with SessionFactory() as session:
            db_user = await upsert_user(
                session,
                telegram_user_id=event_from_user.id,
                username=event_from_user.username,
                first_name=event_from_user.first_name,
                last_name=event_from_user.last_name,
            )

        data["db_user"] = db_user
        if db_user.is_active:
            return await handler(event, data)

        answer = getattr(event, "answer", None)
        if callable(answer):
            await answer("Access denied.")
        return None
