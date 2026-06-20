import logging
import json
import os
from collections.abc import MutableMapping

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.betty_voice_routes import register_betty_voice_routes

from backend.schemas import (
    BudgetAuthorization,
    CoverageLine,
    OracleResolution,
    PolicyRecommendation,
    PolicyRecord,
    PolicyWriteRequest,
    TripIntent,
)
from backend.services.chain import ChainWriteResult, record_oracle_resolution, record_policy_purchase, record_policy_rejection
from backend.services.session_mode import fallback_mode_label, preflight_session_mode

logger = logging.getLogger(__name__)


def _store(app: FastAPI) -> MutableMapping[str, PolicyRecord]:
    if not hasattr(app.state, "policy_store"):
        app.state.policy_store = {}
    return app.state.policy_store


def _budget_authorization_store(app: FastAPI) -> MutableMapping[str, BudgetAuthorization]:
    if not hasattr(app.state, "budget_authorization_store"):
        app.state.budget_authorization_store = {}
    return app.state.budget_authorization_store


def _policy_write_store(app: FastAPI) -> MutableMapping[str, tuple[str, PolicyRecord]]:
    if not hasattr(app.state, "policy_write_store"):
        app.state.policy_write_store = {}
    return app.state.policy_write_store


def _chain_write_store(app: FastAPI) -> MutableMapping[str, ChainWriteResult]:
    if not hasattr(app.state, "chain_write_store"):
        app.state.chain_write_store = {}
    return app.state.chain_write_store


def _oracle_privileged_token() -> str:
    return os.environ.get("ORACLE_PRIVILEGED_TOKEN", "").strip()


def _fingerprint_policy(policy: PolicyRecord) -> str:
    return json.dumps(policy.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, sort_keys=True))


def _guard_policy_write(app: FastAPI, request: PolicyWriteRequest, *, expected_status: str) -> PolicyRecord:
    authorization = _budget_authorization_store(app).get(request.budget_authorization_key)
    if authorization is None:
        raise HTTPException(status_code=403, detail="budget authorization required")

    if request.policy.customer_wallet != authorization.wallet_address:
        raise HTTPException(status_code=403, detail="wallet mismatch")
    if request.policy.budget_locked_usdc > authorization.max_budget_usdc:
        raise HTTPException(status_code=403, detail="budget exceeds authorization")
    if request.policy.research_fee_usdc > authorization.search_fee_cap_usdc:
        raise HTTPException(status_code=403, detail="research fee exceeds authorization")

    if request.policy.status != expected_status:
        raise HTTPException(status_code=400, detail="policy status does not match route")

    mutation_store = _policy_write_store(app)
    mutation_key = f"{expected_status}:{request.idempotency_key}"
    policy_fingerprint = _fingerprint_policy(request.policy)
    existing = mutation_store.get(mutation_key)
    if existing is not None:
        existing_fingerprint, existing_policy = existing
        if existing_fingerprint != policy_fingerprint:
            raise HTTPException(status_code=409, detail="idempotency key reuse with different policy")
        return existing_policy

    policy_store = _store(app)
    stored_policy = policy_store.get(request.policy.policy_id)
    if stored_policy is not None:
        if _fingerprint_policy(stored_policy) != policy_fingerprint:
            raise HTTPException(status_code=409, detail="policy already written with different contents")
        mutation_store[mutation_key] = (policy_fingerprint, stored_policy)
        return stored_policy

    policy_store[request.policy.policy_id] = request.policy
    mutation_store[mutation_key] = (policy_fingerprint, request.policy)
    return request.policy


