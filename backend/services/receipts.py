from decimal import Decimal, ROUND_HALF_UP


def research_fee_usdc(budget_usdc: float) -> float:
    budget = Decimal(str(budget_usdc))
    if budget <= 50:
        rate = Decimal("0.01")
    elif budget <= 150:
        rate = Decimal("0.03")
    else:
        rate = Decimal("0.05")
    fee = (budget * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(min(fee, budget))

