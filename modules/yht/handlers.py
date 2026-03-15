from __future__ import annotations

import asyncio
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from analytics.engine import get_trending_routes, get_user_search_frequency
from core.database import SessionFactory
from core.models import SearchTaskStatus, User, UserRole
from core.repositories import (
    cancel_task,
    clear_task_hold_details,
    create_search_task,
    get_admin_users,
    get_held_tasks_for_user,
    get_open_task_by_signature,
    get_open_tasks_for_user,
    get_user_task_by_public_id,
    set_task_message_id,
)
from modules.yht.logic import TCDDClient, YHTError
from modules.yht.config import yht_settings
from modules.yht.utils import (
    build_choice_keyboard,
    format_last_result_text,
    format_route_sentence,
    format_turkish_date_short,
    format_turkish_datetime_long,
    is_cancel_text,
    remove_choice_keyboard,
)
from tasks.worker import monitor_yht_task


router = Router(name="yht")


class SearchStates(StatesGroup):
    from_station = State()
    from_station_choice = State()
    to_station = State()
    to_station_choice = State()
    travel_date = State()
    travel_hour = State()
    cancel_task_choice = State()
    release_task_choice = State()


async def _send_delayed_support_message(message: Message) -> None:
    await asyncio.sleep(20)
    await message.bot.send_message(
        message.chat.id,
        "Hayır dualarınızı [buradan](https://buymeacoffee.com/atakanakin) kabul ediyorum.",
    )


def _format_admin_release_error(task, user, error_text: str) -> str:
    username = f"@{user.username}" if user and user.username else "-"
    return (
        "*YHT bırakma hatası*\n"
        f"*Kullanıcı:* {username}\n"
        f"*Telegram ID:* `{getattr(user, 'telegram_user_id', '-')}`\n"
        f"*Görev:* `{task.task_id}`\n"
        f"*Güzergâh:* {task.from_station} -> {task.to_station}\n"
        f"*Tarih:* {task.travel_date.isoformat()} {task.travel_hour}\n"
        f"*Koltuk:* {task.seat_number}\n"
        f"*Hata:* `{error_text}`"
    )


async def _notify_admins(message: Message, text: str) -> None:
    async with SessionFactory() as session:
        admin_users = await get_admin_users(session)
    for admin_user in admin_users:
        await message.bot.send_message(admin_user.telegram_user_id, text)


def _format_task_status(status: SearchTaskStatus) -> str:
    labels = {
        SearchTaskStatus.pending: "Bekliyor",
        SearchTaskStatus.running: "Çalışıyor",
        SearchTaskStatus.seat_held: "Koltuk tutuldu",
        SearchTaskStatus.cancelled: "İptal edildi",
        SearchTaskStatus.completed: "Tamamlandı",
        SearchTaskStatus.failed: "Hata",
    }
    return labels.get(status, status.value)


def _format_task_summary(task) -> str:
    return (
        f"*Durum:* {_format_task_status(task.status)}\n"
        f"*Güzergâh:* *{task.from_station} -> {task.to_station}*\n"
        f"*Tarih:* *{format_turkish_datetime_long(task.travel_date, task.travel_hour)}*"
    )


def _build_task_choice_label(task) -> str:
    return (
        f"{task.from_station} -> {task.to_station} | "
        f"{format_turkish_date_short(task.travel_date)} | {task.travel_hour}"
    )


def _get_parallel_task_limit(role: UserRole):
    normalized_role = UserRole.basic if role == UserRole.user else role
    if normalized_role == UserRole.admin:
        return None
    if normalized_role == UserRole.premium:
        return yht_settings.premium_user_max_parallel_tasks
    return yht_settings.basic_user_max_parallel_tasks


def _get_role_label(role: UserRole) -> str:
    normalized_role = UserRole.basic if role == UserRole.user else role
    labels = {
        UserRole.admin: "admin",
        UserRole.premium: "premium",
        UserRole.basic: "basic",
    }
    return labels[normalized_role]


