from __future__ import annotations

from typing import Optional

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.database import SessionFactory
from core.models import User, UserRole
from core.repositories import (
    approve_access_request,
    create_or_refresh_access_request,
    get_admin_users,
    get_first_admin_username,
    get_pending_access_requests,
    mark_access_request_notified,
    reject_access_request,
    revoke_user_access,
)


router = Router(name="core")


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


@router.message(Command("start"))
async def handle_start(message: Message, db_user: Optional[User] = None) -> None:
    async with SessionFactory() as session:
        admin_username = await get_first_admin_username(session)

    admin_line = (
        f"\nİletişim: @{admin_username}"
        if admin_username
        else ""
    )
    if db_user is not None and db_user.is_active:
        await message.answer(
            "Bot aktif.\n"
            "Komutları kullanabilirsiniz.\n"
            "YHT işlemleri için /yht yazın."
        )
        return

    await message.answer(
        "TutunSabri botuna hoş geldiniz.\n"
        "Bu botu kullanmak için yetkiniz olması gerekir.\n"
        "İsterseniz aşağıdaki butondan yetki talebi gönderebilirsiniz."
        f"{admin_line}",
        reply_markup=_request_keyboard(),
    )


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
    full_name = " ".join(
        part for part in [from_user.first_name, from_user.last_name] if part
    ) or "-"
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
        full_name = " ".join(part for part in [item.first_name, item.last_name] if part) or "-"
        lines.append(
            f"{username} | `{item.telegram_user_id}` | {full_name}\n"
            f"`/grant {item.telegram_user_id}`\n"
            f"`/revoke {item.telegram_user_id}`"
        )
    await message.answer("\n\n".join(lines))


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
