"""TrustLayer Streamlit shell — Betty (LangChain broker).

Pool selection and technical details are modeled in receipt helpers below for
redaction tests; the live UI is chat-first. not legally valid insurance wording
is centralized in ``build_non_insurance_disclaimer`` for compliance reuse.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from langchain_core.messages import AIMessage

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from backend.schemas import PolicyRecommendation
from backend.services.receipts import research_fee_usdc
from coverpilot_conversation.agent import build_broker_agent
from coverpilot_conversation.customer_directory import (
    session_crm_context_block,
    user_message_suggests_travel_planning,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CustomerFacingReceipt:
    headline: str
    summary_lines: tuple[str, ...]
    technical_details: tuple[tuple[str, str], ...]
    pool_selection_visible: bool = False
    simulated: bool = False
    provenance: str = ""


def build_non_insurance_disclaimer() -> str:
    return (
        "NOT LEGALLY VALID INSURANCE: this is a demo only, not a legally binding insurance product, "
        "and it may use mocked or degraded dependencies."
    )


def build_customer_facing_receipt(
    recommendation: PolicyRecommendation,
    *,
    simulated: bool = False,
    provenance: str = "",
) -> CustomerFacingReceipt:
    return CustomerFacingReceipt(
        headline=f"{recommendation.policy_name} — {recommendation.premium_usdc:.2f} USDC premium",
        summary_lines=(
            f"Payout if your flight is delayed {recommendation.delay_trigger_minutes} minutes or more: "
            f"{recommendation.payout_usdc:.2f} USDC",
            f"Coverage window: {recommendation.coverage_start} to {recommendation.coverage_end}",
            f"Why this fits: {recommendation.reason}",
        ),
        technical_details=(
            ("Coverage pool", recommendation.pool_id),
            ("Wallet", "hidden in customer view"),
            ("x402 reference", "hidden in customer view"),
            ("Recommendation hash", "hidden in customer view"),
        ),
        simulated=simulated,
        provenance=provenance,
    )


def build_fallback_banner(*, simulated: bool, provenance: str) -> str | None:
    if not simulated and not provenance:
        return None
    details = []
    if simulated:
        details.append("simulated")
    if provenance:
        details.append(provenance)
    return f"Fallback mode: {' / '.join(details)}"


def build_budget_quote_copy(max_budget_usdc: float) -> tuple[str, str]:
    fee_usdc = research_fee_usdc(max_budget_usdc)
    return (
        f"Maximum approved budget: {max_budget_usdc:.2f} USDC",
        f"Deterministic research-fee quote: {fee_usdc:.2f} USDC",
    )


def _extract_assistant_text(result: dict) -> str:
    """Last human-visible AIMessage content (handles str or content blocks)."""
    for m in reversed(result.get("messages", [])):
        if isinstance(m, AIMessage):
            c = m.content
            if isinstance(c, str) and c.strip():
                return c.strip()
            if isinstance(c, list):
                parts: list[str] = []
                for block in c:
                    if isinstance(block, str):
                        parts.append(block)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                text = "\n".join(parts).strip()
                if text:
                    return text
    return (
        "(No assistant text in this turn — the model may have only issued tool calls. "
        "Enable tracing or check logs.)"
    )


def build_ui() -> None:
    st.set_page_config(page_title="TrustLayer — Betty, insurance broker", page_icon="✈️")
    st.title("TrustLayer — Betty, insurance broker")

    if not os.getenv("OPENAI_API_KEY"):
        st.caption("Add `OPENAI_API_KEY` to `.env` to enable replies.")

    if "crm_customer_id" not in st.session_state:
        st.session_state.crm_customer_id = "vasiliy"
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "agent_bundle" not in st.session_state:
        agent, backend = build_broker_agent()
        st.session_state.agent_bundle = (agent, backend)
    if "chat_lines" not in st.session_state:
        st.session_state.chat_lines = []

    agent, backend = st.session_state.agent_bundle

    with st.sidebar:
        if st.button("New chat", use_container_width=True):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.chat_lines = []
            agent, backend = build_broker_agent()
            backend.session_customer_id = st.session_state.crm_customer_id
            st.session_state.agent_bundle = (agent, backend)
            st.rerun()
        crm = st.text_input(
            "CRM customer id",
            value=st.session_state.crm_customer_id,
            help='lookup_customer_profile("") uses this id.',
        )
        st.session_state.crm_customer_id = (crm or "vasiliy").strip().lower()
        backend.session_customer_id = st.session_state.crm_customer_id
        with st.expander("Debug", expanded=False):
            st.caption(st.session_state.thread_id)
            st.code(backend.snapshot_json(), language="json")

    for role, text in st.session_state.chat_lines:
        with st.chat_message(role):
            st.markdown(text)

    config = {
        "configurable": {"thread_id": st.session_state.thread_id},
        "recursion_limit": int(os.getenv("COVERPILOT_RECURSION_LIMIT", "25")),
    }

    user_text = st.chat_input("Message Betty…")
    if user_text:
        st.session_state.chat_lines.append(("user", user_text))
        with st.spinner("Betty is thinking…"):
            payload = user_text
            if user_message_suggests_travel_planning(user_text):
                crm = session_crm_context_block(session_default_customer_id=backend.session_customer_id)
                if crm:
                    payload = f"{crm}\n\n---\nTraveler message:\n{user_text}"
            result = agent.invoke(
                {"messages": [{"role": "user", "content": payload}]},
                config=config,
            )
        reply = _extract_assistant_text(result)
        st.session_state.chat_lines.append(("assistant", reply))
        st.rerun()


if __name__ == "__main__":
    build_ui()