async def _resolve_target_task(
    session,
    *,
    user_id: int,
    task_arg: str,
    allowed_statuses: tuple[SearchTaskStatus, ...],
):
    if not task_arg:
        return None
    task = await get_user_task_by_public_id(
        session,
        user_id=user_id,
        task_id=task_arg,
    )
    if task is None or task.status not in allowed_statuses:
        return None
    return task


async def _release_held_task(message: Message, task, db_user: User) -> bool:
    if (
        task.train_car_id is None
        or task.allocation_id is None
        or task.seat_number is None
    ):
        async with SessionFactory() as session:
            await clear_task_hold_details(
                session,
                task_id=task.task_id,
                status=SearchTaskStatus.failed,
                last_result="missing hold details",
            )
        await message.answer(
            "Tutulan koltuk bilgisi eksik olduğu için işlem sonlandırıldı.",
            reply_markup=remove_choice_keyboard(),
        )
        return False

    client = TCDDClient()
    async with SessionFactory() as session:
        fresh_task = await get_user_task_by_public_id(
            session,
            user_id=db_user.id,
            task_id=task.task_id,
        )
        if fresh_task is None:
            await message.answer(
                "İşlem kaydı bulunamadı.",
                reply_markup=remove_choice_keyboard(),
            )
            return False
        try:
            await client.release_seat(
                train_car_id=fresh_task.train_car_id,
                allocation_id=fresh_task.allocation_id,
                seat_number=fresh_task.seat_number,
            )
        except Exception as exc:
            await clear_task_hold_details(
                session,
                task_id=fresh_task.task_id,
                status=SearchTaskStatus.failed,
                last_result="seat release failed",
            )
            await _notify_admins(
                message,
                _format_admin_release_error(fresh_task, db_user, str(exc)),
            )
            await message.answer(
                "Tutulan koltuk artık aktif görünmüyor. Kayıt temizlendi.",
                reply_markup=remove_choice_keyboard(),
            )
            return False
        await clear_task_hold_details(
            session,
            task_id=fresh_task.task_id,
            status=SearchTaskStatus.completed,
            last_result="seat released by user",
        )
    return True


@router.message(Command("yht"))
async def handle_yht_start(message: Message, state: FSMContext, db_user: User) -> None:
    await state.set_state(SearchStates.from_station)
    await message.answer(
        "Kalkış şehrini yazınız.\n"
        "Örnek: `ank`, `ankara`, `ANkara`\n"
        "İptal etmek için `cancel` yazabilirsiniz."
    )


@router.message(SearchStates.from_station)
async def capture_from_station(message: Message, state: FSMContext) -> None:
    client = TCDDClient()
    if not message.text:
        await message.answer("Lütfen kalkış şehrini yazınız.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.", reply_markup=remove_choice_keyboard()
        )
        return
    matches = await client.get_matching_stations(message.text.strip())
    if not matches:
        await message.answer(
            "Kalkış noktası bulunamadı. Lütfen tekrar deneyin ya da `cancel` yazın."
        )
        return
    if len(matches) == 1:
        await state.update_data(from_station=matches[0])
        await state.set_state(SearchStates.to_station)
        await message.answer(
            "Varış şehrini yazınız.\n" "Örnek: `ist`, `istanbul`, `Eskişehir`",
            reply_markup=remove_choice_keyboard(),
        )
        return
    await state.update_data(from_station_options=matches)
    await state.set_state(SearchStates.from_station_choice)
    await message.answer(
        "*Aşağıdaki kalkış istasyonlarından birini seçin:*",
        reply_markup=build_choice_keyboard(matches),
    )


