from pathlib import Path
import json

from fastapi.testclient import TestClient

from app.streamlit_app import build_customer_facing_receipt, build_fallback_banner, build_non_insurance_disclaimer
from backend.agent import DEFAULT_BROKER_MODEL, build_broker
from backend.main import create_app
from backend.schemas import (
    BudgetAuthorization,
    CoverageLine,
    OracleResolution,
    PolicyRecord,
    PolicyRecommendation,
    PolicyWriteRequest,
    SessionMode,
    TripIntent,
)
from backend.services.chain import ChainWriteResult
from backend.services.circle_x402 import PaymentEvidence, adapt_circle_x402_payment, capture_payment_receipt
from backend.services.chain import (
    ChainWriteResult,
    record_oracle_resolution,
    record_policy_purchase,
    record_policy_rejection,
)
from backend.services.base_sepolia import (
    BaseSepoliaConfig,
    base_sepolia_ready,
    build_base_policy_created_artifact,
    build_claim_payout_receipt,
    load_base_sepolia_config,
)
from backend.services.receipts import research_fee_usdc
from backend.services.oracle import submit_oracle_resolution
from backend.services.session_mode import decide_session_mode, fallback_mode_label, preflight_session_mode
from backend.tools import APPROVED_BROKER_TOOL_NAMES, validate_broker_tools


def test_fastapi_app_boots_and_health_route_exists():
    app = create_app()
    assert app.title == "CoverPilot API"
    assert any(route.path == "/health" for route in app.routes)


def test_customer_facing_receipt_hides_pool_selection_and_crypto_details():
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
        )
    )
    assert receipt.pool_selection_visible is False
    customer_text = " ".join((receipt.headline, *receipt.summary_lines)).lower()
    assert "pool-demo" not in customer_text
    assert "wallet" not in customer_text
    assert "x402" not in customer_text
    assert "base sepolia" not in customer_text
    technical_text = " ".join(value for _, value in receipt.technical_details).lower()
    assert "pool-demo" in technical_text


def test_customer_facing_receipt_can_be_explicitly_marked_as_fallback():
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
        provenance="circle:x402",
    )
    assert receipt.simulated is True
    assert receipt.provenance == "circle:x402"
    assert build_fallback_banner(simulated=False, provenance="") is None
    assert build_fallback_banner(simulated=True, provenance="circle:x402") == "Fallback mode: simulated / circle:x402"


def test_non_insurance_disclaimer_is_explicit():
    disclaimer = build_non_insurance_disclaimer()
    assert disclaimer.startswith("NOT LEGALLY VALID INSURANCE")
    assert "not a legally binding insurance product" in disclaimer
    assert "mocked or degraded dependencies" in disclaimer


def test_core_stack_contract_symbols_exist():
    assert SessionMode.LIVE.value == "LIVE"
    assert CoverageLine.FLIGHT_DELAY.value == "FLIGHT_DELAY"
    assert TripIntent(
        destination="Rome",
        depart_at="2026-07-01",
        return_at="2026-07-10",
        flight_number="TP123",
        traveler_count=1,
        budget_usdc=100,
        concerns="delay protection",
    ).destination == "Rome"


def test_fee_helper_matches_fixed_bands():
    assert research_fee_usdc(50) == 0.5
    assert research_fee_usdc(100) == 3.0
    assert research_fee_usdc(200) == 10.0


def test_session_mode_selection_respects_live_and_mock_only():
    assert decide_session_mode(circle_ready=True, base_sepolia_ready=True) == SessionMode.LIVE
    assert decide_session_mode(circle_ready=False, base_sepolia_ready=True) == SessionMode.DEGRADED
    assert decide_session_mode(circle_ready=False, base_sepolia_ready=False, explicit_mock_only=True) == SessionMode.MOCK_ONLY
    assert fallback_mode_label(SessionMode.LIVE) == "real"
    assert fallback_mode_label(SessionMode.DEGRADED) == "degraded"
    assert fallback_mode_label(SessionMode.MOCK_ONLY) == "mocked"


def test_preflight_session_mode_uses_explicit_env_state():
    assert preflight_session_mode(
        {
            "CIRCLE_READY": "1",
            "BASE_SEPOLIA_READY": "true",
            "CIRCLE_API_KEY": "api-key",
            "CIRCLE_WALLET_ID": "wallet-id",
            "BASE_SEPOLIA_RPC_URL": "https://example.invalid",
            "BASE_SEPOLIA_CONTRACT_ADDRESS": "0x1234",
            "BASE_SEPOLIA_TEST_USDC_ADDRESS": "0xabcd",
        }
    ) == SessionMode.LIVE
    assert preflight_session_mode(
        {"CIRCLE_READY": "0", "BASE_SEPOLIA_READY": "true"}
    ) == SessionMode.DEGRADED
    assert preflight_session_mode(
        {"COVERPILOT_MOCK_ONLY": "yes", "CIRCLE_READY": "1", "BASE_SEPOLIA_READY": "1"}
    ) == SessionMode.MOCK_ONLY


