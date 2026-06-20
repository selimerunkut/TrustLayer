import json
import os
import shutil
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.services.circle_wallet import (
    MOCK_WALLET_USDC,
    CircleWalletError,
    TransferReceipt,
    ensure_broker_payer_usdc,
    fetch_wallet_balance,
    fetch_wallet_transactions,
    transfer_premium_usdc,
)

AGENT_WALLET_ENV = {
    "CIRCLE_WALLET_ID": "0xabc123def4567890123456789012345678901234",
    "CIRCLE_API_KEY": "TEST_API_KEY:abc:secret",
    "BASE_SEPOLIA_RPC_URL": "https://sepolia.base.org",
    "BASE_SEPOLIA_TEST_USDC_ADDRESS": "0xusdc",
    "CIRCLE_BLOCKCHAIN": "BASE-SEPOLIA",
}

BALANCE_PAYLOAD = {
    "data": {
        "tokenBalances": [
            {
                "amount": "123.45",
                "token": {
                    "symbol": "USDC",
                    "blockchain": "BASE-SEPOLIA",
                    "tokenAddress": "0xusdc",
                },
            }
        ]
    }
}

TRANSACTIONS_PAYLOAD = {
    "data": {
        "transactions": [
            {
                "id": "tx-1",
                "state": "COMPLETE",
                "txHash": "0xabc123def4567890123456789012345678901234567890123456789012345678901234",
                "amounts": ["1.50"],
                "operation": "TRANSFER",
                "transactionType": "OUTBOUND",
                "createDate": "2026-06-20T12:00:00Z",
            }
        ]
    }
}


@pytest.fixture(autouse=True)
def _clear_live_gates(monkeypatch):
    monkeypatch.delenv("CIRCLE_READY", raising=False)
    monkeypatch.delenv("BASE_SEPOLIA_READY", raising=False)
    monkeypatch.setenv("CIRCLE_READY", "false")
    monkeypatch.setenv("BASE_SEPOLIA_READY", "false")


def test_mock_balance_when_not_live(monkeypatch):
    monkeypatch.setenv("CIRCLE_WALLET_ID", "mock-wallet")
    result = fetch_wallet_balance()
    assert result.simulated is True
    assert result.provenance == "mock:circle_wallet"
    assert result.usdc_total == MOCK_WALLET_USDC


def test_mock_transactions_when_not_live(monkeypatch):
    monkeypatch.setenv("COVERPILOT_MOCK_ONLY", "true")
    result = fetch_wallet_transactions()
    assert result.simulated is True
    assert len(result.transactions) == 1
    assert result.transactions[0].explorer_url.startswith("https://base-sepolia.blockscout.com/tx/")


