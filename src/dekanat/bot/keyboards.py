from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def doc_type_keyboard(types: list[dict], with_auto: bool = True) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t["title"], callback_data=f"dt:{t['id']}")] for t in types]
    if with_auto:
        rows.append([InlineKeyboardButton(text="🔍 Определить автоматически",
                                          callback_data="dt:auto")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def check_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Проверить комплектность", callback_data="check")]])
