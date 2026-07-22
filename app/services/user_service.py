from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.wallet_transaction import WalletTransaction
from app.utils.barcode import generate_barcode_value


class UserService:
    @staticmethod
    async def get_by_telegram_id(telegram_id):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def get_transactions(user_id: int, limit: int = 10):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WalletTransaction)
                .where(WalletTransaction.user_id == user_id)
                .order_by(WalletTransaction.created_at.desc())
                .limit(limit)
            )
            return result.scalars().all()

    @staticmethod
    async def get_all_telegram_ids():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.telegram_id).where(User.status == "active")
            )
            return [row[0] for row in result.fetchall()]

    @staticmethod
    async def create_user(telegram_id, phone, full_name):
        async with AsyncSessionLocal() as session:
            existing_phone = await session.execute(select(User).where(User.phone == phone))
            existing_user = existing_phone.scalar_one_or_none()
            if existing_user:
                return existing_user

            barcode_value = generate_barcode_value(phone)

            for _ in range(5):
                existing_barcode = await session.execute(
                    select(User).where(User.barcode_value == barcode_value)
                )
                if existing_barcode.scalar_one_or_none() is None:
                    break
                barcode_value = generate_barcode_value(phone)

            user = User(
                telegram_id=telegram_id,
                phone=phone,
                full_name=full_name,
                barcode_value=barcode_value,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
