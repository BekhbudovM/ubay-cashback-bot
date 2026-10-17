"""Admin → 🧑‍💼 Sotuvchilar: list of employees, tap one to see their sales."""

import logging

from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.config import settings
from app.integrations.regos.client import regos_client
from app.services.seller_report import (
    NO_SELLER_ID,
    build_periods,
    clear_cache,
    fmt_sum,
    get_employees,
)

logger = logging.getLogger(__name__)

router = Router()

SELLERS_BUTTON = "🧑‍💼 Sotuvchilar"


class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        return event.from_user.id in settings.get_admin_ids()


async def _render_list():
    periods = await build_periods()
    month = next(p for p in periods if p.key == "month")
    today = next(p for p in periods if p.key == "today")

    employees = await get_employees()
    known = {eid for eid, _, _ in employees}
    # Sellers seen on cheques but missing from the user list (or user/get not allowed)
    for sid, t in month.totals.items():
        if sid != NO_SELLER_ID and sid not in known:
            employees.append((sid, t.name, t.barcode))
            known.add(sid)

    rows = []
    for eid, name, _barcode in employees:
        net = month.totals[eid].net if eid in month.totals else 0
        rows.append([InlineKeyboardButton(
            text=f"👤 {name} — {fmt_sum(net)}",
            callback_data=f"seller:{eid}",
        )])
    if NO_SELLER_ID in month.totals:
        net = month.totals[NO_SELLER_ID].net
        rows.append([InlineKeyboardButton(
            text=f"❔ Sotuvchi urilmagan — {fmt_sum(net)}",
            callback_data=f"seller:{NO_SELLER_ID}",
        )])
    rows.append([InlineKeyboardButton(text="🔄 Yangilash", callback_data="sellers:refresh")])

    month_total = sum(t.net for t in month.totals.values())
    today_total = sum(t.net for t in today.totals.values())
    text = (
        "🧑‍💼 Sotuvchilar\n\n"
        f"📅 {today.title}: {fmt_sum(today_total)} so'm\n"
        f"🗓 {month.title}: {fmt_sum(month_total)} so'm\n\n"
        "Tugmadagi summa — shu oydagi sof savdo.\n"
        "Batafsil ko'rish uchun sotuvchini tanlang:"
    )
    if len(rows) == 1:
        text = (
            "🧑‍💼 Sotuvchilar\n\n"
            "REGOS'da hali sotuvchi topilmadi. Xodimga shtrix-kod bering va "
            "kassada «Продавец» maydoniga urib savdo qiling."
        )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_seller(seller_id: int):
    periods = await build_periods()

    name, barcode = None, ""
    for p in periods:
        if seller_id in p.totals:
            name, barcode = p.totals[seller_id].name, p.totals[seller_id].barcode
            break
    if name is None:
        for eid, ename, ebarcode in await get_employees():
            if eid == seller_id:
                name, barcode = ename, ebarcode
                break
    name = name or f"Xodim #{seller_id}"

    lines = [f"👤 {name}"]
    if barcode:
        lines.append(f"🏷 Shtrix-kod: {barcode}")
    icons = {"today": "📅", "week": "📆", "month": "🗓"}
    for p in periods:
        t = p.totals.get(seller_id)
        lines.append("")
        lines.append(f"{icons[p.key]} {p.title}")
        if not t or (t.sales_count == 0 and t.returns_count == 0):
            lines.append("   Savdo yo'q")
            continue
        lines.append(f"   💰 Savdo: {fmt_sum(t.sales)} so'm ({t.sales_count} ta chek)")
        if t.returns_count:
            lines.append(f"   ↩️ Qaytarish: −{fmt_sum(t.returns)} so'm ({t.returns_count} ta)")
            lines.append(f"   ✅ Sof savdo: {fmt_sum(t.net)} so'm")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"seller_refresh:{seller_id}")],
        [InlineKeyboardButton(text="⬅️ Sotuvchilar ro'yxati", callback_data="sellers:list")],
    ])
    return "\n".join(lines), kb


async def _safe_edit(message: Message, text: str, kb=None):
    try:
        await message.edit_text(text, reply_markup=kb)
    except Exception as e:
        # Telegram refuses an edit when nothing changed (refresh with no new sales)
        if "message is not modified" not in str(e):
            raise


def _regos_error_text(e: Exception) -> str:
    logger.error("Seller report failed: %s", e)
    return f"❌ REGOS'dan ma'lumot olib bo'lmadi.\n\n{e}"


@router.message(F.text == SELLERS_BUTTON, IsAdmin())
async def sellers_list(message: Message):
    if not regos_client.enabled:
        await message.answer("REGOS ulanmagan (REGOS_ENDPOINT bo'sh).")
        return
    wait = await message.answer("⏳ REGOS'dan savdolar olinmoqda...")
    try:
        text, kb = await _render_list()
    except Exception as e:
        await wait.edit_text(_regos_error_text(e))
        return
    await wait.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.in_({"sellers:list", "sellers:refresh"}), IsAdmin())
async def sellers_list_cb(callback: CallbackQuery):
    if callback.data == "sellers:refresh":
        clear_cache()
    await callback.answer("⏳")
    try:
        text, kb = await _render_list()
    except Exception as e:
        await _safe_edit(callback.message, _regos_error_text(e))
        return
    await _safe_edit(callback.message, text, kb)


@router.callback_query(F.data.startswith("seller:") | F.data.startswith("seller_refresh:"), IsAdmin())
async def seller_detail_cb(callback: CallbackQuery):
    action, raw_id = callback.data.split(":", 1)
    if action == "seller_refresh":
        clear_cache()
    await callback.answer("⏳")
    try:
        text, kb = await _render_seller(int(raw_id))
    except Exception as e:
        await _safe_edit(callback.message, _regos_error_text(e))
        return
    await _safe_edit(callback.message, text, kb)
