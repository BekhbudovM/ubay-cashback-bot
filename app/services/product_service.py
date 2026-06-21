from sqlalchemy import select, func

from app.db.session import AsyncSessionLocal
from app.models.product import Product
from app.models.promotion import Promotion

MAX_PRODUCTS = 100


class ProductService:
    @staticmethod
    async def get_all_active():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Product).where(Product.is_active == True).order_by(Product.created_at.desc())
            )
            return result.scalars().all()

    @staticmethod
    async def count_active():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count()).where(Product.is_active == True)
            )
            return result.scalar()

    @staticmethod
    async def add(name: str, price: float, image_file_id: str = None, description: str = None):
        async with AsyncSessionLocal() as session:
            product = Product(
                name=name,
                price=price,
                image_file_id=image_file_id,
                description=description,
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)
            return product

    @staticmethod
    async def delete(product_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()
            if product:
                await session.delete(product)
                await session.commit()
                return True
            return False

    @staticmethod
    async def get_by_id(product_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.id == product_id))
            return result.scalar_one_or_none()


class PromotionService:
    @staticmethod
    async def get_all_active():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.is_active == True).order_by(Promotion.created_at.desc())
            )
            return result.scalars().all()

    @staticmethod
    async def add(name: str, original_price: float, sale_price: float, image_file_id: str = None, description: str = None):
        async with AsyncSessionLocal() as session:
            promo = Promotion(
                name=name,
                original_price=original_price,
                sale_price=sale_price,
                image_file_id=image_file_id,
                description=description,
            )
            session.add(promo)
            await session.commit()
            await session.refresh(promo)
            return promo

    @staticmethod
    async def delete(promo_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Promotion).where(Promotion.id == promo_id))
            promo = result.scalar_one_or_none()
            if promo:
                await session.delete(promo)
                await session.commit()
                return True
            return False

    @staticmethod
    async def get_by_id(promo_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Promotion).where(Promotion.id == promo_id))
            return result.scalar_one_or_none()
