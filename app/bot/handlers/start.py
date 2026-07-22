from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards.common import menu_for_user, phone_keyboard
from app.core.config import settings
from app.services.regos_sync import ensure_regos_card
from app.services.user_service import UserService
from app.utils.barcode import generate_barcode_image

router = Router()


class RegisterState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    existing_user = await UserService.get_by_telegram_id(message.from_user.id)

    if existing_user:
        await ensure_regos_card(existing_user)
        text = (
            f"Assalomu alaykum, {existing_user.full_name}!\n\n"
            "Siz UBAY cashback tizimida ro'yxatdan o'tgansiz."
        )
        await message.answer(text, reply_markup=menu_for_user(message.from_user.id, settings.get_admin_ids()))
        return

    await state.set_state(RegisterState.waiting_for_phone)

    text = (
        "Assalomu alaykum!\n\n"
        "UBAY Cashback botiga xush kelibsiz.\n"
        "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring."
    )
    await message.answer(text, reply_markup=phone_keyboard())


@router.message(RegisterState.waiting_for_phone, F.contact)
async def phone_handler(message: Message, state: FSMContext):
    phone = message.contact.phone_number

    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o'zingizning telefon raqamingizni yuboring.")
        return

    await state.update_data(phone=phone)
    await state.set_state(RegisterState.waiting_for_name)
    await message.answer("Ism-familyangizni yozing:")


@router.message(RegisterState.waiting_for_phone)
async def phone_text_handler(message: Message):
    await message.answer(
        "Iltimos, pastdagi tugma orqali telefon raqamingizni yuboring.",
        reply_markup=phone_keyboard(),
    )


@router.message(RegisterState.waiting_for_name)
async def name_handler(message: Message, state: FSMContext):
    full_name = message.text.strip()

    if len(full_name) < 2:
        await message.answer("Iltimos, ism-familyangizni to'liqroq yozing.")
        return

    data = await state.get_data()
    phone = data["phone"]

    user = await UserService.create_user(
        telegram_id=message.from_user.id,
        phone=phone,
        full_name=full_name,
    )

    # REGOS da mijoz + karta ochish (xato bo'lsa ro'yxatdan o'tish davom etadi)
    await ensure_regos_card(user)

    await state.clear()

    text = (
        "✅ Ro'yxatdan o'tdingiz!\n\n"
        f"Ism: {user.full_name}\n"
        f"Telefon: {user.phone}\n"
        f"Shtrix-kod raqami: `{user.barcode_value}`\n\n"
        "Quyidagi shtrix-kodni kassirga ko'rsatasiz."
    )
    admin_ids = settings.get_admin_ids()
    await message.answer(text, parse_mode="Markdown", reply_markup=menu_for_user(message.from_user.id, admin_ids))

    barcode_path = generate_barcode_image(user.barcode_value)
    await message.answer_photo(
        photo=FSInputFile(barcode_path),
        caption="🏷 UBAY Cashback shtrix-kodingiz",
        reply_markup=menu_for_user(message.from_user.id, admin_ids),
    )

    channel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url="https://t.me/ubayuzbekistan")]
    ])
    await message.answer(
        "📢 UBAY rasmiy Telegram kanaliga obuna bo'ling!\n"
        "Yangiliklar, aksiyalar va maxsus takliflardan birinchi bo'lib xabardor bo'ling 👇",
        reply_markup=channel_kb,
    )
