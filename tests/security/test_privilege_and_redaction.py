from fastapi.testclient import TestClient

from app.streamlit_app import build_customer_facing_receipt, build_non_insurance_disclaimer
from backend.main import create_app
from backend.schemas import PolicyRecommendation


def test_oracle_route_is_restricted_and_customer_copy_is_non_crypto_native(monkeypatch):
    client = TestClient(create_app())
    response = client.post(
        "/oracle/resolve",
        json={
            "policy_id": "p-1",
            "flight_hash": "hash",
            "arrived_on_time": False,
            "delay_minutes": 200,
            "observed_at": "2026-06-20T12:00:00Z",
            "resolver_address": "0xdef",
        },
    )
    assert response.status_code == 403

    disclaimer = build_non_insurance_disclaimer()
    assert "NOT LEGALLY VALID INSURANCE" in disclaimer
    assert "mocked or degraded dependencies" in disclaimer

    receipt = build_customer_facing_receipt(
        PolicyRecommendation(
            policy_name="Flight Delay Guard",
            premium_usdc=42,
            payout_usdc=300,
            delay_trigger_minutes=180,
            coverage_start="2026-06-20T00:00:00Z",
            coverage_end="2026-06-20T23:59:59Z",
            risk_tier="LOW",
            pool_id="pool-demo",
            reason="Matches the approved flight-delay demo profile.",
        ),
        simulated=True,
        provenance="mock:chain",
    )
    visible = " ".join((receipt.headline, *receipt.summary_lines)).lower()
    assert "wallet" not in visible
    assert "pool-demo" not in visible
    assert receipt.simulated is True


def test_internal_routes_require_a_trustlayer_token(monkeypatch, trustlayer_internal_headers):
    monkeypatch.setenv("CIRCLE_READY", "false")
    monkeypatch.delenv("TRUSTLAYER_API_TOKEN", raising=False)
    client = TestClient(create_app())

    unavailable = client.get("/wallet/balance")
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"] == "service unavailable"

    monkeypatch.setenv("TRUSTLAYER_API_TOKEN", "trustlayer-token")

    missing = client.get("/wallet/balance")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "unauthorized"

    allowed = client.get("/wallet/balance", headers=trustlayer_internal_headers)
    assert allowed.status_code == 200
    assert allowed.json()["simulated"] is True

    transcript_missing = client.get("/api/betty/voice-ui-transcript/thread-1234")
    assert transcript_missing.status_code == 401

    transcript_allowed = client.get(
        "/api/betty/voice-ui-transcript/thread-1234",
        headers=trustlayer_internal_headers,
    )
    assert transcript_allowed.status_code == 200
    assert transcript_allowed.json() == {"turns": []}
