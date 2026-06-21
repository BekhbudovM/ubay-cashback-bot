from aiogram import F, Router
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards.common import main_menu_keyboard
from app.services.product_service import ProductService, PromotionService
from app.services.user_service import UserService
from app.utils.barcode import generate_barcode_image

router = Router()

ORDER_MANAGER = "https://t.me/ubayuzbekistanadmin"


def order_keyboard(product_name: str) -> InlineKeyboardMarkup:
    text = f"🛒 Buyurtma berish: {product_name}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Buyurtma berish", url=f"{ORDER_MANAGER}?text=Buyurtma%3A%20{product_name}")]
    ])


@router.message(F.text == "🏷 Mening shtrix-kodim")
async def show_barcode(message: Message):
    user = await UserService.get_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return

    text = (
        "🏷 Sizning shtrix-kod raqamingiz:\n\n"
        f"`{user.barcode_value}`\n\n"
        "Kassada quyidagi shtrix-kodni ko'rsating."
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

    barcode_path = generate_barcode_image(user.barcode_value)
    await message.answer_photo(
        photo=FSInputFile(barcode_path),
        caption="🏷 UBAY Cashback shtrix-kodingiz",
        reply_markup=main_menu_keyboard(),
    )


@router.message(F.text == "💰 Cashback balansim")
async def show_balance(message: Message):
    user = await UserService.get_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer("Avval /start orqali ro'yxatdan o'ting.")
        return

    balance = int(user.cashback_balance)
    text = f"💰 Cashback balansingiz: {balance:,} so'm".replace(",", " ")
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text == "📜 Xaridlar tarixi")
async def show_history(message: Message):
    text = (
        "📜 Xaridlar tarixi hozircha bo'sh.\n\n"
        "REGOS integratsiyasidan keyin bu yerda tranzaksiyalar chiqadi."
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text == "ℹ️ Cashback qoidalari")
async def cashback_rules(message: Message):
    text = (
        "ℹ️ UBAY Cashback qoidalari:\n\n"
        "0 – 500 000 so'm → 2%\n"
        "500 000 – 1 000 000 so'm → 3%\n"
        "1 000 000 – 2 000 000 so'm → 5%\n"
        "2 000 000 – 4 000 000 so'm → 7%\n"
        "4 000 000 – 6 000 000 so'm → 8%\n"
        "6 000 000 so'mdan yuqori → 10%\n\n"
        "Cashback naqd pulga almashtirilmaydi va keyingi xaridlar uchun ishlatiladi."
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text == "☎️ Operator")
async def operator(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Operator bilan bog'lanish", url="https://t.me/ubayuzbekistanadmin")]
    ])
    await message.answer(
        "☎️ Operator bilan bog'lanish uchun quyidagi tugmani bosing:",
        reply_markup=kb,
    )


@router.message(F.text == "🆕 Yangiliklar")
async def show_products(message: Message):
    products = await ProductService.get_all_active()
    if not products:
        await message.answer(
            "🆕 Hozircha yangi mahsulotlar yo'q.\nTez orada yangiliklar qo'shiladi!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        f"🆕 <b>Yangi mahsulotlar</b> ({len(products)} ta):",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )

    for product in products:
        price_str = f"{int(product.price):,}".replace(",", " ")
        caption = f"<b>{product.name}</b>\n💰 Narxi: <b>{price_str} so'm</b>"
        if product.description:
            caption += f"\n\n{product.description}"

        kb = order_keyboard(product.name)

        if product.image_file_id:
            await message.answer_photo(
                photo=product.image_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.answer(caption, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "🔥 Aksiyalar")
async def show_promotions(message: Message):
    promos = await PromotionService.get_all_active()
    if not promos:
        await message.answer(
            "🔥 Hozircha faol aksiyalar yo'q.\nTez orada aksiyalar e'lon qilinadi!",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        f"🔥 <b>Aksiyalar</b> ({len(promos)} ta):",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )

    for promo in promos:
        orig_str = f"{int(promo.original_price):,}".replace(",", " ")
        sale_str = f"{int(promo.sale_price):,}".replace(",", " ")
        discount = int(promo.original_price) - int(promo.sale_price)
        discount_str = f"{discount:,}".replace(",", " ")

        caption = (
            f"🔥 <b>{promo.name}</b>\n"
            f"💰 Asl narxi: <s>{orig_str} so'm</s>\n"
            f"🏷 Aksiya narxi: <b>{sale_str} so'm</b>\n"
            f"✅ Tejash: <b>{discount_str} so'm</b>"
        )
        if promo.description:
            caption += f"\n\n{promo.description}"

        kb = order_keyboard(promo.name)

        if promo.image_file_id:
            await message.answer_photo(
                photo=promo.image_file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.answer(caption, parse_mode="HTML", reply_markup=kb)
