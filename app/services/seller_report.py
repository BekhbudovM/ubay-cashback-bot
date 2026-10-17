"""Sales per seller, read from REGOS cheques.

At the till the cashier scans the seller's barcode into the "Продавец" field,
so every closed cheque carries a `seller` (a REGOS user). Here we sum those
cheques per seller for today / this week / this month (Tashkent time).
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.integrations.regos.client import regos_client

logger = logging.getLogger(__name__)

TASHKENT = timezone(timedelta(hours=5))  # Uzbekistan has no DST
NO_SELLER_ID = 0
CACHE_TTL = 120  # seconds; avoids re-downloading cheques on every button tap

MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]


@dataclass
class SellerTotals:
    seller_id: int
    name: str
    barcode: str = ""
    sales: float = 0.0
    sales_count: int = 0
    returns: float = 0.0
    returns_count: int = 0

    @property
    def net(self) -> float:
        return self.sales - self.returns


@dataclass
class Period:
    key: str
    title: str
    start: int
    end: int
    totals: dict = field(default_factory=dict)  # seller_id -> SellerTotals


def period_bounds(now: datetime = None) -> dict:
    """Unix-second bounds for today, this week (from Monday) and this month."""
    now = now or datetime.now(TASHKENT)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = day_start - timedelta(days=day_start.weekday())
    month_start = day_start.replace(day=1)
    end = int(now.timestamp())
    return {
        "today": (f"Bugun ({day_start:%d.%m})", int(day_start.timestamp()), end),
        "week": (f"Shu hafta ({week_start:%d.%m}–{day_start:%d.%m})", int(week_start.timestamp()), end),
        "month": (f"{MONTHS_UZ[month_start.month - 1]} oyi", int(month_start.timestamp()), end),
    }


_cache = {"start": None, "fetched_at": 0.0, "cheques": []}


async def _cheques_since(start: int) -> list:
    now = time.time()
    if (
        _cache["start"] is not None
        and _cache["start"] <= start
        and now - _cache["fetched_at"] < CACHE_TTL
    ):
        return _cache["cheques"]
    cheques = await regos_client.get_recent_cheques(start, int(now))
    _cache.update(start=start, fetched_at=now, cheques=cheques)
    return cheques


def clear_cache():
    _cache.update(start=None, fetched_at=0.0, cheques=[])


def _seller_name(seller: dict) -> str:
    name = (seller.get("full_name") or "").strip()
    if not name:
        name = " ".join(
            p for p in (seller.get("last_name"), seller.get("first_name")) if p
        ).strip()
    return name or f"Xodim #{seller.get('id')}"


def aggregate(cheques: list, start: int, end: int) -> dict:
    """Sum closed cheques in [start, end] per seller. Returns subtract."""
    totals = {}
    for c in cheques:
        if c.get("status") != "Closed":
            continue
        date = c.get("date") or 0
        if not (start <= date <= end):
            continue
        seller = c.get("seller") or {}
        sid = seller.get("id") or NO_SELLER_ID
        if sid not in totals:
            totals[sid] = SellerTotals(
                seller_id=sid,
                name=_seller_name(seller) if sid else "Sotuvchi urilmagan",
                barcode=seller.get("seller_barcode") or "",
            )
        t = totals[sid]
        amount = abs(float(c.get("amount") or 0))
        if c.get("is_return"):
            t.returns += amount
            t.returns_count += 1
        else:
            t.sales += amount
            t.sales_count += 1
    return totals


async def build_periods() -> list:
    bounds = period_bounds()
    earliest = min(b[1] for b in bounds.values())
    cheques = await _cheques_since(earliest)
    return [
        Period(key=k, title=title, start=s, end=e, totals=aggregate(cheques, s, e))
        for k, (title, s, e) in bounds.items()
    ]


async def get_employees() -> list:
    """Non-system REGOS users as (id, name, seller_barcode), sellers first.

    If the integration can't read users, returns [] and the caller falls back
    to sellers seen on cheques.
    """
    try:
        users = await regos_client.get_users()
    except Exception as e:
        logger.warning("REGOS user/get failed: %s", e)
        return []
    employees = []
    for u in users:
        if u.get("system") or u.get("active") is False:
            continue
        employees.append((u["id"], _seller_name(u), u.get("seller_barcode") or ""))
    employees.sort(key=lambda x: (not x[2], x[1].lower()))
    return employees


def fmt_sum(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ")
