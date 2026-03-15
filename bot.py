from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import settings
from core.database import SessionFactory, init_database
from core.handlers import router as core_router
from core.middlewares import ActiveUserMiddleware, LoggingMiddleware
from core.models import SearchTaskStatus
from core.repositories import (
    clear_task_hold_details,
    get_all_open_tasks,
    set_task_message_id,
    update_task_status,
)
from modules.yht.logic import TCDDClient
from modules.yht.handlers import router as yht_router
from tasks.worker import broker, monitor_yht_task


async def _resume_open_yht_tasks() -> None:
    client = TCDDClient()
    async with SessionFactory() as session:
        open_tasks = await get_all_open_tasks(session)

    for open_task in open_tasks:
        if open_task.status == SearchTaskStatus.seat_held:
            if (
                open_task.train_car_id is not None
                and open_task.allocation_id is not None
                and open_task.seat_number is not None
            ):
                try:
                    await client.release_seat(
                        train_car_id=open_task.train_car_id,
                        allocation_id=open_task.allocation_id,
                        seat_number=open_task.seat_number,
                    )
                except Exception:
                    pass
            async with SessionFactory() as session:
                await clear_task_hold_details(
                    session,
                    task_id=open_task.task_id,
                    status=SearchTaskStatus.running,
                    last_result="recovered after restart",
                )
        elif open_task.status == SearchTaskStatus.pending:
            async with SessionFactory() as session:
                await update_task_status(
                    session,
                    task_id=open_task.task_id,
                    status=SearchTaskStatus.running,
                    last_result="recovered after restart",
                )

        taskiq_result = await monitor_yht_task.kiq(open_task.task_id)
        taskiq_message_id = (
            getattr(getattr(taskiq_result, "message", None), "task_id", None)
            or getattr(taskiq_result, "task_id", None)
            or ""
        )
        async with SessionFactory() as session:
            await set_task_message_id(
                session,
                task_id=open_task.task_id,
                taskiq_message_id=taskiq_message_id,
            )


async def run_bot() -> None:
    await init_database()
    await TCDDClient().ensure_station_cache()
    await broker.startup()
    await _resume_open_yht_tasks()
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
