import asyncio

from aiogram import Bot, Dispatcher

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


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    await create_tables()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(menu_router)

    print("UBAY Cashback bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