def create_app() -> FastAPI:
    app = FastAPI(title="TrustLayer API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_betty_voice_routes(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mode/preflight")
    def preflight_mode() -> dict[str, str]:
        session_mode = preflight_session_mode()
        _log_event(
            "mode_preflight",
            session_mode=session_mode.value,
            fallback_mode=fallback_mode_label(session_mode),
        )
        return {
            "session_mode": session_mode.value,
            "fallback_mode": fallback_mode_label(session_mode),
        }

    @app.post("/chat")
    def chat(intent: TripIntent) -> dict[str, str]:
        return {
            "message": (
                f"Got it — you want coverage for {intent.destination} "
                f"on flight {intent.flight_number}."
            )
        }

    @app.post("/budget/authorize")
    def authorize_budget(request: BudgetAuthorization) -> BudgetAuthorization:
        _budget_authorization_store(app)[request.idempotency_key] = request
        _log_event(
            "budget_authorize",
            policy_draft_id=request.policy_draft_id,
            idempotency_key=request.idempotency_key,
            wallet_address=request.wallet_address,
            max_budget_usdc=request.max_budget_usdc,
            search_fee_cap_usdc=request.search_fee_cap_usdc,
        )
        return request

    @app.post("/insurance/recommend")
    def recommend(_: BudgetAuthorization) -> PolicyRecommendation:
        recommendation = PolicyRecommendation(
            product_line=CoverageLine.FLIGHT_DELAY,
            policy_name="Flight Delay Guard",
            premium_usdc=42.0,
            payout_usdc=300.0,
            delay_trigger_minutes=180,
            coverage_start="2026-06-20T00:00:00Z",
            coverage_end="2026-06-20T23:59:59Z",
            risk_tier="LOW",
            pool_id="pool-demo",
            reason="Matches the approved flight-delay demo profile.",
        )
        _log_event(
            "insurance_recommend",
            policy_name=recommendation.policy_name,
            premium_usdc=recommendation.premium_usdc,
            payout_usdc=recommendation.payout_usdc,
            pool_id=recommendation.pool_id,
        )
        return recommendation

    @app.post("/policy/purchase")
    def purchase_policy(request: PolicyWriteRequest) -> PolicyRecord:
        stored_policy = _guard_policy_write(app, request, expected_status="PENDING")
        chain_result = record_policy_purchase(
            stored_policy,
            tx_hash=f"purchase:{stored_policy.policy_id}",
            simulated=True,
            provenance="mock:chain",
        )
        _chain_write_store(app)[f"purchase:{stored_policy.policy_id}"] = chain_result
        _log_event(
            "policy_purchase",
            policy_id=stored_policy.policy_id,
            idempotency_key=request.idempotency_key,
            tx_hash=chain_result.tx_hash,
            simulated=chain_result.simulated,
            provenance=chain_result.provenance,
        )
        return stored_policy

    @app.post("/policy/reject")
    def reject_policy(request: PolicyWriteRequest) -> PolicyRecord:
        stored_policy = _guard_policy_write(app, request, expected_status="REJECTED")
        chain_result = record_policy_rejection(
            stored_policy,
            tx_hash=f"reject:{stored_policy.policy_id}",
            simulated=True,
            provenance="mock:chain",
        )
        _chain_write_store(app)[f"reject:{stored_policy.policy_id}"] = chain_result
        _log_event(
            "policy_reject",
            policy_id=stored_policy.policy_id,
            idempotency_key=request.idempotency_key,
            tx_hash=chain_result.tx_hash,
            simulated=chain_result.simulated,
            provenance=chain_result.provenance,
        )
        return stored_policy

    @app.get("/policy/{policy_id}")
    def get_policy(policy_id: str) -> PolicyRecord:
        try:
            return _store(app)[policy_id]
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="policy not found") from exc

    @app.post("/oracle/resolve")
    def resolve_oracle(
        resolution: OracleResolution,
        x_oracle_token: str | None = Header(default=None, alias="X-Oracle-Token"),
    ) -> OracleResolution:
        expected_token = _oracle_privileged_token()
        if not expected_token or x_oracle_token != expected_token:
            raise HTTPException(status_code=403, detail="oracle route is privileged")

        resolved = resolution
        chain_result = record_oracle_resolution(
            resolved,
            tx_hash=f"oracle:{resolved.policy_id}",
            simulated=True,
            provenance="mock:oracle",
        )
        _chain_write_store(app)[f"oracle:{resolved.policy_id}"] = chain_result
        _log_event(
            "oracle_resolve",
            policy_id=resolved.policy_id,
            tx_hash=chain_result.tx_hash,
            simulated=chain_result.simulated,
            provenance=chain_result.provenance,
        )
        return resolved

    return app


app = create_app()
