"""LangChain `@tool` definitions for the CoverPilot broker (mock backend).

Aligned with `ideas.md` tool names. Deterministic money/policy transitions live in
`mock_backend.py`; the LLM only selects tools and explains structured results.

`purchase_policy` writes the policy on-chain **only** after the traveler has
explicitly agreed to **buy the insurance** (not the research fee). The small
research/knowledge fee uses `pay_knowledge_research_fee` first; a future version
may add a separate on-chain nanopayment for that fee only.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from langchain_core.tools import tool

from coverpilot_conversation.customer_directory import resolve_customer

if TYPE_CHECKING:
    from coverpilot_conversation.mock_backend import MockBrokerBackend


def _try_build_chain_client():
    """Return an InsuranceManagerClient if all env vars are present, else None."""
    required = (
        "BASE_SEPOLIA_RPC_URL",
        "BASE_SEPOLIA_CONTRACT_ADDRESS",
        "BASE_SEPOLIA_DEPLOYER_PRIVATE_KEY",
    )
    if not all(os.environ.get(k, "").strip() for k in required):
        return None
    try:
        from contracts.insurance_manager_client import InsuranceManagerClient
        return InsuranceManagerClient.from_env()
    except Exception:
        return None


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

        **Session flag:** A successful call sets an internal "KB consulted" flag. Without it,
        ``prepare_budget_authorization`` raises ``ValueError`` — explaining regulations in chat
        does **not** set this flag. You must invoke this tool.

        Run as soon as the trip is identifiable (cities, legs, layovers, fears). If airline names
        or dates are missing, still call with the best narrative you can build from the thread, then
        ask one follow-up in natural language — **do not** skip this tool to go straight to budget prep.

        Loads ``KB/flight_attributes.md`` and returns excerpts, ``mock_subtool_trace``, and narration hints.

        When the user says yes to budget or research fees but you never called this tool earlier,
        call it **in the same step** before ``prepare_budget_authorization``, with a ``trip_digest``
        that concatenates the whole itinerary from the conversation.

        Ground EU261 / South-America / connection explanations in the returned ``excerpts`` and
        ``verbatim_kb_quotes`` only; do not invent regulation.

        Args:
            trip_digest: One string: airline(s) if known, departure/arrival cities and countries,
                connection airports and layover length, final destination, season or dates if known,
                delay/cancellation/missed-connection fears, traveler count, agreed budget if stated.
                Example: "Sofia to Frankfurt 3h layover then to Santiago Chile, delay worries, solo, ~45 USDC cap".
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

        **Prerequisite:** ``policy_research(trip_digest)`` must have completed successfully in this
        session first; otherwise the backend raises ``ValueError`` (TrustLayer workflow). If the user
        just agreed to proceed and you only talked about rules in prose, call ``policy_research`` now
        with a full digest from the thread, then call this tool.

        Call after a clear numeric max budget in USDC and a short trip summary. Does NOT spend funds yet.
        Next step is ``confirm_budget_authorization``.

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
                "next_step": "Call confirm_budget_authorization(customer_confirms_demo_terms=True) after they agree to the cap and fee. Then pay_knowledge_research_fee(customer_confirms_research_fee=True) after they confirm the research fee — never pay while status is still budget_prepared unless you are coalescing both consents in one step (confirm then pay).",
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
    def pay_knowledge_research_fee(
        policy_draft_id: str,
        customer_confirms_research_fee: bool,
    ) -> str:
        """Pay **only** the knowledge/research fee so TrustLayer can fetch the best plan.

        This is **not** the insurance premium. It unlocks ``get_policy_recommendation``.
        A dedicated on-chain "knowledge transaction" for the small fee (e.g. ~0.45 USDC)
        will be wired in a later tool; for now this debits the mock broker wallet only.

        Call **only after** the traveler has explicitly confirmed they accept the
        disclosed research fee (e.g. they said yes to paying for the lookup).

        **Prerequisite:** The draft should be ``authorized`` after ``confirm_budget_authorization``.
        If the model skipped that tool but the user clearly assented in chat, you may still call
        this with ``customer_confirms_research_fee=True`` — the backend will authorize a
        ``budget_prepared`` draft when taking payment (demo safety net).

        Args:
            policy_draft_id: Draft id from ``prepare_budget_authorization`` (may still be awaiting confirm).
            customer_confirms_research_fee: Must be True — set only after explicit user consent to the research fee.
        """
        if not customer_confirms_research_fee:
            return json.dumps(
                {
                    "error": "research_fee_not_confirmed",
                    "message": (
                        "Do not charge the research fee until the traveler explicitly confirms "
                        "they accept the disclosed knowledge/research fee (separate from buying insurance)."
                    ),
                    "policy_draft_id": policy_draft_id,
                }
            )
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
    def purchase_policy(
        policy_draft_id: str,
        customer_confirms_insurance_purchase: bool,
    ) -> str:
        """Purchase the **insurance** product: debit the mock premium and write the policy
        on-chain (Base Sepolia) when env is configured.

        **Only** call after ``get_policy_recommendation`` and **only** when the traveler
        has **explicitly** agreed to buy the presented plan (e.g. clear yes to the premium
        and coverage). The research fee was already handled by ``pay_knowledge_research_fee``;
        this step is strictly the insurance purchase + policy record transaction.

        After success, share ``onchain.block_explorer_url`` in chat so they can view the tx.
        If the chain write fails, mock purchase may still succeed; ``onchain.error`` explains.

        Args:
            policy_draft_id: Draft in recommended state.
            customer_confirms_insurance_purchase: Must be True — only after explicit consent to buy insurance.
        """
        if not customer_confirms_insurance_purchase:
            return json.dumps(
                {
                    "error": "insurance_purchase_not_confirmed",
                    "message": (
                        "Do not purchase insurance until the traveler explicitly confirms they want "
                        "to buy the presented policy (premium, payout, trigger). "
                        "Research fee consent alone is not enough."
                    ),
                    "policy_draft_id": policy_draft_id,
                }
            )
        # Grab draft before state transition so we have all fields for the onchain call.
        draft = backend.drafts.get(policy_draft_id)
        out = backend.purchase_policy(policy_draft_id)

        onchain: dict = {"attempted": False}

        if draft and out.get("policy_id"):
            client = _try_build_chain_client()
            if client:
                onchain["attempted"] = True
                try:
                    rec = draft.recommendation or {}
                    customer_wallet = os.environ.get(
                        "CIRCLE_WALLET_ID",
                        os.environ.get("BASE_SEPOLIA_DEPLOYER_ADDRESS", ""),
                    ).strip()

                    result = client.purchase_policy(
                        policy_id=out["policy_id"],
                        customer_wallet=customer_wallet,
                        budget_locked_usdc=draft.max_budget_usdc,
                        research_fee_usdc=draft.research_fee_usdc,
                        premium_usdc=float(rec.get("premiumUsdc", 0)),
                        payout_usdc=float(rec.get("payoutUsdc", 0)),
                        delay_threshold_minutes=int(rec.get("delayTriggerMinutes", 180)),
                        flight_descriptor=draft.trip_summary,
                        recommendation_json=json.dumps(rec, ensure_ascii=False),
                        x402_receipt=draft.x402_receipt or "no-x402-receipt",
                    )
                    onchain.update(result)
                except Exception as exc:
                    onchain["error"] = str(exc)
            else:
                onchain["skipped_reason"] = (
                    "BASE_SEPOLIA_RPC_URL / CONTRACT_ADDRESS / DEPLOYER_PRIVATE_KEY not all set."
                )

        out["onchain"] = onchain
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
        """Look up status for a purchased policy id (mock state + on-chain record).

        Args:
            policy_id: Value returned by purchase_policy.
        """
        out = backend.get_policy_status(policy_id)
        return json.dumps(out)

    @tool
    def get_policy_onchain(policy_id: str) -> str:
        """Read the policy record directly from the InsuranceManager contract on Base Sepolia.

        Use this to show the traveler live on-chain proof of their policy — status,
        amounts, and a link to the contract on Basescan. Call after purchase_policy succeeds.

        Args:
            policy_id: Policy id returned by purchase_policy (e.g. ``pol-abc123``).
        """
        client = _try_build_chain_client()
        if not client:
            return json.dumps({
                "error": "Chain client not available — BASE_SEPOLIA env vars not set.",
                "policy_id": policy_id,
            })
        try:
            result = client.get_policy(policy_id)
            return json.dumps(result)
        except Exception as exc:
            return json.dumps({"error": str(exc), "policy_id": policy_id})

    return [
        lookup_customer_profile,
        policy_research,
        get_wallet_balance,
        prepare_budget_authorization,
        confirm_budget_authorization,
        get_research_allowance,
        pay_knowledge_research_fee,
        get_policy_recommendation,
        purchase_policy,
        reject_policy,
        get_policy_status,
        get_policy_onchain,
    ]
