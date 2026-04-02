from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Optional

from aiogram import Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from core.database import SessionFactory
from core.models import User, UserRole
from core.repositories import (
    approve_access_request,
    create_or_refresh_access_request,
    get_all_active_users,
    get_all_open_tasks,
    get_all_users,
    get_admin_users,
    get_first_admin_username,
    get_pending_access_requests,
    get_user_by_id,
    mark_access_request_notified,
    reject_access_request,
    revoke_user_access,
    update_user_role,
)
from modules.yht.utils import format_turkish_datetime_long


router = Router(name="core")
INFO_DIR = Path(__file__).resolve().parent.parent / "info"
WHOAMI_PHOTO_ID = "AgACAgQAAxkBAAEBmO1puqJkukjL7wkCMy3c9ojTYBgjhgACvwxrG5X40VE1D6KSZ8KwFwEAAwIAA3cAAzoE"


class BroadcastStates(StatesGroup):
    waiting_payload = State()
    waiting_caption = State()


def _request_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Yetki İste", callback_data="request_access"),
                InlineKeyboardButton(text="İptal", callback_data="cancel_access"),
            ]
        ]
    )


def _is_admin(db_user: User) -> bool:
    role = UserRole.basic if db_user.role == UserRole.user else db_user.role
    return role == UserRole.admin


def _format_role(role: UserRole) -> str:
    normalized_role = UserRole.basic if role == UserRole.user else role
    return normalized_role.value


def _start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Ben Kimim?", callback_data="info_whoami"),
                InlineKeyboardButton(
                    text="Nasıl Çalışır?", callback_data="info_how_it_works"
                ),
            ],
            [InlineKeyboardButton(text="İletişim", callback_data="info_contact")],
        ]
    )


def _read_info_markdown(filename: str) -> str:
    return (INFO_DIR / filename).read_text(encoding="utf-8").strip()


def _broadcast_caption_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Caption Ekle",
                    callback_data="broadcast_add_caption",
                ),
                InlineKeyboardButton(
                    text="Caption Ekleme",
                    callback_data="broadcast_skip_caption",
                ),
            ]
        ]
    )