def test_live_balance_parses_circle_response(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_WALLET_ID": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = BALANCE_PAYLOAD

    with patch("backend.services.circle_wallet.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        result = fetch_wallet_balance()

    assert result.simulated is False
    assert result.provenance == "circle:w3s"
    assert result.usdc_total == 123.45
    assert result.balances[0].symbol == "USDC"
    client_cls.return_value.__enter__.return_value.get.assert_called_once()
    call_kwargs = client_cls.return_value.__enter__.return_value.get.call_args.kwargs
    assert call_kwargs["params"]["tokenAddress"] == "0xusdc"


def test_live_transactions_parses_circle_response(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_WALLET_ID": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = TRANSACTIONS_PAYLOAD

    with patch("backend.services.circle_wallet.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = mock_resp
        result = fetch_wallet_transactions(limit=10)

    assert result.simulated is False
    assert len(result.transactions) == 1
    assert result.transactions[0].tx_hash.startswith("0xabc123")
    assert result.transactions[0].amount_usdc == 1.5
    call_kwargs = client_cls.return_value.__enter__.return_value.get.call_args.kwargs
    assert call_kwargs["params"]["walletIds"] == "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    assert call_kwargs["params"]["pageSize"] == "10"


def test_live_balance_raises_circle_wallet_error_on_http_failure(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_WALLET_ID": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    response = httpx.Response(401, text="unauthorized", request=httpx.Request("GET", "https://api.circle.com"))
    error = httpx.HTTPStatusError("fail", request=response.request, response=response)

    with patch("backend.services.circle_wallet.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.side_effect = error
        with pytest.raises(CircleWalletError, match="Circle balance request failed"):
            fetch_wallet_balance()


def test_live_balance_reads_onchain_usdc_for_agent_wallet_address(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    contract = MagicMock()
    contract.functions.balanceOf.return_value.call.return_value = 2_500_000

    w3 = MagicMock()
    w3.is_connected.return_value = True
    w3.eth.contract.return_value = contract

    with patch("backend.services.circle_wallet.Web3", return_value=w3):
        result = fetch_wallet_balance()

    assert result.provenance == "base:sepolia:erc20"
    assert result.usdc_total == 2.5
    assert result.balances[0].symbol == "USDC"


def test_live_transactions_from_circle_cli_for_agent_wallet(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    cli_payload = {
        "data": {
            "transactions": [
                {
                    "id": "tx-cli-1",
                    "state": "complete",
                    "txHash": "0xabc123def4567890123456789012345678901234567890123456789012345678901234",
                    "amounts": ["1.00"],
                    "operation": "TRANSFER",
                    "transactionType": "OUTBOUND",
                    "createDate": "2026-06-20T12:00:00Z",
                }
            ]
        }
    }
    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = json.dumps(cli_payload)
    completed.stderr = ""

    with patch("backend.services.circle_wallet.shutil.which", return_value="/usr/local/bin/circle"):
        with patch("backend.services.circle_wallet.subprocess.run", return_value=completed) as run:
            result = fetch_wallet_transactions(limit=5)

    assert result.provenance == "circle:cli"
    assert len(result.transactions) == 1
    assert result.transactions[0].amount_usdc == 1.0
    assert result.transactions[0].explorer_url.startswith("https://base-sepolia.blockscout.com/tx/")
    command = run.call_args.args[0]
    assert command[:3] == ["circle", "transaction", "list"]


def test_transfer_premium_usdc_mock_when_not_live(monkeypatch):
    monkeypatch.setenv("BASE_SEPOLIA_DEPLOYER_ADDRESS", "0xdeployer")
    receipt = transfer_premium_usdc(
        amount_usdc=1.0,
        destination_address="0xvault",
        idempotency_key="premium:pol-1",
        reference="pol-1",
    )
    assert receipt.simulated is True
    assert receipt.amount_usdc == 1.0
    assert receipt.tx_hash.startswith("mock-transfer:")


def test_transfer_premium_usdc_parses_cli_tx_hash(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    completed = MagicMock()
    completed.returncode = 0
    completed.stdout = '{"transaction":"0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"}'
    completed.stderr = ""

    with patch("backend.services.circle_wallet.subprocess.run", return_value=completed):
        receipt = transfer_premium_usdc(
            amount_usdc=1.0,
            destination_address="0xvault",
            idempotency_key="premium:pol-2",
            reference="pol-2",
        )

    assert receipt.simulated is False
    assert receipt.tx_hash.startswith("0xdeadbeef")


def test_ensure_broker_payer_usdc_noop_when_sufficient(monkeypatch):
    monkeypatch.setenv("BASE_SEPOLIA_DEPLOYER_ADDRESS", "0xdeployer")
    with patch("backend.services.circle_wallet._read_onchain_usdc_balance", return_value=5.0):
        assert ensure_broker_payer_usdc(required_usdc=1.0) is None


def test_ensure_broker_payer_usdc_transfers_shortfall(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "BASE_SEPOLIA_DEPLOYER_ADDRESS": "0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8",
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    transfer_receipt = TransferReceipt(
        reference="fund",
        amount_usdc=1.0,
        destination_address="0xBA3330FB593dEb0203a5801B2E2f6f295f76FAd8",
        tx_hash="0xfeed",
        attempted=True,
        provenance="circle:agent_wallet",
    )

    with patch("backend.services.circle_wallet._read_onchain_usdc_balance", side_effect=[0.0, 1.0]):
        with patch("backend.services.circle_wallet.transfer_premium_usdc", return_value=transfer_receipt) as transfer:
            with patch("backend.services.circle_wallet.time.sleep"):
                receipt = ensure_broker_payer_usdc(required_usdc=1.0)

    assert receipt is transfer_receipt
    transfer.assert_called_once()
    assert transfer.call_args.kwargs["amount_usdc"] == 1.0


def test_wallet_routes_return_mock_payload(monkeypatch):
    monkeypatch.setenv("CIRCLE_READY", "false")
    client = TestClient(create_app())

    balance = client.get("/wallet/balance")
    assert balance.status_code == 200
    body = balance.json()
    assert body["simulated"] is True
    assert body["usdc_total"] == MOCK_WALLET_USDC

    transactions = client.get("/wallet/transactions")
    assert transactions.status_code == 200
    assert len(transactions.json()["transactions"]) == 1


def test_wallet_balance_route_returns_503_on_live_failure(monkeypatch):
    for key, value in {
        **AGENT_WALLET_ENV,
        "CIRCLE_WALLET_ID": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "CIRCLE_READY": "true",
        "BASE_SEPOLIA_READY": "true",
    }.items():
        monkeypatch.setenv(key, value)

    with patch("backend.main.fetch_wallet_balance", side_effect=CircleWalletError("Circle balance request failed")):
        client = TestClient(create_app())
        response = client.get("/wallet/balance")

    assert response.status_code == 503
    assert response.json()["detail"] == "Circle balance request failed"
