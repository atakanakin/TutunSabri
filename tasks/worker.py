from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from taskiq_redis import ListQueueBroker

from core.config import settings
from core.database import SessionFactory, init_database
from core.models import SearchTaskStatus
from core.repositories import (
    get_admin_users,
    get_task_by_public_id,
    get_user_by_id,
    set_task_hold_details,
    update_task_counts,
    update_task_status,
)
from modules.yht.config import yht_settings
from modules.yht.logic import TCDDClient, YHTError
from modules.yht.utils import format_route_sentence


broker = ListQueueBroker(url=settings.redis_url)


@broker.on_event("startup")
async def startup() -> None:
    await init_database()
    await TCDDClient().ensure_station_cache()


def _format_admin_error(task, user, error_text: str) -> str:
    username = f"@{user.username}" if user and user.username else "-"
    return (
        "*YHT hata bildirimi*\n"
        f"*Kullanıcı:* {username}\n"
        f"*Telegram ID:* `{getattr(user, 'telegram_user_id', '-')}`\n"
        f"*Görev:* `{task.task_id}`\n"
        f"*Güzergâh:* {task.from_station} -> {task.to_station}\n"
        f"*Tarih:* {task.travel_date.isoformat()} {task.travel_hour}\n"
        f"*Durum:* {task.status.value}\n"
        f"*Hata:* `{error_text}`"
    )


async def _notify_admins(bot: Bot, text: str) -> None:
    async with SessionFactory() as session:
        admin_users = await get_admin_users(session)
    for admin_user in admin_users:
        await bot.send_message(admin_user.telegram_user_id, text)


def _economy_message(task, economy_count: int) -> str:
    route_text = format_route_sentence(
        task.from_station,
        task.to_station,
        task.travel_date,
        task.travel_hour,
    )
    if economy_count == 0:
        return f"{route_text} *ekonomi* sınıfında *boş koltuk bulunmamaktadır.*"
    return (
        f"{route_text} *ekonomi* sınıfında *{economy_count}* boş koltuk bulunmaktadır."
    )


def _business_message(task, business_count: int) -> str:
    route_text = format_route_sentence(
        task.from_station,
        task.to_station,
        task.travel_date,
        task.travel_hour,
    )
    if business_count == 0:
        return f"{route_text} *business* sınıfında *boş koltuk bulunmamaktadır.*"
    return f"{route_text} *business* sınıfında *{business_count}* boş koltuk bulunmaktadır."


def _hold_message(task, hold_result: dict, hold_attempt_count: int) -> str:
    route_text = format_route_sentence(
        task.from_station,
        task.to_station,
        task.travel_date,
        task.travel_hour,
    )
    return (
        f"{route_text} için *{hold_result['wagon_number']}. vagonda {hold_result['seat_number']}* numaralı koltuk tutuldu.\n"
        f"Koltuk *{yht_settings.hold_duration_minutes} dakika* boyunca sizin için tutulacaktır.\n"
        "İsterseniz koltuğu /yhtrelease komutuyla hemen bırakabilirsiniz."
    )


