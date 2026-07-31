import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards.common import (
    admin_menu_keyboard,
    cancel_keyboard,
    main_menu_keyboard,
    product_list_inline,
    promo_list_inline,
)
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.product_service import MAX_PRODUCTS, ProductService, PromotionService
from app.services.regos_sync import ensure_regos_card
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = Router()


class IsAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in settings.get_admin_ids()


class BroadcastState(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()


class AddProductState(StatesGroup):
    waiting_photo = State()
    waiting_name = State()
    waiting_price = State()
    waiting_description = State()


class AddPromoState(StatesGroup):
    waiting_photo = State()
    waiting_name = State()
    waiting_original_price = State()
    waiting_sale_price = State()
    waiting_description = State()


# ── Admin panel entry ──────────────────────────────────────────────────────────

@router.message(F.text == "🔧 Admin panel", IsAdmin())
async def admin_panel(message: Message):
    await message.answer("Admin panel:", reply_markup=admin_menu_keyboard())


@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_menu_keyboard())


# ── Cancel ────────────────────────────────────────────────────────────────────

@router.message(F.text == "❌ Bekor qilish")
async def cancel_action(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=admin_menu_keyboard())


# ── Add Product ───────────────────────────────────────────────────────────────

@router.message(F.text == "🆕 Yangilik qo'shish", IsAdmin())
async def start_add_product(message: Message, state: FSMContext):
    count = await ProductService.count_active()
    if count >= MAX_PRODUCTS:
        await message.answer(
            f"❌ Maksimal {MAX_PRODUCTS} ta yangilik qo'shish mumkin. Avval eskisini o'chiring.",
            reply_markup=admin_menu_keyboard(),
        )
        return
    await state.set_state(AddProductState.waiting_photo)
    await message.answer(
        "📸 Mahsulot rasmini yuboring (yoki /skip — rasmsiz qo'shish):",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddProductState.waiting_photo, F.photo)
async def product_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(image_file_id=file_id)
    await state.set_state(AddProductState.waiting_name)
    await message.answer("✏️ Mahsulot nomini yozing:")


@router.message(AddProductState.waiting_photo, F.text == "/skip")
async def product_skip_photo(message: Message, state: FSMContext):
    await state.update_data(image_file_id=None)
    await state.set_state(AddProductState.waiting_name)
    await message.answer("✏️ Mahsulot nomini yozing:")


@router.message(AddProductState.waiting_photo)
async def product_photo_invalid(message: Message):
    await message.answer("Iltimos, rasm yuboring yoki /skip yozing.")


@router.message(AddProductState.waiting_name)
async def product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddProductState.waiting_price)
    await message.answer("💰 Narxini so'mda yozing (masalan: 25000):")


@router.message(AddProductState.waiting_price)
async def product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Iltimos, to'g'ri narx kiriting (masalan: 25000):")
        return
    await state.update_data(price=price)
    await state.set_state(AddProductState.waiting_description)
    await message.answer("📝 Qisqacha tavsif yozing (yoki /skip — tasvirsiz):")


@router.message(AddProductState.waiting_description)
async def product_description(message: Message, state: FSMContext):
    description = None if message.text.strip() == "/skip" else message.text.strip()
    data = await state.get_data()
    await state.clear()

    product = await ProductService.add(
        name=data["name"],
        price=data["price"],
        image_file_id=data.get("image_file_id"),
        description=description,
    )

    price_str = f"{int(product.price):,}".replace(",", " ")
    await message.answer(
        f"✅ Yangilik qo'shildi!\n\n"
        f"📦 Nomi: {product.name}\n"
        f"💰 Narxi: {price_str} so'm",
        reply_markup=admin_menu_keyboard(),
    )
    if product.image_file_id:
        await message.answer_photo(photo=product.image_file_id, caption=product.name)


# ── Delete Product ────────────────────────────────────────────────────────────

