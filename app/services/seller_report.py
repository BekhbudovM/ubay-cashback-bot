"""Sales per seller, read from REGOS cheques.

At the till the cashier scans the seller's barcode into the "Продавец" field,
so every closed cheque carries a `seller` (a REGOS user). Cheques are fetched
from REGOS per day (Tashkent time), cached briefly, and summed per seller.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from app.integrations.regos.client import regos_client

logger = logging.getLogger(__name__)

TASHKENT = timezone(timedelta(hours=5))  # Uzbekistan has no DST
NO_SELLER_ID = 0
HISTORY_DAYS = 7
TODAY_TTL = 120      # seconds: today's sales keep changing
PAST_TTL = 30 * 60   # seconds: past days rarely change
MAX_CACHED_DAYS = 120
MAX_CHEQUE_LINES = 30

WEEKDAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
WEEKDAYS_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
MONTHS_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]


@dataclass
class ChequeLine:
    ts: int
    amount: float
    is_return: bool

    @property
    def time(self) -> str:
        return datetime.fromtimestamp(self.ts, TASHKENT).strftime("%H:%M")


@dataclass
class SellerTotals:
    seller_id: int
    name: str
    barcode: str = ""
    sales: float = 0.0
    sales_count: int = 0
    returns: float = 0.0
    returns_count: int = 0
    cheques: list = field(default_factory=list)

    @property
    def net(self) -> float:
        return self.sales - self.returns

    @property
    def has_activity(self) -> bool:
        return bool(self.sales_count or self.returns_count)


# ── Dates ─────────────────────────────────────────────────────────────────────

def today() -> date:
    return datetime.now(TASHKENT).date()


def day_bounds(d: date) -> tuple:
    start = int(datetime(d.year, d.month, d.day, tzinfo=TASHKENT).timestamp())
    return start, start + 86400 - 1


def day_title(d: date, with_year: bool = True) -> str:
    fmt = "%d.%m.%Y" if with_year else "%d.%m"
    return f"{d.strftime(fmt)}, {WEEKDAYS_UZ[d.weekday()]}"


def short_day(d: date) -> str:
    return f"{d:%d.%m} {WEEKDAYS_SHORT[d.weekday()]}"


def month_title(year: int, month: int) -> str:
    return f"{MONTHS_UZ[month - 1]} {year}"


def fmt_sum(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", " ")


def _ts(cheque: dict) -> int:
    value = int(cheque.get("date") or 0)
    return value // 1000 if value > 10 ** 11 else value  # tolerate milliseconds


# ── Fetching (cached per day) ─────────────────────────────────────────────────

_day_cache = {}  # date -> (fetched_at, [cheques])


def clear_cache():
    _day_cache.clear()


def _is_fresh(d: date, now: float, current_day: date) -> bool:
    hit = _day_cache.get(d)
    if not hit:
        return False
    ttl = TODAY_TTL if d >= current_day else PAST_TTL
    return now - hit[0] < ttl


async def cheques_for_days(days: list) -> dict:
    """{day: [cheques]} for the given days. Missing days are fetched in one call."""
    now = time.time()
    current_day = today()
    missing = [d for d in days if d <= current_day and not _is_fresh(d, now, current_day)]
    if missing:
        lo, hi = min(missing), max(missing)
        start = day_bounds(lo)[0]
        end = min(day_bounds(hi)[1], int(now))
        cheques = await regos_client.get_recent_cheques(start, end)
        buckets = {}
        for c in cheques:
            d = datetime.fromtimestamp(_ts(c), TASHKENT).date()
            buckets.setdefault(d, []).append(c)
        d = lo
        while d <= hi:
            _day_cache[d] = (now, buckets.get(d, []))
            d += timedelta(days=1)
        if len(_day_cache) > MAX_CACHED_DAYS:
            for old in sorted(_day_cache, key=lambda k: _day_cache[k][0])[: len(_day_cache) - MAX_CACHED_DAYS]:
                _day_cache.pop(old, None)
    return {d: (_day_cache[d][1] if d in _day_cache else []) for d in days}


# ── Aggregation ───────────────────────────────────────────────────────────────

def _person_name(person: dict) -> str:
    name = (person.get("full_name") or "").strip()
    if not name:
        name = " ".join(p for p in (person.get("last_name"), person.get("first_name")) if p).strip()
    return name or f"Xodim #{person.get('id')}"


def aggregate(cheques: list) -> dict:
    """Sum closed cheques per seller: {seller_id: SellerTotals}."""
    totals = {}
    for c in cheques:
        if c.get("status") != "Closed":
            continue
        seller = c.get("seller") or {}
        sid = seller.get("id") or NO_SELLER_ID
        if sid not in totals:
            totals[sid] = SellerTotals(
                seller_id=sid,
                name=_person_name(seller) if sid else "Sotuvchi urilmagan",
                barcode=seller.get("seller_barcode") or "",
            )
        t = totals[sid]
        amount = abs(float(c.get("amount") or 0))
        is_return = bool(c.get("is_return"))
        if is_return:
            t.returns += amount
            t.returns_count += 1
        else:
            t.sales += amount
            t.sales_count += 1
        t.cheques.append(ChequeLine(ts=_ts(c), amount=amount, is_return=is_return))
    for t in totals.values():
        t.cheques.sort(key=lambda line: line.ts)
    return totals


def merge(totals_list: list) -> dict:
    """Add several {seller_id: SellerTotals} dicts together (e.g. a week)."""
    merged = {}
    for totals in totals_list:
        for sid, t in totals.items():
            m = merged.setdefault(sid, SellerTotals(seller_id=sid, name=t.name, barcode=t.barcode))
            m.sales += t.sales
            m.sales_count += t.sales_count
            m.returns += t.returns
            m.returns_count += t.returns_count
            m.cheques.extend(t.cheques)
    return merged


async def day_totals(d: date) -> dict:
    return aggregate((await cheques_for_days([d]))[d])


async def history(end: date = None, days: int = HISTORY_DAYS) -> list:
    """[(day, {seller_id: SellerTotals})], newest day first."""
    end = end or today()
    ds = [end - timedelta(days=i) for i in range(days)]
    data = await cheques_for_days(ds)
    return [(d, aggregate(data[d])) for d in ds]


# ── Sellers ───────────────────────────────────────────────────────────────────

async def get_sellers() -> list:
    """Active REGOS users that have a seller barcode: [(id, name, barcode)]."""
    try:
        users = await regos_client.get_users()
    except Exception as e:  # integration may lack permission to list users
        logger.warning("REGOS user/get failed: %s", e)
        return []
    sellers = [
        (u["id"], _person_name(u), u.get("seller_barcode") or "")
        for u in users
        if u.get("seller_barcode") and not u.get("system") and u.get("active") is not False
    ]
    sellers.sort(key=lambda s: s[1].lower())
    return sellers


async def seller_directory(*totals_dicts) -> list:
    """Sellers with a barcode, plus anyone who appears as seller on the given cheques."""
    sellers = await get_sellers()
    known = {s[0] for s in sellers}
    for totals in totals_dicts:
        for sid, t in totals.items():
            if sid != NO_SELLER_ID and sid not in known:
                sellers.append((sid, t.name, t.barcode))
                known.add(sid)
    return sellers


async def seller_info(seller_id: int, *totals_dicts) -> tuple:
    if seller_id == NO_SELLER_ID:
        return "Sotuvchi urilmagan", ""
    for totals in totals_dicts:
        if seller_id in totals:
            return totals[seller_id].name, totals[seller_id].barcode
    for sid, name, barcode in await get_sellers():
        if sid == seller_id:
            return name, barcode
    return f"Xodim #{seller_id}", ""


# ── Texts shared by the bot screens and the daily report ──────────────────────

def totals_line(t: SellerTotals) -> str:
    if not t or not t.has_activity:
        return "0 so'm"
    text = f"{fmt_sum(t.net)} so'm ({t.sales_count} chek"
    if t.returns_count:
        text += f", ↩️ {t.returns_count}"
    return text + ")"


async def all_sellers_day_text(d: date, heading: str) -> str:
    """Every seller's sales for one day, best first (sellers with 0 included)."""
    totals = await day_totals(d)
    directory = await seller_directory(totals)

    rows = []
    for sid, name, _barcode in directory:
        t = totals.get(sid) or SellerTotals(seller_id=sid, name=name)
        rows.append((t.net, name, t))
    rows.sort(key=lambda r: (-r[0], r[1].lower()))

    lines = [heading, ""]
    if not rows and NO_SELLER_ID not in totals:
        lines.append("Bu kuni savdo bo'lmagan.")
    for i, (_, name, t) in enumerate(rows, 1):
        lines.append(f"{i}. {name} — {totals_line(t)}")
    if NO_SELLER_ID in totals:
        lines.append(f"❔ Sotuvchi urilmagan — {totals_line(totals[NO_SELLER_ID])}")

    all_t = merge([totals]).values()
    sales = sum(t.sales for t in all_t)
    returns = sum(t.returns for t in all_t)
    count = sum(t.sales_count for t in all_t)
    returns_count = sum(t.returns_count for t in all_t)
    lines += ["━━━━━━━━━━━━", f"💰 Jami: {fmt_sum(sales - returns)} so'm ({count} chek)"]
    if returns_count:
        lines.append(f"↩️ Qaytarishlar: −{fmt_sum(returns)} so'm ({returns_count} ta)")
    return "\n".join(lines)