@broker.task
async def monitor_yht_task(task_id: str) -> None:
    client = TCDDClient()
    error_count = 0
    sleep_seconds = yht_settings.poll_interval_seconds
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )

    try:
        while True:
            sleep_seconds = yht_settings.poll_interval_seconds
            async with SessionFactory() as session:
                task = await get_task_by_public_id(session, task_id)
                if task is None:
                    return
                user = await get_user_by_id(session, task.user_id)
                if user is None:
                    await update_task_status(
                        session,
                        task_id=task_id,
                        status=SearchTaskStatus.failed,
                        last_result="user record missing",
                    )
                    return

                if task.status in {SearchTaskStatus.completed, SearchTaskStatus.failed}:
                    return

                if task.status == SearchTaskStatus.cancelled:
                    await bot.send_message(
                        user.telegram_user_id,
                        "YHT araması iptal edildi.",
                    )
                    return

                if task.status == SearchTaskStatus.seat_held:
                    expires_at = task.hold_expires_at
                    now = datetime.now(timezone.utc)
                    if expires_at is not None and expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at is not None and expires_at > now:
                        remaining_seconds = int((expires_at - now).total_seconds())
                        sleep_seconds = max(
                            1,
                            min(yht_settings.poll_interval_seconds, remaining_seconds),
                        )
                    else:
                        attempts = task.hold_attempt_count or 0
                        if (
                            task.train_car_id is not None
                            and task.allocation_id is not None
                            and task.seat_number is not None
                        ):
                            try:
                                await client.release_seat(
                                    train_car_id=task.train_car_id,
                                    allocation_id=task.allocation_id,
                                    seat_number=task.seat_number,
                                )
                            except Exception:
                                pass

                        if attempts >= yht_settings.max_hold_attempts:
                            await update_task_status(
                                session,
                                task_id=task_id,
                                status=SearchTaskStatus.completed,
                                last_result="hold retry limit reached",
                            )
                            await bot.send_message(
                                user.telegram_user_id,
                                "Tutulan koltuğun süresi doldu ve yeniden deneme sınırına ulaşıldı. İşlem sonlandırıldı.",
                            )
                            return

                        task.train_id = None
                        task.train_car_id = None
                        task.allocation_id = None
                        task.seat_number = None
                        task.hold_expires_at = None
                        task.status = SearchTaskStatus.running
                        task.last_checked_at = now
                        task.last_result = f"hold expired, retrying ({attempts}/{yht_settings.max_hold_attempts})"
                        await session.commit()
                        await bot.send_message(
                            user.telegram_user_id,
                            "Tutulan koltuğun süresi doldu. Sistem yeniden koltuk tutmayı deneyecek.",
                        )
                        task = await get_task_by_public_id(session, task_id)
                        if task is None:
                            return
                    if task.status == SearchTaskStatus.seat_held:
                        await asyncio.sleep(sleep_seconds)
                        continue

                await update_task_status(
                    session,
                    task_id=task_id,
                    status=SearchTaskStatus.running,
                    last_result="checking availability",
                )

                try:
                    availability = await client.check_specific_departure(
                        from_station=task.from_station,
                        to_station=task.to_station,
                        travel_date=task.travel_date,
                        travel_hour=task.travel_hour,
                    )
                except YHTError as exc:
                    error_count += 1
                    await update_task_status(
                        session,
                        task_id=task_id,
                        status=(
                            SearchTaskStatus.failed
                            if error_count >= yht_settings.max_poll_errors
                            else SearchTaskStatus.running
                        ),
                        last_result=f"tcdd error: {exc}",
                    )
                    if error_count >= yht_settings.max_poll_errors:
                        await bot.send_message(
                            user.telegram_user_id,
                            "YHT araması sırasında bir sorun oluştu. Lütfen daha sonra tekrar deneyin.",
                        )
                        await _notify_admins(
                            bot, _format_admin_error(task, user, str(exc))
                        )
                        return
                except Exception as exc:
                    error_count += 1
                    await update_task_status(
                        session,
                        task_id=task_id,
                        status=(
                            SearchTaskStatus.failed
                            if error_count >= yht_settings.max_poll_errors
                            else SearchTaskStatus.running
                        ),
                        last_result=f"unexpected error: {exc}",
                    )
                    if error_count >= yht_settings.max_poll_errors:
                        await bot.send_message(
                            user.telegram_user_id,
                            "YHT araması sırasında bir hata oluştu. Lütfen daha sonra tekrar deneyin.",
                        )
                        await _notify_admins(
                            bot, _format_admin_error(task, user, str(exc))
                        )
                        return
                else:
                    error_count = 0

                    if availability is None:
                        previous_text = task.last_result or ""
                        message = "Seçtiğiniz saat için tren bulunamadı."
                        await update_task_status(
                            session,
                            task_id=task_id,
                            status=SearchTaskStatus.running,
                            last_result="train not found for selected departure",
                        )
                        if previous_text != "train not found for selected departure":
                            await bot.send_message(user.telegram_user_id, message)
                    elif availability.economy_available > 0:
                        hold_result = await client.hold_seat(
                            train_id=availability.train_id,
                            from_station=task.from_station,
                            to_station=task.to_station,
                        )
                        hold_attempt_count = (task.hold_attempt_count or 0) + 1
                        message = _hold_message(
                            task,
                            hold_result,
                            hold_attempt_count,
                        )
                        await set_task_hold_details(
                            session,
                            task_id=task_id,
                            train_id=int(hold_result["train_id"]),
                            train_car_id=int(hold_result["train_car_id"]),
                            allocation_id=str(hold_result["allocation_id"]),
                            seat_number=str(hold_result["seat_number"]),
                            last_result=message,
                        )
                        await bot.send_message(user.telegram_user_id, message)
                        sleep_seconds = yht_settings.poll_interval_seconds
                    else:
                        outgoing_messages = []
                        if task.last_economy_count != availability.economy_available:
                            outgoing_messages.append(
                                _economy_message(task, availability.economy_available)
                            )
                        if task.last_business_count != availability.business_available:
                            outgoing_messages.append(
                                _business_message(task, availability.business_available)
                            )
                        snapshot_text = (
                            f"economy={availability.economy_available}, "
                            f"business={availability.business_available}"
                        )
                        await update_task_counts(
                            session,
                            task_id=task_id,
                            economy_count=availability.economy_available,
                            business_count=availability.business_available,
                            last_result=snapshot_text,
                        )
                        for outgoing_message in outgoing_messages:
                            await bot.send_message(
                                user.telegram_user_id, outgoing_message
                            )
            await asyncio.sleep(sleep_seconds)
    finally:
        await bot.session.close()
