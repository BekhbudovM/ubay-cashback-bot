import logging

import aiohttp
from fastapi import FastAPI, Request

from app.core.config import settings
from app.services.cashback import calculate_cashback, get_cashback_percent
from app.services.regos_sync import process_cheque_closed

logger = logging.getLogger(__name__)

app = FastAPI(title="UBAY Cashback API", version="0.2.0")


@app.get("/")
async def root():
    return {"service": "UBAY Cashback API", "status": "ok"}


@app.get("/cashback/calculate")
async def cashback_calculate(amount: int):
    return {
        "amount": amount,
        "percent": float(get_cashback_percent(amount)),
        "cashback": int(calculate_cashback(amount)),
    }


async def notify_user(telegram_id: int, text: str):
    url = f"https://api.telegram.org/bot{settings.bot_token}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json={"chat_id": telegram_id, "text": text})
    except Exception as e:
        logger.error("Failed to notify user %s: %s", telegram_id, e)


@app.post("/webhooks/regos")
async def regos_webhook(request: Request):
    payload = await request.json()

    integration_id = payload.get("connected_integration_id", "")
    if settings.regos_connected_integration_id and integration_id != settings.regos_connected_integration_id:
        logger.warning("Webhook with unknown integration id: %s", integration_id)
        return {"ok": False}

    data = payload.get("data") or {}
    action = data.get("action")
    event_data = data.get("data") or {}

    if action == "DocChequeClosed":
        cheque_uuid = event_data.get("uuid")
        if cheque_uuid:
            result = await process_cheque_closed(cheque_uuid)
            if result:
                user, cashback, amount, percent = result
                amount_str = f"{int(amount):,}".replace(",", " ")
                cashback_str = f"{int(cashback):,}".replace(",", " ")
                balance_str = f"{int(user.cashback_balance):,}".replace(",", " ")
                await notify_user(
                    user.telegram_id,
                    "🎉 Xaridingiz uchun cashback tushdi!\n\n"
                    f"🧾 Xarid summasi: {amount_str} so'm\n"
                    f"💰 Cashback ({percent:.0f}%): +{cashback_str} so'm\n"
                    f"💳 Jami balans: {balance_str} so'm",
                )

    return {"ok": True}
