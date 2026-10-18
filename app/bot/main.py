import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.sellers import router as sellers_router
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
    dp.include_router(sellers_router)
    dp.include_router(start_router)
    dp.include_router(menu_router)

    from app.services.daily_report import daily_report_loop

    print("UBAY Cashback bot started...")
    await asyncio.gather(dp.start_polling(bot), daily_report_loop(bot))


if __name__ == "__main__":
    asyncio.run(main())
