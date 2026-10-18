"""Admin → 🧑‍💼 Sotuvchilar.

Screens (all inline, edited in place):
  list      sl / slr            sellers with their last-7-days sales
  week      sw:<id> / swr:<id>  one seller, day by day for the last 7 days
  day       sd:<id|all>:<YYYYMMDD>  one seller (or everyone) on one date
  calendar  sc:<id|all>:<YYYYMM>    pick any date
"""

import calendar
import logging
from datetime import date, datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.core.config import settings
from app.integrations.regos.client import regos_client
from app.services.daily_report import send_daily_report
from app.services.seller_report import (
    HISTORY_DAYS,
    MAX_CHEQUE_LINES,
    NO_SELLER_ID,
    WEEKDAYS_SHORT,
    all_sellers_day_text,
    clear_cache,
    day_title,
    day_totals,
    fmt_sum,
    history,
    merge,
    month_title,
    seller_directory,
    seller_info,
    short_day,
    today,
    totals_line,
)

logger = logging.getLogger(__name__)

router = Router()

SELLERS_BUTTON = "🧑‍💼 Sotuvchilar"
ALL = "all"


class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        return event.from_user.id in settings.get_admin_ids()


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _parse_target(raw: str):
    return ALL if raw == ALL else int(raw)


# ── Screens ───────────────────────────────────────────────────────────────────

