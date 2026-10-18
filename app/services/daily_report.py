"""Every evening (default 22:10 Tashkent) send admins each seller's sales for the day."""

import asyncio
import logging
from datetime import date, datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.integrations.regos.client import regos_client
from app.services.seller_report import TASHKENT, all_sellers_day_text, clear_cache, day_title, today

logger = logging.getLogger(__name__)

RETRIES = 3
RETRY_PAUSE = 60  # seconds between attempts when REGOS is unavailable


def report_time():
    """(hour, minute) from SELLER_REPORT_TIME like "22:10"; None disables the report."""
    raw = (settings.seller_report_time or "").strip()
    if not raw:
        return None
    try:
        hour, minute = (int(x) for x in raw.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except ValueError:
        logger.error("Bad SELLER_REPORT_TIME %r, using 22:10", raw)
        return 22, 10
    return hour, minute


def seconds_until(now: datetime, hour: int, minute: int) -> float:
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _keyboard(d: date) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧑‍💼 Sotuvchilar", callback_data="sl"),
         InlineKeyboardButton(text="🗓 Boshqa sana", callback_data=f"sc:all:{d:%Y%m}")],
    ])


async def build_daily_report(d: date = None) -> str:
    d = d or today()
    clear_cache()  # always report fresh numbers
    return await all_sellers_day_text(d, f"🌙 Kunlik hisobot — {day_title(d)}")


async def send_daily_report(bot: Bot, chat_ids=None, d: date = None) -> int:
    """Build the report (retrying REGOS) and send it. Returns how many chats got it."""
    d = d or today()
    chat_ids = chat_ids if chat_ids is not None else settings.get_admin_ids()
    if not chat_ids:
        logger.warning("Daily seller report: ADMIN_IDS is empty, nothing to send")
        return 0

    text, kb, error = None, None, None
    for attempt in range(1, RETRIES + 1):
        try:
            text, kb = await build_daily_report(d), _keyboard(d)
            break
        except Exception as e:
            error = e
            logger.error("Daily seller report attempt %s failed: %s", attempt, e)
            if attempt < RETRIES:
                await asyncio.sleep(RETRY_PAUSE)
    if text is None:
        text = f"❌ Kunlik sotuvchilar hisobotini REGOS'dan olib bo'lmadi ({day_title(d)}).\n\n{error}"

    sent = 0
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
            sent += 1
        except Exception as e:
            logger.error("Daily seller report: can't send to %s: %s", chat_id, e)
    logger.info("Daily seller report for %s sent to %s chat(s)", d, sent)
    return sent


async def daily_report_loop(bot: Bot):
    """Runs forever; never raises, so it can't take the bot down with it."""
    when = report_time()
    if not when or not regos_client.enabled:
        logger.warning("Daily seller report disabled (SELLER_REPORT_TIME or REGOS not set)")
        return
    hour, minute = when
    logger.info("Daily seller report scheduled at %02d:%02d Tashkent time", hour, minute)
    while True:
        try:
            await asyncio.sleep(seconds_until(datetime.now(TASHKENT), hour, minute))
            await send_daily_report(bot)
            await asyncio.sleep(90)  # step past the target minute so it fires once a day
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Daily seller report loop error: %s", e)
            await asyncio.sleep(60)