@router.message(F.text == "🗑 Yangilik o'chirish", IsAdmin())
async def list_products_for_delete(message: Message):
    products = await ProductService.get_all_active()
    if not products:
        await message.answer("Hozircha yangiliklar yo'q.", reply_markup=admin_menu_keyboard())
        return
    kb = product_list_inline(products, prefix="del_prod")
    await message.answer("O'chirmoqchi bo'lgan yangilikni tanlang:", reply_markup=kb)


@router.callback_query(F.data.startswith("del_prod:"))
async def delete_product_cb(callback: CallbackQuery):
    if callback.from_user.id not in settings.get_admin_ids():
        await callback.answer("Ruxsat yo'q.")
        return
    product_id = int(callback.data.split(":")[1])
    deleted = await ProductService.delete(product_id)
    if deleted:
        await callback.answer("✅ O'chirildi.")
        await callback.message.edit_text(f"✅ #{product_id} yangilik o'chirildi.")
    else:
        await callback.answer("Topilmadi.")


# ── Products list (admin view) ────────────────────────────────────────────────

@router.message(F.text == "📋 Yangiliklar ro'yxati", IsAdmin())
async def admin_products_list(message: Message):
    products = await ProductService.get_all_active()
    if not products:
        await message.answer("Yangiliklar yo'q.", reply_markup=admin_menu_keyboard())
        return
    lines = [f"#{p.id} {p.name} — {int(p.price):,} so'm".replace(",", " ") for p in products]
    await message.answer(
        f"📋 Yangiliklar ({len(products)}/{MAX_PRODUCTS}):\n\n" + "\n".join(lines),
        reply_markup=admin_menu_keyboard(),
    )


# ── Add Promotion ─────────────────────────────────────────────────────────────

@router.message(F.text == "🔥 Aksiya qo'shish", IsAdmin())
async def start_add_promo(message: Message, state: FSMContext):
    await state.set_state(AddPromoState.waiting_photo)
    await message.answer(
        "📸 Aksiya mahsuloti rasmini yuboring (yoki /skip):",
        reply_markup=cancel_keyboard(),
    )


@router.message(AddPromoState.waiting_photo, F.photo)
async def promo_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(image_file_id=file_id)
    await state.set_state(AddPromoState.waiting_name)
    await message.answer("✏️ Aksiya nomini yozing:")


@router.message(AddPromoState.waiting_photo, F.text == "/skip")
async def promo_skip_photo(message: Message, state: FSMContext):
    await state.update_data(image_file_id=None)
    await state.set_state(AddPromoState.waiting_name)
    await message.answer("✏️ Aksiya nomini yozing:")


@router.message(AddPromoState.waiting_photo)
async def promo_photo_invalid(message: Message):
    await message.answer("Iltimos, rasm yuboring yoki /skip yozing.")


@router.message(AddPromoState.waiting_name)
async def promo_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(AddPromoState.waiting_original_price)
    await message.answer("💰 Asl narxini so'mda yozing:")


@router.message(AddPromoState.waiting_original_price)
async def promo_original_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Iltimos, to'g'ri narx kiriting:")
        return
    await state.update_data(original_price=price)
    await state.set_state(AddPromoState.waiting_sale_price)
    await message.answer("🏷 Aksiya narxini so'mda yozing:")


@router.message(AddPromoState.waiting_sale_price)
async def promo_sale_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", "").replace(",", ""))
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Iltimos, to'g'ri narx kiriting:")
        return
    await state.update_data(sale_price=price)
    await state.set_state(AddPromoState.waiting_description)
    await message.answer("📝 Qisqacha tavsif yozing (yoki /skip):")


