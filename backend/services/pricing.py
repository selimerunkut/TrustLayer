from decimal import Decimal, ROUND_HALF_UP

DEMO_PREMIUM_USDC = Decimal("1.00")
MIN_PREMIUM_USDC = Decimal("0.01")


def quote_premium_usdc(max_budget_usdc: float, research_fee_usdc: float) -> float:
    """Return a micro-demo premium (target 1 USDC) within authorized budget."""
    budget = Decimal(str(max_budget_usdc))
    research = Decimal(str(research_fee_usdc))
    available = budget - research
    if available <= 0:
        return float(MIN_PREMIUM_USDC)
    premium = min(DEMO_PREMIUM_USDC, available)
    premium = max(MIN_PREMIUM_USDC, premium)
    return float(premium.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def quote_payout_usdc(max_budget_usdc: float) -> float:
    """Scale payout benefit to the customer's authorized budget band."""
    budget = Decimal(str(max_budget_usdc))
    if budget <= Decimal("5"):
        payout = Decimal("10")
    elif budget <= Decimal("50"):
        payout = Decimal("50")
    else:
        payout = Decimal("300")
    return float(payout.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
