from unittest.mock import patch

from backend.services.blockscout_activity import (
    fetch_blockscout_token_transfers,
    fetch_onchain_wallet_activity,
    merge_wallet_transactions,
)
from backend.schemas import WalletTransactionItem


TOKEN_TRANSFER_PAYLOAD = {
    "items": [
        {
            "transaction_hash": "0xba3aefeca1a9d6f9a4e50b528f4413623f7a6ba2d22dc4e7d46d7f2619ad8469",
            "log_index": 98,
            "timestamp": "2026-06-20T08:30:20.000000Z",
            "from": {"hash": "0xFaEc9cDC3Ef75713b48f46057B98BA04885e3391"},
            "to": {"hash": "0x9084A185B4c870321f261D12efb2305F8e3D4504"},
            "total": {"value": "20000000", "decimals": "6"},
        }
    ]
}

DEPLOYER_TX_PAYLOAD = {
    "items": [
        {
            "hash": "0x1601c146652eca7250f562d2ccf21f474753c253e915786b49272da2845b3f89",
            "method": "purchasePolicy",
            "status": "ok",
            "timestamp": "2026-06-20T11:26:00.000000Z",
            "token_transfers": [{"total": {"value": "1000000", "decimals": "6"}}],
        }
    ]
}


def test_parse_token_transfer_in():
    with patch("backend.services.blockscout_activity._get_json", return_value=TOKEN_TRANSFER_PAYLOAD):
        items = fetch_blockscout_token_transfers("0x9084A185B4c870321f261D12efb2305F8e3D4504", limit=5)
    assert len(items) == 1
    assert items[0].operation == "USDC in"
    assert items[0].amount_usdc == 20.0
    assert items[0].tx_hash.startswith("0xba3a")


def test_fetch_onchain_wallet_activity_merges_wallet_and_deployer(monkeypatch):
    env = {
        "CIRCLE_WALLET_ID": "0x9084A185B4c870321f261D12efb2305F8e3D4504",
        "BASE_SEPOLIA_DEPLOYER_ADDRESS": "0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8",
    }

    def fake_get(path, **_kwargs):
        if path.endswith("/token-transfers"):
            return TOKEN_TRANSFER_PAYLOAD
        if path.endswith("/transactions"):
            return DEPLOYER_TX_PAYLOAD
        return {"items": []}

    with patch("backend.services.blockscout_activity._get_json", side_effect=fake_get):
        items = fetch_onchain_wallet_activity(limit=10, env=env)

    assert len(items) == 2
    assert items[0].operation == "USDC in"
    assert items[1].operation == "purchasePolicy"


def test_merge_wallet_transactions_dedupes_by_id():
    a = WalletTransactionItem(id="0xabc", state="ok", amount_usdc=1.0, operation="a")
    b = WalletTransactionItem(id="0xabc", state="ok", amount_usdc=1.0, operation="b")
    c = WalletTransactionItem(id="0xdef", state="ok", amount_usdc=2.0, operation="c", create_date="2026-06-20 12:00:00 UTC")
    merged = merge_wallet_transactions([a, b], [c], limit=5)
    assert len(merged) == 2
