from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from core.database import SessionFactory
from core.repositories import get_first_admin_username, get_user_by_telegram_id, sync_user_profile


logger = logging.getLogger(__name__)

PUBLIC_COMMANDS = {"start"}
PUBLIC_CALLBACKS = {
    "request_access",
    "cancel_access",
    "info_whoami",
    "info_how_it_works",
    "info_contact",
}


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
        telegram_event = self._resolve_telegram_event(event, data)

        async with SessionFactory() as session:
            db_user = await get_user_by_telegram_id(session, event_from_user.id)
            admin_username = await get_first_admin_username(session)
            if db_user is not None:
                db_user = await sync_user_profile(
                    session,
                    user=db_user,
                    username=event_from_user.username,
                    first_name=event_from_user.first_name,
                    last_name=event_from_user.last_name,
                )

        data["db_user"] = db_user
        if db_user is not None and db_user.is_active:
            return await handler(event, data)

        if self._is_public_event(telegram_event):
            return await handler(event, data)

        await self._deny_access(telegram_event, admin_username)
        return None

    def _resolve_telegram_event(
        self,
        event: TelegramObject,
        data: dict[str, Any],
    ) -> TelegramObject:
        return (
            data.get("event_message")
            or data.get("event_callback_query")
            or data.get("event")
            or event
        )

    def _is_public_event(self, event: TelegramObject) -> bool:
        if isinstance(event, Message):
            if not event.text or not event.text.startswith("/"):
                return False
            command_name = event.text.split()[0].split("@")[0].lstrip("/").lower()
            return command_name in PUBLIC_COMMANDS
        if isinstance(event, CallbackQuery):
            return event.data in PUBLIC_CALLBACKS
        return False

    async def _deny_access(self, event: TelegramObject, admin_username: Optional[str]) -> None:
        admin_line = (
            f"\n\nYetkili ile iletişim için: @{admin_username}"
            if admin_username
            else ""
        )
        text = (
            "Bu botu kullanma yetkiniz bulunmuyor.\n"
            "Yetki talebi gönderebilir veya yöneticiyle iletişime geçebilirsiniz."
            f"{admin_line}"
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Yetki İste", callback_data="request_access"),
                    InlineKeyboardButton(text="İptal", callback_data="cancel_access"),
                ]
            ]
        )
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
            return
        if isinstance(event, CallbackQuery):
            await event.answer("Bu işlem için yetkiniz yok.", show_alert=True)
            if event.message is not None:
                await event.message.answer(text, reply_markup=keyboard)
