"""Run the Telegram bot (polling) and the FastAPI webhook server together."""

import asyncio
import logging
import os

import uvicorn
from aiogram import Bot, Dispatcher

from app.api.main import app as fastapi_app
from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.start import router as start_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.models.product import Product
from app.models.promotion import Promotion
from app.models.user import User
from app.models.wallet_transaction import WalletTransaction

logging.basicConfig(level=logging.INFO)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def run_bot():
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(menu_router)
    print("UBAY Cashback bot started...")
    await dp.start_polling(bot)


async def run_api():
    port = int(os.environ.get("PORT", 8000))
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    print(f"UBAY Cashback API started on port {port}...")
    await server.serve()


async def main():
    await create_tables()
    from app.services.recovery import recovery_loop
    await asyncio.gather(run_bot(), run_api(), recovery_loop())


if __name__ == "__main__":
    asyncio.run(main())