def _admin_display_name(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Yönetici"


def _safe_value(value: Optional[object], fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _safe_username(username: Optional[str]) -> str:
    username_text = _safe_value(username)
    if username_text == "-":
        return username_text
    if username_text.startswith("@"):
        return username_text
    return f"@{username_text}"


def _safe_full_name(first_name: Optional[str], last_name: Optional[str]) -> str:
    parts = [_safe_value(first_name, ""), _safe_value(last_name, "")]
    full_name = " ".join(part for part in parts if part).strip()
    return full_name or "-"


def _build_media_caption(db_user: User, media_type: str, extra_html: str = "") -> str:
    admin_name = escape(_admin_display_name(db_user))
    base_map = {
        "photo": f"{admin_name} bu fotoğrafı herkesin görmesi gerektiğini düşünüyor.",
        "video": f"{admin_name} bu videoyu herkesin izlemesi gerektiğini düşünüyor.",
        "audio": f"{admin_name} bu ses dosyasını herkesin dinlemesi gerektiğini düşünüyor.",
        "document": f"{admin_name} bu dosyayı herkesin görmesi gerektiğini düşünüyor.",
    }
    base_text = base_map[media_type]
    if extra_html.strip():
        return f"{base_text}\n\n{extra_html.strip()}"
    return base_text


def _format_broadcast_delivery_error(user: User, error_text: str) -> str:
    username = escape(_safe_username(user.username))
    full_name = escape(_safe_full_name(user.first_name, user.last_name))
    telegram_user_id = escape(_safe_value(user.telegram_user_id))
    return (
        "<b>Broadcast teslim hatası</b>\n"
        f"<b>Kullanıcı:</b> {username}\n"
        f"<b>Telegram ID:</b> <code>{telegram_user_id}</code>\n"
        f"<b>Ad Soyad:</b> {full_name}\n"
        f"<b>Hata:</b> <code>{escape(error_text)}</code>"
    )


async def _notify_admins(bot, html_text: str) -> None:
    async with SessionFactory() as session:
        admin_users = await get_admin_users(session)
    for admin_user in admin_users:
        await bot.send_message(
            admin_user.telegram_user_id,
            html_text,
            parse_mode="HTML",
        )


async def _send_html_broadcast(bot, html_text: str) -> tuple[int, int]:
    async with SessionFactory() as session:
        users = await get_all_active_users(session)
    sent_count = 0
    failed_count = 0
    for user in users:
        try:
            await bot.send_message(
                user.telegram_user_id,
                html_text,
                parse_mode="HTML",
            )
            sent_count += 1
        except (TelegramForbiddenError, TelegramAPIError) as exc:
            failed_count += 1
            await _notify_admins(bot, _format_broadcast_delivery_error(user, str(exc)))
    return sent_count, failed_count


async def _send_media_broadcast(
    bot,
    *,
    media_type: str,
    file_id: str,
    caption_html: str,
) -> tuple[int, int]:
    async with SessionFactory() as session:
        users = await get_all_active_users(session)
    sent_count = 0
    failed_count = 0
    for user in users:
        try:
            if media_type == "photo":
                await bot.send_photo(
                    user.telegram_user_id,
                    file_id,
                    caption=caption_html,
                    parse_mode="HTML",
                )
            elif media_type == "video":
                await bot.send_video(
                    user.telegram_user_id,
                    file_id,
                    caption=caption_html,
                    parse_mode="HTML",
                    supports_streaming=True,
                )
            elif media_type == "audio":
                await bot.send_audio(
                    user.telegram_user_id,
                    file_id,
                    caption=caption_html,
                    parse_mode="HTML",
                )
            elif media_type == "document":
                await bot.send_document(
                    user.telegram_user_id,
                    file_id,
                    caption=caption_html,
                    parse_mode="HTML",
                )
            sent_count += 1
        except (TelegramForbiddenError, TelegramAPIError) as exc:
            failed_count += 1
            await _notify_admins(bot, _format_broadcast_delivery_error(user, str(exc)))
    return sent_count, failed_count


def _extract_broadcast_media(message: Message) -> tuple[Optional[str], Optional[str]]:
    if message.photo:
        return "photo", message.photo[-1].file_id
    if message.video:
        return "video", message.video.file_id
    if message.audio:
        return "audio", message.audio.file_id
    if message.document:
        return "document", message.document.file_id
    return None, None


async def _set_role_for_user(
    message: Message,
    db_user: User,
    *,
    role: UserRole,
) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(f"Kullanım: `/{role.value} TELEGRAM_ID`")
        return
    telegram_user_id = int(parts[1])
    async with SessionFactory() as session:
        user = await update_user_role(
            session,
            telegram_user_id=telegram_user_id,
            role=role,
        )
    if user is None:
        await message.answer("Kullanıcı bulunamadı.")
        return
    await message.answer(
        f"Kullanıcının rolü güncellendi: `{telegram_user_id}` -> `{role.value}`"
    )
    if role == UserRole.premium:
        await message.bot.send_message(
            telegram_user_id,
            "Premium'a yükseltildiniz. Aynı anda 5 bilet arayabilirsiniz.",
        )


@router.message(Command(commands=["start", "help", "info"]))
async def handle_start(message: Message, db_user: Optional[User] = None) -> None:
    await message.answer(
        _read_info_markdown("start.md"),
        reply_markup=_start_keyboard(),
    )


@router.message(Command("pedro"))
async def handle_pedro(message: Message, db_user: User) -> None:
    await message.answer_video(
        "BAACAgQAAxkDAAIEI2YkHfk_t10R31SISqYxWk27VaDcAAJGEwACwmwgUZ6kBxvyfD_UNAQ",
        supports_streaming=True,
        width=1920,
        height=1080,
    )


@router.callback_query(lambda query: query.data == "info_whoami")
async def handle_info_whoami(query: CallbackQuery) -> None:
    await query.answer()
    if query.message is not None:
        await query.message.answer(_read_info_markdown("whoami.md"))
        await query.message.answer_photo(
            WHOAMI_PHOTO_ID,
            caption="Gerçekte ben",
        )


@router.callback_query(lambda query: query.data == "info_how_it_works")
async def handle_info_how_it_works(query: CallbackQuery) -> None:
    await query.answer()
    if query.message is not None:
        await query.message.answer(_read_info_markdown("howtowork.md"))


@router.callback_query(lambda query: query.data == "info_contact")
async def handle_info_contact(query: CallbackQuery) -> None:
    await query.answer()
    if query.message is not None:
        await query.message.answer(_read_info_markdown("contact.md"))


@router.callback_query(lambda query: query.data == "cancel_access")
async def handle_cancel_access(query: CallbackQuery) -> None:
    if query.message is not None:
        await query.message.edit_reply_markup(reply_markup=None)
    await query.answer("İşlem iptal edildi.")


@router.callback_query(lambda query: query.data == "request_access")
async def handle_request_access(query: CallbackQuery) -> None:
    from_user = query.from_user
    async with SessionFactory() as session:
        access_request = await create_or_refresh_access_request(
            session,
            telegram_user_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
        )
        admin_users = await get_admin_users(session)

    username = escape(_safe_username(from_user.username))
    full_name = escape(_safe_full_name(from_user.first_name, from_user.last_name))
    telegram_user_id = escape(_safe_value(from_user.id))
    notify_text = (
        "<b>Yeni yetki talebi</b>\n"
        f"<b>Kullanıcı:</b> {username}\n"
        f"<b>Telegram ID:</b> <code>{telegram_user_id}</code>\n"
        f"<b>Ad Soyad:</b> {full_name}\n"
        f"<b>Onay:</b> <code>/grant {telegram_user_id}</code>\n"
        f"<b>Reddet / Kapat:</b> <code>/revoke {telegram_user_id}</code>"
    )
    if not access_request.is_notified:
        for admin_user in admin_users:
            await query.bot.send_message(
                admin_user.telegram_user_id,
                notify_text,
                parse_mode="HTML",
            )
        async with SessionFactory() as session:
            await mark_access_request_notified(
                session,
                telegram_user_id=from_user.id,
            )

    if query.message is not None:
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.answer(
            "Yetki talebiniz yöneticilere iletildi.\nLütfen yanıt bekleyin."
        )
    await query.answer("Talep gönderildi.")


@router.message(Command("requests"))
async def handle_requests(message: Message, db_user: User) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    async with SessionFactory() as session:
        requests = await get_pending_access_requests(session)
    if not requests:
        await message.answer("Bekleyen yetki talebi bulunmuyor.")
        return
    lines = ["<b>Bekleyen yetki talepleri</b>"]
    for item in requests:
        username = escape(_safe_username(item.username))
        full_name = escape(_safe_full_name(item.first_name, item.last_name))
        telegram_user_id = escape(_safe_value(item.telegram_user_id))
        lines.append(
            f"{username} | <code>{telegram_user_id}</code> | {full_name}\n"
            f"<code>/grant {telegram_user_id}</code>\n"
            f"<code>/revoke {telegram_user_id}</code>"
        )
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(Command("users"))
async def handle_users(message: Message, db_user: User) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    async with SessionFactory() as session:
        users = await get_all_users(session)
    if not users:
        await message.answer("Kayıtlı kullanıcı bulunmuyor.")
        return
    lines = ["<b>Kullanıcı listesi</b>"]
    for user in users:
        username = escape(_safe_username(user.username))
        status = "aktif" if user.is_active else "pasif"
        full_name = escape(_safe_full_name(user.first_name, user.last_name))
        telegram_user_id = escape(_safe_value(user.telegram_user_id))
        role = escape(_safe_value(_format_role(user.role)))
        lines.append(
            f"{username} | <code>{telegram_user_id}</code>\n"
            f"<b>Rol:</b> {role} | <b>Durum:</b> {escape(status)}\n"
            f"<b>Ad Soyad:</b> {full_name}"
        )
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(Command("process"))
async def handle_processes(message: Message, db_user: User) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    async with SessionFactory() as session:
        tasks = await get_all_open_tasks(session)
        users_by_id = {}
        for task in tasks:
            if task.user_id not in users_by_id:
                users_by_id[task.user_id] = await get_user_by_id(session, task.user_id)
    if not tasks:
        await message.answer("Aktif çalışan YHT görevi bulunmuyor.")
        return
    lines = ["<b>Aktif süreçler</b>"]
    for task in tasks:
        user = users_by_id.get(task.user_id)
        username = _safe_username(getattr(user, "username", None))
        lines.append(
            f"<b>Görev:</b> <code>{escape(task.task_id)}</code>\n"
            f"<b>Kullanıcı:</b> {escape(username)} "
            f"(<code>{escape(_safe_value(getattr(user, 'telegram_user_id', task.user_id)))}</code>)\n"
            f"<b>Durum:</b> {escape(task.status.value)}\n"
            f"<b>Güzergâh:</b> {escape(_safe_value(task.from_station))} -&gt; {escape(_safe_value(task.to_station))}\n"
            f"<b>Kalkış:</b> {escape(format_turkish_datetime_long(task.travel_date, task.travel_hour))}"
        )
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(Command("basic"))
async def handle_basic_role(message: Message, db_user: User) -> None:
    await _set_role_for_user(message, db_user, role=UserRole.basic)


@router.message(Command("premium"))
async def handle_premium_role(message: Message, db_user: User) -> None:
    await _set_role_for_user(message, db_user, role=UserRole.premium)


@router.message(Command("admin"))
async def handle_admin_role(message: Message, db_user: User) -> None:
    await _set_role_for_user(message, db_user, role=UserRole.admin)


@router.message(Command("broadcast"))
async def handle_broadcast_start(
    message: Message,
    state: FSMContext,
    db_user: User,
) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    await state.clear()
    await state.set_state(BroadcastStates.waiting_payload)
    await message.answer(
        "Broadcast için bir metin, fotoğraf, video, ses dosyası veya belge gönderin.\n"
        "İptal etmek için `cancel` yazabilirsiniz."
    )


@router.message(BroadcastStates.waiting_payload)
async def handle_broadcast_payload(
    message: Message,
    state: FSMContext,
    db_user: User,
) -> None:
    if not _is_admin(db_user):
        await state.clear()
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    if message.text and message.text.strip().lower() == "cancel":
        await state.clear()
        await message.answer("Broadcast işlemi iptal edildi.")
        return
    if message.text:
        await state.clear()
        sent_count, failed_count = await _send_html_broadcast(message.bot, message.text)
        await message.answer(
            f"Broadcast gönderildi. Başarılı: {sent_count} | Başarısız: {failed_count}"
        )
        return

    media_type, file_id = _extract_broadcast_media(message)
    if media_type is None or file_id is None:
        await message.answer(
            "Lütfen metin, fotoğraf, video, ses dosyası veya belge gönderin."
        )
        return

    await state.update_data(
        broadcast_media_type=media_type,
        broadcast_file_id=file_id,
    )
    await message.answer(
        "Bu içerik için caption eklensin mi?",
        reply_markup=_broadcast_caption_keyboard(),
    )


@router.callback_query(lambda query: query.data == "broadcast_add_caption")
async def handle_broadcast_add_caption(
    query: CallbackQuery,
    state: FSMContext,
    db_user: User,
) -> None:
    if not _is_admin(db_user):
        await query.answer("Bu işlem için yetkiniz yok.", show_alert=True)
        return
    await state.set_state(BroadcastStates.waiting_caption)
    if query.message is not None:
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.answer(
            "Caption metnini HTML formatında gönderin.\nİptal etmek için `cancel` yazabilirsiniz."
        )
    await query.answer()


@router.callback_query(lambda query: query.data == "broadcast_skip_caption")
async def handle_broadcast_skip_caption(
    query: CallbackQuery,
    state: FSMContext,
    db_user: User,
) -> None:
    if not _is_admin(db_user):
        await query.answer("Bu işlem için yetkiniz yok.", show_alert=True)
        return
    data = await state.get_data()
    media_type = data.get("broadcast_media_type")
    file_id = data.get("broadcast_file_id")
    if not media_type or not file_id:
        await state.clear()
        await query.answer("Broadcast verisi bulunamadı.", show_alert=True)
        return
    caption_html = _build_media_caption(db_user, media_type)
    await state.clear()
    sent_count, failed_count = await _send_media_broadcast(
        query.bot,
        media_type=media_type,
        file_id=file_id,
        caption_html=caption_html,
    )
    if query.message is not None:
        await query.message.edit_reply_markup(reply_markup=None)
        await query.message.answer(
            f"Broadcast gönderildi. Başarılı: {sent_count} | Başarısız: {failed_count}"
        )
    await query.answer()


@router.message(BroadcastStates.waiting_caption)
async def handle_broadcast_caption(
    message: Message,
    state: FSMContext,
    db_user: User,
) -> None:
    if not _is_admin(db_user):
        await state.clear()
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    if message.text and message.text.strip().lower() == "cancel":
        await state.clear()
        await message.answer("Broadcast işlemi iptal edildi.")
        return
    if not message.text:
        await message.answer("Lütfen caption metnini HTML formatında gönderin.")
        return
    data = await state.get_data()
    media_type = data.get("broadcast_media_type")
    file_id = data.get("broadcast_file_id")
    if not media_type or not file_id:
        await state.clear()
        await message.answer("Broadcast verisi bulunamadı.")
        return
    caption_html = _build_media_caption(db_user, media_type, message.text)
    await state.clear()
    sent_count, failed_count = await _send_media_broadcast(
        message.bot,
        media_type=media_type,
        file_id=file_id,
        caption_html=caption_html,
    )
    await message.answer(
        f"Broadcast gönderildi. Başarılı: {sent_count} | Başarısız: {failed_count}"
    )


@router.message(Command("grant"))
async def handle_grant(message: Message, db_user: User) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Kullanım: `/grant TELEGRAM_ID`")
        return
    telegram_user_id = int(parts[1])
    async with SessionFactory() as session:
        user = await approve_access_request(session, telegram_user_id=telegram_user_id)
    if user is None:
        await message.answer("Kullanıcı kaydı oluşturulamadı.")
        return
    await message.answer(f"Kullanıcı onaylandı: `{telegram_user_id}`")
    await message.bot.send_message(
        telegram_user_id,
        "Bot erişim yetkiniz verildi.\nArtık komutları kullanabilirsiniz.",
    )


@router.message(Command("revoke"))
async def handle_revoke(message: Message, db_user: User) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Kullanım: `/revoke TELEGRAM_ID`")
        return
    telegram_user_id = int(parts[1])
    async with SessionFactory() as session:
        user = await revoke_user_access(session, telegram_user_id=telegram_user_id)
        if user is None:
            access_request = await reject_access_request(
                session,
                telegram_user_id=telegram_user_id,
            )
        else:
            access_request = None
    if user is None and access_request is None:
        await message.answer("Kullanıcı veya bekleyen talep bulunamadı.")
        return
    if user is not None:
        await message.answer(f"Kullanıcının erişimi kaldırıldı: `{telegram_user_id}`")
        await message.bot.send_message(
            telegram_user_id,
            "Bot erişim yetkiniz kaldırıldı.",
        )
        return
    await message.answer(f"Bekleyen talep reddedildi: `{telegram_user_id}`")
