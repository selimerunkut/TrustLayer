"""LangChain `@tool` definitions for the CoverPilot broker (mock backend).

Aligned with `ideas.md` tool names. Deterministic money/policy transitions live in
`mock_backend.py`; the LLM only selects tools and explains structured results.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from coverpilot_conversation.customer_directory import resolve_customer

if TYPE_CHECKING:
    from coverpilot_conversation.mock_backend import MockBrokerBackend


def build_broker_tools(backend: MockBrokerBackend) -> list:
    """Return a fresh tool list bound to `backend` (one backend per user session)."""

    @tool
    def lookup_customer_profile(name_email_or_handle: str) -> str:
        """TrustLayer CRM: resolve the traveler before asking for identity.

        **Call with empty string `""` immediately** when the user states trip or flight
        insurance intent but has not given a name—this loads the **session / kiosk**
        customer (e.g. returning Vasiliy). Do not ask for name or email first.

        If they gave a name, email, or handle in their message, pass that string instead.

        Args:
            name_email_or_handle: Customer identifier, or "" for session default.
        """
        out = resolve_customer(
            name_email_or_handle,
            session_default_customer_id=backend.session_customer_id,
        )
        return json.dumps(out)

    @tool
    def policy_research(trip_digest: str) -> str:
        """TrustLayer internal KB consult before any budget lock (ideas.md journey).

        Run after you have enough trip detail (airlines, EU vs long-haul legs, layovers, destinations,
        delay/cancellation fears). Loads static ``KB/flight_attributes.md`` and returns excerpts,
        ``mock_subtool_trace`` (mocked pipeline steps), and narration hints. **Mandatory** before
        ``prepare_budget_authorization``—the backend rejects budget prep without this.

        Ground EU261 / South-America / connection explanations in the returned ``excerpts`` and
        ``verbatim_kb_quotes`` only; do not invent regulation.

        Args:
            trip_digest: Full trip narrative in one string (e.g. Ryanair to London, 3h layover, onward to Bogotá).
        """
        from coverpilot_conversation.kb_policy_research import run_policy_research

        payload = run_policy_research(trip_digest)
        backend.mark_policy_research_done()
        return json.dumps(payload, ensure_ascii=False)

    @tool
    def get_wallet_balance() -> str:
        """Return the broker's current mock USDC wallet balance.

        Use before paying for knowledge services to ensure sufficient demo funds.
        """
        return json.dumps({"broker_wallet_usdc": round(backend.broker_wallet_usdc, 2)})

    @tool
    def prepare_budget_authorization(max_budget_usdc: float, trip_summary: str) -> str:
        """Create a policy draft and compute the research fee from the approved budget bands.

        Call this after you have a clear trip summary and a numeric max budget in USDC.
        This does NOT spend funds yet. Next step is `confirm_budget_authorization`.

        Args:
            max_budget_usdc: Customer's maximum spend cap in USDC for this quote flow.
            trip_summary: Short plain-language summary of destination, dates, flight/route, travelers, concerns
                (delays, cancellations, disruptions, etc.).
        """
        d = backend.prepare_budget_authorization(max_budget_usdc, trip_summary)
        return json.dumps(
            {
                "policy_draft_id": d.draft_id,
                "max_budget_usdc": d.max_budget_usdc,
                "research_allowance_usdc": d.research_fee_usdc,
                "trip_summary": d.trip_summary,
                "next_step": "Ask the traveler to confirm the fee disclosure, then call confirm_budget_authorization.",
            }
        )

    @tool
    def confirm_budget_authorization(policy_draft_id: str, customer_confirms_demo_terms: bool) -> str:
        """Confirm (or decline) locking the authorized budget for the demo flow.

        Args:
            policy_draft_id: Draft id returned by prepare_budget_authorization.
            customer_confirms_demo_terms: Must be True to proceed; False cancels the draft.
        """
        d = backend.confirm_budget_authorization(policy_draft_id, customer_confirms_demo_terms)
        return json.dumps(
            {
                "policy_draft_id": d.draft_id,
                "status": d.status.value,
                "authorized": d.status.value == "authorized",
            }
        )

    @tool
    def get_research_allowance(policy_draft_id: str) -> str:
        """Show the research allowance for an authorized draft (no payment).

        Args:
            policy_draft_id: Active draft id.
        """
        info = backend.get_research_allowance(policy_draft_id)
        return json.dumps(info)

    @tool
    def pay_knowledge_service(policy_draft_id: str) -> str:
        """Pay the mocked x402 knowledge service using broker wallet funds (demo).

        Args:
            policy_draft_id: Authorized draft id.
        """
        receipt = backend.pay_knowledge_service(policy_draft_id)
        return json.dumps(receipt)

    @tool
    def get_policy_recommendation(policy_draft_id: str, trip_details: str) -> str:
        """Fetch the structured TrustLayer flight recommendation after research is paid.

        Returns delay, cancellation, and bundled risk fields from the mock catalogue.
        The model must NOT invent premiums or benefits; explain exactly what the JSON contains.

        Args:
            policy_draft_id: Draft id with research already paid.
            trip_details: Concise recap of trip constraints for the audit trail (can mirror trip_summary).
        """
        rec = backend.get_policy_recommendation(policy_draft_id, trip_details)
        return json.dumps(rec)

    @tool
    def purchase_policy(policy_draft_id: str) -> str:
        """Purchase the recommended policy for this draft (mock premium debit).

        Args:
            policy_draft_id: Draft in recommended state.
        """
        out = backend.purchase_policy(policy_draft_id)
        return json.dumps(out)

    @tool
    def reject_policy(policy_draft_id: str) -> str:
        """Decline the recommendation / cancel the draft (mock).

        Args:
            policy_draft_id: Draft id to close.
        """
        out = backend.reject_policy(policy_draft_id)
        return json.dumps(out)

    @tool
    def get_policy_status(policy_id: str) -> str:
        """Look up status for a purchased policy id.

        Args:
            policy_id: Value returned by purchase_policy.
        """
        out = backend.get_policy_status(policy_id)
        return json.dumps(out)

    return [
        lookup_customer_profile,
        policy_research,
        get_wallet_balance,
        prepare_budget_authorization,
        confirm_budget_authorization,
        get_research_allowance,
        pay_knowledge_service,
        get_policy_recommendation,
        purchase_policy,
        reject_policy,
        get_policy_status,
    ]
