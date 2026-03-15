from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import settings
from core.database import init_database
from core.handlers import router as core_router
from core.middlewares import ActiveUserMiddleware, LoggingMiddleware
from modules.yht.logic import TCDDClient
from modules.yht.handlers import router as yht_router
from tasks.worker import broker


async def run_bot() -> None:
    await init_database()
    await TCDDClient().ensure_station_cache()
    await broker.startup()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dispatcher = Dispatcher()
    dispatcher.update.middleware(LoggingMiddleware())
    dispatcher.message.middleware(ActiveUserMiddleware())
    dispatcher.callback_query.middleware(ActiveUserMiddleware())
    dispatcher.include_router(core_router)
    dispatcher.include_router(yht_router)
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
