from __future__ import annotations

from typing import Iterable

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


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
