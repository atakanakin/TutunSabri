from __future__ import annotations

from datetime import date
from typing import Iterable

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


MONTH_NAMES_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}

MARKDOWN_SPECIAL_CHARS = r"_*[]()~`>#+-=|{}.!"


def normalize_text(text: str) -> str:
    normalized = text.replace("I", "ı").replace("İ", "i")
    return normalized.lower().strip()


def build_choice_keyboard(
    options: Iterable[str], include_cancel: bool = True
) -> ReplyKeyboardMarkup:
    rows = []
    option_list = list(options)
    for index in range(0, len(option_list), 2):
        row = [KeyboardButton(text=option_list[index])]
        if index + 1 < len(option_list):
            row.append(KeyboardButton(text=option_list[index + 1]))
        rows.append(row)
    if include_cancel:
        rows.append([KeyboardButton(text="cancel")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_choice_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def is_cancel_text(text: str) -> bool:
    return text.strip().lower() == "cancel"


def escape_markdown(text: str) -> str:
    escaped = str(text)
    for char in MARKDOWN_SPECIAL_CHARS:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def format_turkish_date_short(value: date) -> str:
    return f"{value.day} {MONTH_NAMES_TR[value.month]} {value.strftime('%y')}"


def format_turkish_datetime_long(value: date, hour_text: str) -> str:
    return f"{value.day} {MONTH_NAMES_TR[value.month]} {value.year} {hour_text}"


def format_route_sentence(
    from_station: str,
    to_station: str,
    travel_date: date,
    travel_hour: str,
) -> str:
    return (
        f"*{escape_markdown(from_station)} -> {escape_markdown(to_station)}* güzergâhında "
        f"*{format_turkish_datetime_long(travel_date, travel_hour)}* tarihli trende"
    )


def format_last_result_text(last_result: str) -> str:
    text = (last_result or "").strip()
    if not text:
        return ""

    mappings = {
        "checking availability": "Uygun koltuk kontrol ediliyor.",
        "train not found for selected departure": "Seçilen saatte uygun tren bulunamadı.",
        "availability updated": "Son koltuk durumu güncellendi.",
        "seat held": "Koltuk tutuldu.",
        "seat hold retrying": "Koltuk tutma yeniden deneniyor.",
        "seat released by user": "Koltuk kullanıcı tarafından bırakıldı.",
        "seat release failed": "Koltuk bırakılırken bir sorun oluştu.",
        "task cancelled by user": "İşlem kullanıcı tarafından iptal edildi.",
        "hold retry limit reached": "Yeniden deneme sınırına ulaşıldı.",
        "hold expired retrying": "Tutma süresi doldu, yeniden deneniyor.",
        "recovered after restart": "İşlem yeniden başlatıldı ve devam ediyor.",
        "missing hold details": "Tutulan koltuk bilgileri eksik.",
        "user record missing": "Kullanıcı kaydı bulunamadı.",
        "tcdd error": "TCDD tarafında geçici bir sorun oluştu.",
        "unexpected error": "Beklenmeyen bir hata oluştu.",
    }
    if text in mappings:
        return mappings[text]
    return text
