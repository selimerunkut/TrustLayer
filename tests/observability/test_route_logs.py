import json

from fastapi.testclient import TestClient

from backend.main import create_app


def test_route_logs_capture_observability_fields(caplog, monkeypatch):
    monkeypatch.setenv("ORACLE_PRIVILEGED_TOKEN", "oracle-token")
    monkeypatch.setenv("CIRCLE_READY", "1")
    monkeypatch.setenv("BASE_SEPOLIA_READY", "1")
    monkeypatch.setenv("CIRCLE_API_KEY", "api-key")
    monkeypatch.setenv("CIRCLE_WALLET_ID", "wallet-id")
    monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", "https://example.invalid")
    monkeypatch.setenv("BASE_SEPOLIA_CONTRACT_ADDRESS", "0x1234")
    monkeypatch.setenv("BASE_SEPOLIA_TEST_USDC_ADDRESS", "0xabcd")

    client = TestClient(create_app())
    with caplog.at_level("INFO"):
        client.get("/mode/preflight")
        client.post(
            "/budget/authorize",
            json={
                "policy_draft_id": "draft-obs",
                "max_budget_usdc": 100,
                "search_fee_cap_usdc": 3,
                "idempotency_key": "auth-obs",
                "wallet_address": "0xabc",
            },
        )
        client.post(
            "/policy/purchase",
            json={
                "policy": {
                    "product_line": "FLIGHT_DELAY",
                    "policy_id": "p-obs",
                    "customer_wallet": "0xabc",
                    "budget_locked_usdc": 100,
                    "research_fee_usdc": 3,
                    "premium_usdc": 42,
                    "payout_usdc": 300,
                    "delay_threshold_minutes": 180,
                    "policy_start": "2026-06-20T00:00:00Z",
                    "policy_end": "2026-06-20T23:59:59Z",
                    "flight_hash": "hash",
                    "recommendation_hash": "rec",
                    "x402_reference": "x402",
                    "risk_tier": "LOW",
                    "pool_id": "pool-demo",
                    "status": "PENDING",
                },
                "budget_authorization_key": "auth-obs",
                "idempotency_key": "purchase-obs",
            },
        )
        client.post(
            "/oracle/resolve",
            headers={"X-Oracle-Token": "oracle-token"},
            json={
                "policy_id": "p-obs",
                "flight_hash": "hash",
                "arrived_on_time": False,
                "delay_minutes": 200,
                "observed_at": "2026-06-20T12:00:00Z",
                "resolver_address": "0xdef",
            },
        )

    messages = [record.message for record in caplog.records if record.name == "backend.main"]
    payloads = [json.loads(message) for message in messages]
    assert any(item["event"] == "mode_preflight" and item["fallback_mode"] == "real" for item in payloads)
    assert any(item["event"] == "budget_authorize" and item["policy_draft_id"] == "draft-obs" for item in payloads)
    assert any(item["event"] == "policy_purchase" and item["idempotency_key"] == "purchase-obs" for item in payloads)
    assert any(item["event"] == "oracle_resolve" and item["tx_hash"] == "oracle:p-obs" for item in payloads)