def test_uv_python_version_and_toml_dependency_contract():
    assert Path(".python-version").read_text().strip() == "3.12"
    env_example = Path(".env.example").read_text()
    assert "COVERPILOT_MOCK_ONLY=false" in env_example
    assert "CIRCLE_READY=false" in env_example
    assert "BASE_SEPOLIA_READY=false" in env_example
    assert "ORACLE_PRIVILEGED_TOKEN=" in env_example
    pyproject = Path("pyproject.toml").read_text()
    assert "fastapi" in pyproject
    assert "streamlit" in pyproject
    assert "pydantic" in pyproject
    assert "langchain" in pyproject


def test_manual_evidence_bundle_template_exposes_required_live_fields():
    template = json.loads(Path("tests/manual/evidence-bundle-template.json").read_text())
    assert template["commit_hash"] == ""
    assert template["fallback_mode"] is False
    assert template["live_requirements"] == {
        "circle_x402_payment": False,
        "base_sepolia_policy_creation": False,
        "test_usdc_payout_after_oracle_resolution": False,
    }
    for key in [
        "screenshots",
        "logs",
        "policy_ids",
        "idempotency_keys",
        "receipt_references",
        "tx_hashes",
        "demo_transcript",
    ]:
        assert key in template


def test_shared_models_cover_the_fixed_stack_contract():
    assert BudgetAuthorization(
        policy_draft_id="draft-1",
        max_budget_usdc=100,
        search_fee_cap_usdc=3,
        idempotency_key="abc",
        wallet_address="0xabc",
    ).wallet_address == "0xabc"
    assert PolicyRecommendation(
        product_line=CoverageLine.FLIGHT_DELAY,
        policy_name="Flight Delay Guard",
        premium_usdc=42,
        payout_usdc=300,
        delay_trigger_minutes=180,
        coverage_start="2026-06-20T00:00:00Z",
        coverage_end="2026-06-20T23:59:59Z",
        risk_tier="LOW",
        pool_id="pool-demo",
        reason="demo",
    ).pool_id == "pool-demo"
    assert PolicyRecord(
        product_line=CoverageLine.FLIGHT_DELAY,
        policy_id="p-1",
        customer_wallet="0xabc",
        budget_locked_usdc=100,
        research_fee_usdc=3,
        premium_usdc=42,
        payout_usdc=300,
        delay_threshold_minutes=180,
        policy_start="2026-06-20T00:00:00Z",
        policy_end="2026-06-20T23:59:59Z",
        flight_hash="hash",
        recommendation_hash="rec",
        x402_reference="x402",
        risk_tier="LOW",
        pool_id="pool-demo",
        status="PENDING",
    ).status == "PENDING"
    assert OracleResolution(
        policy_id="p-1",
        flight_hash="hash",
        arrived_on_time=False,
        delay_minutes=200,
        observed_at="2026-06-20T12:00:00Z",
        resolver_address="0xdef",
    ).resolver_address == "0xdef"
    assert PolicyWriteRequest(
        policy={
            "product_line": "FLIGHT_DELAY",
            "policy_id": "p-1",
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
        budget_authorization_key="abc",
        idempotency_key="abc",
    ).budget_authorization_key == "abc"


def test_fastapi_routes_cover_the_planned_boundary(monkeypatch):
    client = TestClient(create_app())
    assert client.get("/health").json() == {"status": "ok"}
    chat = client.post(
        "/chat",
        json={
            "destination": "Rome",
            "depart_at": "2026-07-01",
            "return_at": "2026-07-10",
            "flight_number": "TP123",
            "traveler_count": 1,
            "budget_usdc": 100,
            "concerns": "delay protection",
        },
    )
    assert "Rome" in chat.json()["message"]
    auth = client.post(
        "/budget/authorize",
        json={
            "policy_draft_id": "draft-1",
            "max_budget_usdc": 100,
            "search_fee_cap_usdc": 3,
            "idempotency_key": "abc",
            "wallet_address": "0xabc",
        },
    )
    assert auth.json()["max_budget_usdc"] == 100
    assert client.post("/policy/purchase", json={
        "policy": {
            "product_line": "FLIGHT_DELAY",
            "policy_id": "p-1",
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
        "budget_authorization_key": "missing-auth",
        "idempotency_key": "purchase-1",
    }).status_code == 403
    rec = client.post(
        "/insurance/recommend",
        json={
            "policy_draft_id": "draft-1",
            "max_budget_usdc": 100,
            "search_fee_cap_usdc": 3,
            "idempotency_key": "abc",
            "wallet_address": "0xabc",
        },
    )
    assert rec.json()["policy_name"] == "Flight Delay Guard"
    policy = {
        "policy": {
            "product_line": "FLIGHT_DELAY",
            "policy_id": "p-1",
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
        "budget_authorization_key": "abc",
        "idempotency_key": "purchase-1",
    }
    assert client.post("/policy/purchase", json=policy).json()["policy_id"] == "p-1"
    assert client.post("/policy/purchase", json=policy).json()["policy_id"] == "p-1"
    assert client.app.state.chain_write_store["purchase:p-1"].tx_hash == "purchase:p-1"
    assert client.app.state.chain_write_store["purchase:p-1"].provenance == "mock:chain"
    assert client.get("/policy/p-1").json()["policy_id"] == "p-1"
    assert client.post(
        "/policy/purchase",
        json={**policy, "idempotency_key": "purchase-2", "policy": {**policy["policy"], "premium_usdc": 41}},
    ).status_code == 409
    assert client.post(
        "/policy/reject",
        json={
            **policy,
            "idempotency_key": "reject-1",
            "policy": {**policy["policy"], "status": "REJECTED", "policy_id": "p-2"},
        },
    ).json()["policy_id"] == "p-2"
    assert client.app.state.chain_write_store["reject:p-2"].tx_hash == "reject:p-2"
    monkeypatch.setenv("ORACLE_PRIVILEGED_TOKEN", "oracle-token")
    oracle = client.post(
        "/oracle/resolve",
        headers={"X-Oracle-Token": "oracle-token"},
        json={
            "policy_id": "p-1",
            "flight_hash": "hash",
            "arrived_on_time": False,
            "delay_minutes": 200,
            "observed_at": "2026-06-20T12:00:00Z",
            "resolver_address": "0xdef",
        },
    )
    assert oracle.json()["policy_id"] == "p-1"
    assert client.app.state.chain_write_store["oracle:p-1"].provenance == "mock:oracle"


def test_oracle_route_requires_a_privileged_token(monkeypatch):
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
    assert response.json()["detail"] == "oracle route is privileged"

    monkeypatch.setenv("ORACLE_PRIVILEGED_TOKEN", "oracle-token")
    privileged_client = TestClient(create_app())
    allowed = privileged_client.post(
        "/oracle/resolve",
        headers={"X-Oracle-Token": "oracle-token"},
        json={
            "policy_id": "p-1",
            "flight_hash": "hash",
            "arrived_on_time": False,
            "delay_minutes": 200,
            "observed_at": "2026-06-20T12:00:00Z",
            "resolver_address": "0xdef",
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["policy_id"] == "p-1"


def test_mode_preflight_route_reports_session_mode(monkeypatch):
    monkeypatch.setenv("CIRCLE_READY", "1")
    monkeypatch.setenv("BASE_SEPOLIA_READY", "1")
    monkeypatch.setenv("CIRCLE_API_KEY", "api-key")
    monkeypatch.setenv("CIRCLE_WALLET_ID", "wallet-id")
    monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", "https://example.invalid")
    monkeypatch.setenv("BASE_SEPOLIA_CONTRACT_ADDRESS", "0x1234")
    monkeypatch.setenv("BASE_SEPOLIA_TEST_USDC_ADDRESS", "0xabcd")
    client = TestClient(create_app())
    assert client.get("/mode/preflight").json() == {
        "session_mode": "LIVE",
        "fallback_mode": "real",
    }


def test_broker_factory_is_langchain_backed():
    broker = build_broker(model=object(), tools=[])
    assert broker is not None


def test_broker_defaults_to_the_fixed_gpt_5_4_mini_model():
    assert DEFAULT_BROKER_MODEL == "gpt-5.4-mini"
    assert build_broker.__kwdefaults__["model"] == DEFAULT_BROKER_MODEL


def test_streamlit_app_keeps_pool_selection_out_of_the_customer_path():
    source = Path("app/streamlit_app.py").read_text().lower()
    assert "selectbox" not in source
    assert "radio(" not in source
    assert "pool selection" in source
    assert "technical details" in source
    assert "not legally valid insurance" in source


def test_streamlit_app_shows_budget_and_fee_before_authorization():
    source = Path("app/streamlit_app.py").read_text().lower()
    assert "maximum approved budget" in source
    assert "deterministic research-fee quote" in source


def test_solidity_contract_scaffold_exists():
    contract = Path("contracts/InsuranceManager.sol").read_text()
    assert "contract InsuranceManager" in contract
    assert "purchasePolicy" in contract
    assert "resolvePolicy" in contract


def test_wallet_chain_and_oracle_service_seams_exist():
    assert PaymentEvidence(reference="x402-1", amount_usdc=1).reference == "x402-1"
    assert PaymentEvidence(reference="x402-1", amount_usdc=1, simulated=True, provenance="circle:x402").provenance == "circle:x402"
    evidence = adapt_circle_x402_payment(reference="x402-2", amount_usdc=2, simulated=True)
    receipt = capture_payment_receipt(evidence)
    assert evidence.reference == "x402-2"
    assert receipt.reference == "x402-2"
    assert receipt.simulated is True
    assert ChainWriteResult(policy_id="p-1", tx_hash="0xabc").tx_hash == "0xabc"
    assert ChainWriteResult(policy_id="p-1", tx_hash="0xabc", simulated=True, provenance="base:sepolia").provenance == "base:sepolia"
    policy = PolicyRecord(
        product_line=CoverageLine.FLIGHT_DELAY,
        policy_id="p-1",
        customer_wallet="0xabc",
        budget_locked_usdc=100,
        research_fee_usdc=3,
        premium_usdc=42,
        payout_usdc=300,
        delay_threshold_minutes=180,
        policy_start="2026-06-20T00:00:00Z",
        policy_end="2026-06-20T23:59:59Z",
        flight_hash="hash",
        recommendation_hash="rec",
        x402_reference="x402",
        risk_tier="LOW",
        pool_id="pool-demo",
        status="PENDING",
    )
    resolution = OracleResolution(
        policy_id="p-1",
        flight_hash="hash",
        arrived_on_time=False,
        delay_minutes=200,
        observed_at="2026-06-20T12:00:00Z",
        resolver_address="0xdef",
    )
    assert record_policy_purchase(policy, tx_hash="purchase:p-1", simulated=True).policy_id == "p-1"
    assert record_policy_rejection(policy, tx_hash="reject:p-1", simulated=True).provenance == "base:sepolia"
    assert record_oracle_resolution(resolution, tx_hash="oracle:p-1", simulated=True, provenance="mock:oracle").provenance == "mock:oracle"
    assert submit_oracle_resolution(resolution).policy_id == "p-1"


def test_base_sepolia_config_and_live_artifact_shapes_are_defined():
    config = load_base_sepolia_config(
        {
            "BASE_SEPOLIA_RPC_URL": "https://example.invalid",
            "BASE_SEPOLIA_CONTRACT_ADDRESS": "0x1234",
            "BASE_SEPOLIA_TEST_USDC_ADDRESS": "0xabcd",
            "CIRCLE_API_KEY": "api-key",
            "CIRCLE_WALLET_ID": "wallet-id",
        }
    )
    assert isinstance(config, BaseSepoliaConfig)
    assert base_sepolia_ready(config) is True

    policy = PolicyRecord(
        product_line=CoverageLine.FLIGHT_DELAY,
        policy_id="p-1",
        customer_wallet="0xabc",
        budget_locked_usdc=100,
        research_fee_usdc=3,
        premium_usdc=42,
        payout_usdc=300,
        delay_threshold_minutes=180,
        policy_start="2026-06-20T00:00:00Z",
        policy_end="2026-06-20T23:59:59Z",
        flight_hash="hash",
        recommendation_hash="rec",
        x402_reference="x402",
        risk_tier="LOW",
        pool_id="pool-demo",
        status="PENDING",
    )
    resolution = OracleResolution(
        policy_id="p-1",
        flight_hash="hash",
        arrived_on_time=False,
        delay_minutes=200,
        observed_at="2026-06-20T12:00:00Z",
        resolver_address="0xdef",
    )
    created = build_base_policy_created_artifact(
        policy,
        tx_hash="0xtx",
        contract_address="0x1234",
        block_number=99,
        simulated=False,
    )
    payout = build_claim_payout_receipt(
        policy_id="p-1",
        tx_hash="0xpay",
        oracle_resolution=resolution,
        contract_address="0x1234",
        block_number=100,
        simulated=False,
    )
    assert created["contract_address"] == "0x1234"
    assert created["policy_id"] == "p-1"
    assert created["block_number"] == 99
    assert payout["policy_id"] == "p-1"
    assert payout["contract_address"] == "0x1234"
    assert payout["resolver_address"] == "0xdef"


def test_broker_allowlist_excludes_oracle_and_rejects_unapproved_tools():
    assert "submit_oracle_resolution" not in APPROVED_BROKER_TOOL_NAMES
    def get_wallet_balance() -> None:
        return None

    def purchase_policy() -> None:
        return None

    validate_broker_tools([get_wallet_balance, purchase_policy])

    def oracle() -> None:
        return None

    oracle.__name__ = "oracle"
    try:
        validate_broker_tools([oracle])
    except ValueError as exc:
        assert "forbidden broker tools" in str(exc)
    else:
        raise AssertionError("oracle tool should be rejected")