@router.message(SearchStates.from_station_choice)
async def capture_from_station_choice(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Listeden bir seçim yapın.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.", reply_markup=remove_choice_keyboard()
        )
        return
    data = await state.get_data()
    options = data.get("from_station_options", [])
    selected = message.text.strip()
    if selected not in options:
        await message.answer(
            "Listeden bir kalkış istasyonu seçin veya `cancel` yazın.",
            reply_markup=build_choice_keyboard(options),
        )
        return
    await state.update_data(from_station=selected, from_station_options=[])
    await state.set_state(SearchStates.to_station)
    await message.answer(
        "Varış şehrini yazınız.\n" "Örnek: `ist`, `istanbul`, `Eskişehir`",
        reply_markup=remove_choice_keyboard(),
    )


@router.message(SearchStates.to_station)
async def capture_to_station(message: Message, state: FSMContext) -> None:
    client = TCDDClient()
    if not message.text:
        await message.answer("Lütfen varış şehrini yazınız.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.", reply_markup=remove_choice_keyboard()
        )
        return
    matches = await client.get_matching_stations(message.text.strip())
    if not matches:
        await message.answer(
            "Varış noktası bulunamadı. Lütfen tekrar deneyin ya da `cancel` yazın."
        )
        return
    if len(matches) == 1:
        await state.update_data(to_station=matches[0])
        await state.set_state(SearchStates.travel_date)
        await message.answer(
            "Tarihi yazınız.\n" "Örnek: *16.03.2026*",
            reply_markup=remove_choice_keyboard(),
        )
        return
    await state.update_data(to_station_options=matches)
    await state.set_state(SearchStates.to_station_choice)
    await message.answer(
        "*Aşağıdaki varış istasyonlarından birini seçin:*",
        reply_markup=build_choice_keyboard(matches),
    )


@router.message(SearchStates.to_station_choice)
async def capture_to_station_choice(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Listeden bir seçim yapın.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.", reply_markup=remove_choice_keyboard()
        )
        return
    data = await state.get_data()
    options = data.get("to_station_options", [])
    selected = message.text.strip()
    if selected not in options:
        await message.answer(
            "Listeden bir varış istasyonu seçin veya `cancel` yazın.",
            reply_markup=build_choice_keyboard(options),
        )
        return
    await state.update_data(to_station=selected, to_station_options=[])
    await state.set_state(SearchStates.travel_date)
    await message.answer(
        "Tarihi yazınız.\n" "Örnek: *16.03.2026*",
        reply_markup=remove_choice_keyboard(),
    )


@router.message(SearchStates.travel_date)
async def capture_travel_date(message: Message, state: FSMContext) -> None:
    client = TCDDClient()
    if not message.text:
        await message.answer("Lütfen tarihi yazınız.\nÖrnek: *16.03.2026*")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.", reply_markup=remove_choice_keyboard()
        )
        return
    try:
        travel_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer(
            "Tarih formatı hatalı.\nLütfen *DD.MM.YYYY* formatında yazınız.\nÖrnek: *16.03.2026*"
        )
        return
    if travel_date < datetime.now().date():
        await message.answer(
            "Geçmiş bir tarih seçemezsiniz. Lütfen ileri bir tarih yazınız."
        )
        return
    data = await state.get_data()
    try:
        hour_options = await client.list_train_hours(
            from_station=data["from_station"],
            to_station=data["to_station"],
            travel_date=travel_date,
        )
    except YHTError as exc:
        await message.answer(
            f"İşlem sırasında bir sorun oluştu: {exc}",
            reply_markup=remove_choice_keyboard(),
        )
        return
    if not hour_options:
        await state.clear()
        await message.answer(
            "Bu tarih için uygun sefer bulunamadı. Lütfen başka bir tarih deneyin.",
            reply_markup=remove_choice_keyboard(),
        )
        return
    await state.update_data(
        travel_date=travel_date.isoformat(),
        hour_options=hour_options,
    )
    await state.set_state(SearchStates.travel_hour)
    await message.answer(
        "Saat seçiniz:",
        reply_markup=build_choice_keyboard(hour_options),
    )