async def render_list():
    hist = await history()
    week = merge([totals for _, totals in hist])
    today_totals = hist[0][1]
    directory = await seller_directory(*[totals for _, totals in hist])

    rows = []
    ranked = sorted(directory, key=lambda s: (-(week[s[0]].net if s[0] in week else 0), s[1].lower()))
    for sid, name, _barcode in ranked:
        net = week[sid].net if sid in week else 0
        rows.append([_btn(f"👤 {name} — {fmt_sum(net)}", f"sw:{sid}")])
    if NO_SELLER_ID in week:
        rows.append([_btn(f"❔ Sotuvchi urilmagan — {fmt_sum(week[NO_SELLER_ID].net)}", f"sw:{NO_SELLER_ID}")])

    if not rows:
        text = (
            "🧑‍💼 Sotuvchilar\n\n"
            "REGOS'da hali sotuvchi topilmadi. Xodimga shtrix-kod bering va "
            "kassada «Продавец» maydoniga urib savdo qiling."
        )
    else:
        today_net = sum(t.net for t in today_totals.values())
        week_net = sum(t.net for t in week.values())
        text = (
            "🧑‍💼 Sotuvchilar\n\n"
            f"📅 Bugun ({today():%d.%m}): {fmt_sum(today_net)} so'm\n"
            f"📊 Oxirgi {HISTORY_DAYS} kun: {fmt_sum(week_net)} so'm\n\n"
            f"Tugmadagi summa — oxirgi {HISTORY_DAYS} kundagi sof savdo.\n"
            "Tarixini ko'rish uchun sotuvchini tanlang:"
        )
    rows.append([_btn("📅 Kun bo'yicha (hamma sotuvchilar)", f"sd:{ALL}:{today():%Y%m%d}")])
    rows.append([_btn("🔄 Yangilash", "slr")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def render_week(seller_id: int):
    hist = await history()
    name, barcode = await seller_info(seller_id, *[totals for _, totals in hist])

    lines = [f"👤 {name}"]
    if barcode:
        lines.append(f"🏷 Shtrix-kod: {barcode}")
    lines += ["", f"📊 Oxirgi {HISTORY_DAYS} kun:"]
    for d, totals in hist:
        lines.append(f"▫️ {short_day(d)} — {totals_line(totals.get(seller_id))}")
    week = merge([totals for _, totals in hist]).get(seller_id)
    lines += ["━━━━━━━━━━━━", f"💰 Jami: {totals_line(week)}", "", "Kunni tanlang — o'sha kungi savdo chiqadi:"]

    day_buttons = [_btn(f"{d:%d.%m}", f"sd:{seller_id}:{d:%Y%m%d}") for d, _ in hist]
    rows = [day_buttons[:4], day_buttons[4:]]
    rows.append([_btn("🗓 Boshqa sana", f"sc:{seller_id}:{today():%Y%m}")])
    rows.append([_btn("🔄 Yangilash", f"swr:{seller_id}"), _btn("⬅️ Ro'yxat", "sl")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _day_nav(target, d: date) -> list:
    nav = [_btn(f"◀️ {d - timedelta(days=1):%d.%m}", f"sd:{target}:{d - timedelta(days=1):%Y%m%d}")]
    if d < today():
        nav.append(_btn(f"{d + timedelta(days=1):%d.%m} ▶️", f"sd:{target}:{d + timedelta(days=1):%Y%m%d}"))
    return nav


async def render_day(target, d: date):
    if d > today():
        d = today()

    if target == ALL:
        text = await all_sellers_day_text(d, f"📅 {day_title(d)} — sotuvchilar savdosi")
        rows = [
            _day_nav(ALL, d),
            [_btn("🗓 Boshqa sana", f"sc:{ALL}:{d:%Y%m}")],
            [_btn("⬅️ Sotuvchilar ro'yxati", "sl")],
        ]
        return text, InlineKeyboardMarkup(inline_keyboard=rows)

    totals = await day_totals(d)
    t = totals.get(target)
    name, _barcode = await seller_info(target, totals)

    lines = [f"👤 {name}", f"📅 {day_title(d)}", ""]
    if not t or not t.has_activity:
        lines.append("Bu kuni savdo yo'q.")
    else:
        lines.append(f"💰 Savdo: {fmt_sum(t.sales)} so'm ({t.sales_count} ta chek)")
        if t.returns_count:
            lines.append(f"↩️ Qaytarish: −{fmt_sum(t.returns)} so'm ({t.returns_count} ta)")
        lines.append(f"✅ Jami sof savdo: {fmt_sum(t.net)} so'm")
        lines += ["", "🧾 Cheklar:"]
        for line in t.cheques[:MAX_CHEQUE_LINES]:
            amount = f"↩️ −{fmt_sum(line.amount)}" if line.is_return else fmt_sum(line.amount)
            lines.append(f"{line.time} — {amount}")
        if len(t.cheques) > MAX_CHEQUE_LINES:
            lines.append(f"… va yana {len(t.cheques) - MAX_CHEQUE_LINES} ta")

    rows = [
        _day_nav(target, d),
        [_btn("🗓 Boshqa sana", f"sc:{target}:{d:%Y%m}")],
        [_btn("📊 Haftalik tarix", f"sw:{target}"), _btn("⬅️ Ro'yxat", "sl")],
    ]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def render_calendar(target, year: int, month: int):
    current = today()
    if (year, month) > (current.year, current.month):
        year, month = current.year, current.month

    if target == ALL:
        text = "🗓 Sanani tanlang — o'sha kungi hamma sotuvchilar savdosi chiqadi."
        back = _btn("⬅️ Ro'yxat", "sl")
    else:
        name, _ = await seller_info(target)
        text = f"🗓 {name}\nSanani tanlang — o'sha kungi savdosi chiqadi."
        back = _btn("⬅️ Haftalik tarix", f"sw:{target}")

    prev_month = date(year, month, 1) - timedelta(days=1)
    next_month = date(year, month, 28) + timedelta(days=4)
    header = [_btn("◀️", f"sc:{target}:{prev_month:%Y%m}"), _btn(month_title(year, month), "noop")]
    if (next_month.year, next_month.month) <= (current.year, current.month):
        header.append(_btn("▶️", f"sc:{target}:{next_month:%Y%m}"))
    else:
        header.append(_btn(" ", "noop"))

    rows = [header, [_btn(w, "noop") for w in WEEKDAYS_SHORT]]
    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(_btn(" ", "noop"))
                continue
            d = date(year, month, day)
            if d > current:
                row.append(_btn("·", "noop"))
            else:
                label = f"•{day}" if d == current else str(day)
                row.append(_btn(label, f"sd:{target}:{d:%Y%m%d}"))
        rows.append(row)
    rows.append([back])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


async def _show(callback: CallbackQuery, render, *args):
    await callback.answer()
    try:
        text, kb = await render(*args)
    except Exception as e:
        await _safe_edit(callback.message, _regos_error_text(e),
                         InlineKeyboardMarkup(inline_keyboard=[[_btn("🔄 Qayta urinish", callback.data)]]))
        return
    await _safe_edit(callback.message, text, kb)


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.message(F.text == SELLERS_BUTTON, IsAdmin())
async def sellers_list(message: Message):
    if not regos_client.enabled:
        await message.answer("REGOS ulanmagan (REGOS_ENDPOINT bo'sh).")
        return
    wait = await message.answer("⏳ REGOS'dan savdolar olinmoqda...")
    try:
        text, kb = await render_list()
    except Exception as e:
        await wait.edit_text(_regos_error_text(e))
        return
    await wait.edit_text(text, reply_markup=kb)


@router.message(Command("kunlik"), IsAdmin())
async def daily_report_now(message: Message):
    """Send today's seller report right now (same as the evening one)."""
    await send_daily_report(message.bot, chat_ids=[message.chat.id])


@router.callback_query(F.data.in_({"sl", "slr"}), IsAdmin())
async def list_cb(callback: CallbackQuery):
    if callback.data == "slr":
        clear_cache()
    await _show(callback, render_list)


@router.callback_query(F.data.startswith("sw:") | F.data.startswith("swr:"), IsAdmin())
async def week_cb(callback: CallbackQuery):
    action, raw_id = callback.data.split(":", 1)
    if action == "swr":
        clear_cache()
    await _show(callback, render_week, int(raw_id))


@router.callback_query(F.data.startswith("sd:"), IsAdmin())
async def day_cb(callback: CallbackQuery):
    _, raw_target, raw_date = callback.data.split(":")
    d = datetime.strptime(raw_date, "%Y%m%d").date()
    await _show(callback, render_day, _parse_target(raw_target), d)


@router.callback_query(F.data.startswith("sc:"), IsAdmin())
async def calendar_cb(callback: CallbackQuery):
    _, raw_target, raw_month = callback.data.split(":")
    await _show(callback, render_calendar, _parse_target(raw_target), int(raw_month[:4]), int(raw_month[4:]))


@router.callback_query(F.data == "noop")
async def noop_cb(callback: CallbackQuery):
    await callback.answer()