@router.message(AddPromoState.waiting_description)
async def promo_description(message: Message, state: FSMContext):
    description = None if message.text.strip() == "/skip" else message.text.strip()
    data = await state.get_data()
    await state.clear()

    promo = await PromotionService.add(
        name=data["name"],
        original_price=data["original_price"],
        sale_price=data["sale_price"],
        image_file_id=data.get("image_file_id"),
        description=description,
    )

    orig = f"{int(promo.original_price):,}".replace(",", " ")
    sale = f"{int(promo.sale_price):,}".replace(",", " ")
    await message.answer(
        f"✅ Aksiya qo'shildi!\n\n"
        f"🔥 Nomi: {promo.name}\n"
        f"💰 Asl narxi: {orig} so'm\n"
        f"🏷 Aksiya narxi: {sale} so'm",
        reply_markup=admin_menu_keyboard(),
    )
    if promo.image_file_id:
        await message.answer_photo(photo=promo.image_file_id, caption=promo.name)


# ── Delete Promotion ──────────────────────────────────────────────────────────

@router.message(F.text == "🗑 Aksiya o'chirish", IsAdmin())
async def list_promos_for_delete(message: Message):
    promos = await PromotionService.get_all_active()
    if not promos:
        await message.answer("Hozircha aksiyalar yo'q.", reply_markup=admin_menu_keyboard())
        return
    kb = promo_list_inline(promos, prefix="del_promo")
    await message.answer("O'chirmoqchi bo'lgan aksiyani tanlang:", reply_markup=kb)


@router.callback_query(F.data.startswith("del_promo:"))
async def delete_promo_cb(callback: CallbackQuery):
    if callback.from_user.id not in settings.get_admin_ids():
        await callback.answer("Ruxsat yo'q.")
        return
    promo_id = int(callback.data.split(":")[1])
    deleted = await PromotionService.delete(promo_id)
    if deleted:
        await callback.answer("✅ O'chirildi.")
        await callback.message.edit_text(f"✅ #{promo_id} aksiya o'chirildi.")
    else:
        await callback.answer("Topilmadi.")


# ── Promotions list (admin view) ──────────────────────────────────────────────

@router.message(F.text == "📋 Aksiyalar ro'yxati", IsAdmin())
async def admin_promos_list(message: Message):
    promos = await PromotionService.get_all_active()
    if not promos:
        await message.answer("Aksiyalar yo'q.", reply_markup=admin_menu_keyboard())
        return
    lines = [
        f"#{p.id} {p.name} — {int(p.sale_price):,} so'm (asl: {int(p.original_price):,})".replace(",", " ")
        for p in promos
    ]
    await message.answer(
        f"📋 Aksiyalar ({len(promos)} ta):\n\n" + "\n".join(lines),
        reply_markup=admin_menu_keyboard(),
    )


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.message(F.text == "📢 Xabar yuborish", IsAdmin())
async def start_broadcast(message: Message, state: FSMContext):
    await state.set_state(BroadcastState.waiting_message)
    await message.answer(
        "📢 Foydalanuvchilarga yuboriladigan xabarni yozing.\n\n"
        "Matn, rasm+matn yoki faqat rasm yuborishingiz mumkin.\n"
        "Bekor qilish uchun — ❌ Bekor qilish",
        reply_markup=cancel_keyboard(),
    )


@router.message(BroadcastState.waiting_message)
async def broadcast_preview(message: Message, state: FSMContext):
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    if message.photo:
        await state.update_data(
            photo_file_id=message.photo[-1].file_id,
            caption=message.caption or "",
            msg_type="photo",
        )
    elif message.text:
        await state.update_data(text=message.text, msg_type="text")
    else:
        await message.answer("Faqat matn yoki rasm+matn yuboring.")
        return

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="broadcast:confirm"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="broadcast:cancel"),
        ]
    ])

    user_ids = await UserService.get_all_telegram_ids()
    await message.answer(
        f"👁 Ko'rib chiqing. Jami {len(user_ids)} ta foydalanuvchiga yuboriladi.\n\nYuborishni tasdiqlaysizmi?",
        reply_markup=confirm_kb,
    )