@router.message(SearchStates.travel_hour)
async def capture_travel_hour(
    message: Message, state: FSMContext, db_user: User
) -> None:
    if not message.text:
        await message.answer("Lütfen bir saat seçiniz.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "İşlem iptal edildi.", reply_markup=remove_choice_keyboard()
        )
        return
    data = await state.get_data()
    hour_options = data.get("hour_options", [])
    selected_hour = message.text.strip()
    if selected_hour not in hour_options:
        await message.answer(
            "Listeden bir saat seçin veya `cancel` yazın.",
            reply_markup=build_choice_keyboard(hour_options),
        )
        return

    async with SessionFactory() as session:
        existing_task = await get_open_task_by_signature(
            session,
            user_id=db_user.id,
            from_station=data["from_station"],
            to_station=data["to_station"],
            travel_date=datetime.fromisoformat(data["travel_date"]).date(),
            travel_hour=selected_hour,
        )
        if existing_task is not None:
            await state.clear()
            if existing_task.status == SearchTaskStatus.seat_held:
                await message.answer(
                    f"{format_route_sentence(existing_task.from_station, existing_task.to_station, existing_task.travel_date, existing_task.travel_hour)} için zaten tutulmuş bir koltuk bulunuyor.\n"
                    "Koltuk bırakmak isterseniz /yhtrelease kullanabilirsiniz.",
                    reply_markup=remove_choice_keyboard(),
                )
                return
            await message.answer(
                f"{format_route_sentence(existing_task.from_station, existing_task.to_station, existing_task.travel_date, existing_task.travel_hour)} için zaten aktif bir arama bulunuyor.\n"
                "Tüm işlemleriniz için /yhtinfo kullanabilirsiniz.",
                reply_markup=remove_choice_keyboard(),
            )
            return
        open_tasks = await get_open_tasks_for_user(session, db_user.id)
        parallel_task_limit = _get_parallel_task_limit(db_user.role)
        if parallel_task_limit is not None and len(open_tasks) >= parallel_task_limit:
            await state.clear()
            await message.answer(
                "*YHT görev limitinize ulaştınız.*\n"
                f"*Rolünüz:* {_get_role_label(db_user.role)}\n"
                f"*Açık görev limiti:* {parallel_task_limit}\n"
                "Yeni bir arama başlatmadan önce açık işlemlerinizden birini sonlandırmanız gerekiyor.\n"
                "Tüm işlemleriniz için /yhtinfo kullanabilirsiniz.",
                reply_markup=remove_choice_keyboard(),
            )
            return
        task = await create_search_task(
            session,
            user_id=db_user.id,
            from_station=data["from_station"],
            to_station=data["to_station"],
            travel_date=datetime.fromisoformat(data["travel_date"]).date(),
            travel_hour=selected_hour,
        )

    taskiq_result = await monitor_yht_task.kiq(task.task_id)
    taskiq_message_id = (
        getattr(getattr(taskiq_result, "message", None), "task_id", None)
        or getattr(taskiq_result, "task_id", None)
        or ""
    )

    async with SessionFactory() as session:
        await set_task_message_id(
            session,
            task_id=task.task_id,
            taskiq_message_id=taskiq_message_id,
        )

    await state.clear()
    await message.answer(
        f"{format_route_sentence(data['from_station'], data['to_station'], datetime.fromisoformat(data['travel_date']).date(), selected_hour)} için arama başlatıldı.\n"
        "Tüm işlemleriniz için /yhtinfo kullanabilirsiniz.",
        reply_markup=remove_choice_keyboard(),
    )


