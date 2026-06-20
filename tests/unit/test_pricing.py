from backend.services.pricing import quote_payout_usdc, quote_premium_usdc
from backend.services.receipts import research_fee_usdc


def test_micro_premium_for_small_budget():
    fee = research_fee_usdc(2.0)
    assert quote_premium_usdc(2.0, fee) == 1.0
    assert quote_payout_usdc(2.0) == 10.0


def test_micro_premium_for_typical_demo_budget():
    fee = research_fee_usdc(45.0)
    assert quote_premium_usdc(45.0, fee) == 1.0
    assert quote_payout_usdc(45.0) == 50.0


def test_premium_respects_available_budget():
    assert quote_premium_usdc(1.02, 0.02) == 1.0
    assert quote_premium_usdc(0.5, 0.02) == 0.48