@router.callback_query(F.data == "broadcast:cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.message.answer("Admin panel:", reply_markup=admin_menu_keyboard())


@router.callback_query(F.data == "broadcast:confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in settings.get_admin_ids():
        await callback.answer("Ruxsat yo'q.")
        return

    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("⏳ Xabar yuborilmoqda...")

    bot: Bot = callback.bot
    user_ids = await UserService.get_all_telegram_ids()

    sent = 0
    failed = 0

    for telegram_id in user_ids:
        try:
            if data["msg_type"] == "photo":
                await bot.send_photo(
                    chat_id=telegram_id,
                    photo=data["photo_file_id"],
                    caption=data.get("caption", "") or None,
                )
            else:
                await bot.send_message(chat_id=telegram_id, text=data["text"])
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Telegram rate limit

    await callback.message.answer(
        f"✅ Broadcast yakunlandi!\n\n"
        f"📨 Yuborildi: {sent} ta\n"
        f"❌ Yetkazilmadi: {failed} ta",
        reply_markup=admin_menu_keyboard(),
    )


# ── REGOS Resync ──────────────────────────────────────────────────────────────

@router.message(F.text == "🔄 REGOS Sinxronizatsiya", IsAdmin())
async def regos_resync(message: Message):
    await message.answer("⏳ REGOS sinxronizatsiya boshlanmoqda...")

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.regos_card_id == None)  # noqa: E711
        )
        users_without_card = result.scalars().all()

    total = len(users_without_card)
    if total == 0:
        await message.answer(
            "✅ Barcha foydalanuvchilar allaqachon REGOS da ro'yxatdan o'tgan!",
            reply_markup=admin_menu_keyboard(),
        )
        return

    await message.answer(f"🔄 {total} ta foydalanuvchi uchun REGOS karta yaratilmoqda...")

    success = 0
    failed = 0
    failed_users = []

    for user in users_without_card:
        old_card_id = user.regos_card_id
        try:
            await ensure_regos_card(user)
            if user.regos_card_id:
                success += 1
                logger.info("REGOS resync: card created for user %s (%s)", user.id, user.phone)
            else:
                failed += 1
                failed_users.append(f"{user.full_name} ({user.phone})")
                logger.warning("REGOS resync: failed for user %s (%s)", user.id, user.phone)
        except Exception as e:
            failed += 1
            failed_users.append(f"{user.full_name} ({user.phone})")
            logger.error("REGOS resync exception for user %s: %s", user.id, e)
        await asyncio.sleep(0.3)

    report = (
        f"✅ REGOS sinxronizatsiya yakunlandi!\n\n"
        f"✔️ Muvaffaqiyatli: {success} ta\n"
        f"❌ Xato: {failed} ta"
    )
    if failed_users:
        names = "\n".join(f"• {u}" for u in failed_users[:15])
        report += f"\n\nXato bo'lgan foydalanuvchilar:\n{names}"
        if len(failed_users) > 15:
            report += f"\n...va yana {len(failed_users) - 15} ta"

    await message.answer(report, reply_markup=admin_menu_keyboard())


# ── Users list ────────────────────────────────────────────────────────────────

@router.message(F.text == "👥 Foydalanuvchilar", IsAdmin())
async def users_list(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        all_users = result.scalars().all()

    total = len(all_users)
    synced = sum(1 for u in all_users if u.regos_card_id)
    not_synced = total - synced

    lines = []
    for u in all_users[-20:]:
        status = "✅" if u.regos_card_id else "❌"
        balance = int(float(u.cashback_balance or 0))
        lines.append(f"{status} {u.full_name} | {u.phone} | {balance:,} so'm".replace(",", " "))

    text = (
        f"👥 Foydalanuvchilar: {total} ta\n"
        f"✅ REGOS sinx: {synced} ta\n"
        f"❌ REGOS yo'q: {not_synced} ta\n\n"
        f"Oxirgi 20 ta:\n" + "\n".join(lines)
    )
    await message.answer(text, reply_markup=admin_menu_keyboard())