@router.message(Command("yhtcancel"))
async def handle_yht_cancel(
    message: Message,
    state: FSMContext,
    db_user: User,
    command: CommandObject,
) -> None:
    await state.clear()
    async with SessionFactory() as session:
        open_tasks = await get_open_tasks_for_user(session, db_user.id)
        if not open_tasks:
            await message.answer(
                "Aktif bir YHT araması bulunamadı.",
                reply_markup=remove_choice_keyboard(),
            )
            return

        task_arg = (command.args or "").strip()
        target_task = await _resolve_target_task(
            session,
            user_id=db_user.id,
            task_arg=task_arg,
            allowed_statuses=(
                SearchTaskStatus.pending,
                SearchTaskStatus.running,
                SearchTaskStatus.seat_held,
            ),
        )
        if task_arg and target_task is None:
            await message.answer(
                "Geçerli bir aktif işlem bulunamadı. Tüm işlemleriniz için /yhtinfo kullanabilirsiniz.",
                reply_markup=remove_choice_keyboard(),
            )
            return
        if target_task is None and len(open_tasks) == 1:
            target_task = open_tasks[0]
        elif target_task is None:
            options = {
                _build_task_choice_label(task): task.task_id for task in open_tasks
            }
            await state.update_data(cancel_task_options=options)
            await state.set_state(SearchStates.cancel_task_choice)
            await message.answer(
                "İptal etmek istediğiniz işlemi seçin:",
                reply_markup=build_choice_keyboard(options.keys()),
            )
            return

        if target_task.status == SearchTaskStatus.seat_held:
            released = await _release_held_task(message, target_task, db_user)
            if not released:
                return
            await message.answer(
                "Tutulan koltuk bırakıldı ve işlem sonlandırıldı.",
                reply_markup=remove_choice_keyboard(),
            )
            asyncio.create_task(_send_delayed_support_message(message))
            return

        await cancel_task(session, target_task.task_id)
    await message.answer(
        "YHT araması iptal edildi.",
        reply_markup=remove_choice_keyboard(),
    )


@router.message(SearchStates.cancel_task_choice)
async def handle_yht_cancel_choice(
    message: Message,
    state: FSMContext,
    db_user: User,
) -> None:
    if not message.text:
        await message.answer("Listeden bir görev seçin.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "*İşlem iptal edildi.*",
            reply_markup=remove_choice_keyboard(),
        )
        return
    data = await state.get_data()
    options = data.get("cancel_task_options", {})
    selected = message.text.strip()
    task_id = options.get(selected)
    if not task_id:
        await message.answer(
            "Listeden bir görev seçin veya `cancel` yazın.",
            reply_markup=build_choice_keyboard(options.keys()),
        )
        return
    async with SessionFactory() as session:
        target_task = await _resolve_target_task(
            session,
            user_id=db_user.id,
            task_arg=task_id,
            allowed_statuses=(
                SearchTaskStatus.pending,
                SearchTaskStatus.running,
                SearchTaskStatus.seat_held,
            ),
        )
        if target_task is None:
            await state.clear()
            await message.answer(
                "Seçtiğiniz işlem artık aktif değil.",
                reply_markup=remove_choice_keyboard(),
            )
            return
        if target_task.status == SearchTaskStatus.seat_held:
            released = await _release_held_task(message, target_task, db_user)
            await state.clear()
            if not released:
                return
            await message.answer(
                "Tutulan koltuk bırakıldı ve işlem sonlandırıldı.",
                reply_markup=remove_choice_keyboard(),
            )
            asyncio.create_task(_send_delayed_support_message(message))
            return
        await cancel_task(session, target_task.task_id)
    await state.clear()
    await message.answer(
        "YHT araması iptal edildi.",
        reply_markup=remove_choice_keyboard(),
    )


