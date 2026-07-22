"""REGOS <-> bot synchronization: card creation and cashback crediting."""

import logging

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.integrations.regos.client import RegosError, regos_client
from app.models.user import User
from app.models.wallet_transaction import WalletTransaction
from app.services.cashback import calculate_cashback, get_cashback_percent

logger = logging.getLogger(__name__)


async def ensure_regos_card(user: User) -> None:
    """Create a REGOS customer + card for the user if not yet linked."""
    if not regos_client.enabled or user.regos_card_id:
        return

    try:
        customer_id = user.regos_customer_id
        if not customer_id:
            try:
                customer_id = await regos_client.create_customer(user.full_name, user.phone)
            except RegosError as e:
                if e.error_code == 1165:  # phone already in use: reuse existing customer
                    customer_id = await regos_client.find_customer_by_phone(user.phone)
                    if not customer_id:
                        logger.error("Phone in use but customer not found for user %s", user.id)
                        return
                else:
                    raise
        card_id = await regos_client.create_card(int(customer_id), user.barcode_value)
    except RegosError as e:
        logger.error("REGOS card creation failed for user %s: %s", user.id, e)
        return
    except Exception as e:
        logger.error("REGOS unavailable for user %s: %s", user.id, e)
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user.id))
        db_user = result.scalar_one_or_none()
        if db_user:
            db_user.regos_customer_id = str(customer_id)
            db_user.regos_card_id = str(card_id)
            await session.commit()
    user.regos_customer_id = str(customer_id)
    user.regos_card_id = str(card_id)


async def process_cheque_closed(cheque_uuid: str):
    """Handle DocChequeClosed webhook: credit cashback to the card owner.

    Returns (user, cashback_amount, purchase_amount, percent) if credited, otherwise None.
    """
    if not regos_client.enabled:
        logger.warning("REGOS not configured, skipping cheque %s", cheque_uuid)
        return None

    async with AsyncSessionLocal() as session:
        dup = await session.execute(
            select(WalletTransaction).where(WalletTransaction.regos_document_uuid == cheque_uuid)
        )
        if dup.scalar_one_or_none():
            logger.info("Cheque %s already processed, skipping", cheque_uuid)
            return None

    cheque = await regos_client.get_cheque(cheque_uuid)
    if not cheque:
        logger.warning("Cheque %s not found in REGOS", cheque_uuid)
        return None

    if cheque.get("status") != "Closed" or cheque.get("is_return"):
        return None

    card = cheque.get("card")
    if not card:
        return None  # purchase without a loyalty card

    card_id = card.get("id")
    barcode_value = card.get("barcode_value", "")
    amount = float(cheque.get("amount") or 0)
    if amount <= 0 or not card_id:
        return None

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(
                (User.regos_card_id == str(card_id)) | (User.barcode_value == barcode_value)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.info("No bot user for REGOS card %s (%s)", card_id, barcode_value)
            return None

        percent = get_cashback_percent(amount)
        cashback = calculate_cashback(amount)

        try:
            await regos_client.add_cashback(
                int(card_id), cashback,
                description=f"UBAY cashback {percent}% (chek {cheque.get('code', cheque_uuid)})",
            )
        except Exception as e:
            logger.error("Failed to credit cashback in REGOS for cheque %s: %s", cheque_uuid, e)
            return None

        balance_before = float(user.cashback_balance or 0)
        balance_after = balance_before + float(cashback)

        tx = WalletTransaction(
            user_id=user.id,
            regos_document_uuid=cheque_uuid,
            transaction_type="cashback_income",
            purchase_amount=amount,
            cashback_percent=float(percent),
            cashback_amount=float(cashback),
            balance_before=balance_before,
            balance_after=balance_after,
            status="success",
        )
        session.add(tx)
        user.cashback_balance = balance_after
        await session.commit()

        return user, float(cashback), amount, float(percent)
