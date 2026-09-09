"""Auto-recovery: periodically re-credits cashback for cheques whose webhook was missed.

REGOS retries a webhook only 3 times; if the server is down at that moment the
cheque never gets cashback. This loop scans the last 24h of card cheques every
10 minutes and processes any that have no cashback yet. Double-crediting is
prevented twice: by the WalletTransaction uuid dedup in process_cheque_closed,
and by checking the card's REGOS operation descriptions for the cheque code
(covers credits made manually or before a DB reset).
"""

import asyncio
import logging
import time

import aiohttp

from app.core.config import settings
from app.integrations.regos.client import regos_client
from app.services.regos_sync import process_cheque_closed

logger = logging.getLogger(__name__)

SCAN_INTERVAL = 600  # 10 minutes
SCAN_WINDOW = 24 * 3600


async def _notify(telegram_id: int, text: str):
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"chat_id": telegram_id, "text": text})
    except Exception as e:
        logger.error("Recovery: failed to notify user %s: %s", telegram_id, e)


async def recover_missed_cheques():
    now = int(time.time())
    cheques = await regos_client.get_recent_cheques(now - SCAN_WINDOW, now)

    candidates = [
        c for c in cheques
        if c.get("card") and c.get("status") == "Closed" and not c.get("is_return")
    ]

    ops_cache = {}
    recovered = 0
    for cheque in candidates:
        card_id = cheque["card"]["id"]
        code = cheque.get("code") or ""

        if card_id not in ops_cache:
            try:
                ops_cache[card_id] = await regos_client.get_card_operations(card_id)
            except Exception as e:
                logger.error("Recovery: can't read ops for card %s: %s", card_id, e)
                continue

        already = any(code and code in (op.get("description") or "") for op in ops_cache[card_id])
        if already:
            continue

        result = await process_cheque_closed(cheque["uuid"])
        if result:
            user, cashback, amount, percent = result
            recovered += 1
            amount_str = f"{int(amount):,}".replace(",", " ")
            cashback_str = f"{int(cashback):,}".replace(",", " ")
            balance_str = f"{int(user.cashback_balance):,}".replace(",", " ")
            await _notify(
                user.telegram_id,
                "🎉 Xaridingiz uchun cashback tushdi!\n\n"
                f"🧾 Xarid summasi: {amount_str} so'm\n"
                f"💰 Cashback ({percent:.0f}%): +{cashback_str} so'm\n"
                f"💳 Jami balans: {balance_str} so'm",
            )

    if recovered:
        logger.info("Recovery: credited %s missed cheque(s)", recovered)


async def recovery_loop():
    if not regos_client.enabled:
        logger.warning("Recovery loop disabled: REGOS not configured")
        return
    await asyncio.sleep(60)  # let the app start up first
    while True:
        try:
            await recover_missed_cheques()
        except Exception as e:
            logger.error("Recovery scan failed: %s", e)
        await asyncio.sleep(SCAN_INTERVAL)
