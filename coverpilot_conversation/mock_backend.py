"""In-memory mock for broker wallet, policy drafts, and knowledge service (hackathon demo).

Real CoverPilot will move this logic behind FastAPI + Circle + x402 + contracts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.services.receipts import research_fee_usdc


class DraftStatus(str, Enum):
    BUDGET_PREPARED = "budget_prepared"
    AUTHORIZED = "authorized"
    RESEARCH_PAID = "research_paid"
    RECOMMENDED = "recommended"
    PURCHASED = "purchased"
    REJECTED = "rejected"


@dataclass
class PolicyDraft:
    draft_id: str
    trip_summary: str
    max_budget_usdc: float
    status: DraftStatus = DraftStatus.BUDGET_PREPARED
    research_fee_usdc: float = 0.0
    x402_receipt: str | None = None
    recommendation: dict[str, Any] | None = None
    policy_id: str | None = None


@dataclass
class MockBrokerBackend:
    """Mutable demo state scoped to one Streamlit session / CLI process."""

    broker_wallet_usdc: float = 10_000.0
    drafts: dict[str, PolicyDraft] = field(default_factory=dict)
    #: When `lookup_customer_profile` is called with an empty hint, resolve this CRM id (demo: Vasiliy).
    session_customer_id: str = "vasiliy"

    def _require_draft(self, draft_id: str) -> PolicyDraft:
        d = self.drafts.get(draft_id)
        if not d:
            raise ValueError(f"Unknown policy_draft_id: {draft_id}")
        return d

    def research_allowance_usdc(self, max_budget_usdc: float) -> float:
        """Same bands as `backend.services.receipts.research_fee_usdc` (single source of truth)."""
        return research_fee_usdc(max_budget_usdc)

    def prepare_budget_authorization(self, max_budget_usdc: float, trip_summary: str) -> PolicyDraft:
        if max_budget_usdc <= 0:
            raise ValueError("max_budget_usdc must be positive")
        if not trip_summary.strip():
            raise ValueError("trip_summary must be non-empty")
        draft_id = f"draft-{uuid.uuid4().hex[:10]}"
        fee = self.research_allowance_usdc(max_budget_usdc)
        d = PolicyDraft(
            draft_id=draft_id,
            trip_summary=trip_summary.strip(),
            max_budget_usdc=float(max_budget_usdc),
            status=DraftStatus.BUDGET_PREPARED,
            research_fee_usdc=fee,
        )
        self.drafts[draft_id] = d
        return d

    def confirm_budget_authorization(self, draft_id: str, customer_confirms_demo_terms: bool) -> PolicyDraft:
        d = self._require_draft(draft_id)
        if d.status != DraftStatus.BUDGET_PREPARED:
            raise ValueError(f"Draft not awaiting confirmation (status={d.status})")
        if not customer_confirms_demo_terms:
            d.status = DraftStatus.REJECTED
            return d
        d.status = DraftStatus.AUTHORIZED
        return d

    def get_research_allowance(self, draft_id: str) -> dict[str, Any]:
        d = self._require_draft(draft_id)
        if d.status != DraftStatus.AUTHORIZED:
            raise ValueError("Budget must be authorized before research allowance is available.")
        return {
            "policy_draft_id": d.draft_id,
            "max_budget_usdc": d.max_budget_usdc,
            "research_allowance_usdc": d.research_fee_usdc,
            "disclosure": (
                "Demo: up to the research allowance may be spent on the knowledge lookup "
                "even if you decline the final policy."
            ),
        }

    def pay_knowledge_service(self, draft_id: str) -> dict[str, Any]:
        d = self._require_draft(draft_id)
        if d.status != DraftStatus.AUTHORIZED:
            raise ValueError("Cannot pay knowledge service unless budget is authorized.")
        fee = d.research_fee_usdc
        if self.broker_wallet_usdc < fee:
            raise ValueError("Insufficient broker wallet balance for research fee (mock).")
        self.broker_wallet_usdc -= fee
        d.status = DraftStatus.RESEARCH_PAID
        d.x402_receipt = f"x402-mock-receipt-{uuid.uuid4().hex[:12]}"
        return {
            "policy_draft_id": d.draft_id,
            "paid_usdc": fee,
            "x402_receipt": d.x402_receipt,
            "broker_wallet_after_usdc": round(self.broker_wallet_usdc, 2),
        }

    def get_policy_recommendation(self, draft_id: str, trip_details: str) -> dict[str, Any]:
        d = self._require_draft(draft_id)
        if d.status != DraftStatus.RESEARCH_PAID:
            raise ValueError("Pay the knowledge service before requesting a recommendation.")
        # Deterministic-ish mock premium from budget (do not let the LLM invent numbers)
        premium = max(10.0, min(d.max_budget_usdc * 0.42, d.max_budget_usdc - d.research_fee_usdc))
        payout = 300.0 if d.max_budget_usdc >= 80 else 150.0
        rec = {
            "policyName": "Long-Haul Delay Protect (demo)",
            "premiumUsdc": round(premium, 2),
            "payoutUsdc": payout,
            "delayTriggerMinutes": 180,
            "riskTier": "LOW",
            "poolId": "POOL-LOW-01",
            "reason": "Mock underwriting: long-haul delay cover within authorized budget.",
            "tripDetailsEcho": trip_details.strip()[:500],
        }
        d.recommendation = rec
        d.status = DraftStatus.RECOMMENDED
        return rec

    def purchase_policy(self, draft_id: str) -> dict[str, Any]:
        d = self._require_draft(draft_id)
        if d.status != DraftStatus.RECOMMENDED or not d.recommendation:
            raise ValueError("No recommendation to purchase for this draft.")
        premium = float(d.recommendation["premiumUsdc"])
        if premium + d.research_fee_usdc > d.max_budget_usdc + 1e-6:
            raise ValueError("Premium exceeds authorized maximum budget (mock check).")
        if self.broker_wallet_usdc < premium:
            raise ValueError("Insufficient broker wallet for premium (mock).")
        self.broker_wallet_usdc -= premium
        d.policy_id = f"pol-{uuid.uuid4().hex[:10]}"
        d.status = DraftStatus.PURCHASED
        return {
            "policy_id": d.policy_id,
            "premium_paid_usdc": premium,
            "policy_snapshot": d.recommendation,
            "broker_wallet_after_usdc": round(self.broker_wallet_usdc, 2),
        }

    def reject_policy(self, draft_id: str) -> dict[str, Any]:
        d = self._require_draft(draft_id)
        if d.status == DraftStatus.PURCHASED:
            raise ValueError("Policy already purchased; cannot reject.")
        if d.status == DraftStatus.REJECTED:
            raise ValueError("Draft already rejected.")
        already_paid_research = float(d.research_fee_usdc) if d.x402_receipt else 0.0
        d.status = DraftStatus.REJECTED
        return {
            "policy_draft_id": d.draft_id,
            "research_fee_already_paid_usdc": already_paid_research,
            "note": "Demo: unused customer budget would be returned via escrow (not simulated in this mock).",
        }

    def get_policy_status(self, policy_id: str) -> dict[str, Any]:
        for d in self.drafts.values():
            if d.policy_id == policy_id:
                return {
                    "policy_id": policy_id,
                    "status": d.status.value,
                    "recommendation": d.recommendation,
                    "x402_receipt": d.x402_receipt,
                }
        raise ValueError(f"Unknown policy_id: {policy_id}")

    def snapshot_json(self) -> str:
        """Debug helper."""
        return json.dumps(
            {
                "session_customer_id": self.session_customer_id,
                "broker_wallet_usdc": self.broker_wallet_usdc,
                "drafts": {k: {"status": v.status.value, "max": v.max_budget_usdc} for k, v in self.drafts.items()},
            },
            indent=2,
        )
