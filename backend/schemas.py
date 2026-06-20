from enum import Enum

from pydantic import BaseModel, Field


class SessionMode(str, Enum):
    LIVE = "LIVE"
    DEGRADED = "DEGRADED"
    MOCK_ONLY = "MOCK_ONLY"


class CoverageLine(str, Enum):
    FLIGHT_DELAY = "FLIGHT_DELAY"


class TripIntent(BaseModel):
    destination: str = Field(min_length=1)
    depart_at: str = Field(min_length=1)
    return_at: str = Field(min_length=1)
    flight_number: str = Field(min_length=1)
    traveler_count: int = Field(gt=0)
    budget_usdc: float = Field(gt=0)
    concerns: str = Field(min_length=1)


class BudgetAuthorization(BaseModel):
    policy_draft_id: str = Field(min_length=1)
    max_budget_usdc: float = Field(gt=0)
    search_fee_cap_usdc: float = Field(gt=0)
    idempotency_key: str = Field(min_length=1)
    wallet_address: str = Field(min_length=1)


class PolicyRecommendation(BaseModel):
    product_line: CoverageLine = CoverageLine.FLIGHT_DELAY
    policy_name: str = Field(min_length=1)
    premium_usdc: float = Field(gt=0)
    payout_usdc: float = Field(gt=0)
    delay_trigger_minutes: int = Field(gt=0)
    coverage_start: str = Field(min_length=1)
    coverage_end: str = Field(min_length=1)
    risk_tier: str = Field(min_length=1)
    pool_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PolicyRecord(BaseModel):
    product_line: CoverageLine = CoverageLine.FLIGHT_DELAY
    policy_id: str = Field(min_length=1)
    customer_wallet: str = Field(min_length=1)
    budget_locked_usdc: float = Field(ge=0)
    research_fee_usdc: float = Field(ge=0)
    premium_usdc: float = Field(ge=0)
    payout_usdc: float = Field(ge=0)
    delay_threshold_minutes: int = Field(gt=0)
    policy_start: str = Field(min_length=1)
    policy_end: str = Field(min_length=1)
    flight_hash: str = Field(min_length=1)
    recommendation_hash: str = Field(min_length=1)
    x402_reference: str = Field(min_length=1)
    risk_tier: str = Field(min_length=1)
    pool_id: str = Field(min_length=1)
    status: str = Field(min_length=1)


class PolicyWriteRequest(BaseModel):
    policy: PolicyRecord
    budget_authorization_key: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class OracleResolution(BaseModel):
    policy_id: str = Field(min_length=1)
    flight_hash: str = Field(min_length=1)
    arrived_on_time: bool
    delay_minutes: int = Field(ge=0)
    observed_at: str = Field(min_length=1)
    resolver_address: str = Field(min_length=1)
