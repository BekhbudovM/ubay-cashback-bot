from typing import List

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏷 Mening shtrix-kodim")],
            [KeyboardButton(text="💰 Cashback balansim"), KeyboardButton(text="📜 Xaridlar tarixi")],
            [KeyboardButton(text="🆕 Yangiliklar"), KeyboardButton(text="🔥 Aksiyalar")],
            [KeyboardButton(text="ℹ️ Cashback qoidalari"), KeyboardButton(text="☎️ Operator")],
        ],
        resize_keyboard=True,
    )


def menu_for_user(telegram_id: int, admin_ids: List[int] = None):
    kb = main_menu_keyboard()
    if admin_ids and telegram_id in admin_ids:
        kb.keyboard.append([KeyboardButton(text="🔧 Admin panel")])
    return kb


def admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆕 Yangilik qo'shish"), KeyboardButton(text="🗑 Yangilik o'chirish")],
            [KeyboardButton(text="🔥 Aksiya qo'shish"), KeyboardButton(text="🗑 Aksiya o'chirish")],
            [KeyboardButton(text="📋 Yangiliklar ro'yxati"), KeyboardButton(text="📋 Aksiyalar ro'yxati")],
            [KeyboardButton(text="📢 Xabar yuborish")],
            [KeyboardButton(text="🔙 Asosiy menyu")],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def product_list_inline(products, prefix="del_prod"):
    buttons = []
    for p in products:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 #{p.id} {p.name[:30]}",
            callback_data=f"{prefix}:{p.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def promo_list_inline(promos, prefix="del_promo"):
    buttons = []
    for p in promos:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 #{p.id} {p.name[:30]}",
            callback_data=f"{prefix}:{p.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
