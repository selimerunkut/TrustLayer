from fastapi.testclient import TestClient

from backend.main import create_app


def _seed_policy(client: TestClient, policy_id: str, status: str = "PENDING") -> dict[str, object]:
    return {
        "policy": {
            "product_line": "FLIGHT_DELAY",
            "policy_id": policy_id,
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
            "status": status,
        },
        "budget_authorization_key": "auth-e2e",
        "idempotency_key": f"{policy_id}-idem",
    }


def test_demo_paths_cover_live_degraded_and_mock_only(monkeypatch):
    monkeypatch.setenv("ORACLE_PRIVILEGED_TOKEN", "oracle-token")

    live_env = {
        "CIRCLE_READY": "1",
        "BASE_SEPOLIA_READY": "1",
        "CIRCLE_API_KEY": "api-key",
        "CIRCLE_WALLET_ID": "wallet-id",
        "BASE_SEPOLIA_RPC_URL": "https://example.invalid",
        "BASE_SEPOLIA_CONTRACT_ADDRESS": "0x1234",
        "BASE_SEPOLIA_TEST_USDC_ADDRESS": "0xabcd",
    }
    monkeypatch.setenv("CIRCLE_READY", live_env["CIRCLE_READY"])
    monkeypatch.setenv("BASE_SEPOLIA_READY", live_env["BASE_SEPOLIA_READY"])
    monkeypatch.setenv("CIRCLE_API_KEY", live_env["CIRCLE_API_KEY"])
    monkeypatch.setenv("CIRCLE_WALLET_ID", live_env["CIRCLE_WALLET_ID"])
    monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", live_env["BASE_SEPOLIA_RPC_URL"])
    monkeypatch.setenv("BASE_SEPOLIA_CONTRACT_ADDRESS", live_env["BASE_SEPOLIA_CONTRACT_ADDRESS"])
    monkeypatch.setenv("BASE_SEPOLIA_TEST_USDC_ADDRESS", live_env["BASE_SEPOLIA_TEST_USDC_ADDRESS"])

    client = TestClient(create_app())
    assert client.get("/mode/preflight").json()["session_mode"] == "LIVE"
    assert client.post("/budget/authorize", json={
        "policy_draft_id": "draft-e2e",
        "max_budget_usdc": 100,
        "search_fee_cap_usdc": 3,
        "idempotency_key": "auth-e2e",
        "wallet_address": "0xabc",
    }).status_code == 200
    assert client.post("/policy/purchase", json=_seed_policy(client, "p-live")).status_code == 200
    assert client.post("/oracle/resolve", headers={"X-Oracle-Token": "oracle-token"}, json={
        "policy_id": "p-live",
        "flight_hash": "hash",
        "arrived_on_time": False,
        "delay_minutes": 200,
        "observed_at": "2026-06-20T12:00:00Z",
        "resolver_address": "0xdef",
    }).status_code == 200

    monkeypatch.setenv("CIRCLE_READY", "0")
    degraded_client = TestClient(create_app())
    assert degraded_client.get("/mode/preflight").json()["session_mode"] == "DEGRADED"

    monkeypatch.setenv("COVERPILOT_MOCK_ONLY", "1")
    mock_only_client = TestClient(create_app())
    assert mock_only_client.get("/mode/preflight").json()["session_mode"] == "MOCK_ONLY"
