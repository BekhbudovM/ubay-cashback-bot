from decimal import Decimal, ROUND_HALF_UP


def get_cashback_percent(amount):
    amount = Decimal(str(amount))

    if amount <= Decimal("500000"):
        return Decimal("2")
    if amount <= Decimal("1000000"):
        return Decimal("3")
    if amount <= Decimal("2000000"):
        return Decimal("5")
    if amount <= Decimal("4000000"):
        return Decimal("7")
    if amount <= Decimal("6000000"):
        return Decimal("8")
    return Decimal("10")


def calculate_cashback(amount):
    amount = Decimal(str(amount))
    percent = get_cashback_percent(amount)
    cashback = amount * percent / Decimal("100")
    return cashback.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
