from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    regos_document_uuid: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    transaction_type: Mapped[str] = mapped_column(String(32))
    purchase_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    cashback_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    cashback_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    balance_before: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    balance_after: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    status: Mapped[str] = mapped_column(String(32), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
