"""In-memory mock for broker wallet, policy drafts, and knowledge service (hackathon demo).

Real TrustLayer will move this logic behind FastAPI + Circle + x402 + contracts.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.services.pricing import quote_payout_usdc, quote_premium_usdc
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
    #: Set true after successful `policy_research` (ideas.md: KB before budget lock).
    policy_research_completed: bool = False

    def mark_policy_research_done(self) -> None:
        self.policy_research_completed = True

    def _resolve_draft_id(self, draft_id: str) -> str:
        """Map a requested id to a real draft key.

        The LLM often hallucinates placeholders (e.g. ``draft-id-1``) because chat
        transcripts omit tool JSON. If there is exactly one draft in the session,
        use it; otherwise the caller must pass the exact ``policy_draft_id`` from
        ``prepare_budget_authorization``.
        """
        key = (draft_id or "").strip()
        if key in self.drafts:
            return key
        if not self.drafts:
            raise ValueError(
                f"Unknown policy_draft_id: {draft_id!r} (no drafts in session; "
                "call prepare_budget_authorization first)."
            )
        if len(self.drafts) == 1:
            return next(iter(self.drafts.keys()))
        known = ", ".join(sorted(self.drafts.keys()))
        raise ValueError(
            f"Unknown policy_draft_id: {draft_id!r}. Known drafts: {known}. "
            "Copy policy_draft_id exactly from the prepare_budget_authorization tool output."
        )

    def active_draft_context_block(self) -> str | None:
        """Text to inject into the user message so the model sees real draft ids.

        Streamlit/voice only pass human and assistant *text* to the model, not prior
        tool results — without this, the model invents ``draft-id-1`` style placeholders.
        """
        if not self.drafts:
            return None
        if len(self.drafts) == 1:
            d = next(iter(self.drafts.values()))
            return (
                "[TrustLayer session — active policy draft; use this id in tools verbatim]\n"
                f"policy_draft_id: {d.draft_id}\n"
                f"draft_status: {d.status.value}\n"
                "Do not invent ids (never use draft-id-1 or placeholders)."
            )
        lines = "\n".join(
            f"- {d.draft_id} (status={d.status.value})" for d in sorted(self.drafts.values(), key=lambda x: x.draft_id)
        )
        return (
            "[TrustLayer session — multiple policy drafts; pick the id that matches the current step]\n"
            f"{lines}\n"
            "Copy a policy_draft_id exactly from this list."
        )

    def _require_draft(self, draft_id: str) -> PolicyDraft:
        resolved = self._resolve_draft_id(draft_id)
        return self.drafts[resolved]

    def research_allowance_usdc(self, max_budget_usdc: float) -> float:
        """Same bands as `backend.services.receipts.research_fee_usdc` (single source of truth)."""
        return research_fee_usdc(max_budget_usdc)

    def prepare_budget_authorization(self, max_budget_usdc: float, trip_summary: str) -> PolicyDraft:
        if max_budget_usdc <= 0:
            raise ValueError("max_budget_usdc must be positive")
        if not trip_summary.strip():
            raise ValueError("trip_summary must be non-empty")
        if not self.policy_research_completed:
            raise ValueError(
                "TrustLayer workflow (ideas.md): call policy_research(trip_digest) first with the full trip "
                "(airlines, EU legs, layovers, destinations, fears) so KB `flight_attributes.md` is consulted "
                "before prepare_budget_authorization."
            )
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
        if d.status == DraftStatus.BUDGET_PREPARED:
            if not customer_confirms_demo_terms:
                d.status = DraftStatus.REJECTED
                return d
            d.status = DraftStatus.AUTHORIZED
            return d
        # Demo resilience: the LLM often re-calls confirm after coalescing steps
        # (pay_knowledge_service / get_policy_recommendation) advanced the draft.
        if d.status in (
            DraftStatus.AUTHORIZED,
            DraftStatus.RESEARCH_PAID,
            DraftStatus.RECOMMENDED,
            DraftStatus.PURCHASED,
        ):
            return d
        if d.status == DraftStatus.REJECTED:
            raise ValueError(f"Draft already rejected (status={d.status})")
        raise ValueError(f"Draft not awaiting confirmation (status={d.status})")

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
        """Debit the research/knowledge fee (mock). Invoked by the ``pay_knowledge_research_fee`` tool."""
        d = self._require_draft(draft_id)
        # Demo resilience: the LLM often obtains a spoken "yes" but skips
        # ``confirm_budget_authorization`` before ``pay_knowledge_research_fee``.
        # ``pay_knowledge_research_fee`` only runs after ``customer_confirms_research_fee=True``,
        # so treating BUDGET_PREPARED as authorized here matches traveler intent.
        if d.status == DraftStatus.BUDGET_PREPARED:
            d.status = DraftStatus.AUTHORIZED
        elif d.status != DraftStatus.AUTHORIZED:
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
        # Demo resilience: the LLM often obtains buy-in in chat but skips
        # ``pay_knowledge_research_fee`` before ``get_policy_recommendation``.
        if d.status in (DraftStatus.BUDGET_PREPARED, DraftStatus.AUTHORIZED):
            self.pay_knowledge_service(draft_id)
            d = self._require_draft(draft_id)
        if d.status != DraftStatus.RESEARCH_PAID:
            raise ValueError("Pay the knowledge service before requesting a recommendation.")
        # Deterministic micro-premium from budget (do not let the LLM invent numbers)
        premium = quote_premium_usdc(d.max_budget_usdc, d.research_fee_usdc)
        payout = quote_payout_usdc(d.max_budget_usdc)
        rec = {
            "policyName": "TrustLayer Flight Bundle (delay + cancellation)",
            "premiumUsdc": round(premium, 2),
            "payoutUsdc": payout,
            "delayTriggerMinutes": 180,
            "cancellationBenefitUsdc": round(min(200.0, payout * 0.5), 2),
            "coveredRisks": ["flight_delay", "flight_cancellation", "significant_disruption"],
            "riskTier": "LOW",
            "poolId": "POOL-LOW-01",
            "reason": (
                "Multi-peril flight bundle within authorized budget: delay cash benefit after trigger, "
                "cancellation benefit as listed, plus disruption guidance per TrustLayer mock catalogue."
            ),
            "tripDetailsEcho": trip_details.strip()[:500],
        }
        d.recommendation = rec
        d.status = DraftStatus.RECOMMENDED
        return rec

    def purchase_policy(self, draft_id: str) -> dict[str, Any]:
        d = self._require_draft(draft_id)
        # Demo resilience: the LLM often obtains buy-in in chat but skips
        # ``get_policy_recommendation`` before ``purchase_policy``.
        if d.status == DraftStatus.RESEARCH_PAID:
            self.get_policy_recommendation(draft_id, d.trip_summary)
            d = self._require_draft(draft_id)
        if d.status != DraftStatus.RECOMMENDED or not d.recommendation:
            raise ValueError(
                "No recommendation to purchase for this draft. "
                "Call get_policy_recommendation after the research fee is paid, "
                f"then purchase once the traveler accepts (current status={d.status.value})."
            )
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
        key = (policy_id or "").strip()
        for d in self.drafts.values():
            if d.policy_id and d.policy_id == key:
                return {
                    "policy_id": d.policy_id,
                    "policy_draft_id": d.draft_id,
                    "status": d.status.value,
                    "recommendation": d.recommendation,
                    "x402_receipt": d.x402_receipt,
                }
        # Demo resilience: the LLM often passes policy_draft_id (draft-...) here.
        d = self._require_draft(key)
        return {
            "policy_id": d.policy_id,
            "policy_draft_id": d.draft_id,
            "status": d.status.value,
            "recommendation": d.recommendation,
            "x402_receipt": d.x402_receipt,
        }

    def snapshot_json(self) -> str:
        """Debug helper."""
        return json.dumps(
            {
                "session_customer_id": self.session_customer_id,
                "policy_research_completed": self.policy_research_completed,
                "broker_wallet_usdc": self.broker_wallet_usdc,
                "drafts": {k: {"status": v.status.value, "max": v.max_budget_usdc} for k, v in self.drafts.items()},
            },
            indent=2,
        )
