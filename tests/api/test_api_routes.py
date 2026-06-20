from fastapi.testclient import TestClient

from backend.main import create_app


def test_api_routes_support_the_core_money_movement_flow(monkeypatch):
    monkeypatch.setenv("ORACLE_PRIVILEGED_TOKEN", "oracle-token")
    client = TestClient(create_app())

    auth = client.post(
        "/budget/authorize",
        json={
            "policy_draft_id": "draft-1",
            "max_budget_usdc": 100,
            "search_fee_cap_usdc": 3,
            "idempotency_key": "auth-1",
            "wallet_address": "0xabc",
        },
    )
    assert auth.status_code == 200

    rec = client.post(
        "/insurance/recommend",
        json={
            "policy_draft_id": "draft-1",
            "max_budget_usdc": 100,
            "search_fee_cap_usdc": 3,
            "idempotency_key": "auth-1",
            "wallet_address": "0xabc",
        },
    )
    assert rec.status_code == 200
    assert rec.json()["policy_name"] == "Flight Delay Guard"
    assert rec.json()["premium_usdc"] == 1.0
    assert rec.json()["payout_usdc"] == 300.0

    policy = {
        "policy": {
            "product_line": "FLIGHT_DELAY",
            "policy_id": "p-api",
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
        "budget_authorization_key": "auth-1",
        "idempotency_key": "purchase-1",
    }

    purchase = client.post("/policy/purchase", json=policy)
    assert purchase.status_code == 200
    assert purchase.json()["policy_id"] == "p-api"
    assert client.post("/policy/purchase", json=policy).status_code == 200

    assert client.get("/policy/p-api").status_code == 200
    assert client.get("/policy/missing").status_code == 404

    reject = client.post(
        "/policy/reject",
        json={
            **policy,
            "idempotency_key": "reject-1",
            "policy": {**policy["policy"], "policy_id": "p-reject", "status": "REJECTED"},
        },
    )
    assert reject.status_code == 200

    denied = client.post(
        "/oracle/resolve",
        json={
            "policy_id": "p-api",
            "flight_hash": "hash",
            "arrived_on_time": False,
            "delay_minutes": 200,
            "observed_at": "2026-06-20T12:00:00Z",
            "resolver_address": "0xdef",
        },
    )
    assert denied.status_code == 403

    resolved = client.post(
        "/oracle/resolve",
        headers={"X-Oracle-Token": "oracle-token"},
        json={
            "policy_id": "p-api",
            "flight_hash": "hash",
            "arrived_on_time": False,
            "delay_minutes": 200,
            "observed_at": "2026-06-20T12:00:00Z",
            "resolver_address": "0xdef",
        },
    )
    assert resolved.status_code == 200