@router.message(Command("yhtrelease"))
async def handle_yht_release(
    message: Message,
    state: FSMContext,
    db_user: User,
    command: CommandObject,
) -> None:
    await state.clear()
    async with SessionFactory() as session:
        held_tasks = await get_held_tasks_for_user(session, db_user.id)
        if not held_tasks:
            await message.answer(
                "Bırakılacak tutulmuş koltuk bulunamadı.",
                reply_markup=remove_choice_keyboard(),
            )
            return
        task_arg = (command.args or "").strip()
        held_task = await _resolve_target_task(
            session,
            user_id=db_user.id,
            task_arg=task_arg,
            allowed_statuses=(SearchTaskStatus.seat_held,),
        )
        if task_arg and held_task is None:
            await message.answer(
                "Belirtilen işlemde tutulmuş koltuk bulunamadı. Tüm işlemleriniz için /yhtinfo kullanabilirsiniz.",
                reply_markup=remove_choice_keyboard(),
            )
            return
        if held_task is None and len(held_tasks) == 1:
            held_task = held_tasks[0]
        elif held_task is None:
            options = {
                _build_task_choice_label(task): task.task_id for task in held_tasks
            }
            await state.update_data(release_task_options=options)
            await state.set_state(SearchStates.release_task_choice)
            await message.answer(
                "Bırakmak istediğiniz koltuğu seçin:",
                reply_markup=build_choice_keyboard(options.keys()),
            )
            return
    released = await _release_held_task(message, held_task, db_user)
    if not released:
        return
    await message.answer(
        "Tutulan koltuk bırakıldı.", reply_markup=remove_choice_keyboard()
    )
    asyncio.create_task(_send_delayed_support_message(message))


@router.message(SearchStates.release_task_choice)
async def handle_yht_release_choice(
    message: Message,
    state: FSMContext,
    db_user: User,
) -> None:
    if not message.text:
        await message.answer("Listeden bir görev seçin.")
        return
    if is_cancel_text(message.text):
        await state.clear()
        await message.answer(
            "*İşlem iptal edildi.*",
            reply_markup=remove_choice_keyboard(),
        )
        return
    data = await state.get_data()
    options = data.get("release_task_options", {})
    selected = message.text.strip()
    task_id = options.get(selected)
    if not task_id:
        await message.answer(
            "Listeden bir görev seçin veya `cancel` yazın.",
            reply_markup=build_choice_keyboard(options.keys()),
        )
        return
    async with SessionFactory() as session:
        held_task = await _resolve_target_task(
            session,
            user_id=db_user.id,
            task_arg=task_id,
            allowed_statuses=(SearchTaskStatus.seat_held,),
        )
        if held_task is None:
            await state.clear()
            await message.answer(
                "Seçtiğiniz işlemde artık tutulmuş koltuk bulunmuyor.",
                reply_markup=remove_choice_keyboard(),
            )
            return
    released = await _release_held_task(message, held_task, db_user)
    await state.clear()
    if not released:
        return
    await message.answer(
        "Tutulan koltuk bırakıldı.",
        reply_markup=remove_choice_keyboard(),
    )
    asyncio.create_task(_send_delayed_support_message(message))


@router.message(Command("yhtinfo"))
async def handle_yht_info(message: Message, db_user: User) -> None:
    async with SessionFactory() as session:
        open_tasks = await get_open_tasks_for_user(session, db_user.id)
    if not open_tasks:
        await message.answer("Aktif ya da tutulmuş bir YHT işleminiz bulunmuyor.")
        return

    lines = ["*Açık YHT işlemleriniz*"]
    for index, task in enumerate(open_tasks, start=1):
        lines.append(f"{index}.")
        lines.append(_format_task_summary(task))
        if task.last_result:
            lines.append(f"*Son durum:* {format_last_result_text(task.last_result)}")
    await message.answer("\n".join(lines))


@router.message(Command("stats"))
async def handle_stats(message: Message, db_user: User) -> None:
    async with SessionFactory() as session:
        stats = await get_user_search_frequency(session, user_id=db_user.id)
    await message.answer(
        "*Arama sıklığınız*\n"
        f"*Toplam arama:* {stats['total_searches']}\n"
        f"*Farklı seyahat tarihi:* {stats['distinct_travel_dates']}"
    )


@router.message(Command("trending"))
async def handle_trending(message: Message) -> None:
    async with SessionFactory() as session:
        routes = await get_trending_routes(session)
    if not routes:
        await message.answer("*Henüz güzergâh istatistiği yok.*")
        return
    formatted = "\n".join(
        f"{index}. {item['from_station']} -> {item['to_station']} ({item['search_count']})"
        for index, item in enumerate(routes, start=1)
    )
    await message.answer(f"*Popüler güzergâhlar*\n{formatted}")
