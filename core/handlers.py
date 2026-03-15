from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Optional

from aiogram import Router
from aiogram.filters import Command
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
    get_all_open_tasks,
    get_all_users,
    get_admin_users,
    get_first_admin_username,
    get_pending_access_requests,
    get_user_by_id,
    mark_access_request_notified,
    reject_access_request,
    revoke_user_access,
)


router = Router(name="core")
INFO_DIR = Path(__file__).resolve().parent.parent / "info"
WHOAMI_PHOTO_ID = "AgACAgQAAxkBAAIHImm3Ilp3SvfAFv8zY6EaW9gzvFT1AAJyDWsb5OS5UXEuXr4ixWKrAQADAgADdwADOgQ"


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


@router.message(Command("start"))
async def handle_start(message: Message, db_user: Optional[User] = None) -> None:
    await message.answer(
        _read_info_markdown("start.md"),
        reply_markup=_start_keyboard(),
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

    username = f"@{from_user.username}" if from_user.username else "-"
    full_name = (
        " ".join(part for part in [from_user.first_name, from_user.last_name] if part)
        or "-"
    )
    notify_text = (
        "*Yeni yetki talebi*\n"
        f"*Kullanıcı:* {username}\n"
        f"*Telegram ID:* `{from_user.id}`\n"
        f"*Ad Soyad:* {full_name}\n"
        + f"*Onay:* `/grant {from_user.id}`\n"
        + f"*Reddet / Kapat:* `/revoke {from_user.id}`"
    )
    if not access_request.is_notified:
        for admin_user in admin_users:
            await query.bot.send_message(admin_user.telegram_user_id, notify_text)
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
    lines = ["*Bekleyen yetki talepleri*"]
    for item in requests:
        username = f"@{item.username}" if item.username else "-"
        full_name = (
            " ".join(part for part in [item.first_name, item.last_name] if part) or "-"
        )
        lines.append(
            f"{username} | `{item.telegram_user_id}` | {full_name}\n"
            f"`/grant {item.telegram_user_id}`\n"
            f"`/revoke {item.telegram_user_id}`"
        )
    await message.answer("\n\n".join(lines))


@router.message(Command("listusers"))
async def handle_listusers(message: Message, db_user: User) -> None:
    if not _is_admin(db_user):
        await message.answer("Bu komutu kullanma yetkiniz yok.")
        return
    async with SessionFactory() as session:
        users = await get_all_users(session)
    if not users:
        await message.answer("Kayıtlı kullanıcı bulunmuyor.")
        return
    lines = ["*Kullanıcı listesi*"]
    for user in users:
        username = f"@{user.username}" if user.username else "-"
        status = "aktif" if user.is_active else "pasif"
        full_name = " ".join(part for part in [user.first_name, user.last_name] if part) or "-"
        lines.append(
            f"{username} | `{user.telegram_user_id}`\n"
            f"*Rol:* {_format_role(user.role)} | *Durum:* {status}\n"
            f"*Ad Soyad:* {full_name}"
        )
    await message.answer("\n\n".join(lines))


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
        username = f"@{user.username}" if user and user.username else "-"
        lines.append(
            f"<b>Görev:</b> <code>{escape(task.task_id)}</code>\n"
            f"<b>Kullanıcı:</b> {escape(username)} "
            f"(<code>{getattr(user, 'telegram_user_id', task.user_id)}</code>)\n"
            f"<b>Durum:</b> {escape(task.status.value)}\n"
            f"<b>Güzergâh:</b> {escape(task.from_station)} -&gt; {escape(task.to_station)}\n"
            f"<b>Kalkış:</b> {escape(task.travel_date.isoformat())} {escape(task.travel_hour)}"
        )
    await message.answer("\n\n".join(lines), parse_mode="HTML")


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
