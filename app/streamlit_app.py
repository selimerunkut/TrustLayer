"""TrustLayer Streamlit shell — Betty (LangChain broker).

Pool selection and technical details are modeled in receipt helpers below for
redaction tests; the live UI is chat-first. not legally valid insurance wording
is centralized in ``build_non_insurance_disclaimer`` for compliance reuse.
"""

from __future__ import annotations

import base64
import html
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import httpx
import streamlit as st
import streamlit.components.v1 as components
from langchain_core.messages import AIMessage, HumanMessage

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

from coverpilot_conversation.message_extract import (
    extract_last_ai_text,
    format_assistant_reply_for_display,
)

logger = logging.getLogger(__name__)


def _betty_public_api_base() -> str:
    return os.getenv("BETTY_PUBLIC_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def _betty_internal_api_base() -> str:
    return os.getenv("BETTY_INTERNAL_API_BASE", _betty_public_api_base()).rstrip("/")


def _sync_voice_ui_transcript() -> None:
    """Pull voice turns recorded by the iframe API into this session's chat_lines."""
    tid = st.session_state.thread_id
    if st.session_state.get("_voice_ui_sync_tid") != tid:
        st.session_state["voice_ui_merged_count"] = 0
        st.session_state["_voice_ui_sync_tid"] = tid
    merged = int(st.session_state.get("voice_ui_merged_count", 0))
    base = _betty_internal_api_base()
    try:
        r = httpx.get(f"{base}/api/betty/voice-ui-transcript/{tid}", timeout=3.0)
        if r.status_code != 200:
            return
        turns = r.json().get("turns") or []
    except Exception:
        logger.debug("voice UI transcript sync failed (is the API running?)", exc_info=True)
        return
    for i in range(merged, len(turns)):
        item = turns[i]
        u = (item.get("user") or "").strip()
        a = (item.get("assistant") or "").strip()
        if u:
            st.session_state.chat_lines.append(("user", u, None))
        if a:
            st.session_state.chat_lines.append(("assistant", a, None))
    st.session_state["voice_ui_merged_count"] = len(turns)


@st.fragment(run_every=timedelta(seconds=1.25))
def _render_chat_messages_fragment() -> None:
    _sync_voice_ui_transcript()
    for role, text, reply_audio in st.session_state.chat_lines:
        with st.chat_message(role):
            st.markdown(text)
            if role == "assistant" and reply_audio:
                st.audio(reply_audio, format="audio/mpeg")


def _chat_bootstrap_for_voice() -> str:
    """Snip typed chat so the FastAPI voice broker can align with the same session."""
    lines: list[str] = []
    for item in st.session_state.get("chat_lines", []):
        if len(item) < 2:
            continue
        role, text = item[0], item[1]
        if role not in ("user", "assistant"):
            continue
        t = (text or "").strip()
        if not t:
            continue
        label = "USER" if role == "user" else "BETTY"
        lines.append(f"{label}: {t[:2000]}")
    out = "\n".join(lines).strip()
    return out[:6000]


def _voice_embed_html() -> str:
    path = Path(__file__).resolve().parent / "voice_embed.html"
    raw = path.read_text(encoding="utf-8")
    crm = st.session_state.crm_customer_id or "vasiliy"
    boot = _chat_bootstrap_for_voice()
    boot_b64 = base64.b64encode(boot.encode("utf-8")).decode("ascii") if boot else ""
    return (
        raw.replace("__BETTY_API_BASE__", _betty_public_api_base())
        .replace("__THREAD_ID__", st.session_state.thread_id)
        .replace("__CRM_ID__", html.escape(crm, quote=True))
        .replace("__BOOTSTRAP_B64__", boot_b64)
    )


def _normalize_chat_line(item: tuple) -> tuple[str, str, bytes | None]:
    """Support legacy 2-tuples (role, text) and current 3-tuples (role, text, mp3_or_none)."""
    if len(item) == 2:
        return (item[0], item[1], None)
    return (item[0], item[1], item[2])


def _maybe_synthesize_reply_audio(reply: str, *, voice_mode: bool) -> bytes | None:
    if not voice_mode:
        return None
    try:
        from backend.services.elevenlabs_voice import (
            elevenlabs_configured,
            synthesize_speech_mp3,
        )
    except ImportError:
        return None
    if not elevenlabs_configured():
        return None
    try:
        return synthesize_speech_mp3(reply)
    except Exception:
        logger.exception("ElevenLabs TTS failed; continuing without audio.")
        return None


def _messages_from_chat_lines_for_invoke() -> list[HumanMessage | AIMessage]:
    """Rebuild LangChain messages from the visible thread (typed + voice-synced)."""
    msgs: list[HumanMessage | AIMessage] = []
    for role, text, _ in st.session_state.chat_lines:
        t = (text or "").strip()
        if not t:
            continue
        if role == "user":
            msgs.append(HumanMessage(content=t))
        elif role == "assistant":
            msgs.append(AIMessage(content=t))
    return msgs


def _run_betty_turn(
    user_text: str,
    *,
    agent,
    backend,
    config: dict,
    voice_mode: bool,
) -> None:
    """Append user message, invoke broker, append assistant reply (optional MP3 for voice mode).

    Streamlit uses ``use_memory=False`` on the agent, so we pass the **full** transcript
    each turn. That keeps the model aligned with voice rows synced into ``chat_lines``.
    """
    st.session_state.chat_lines.append(("user", user_text, None))
    with st.spinner("Betty is thinking…"):
        msgs = _messages_from_chat_lines_for_invoke()
        if not msgs or not isinstance(msgs[-1], HumanMessage):
            st.session_state.chat_lines.pop()
            return
        if user_message_suggests_travel_planning(user_text):
            crm = session_crm_context_block(session_default_customer_id=backend.session_customer_id)
            if crm:
                msgs[-1] = HumanMessage(
                    content=f"{crm}\n\n---\nTraveler message:\n{user_text}",
                )
        draft_hint = backend.active_draft_context_block()
        if draft_hint:
            msgs[-1] = HumanMessage(
                content=f"{draft_hint}\n\n---\n{msgs[-1].content}",
            )
        result = agent.invoke({"messages": msgs}, config=config)
    reply = format_assistant_reply_for_display(extract_last_ai_text(result))
    audio = _maybe_synthesize_reply_audio(reply, voice_mode=voice_mode)
    st.session_state.chat_lines.append(("assistant", reply, audio))


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


def build_ui() -> None:
    st.set_page_config(
        page_title="Betty — TrustLayer",
        page_icon="✈️",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    st.title("Betty")
    st.caption("TrustLayer travel insurance broker — type a message or use Hold to speak for voice.")

    if not os.getenv("OPENAI_API_KEY"):
        st.caption("Add `OPENAI_API_KEY` to `.env` to enable replies.")

    if "crm_customer_id" not in st.session_state:
        st.session_state.crm_customer_id = "vasiliy"
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "agent_bundle" not in st.session_state:
        agent, backend = build_broker_agent(use_memory=False)
        st.session_state.agent_bundle = (agent, backend)
    if "chat_lines" not in st.session_state:
        st.session_state.chat_lines = []

    st.session_state.chat_lines = [_normalize_chat_line(x) for x in st.session_state.chat_lines]

    agent, backend = st.session_state.agent_bundle

    config = {
        "configurable": {"thread_id": st.session_state.thread_id},
        "recursion_limit": int(os.getenv("COVERPILOT_RECURSION_LIMIT", "25")),
    }

    with st.sidebar:
        if st.button("New chat", use_container_width=True):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.chat_lines = []
            st.session_state["voice_ui_merged_count"] = 0
            st.session_state["_voice_ui_sync_tid"] = st.session_state.thread_id
            agent, backend = build_broker_agent(use_memory=False)
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

    st.markdown(
        """
<style>
  div[data-testid="stChatMessage"] {
    max-height: none !important;
    overflow-y: visible !important;
  }
  div[data-testid="stChatMessage"] div[data-testid="stVerticalBlockBorderWrapper"] {
    max-height: none !important;
    overflow-y: visible !important;
  }
  .block-container {
    padding-bottom: 4rem !important;
  }
</style>
""",
        unsafe_allow_html=True,
    )

    _render_chat_messages_fragment()

    try:
        from backend.services.elevenlabs_voice import elevenlabs_configured
    except ImportError:
        elevenlabs_configured = lambda: False  # type: ignore[misc, assignment]
    if not elevenlabs_configured():
        st.caption("Optional: set `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in `.env` for spoken replies in the browser.")
    try:
        components.html(_voice_embed_html(), height=145, scrolling=False)
    except FileNotFoundError:
        st.error("Voice embed template missing (`app/voice_embed.html`).")

    user_text = st.chat_input("Message Betty…")
    if user_text:
        _run_betty_turn(
            user_text,
            agent=agent,
            backend=backend,
            config=config,
            voice_mode=False,
        )
        st.rerun()


if __name__ == "__main__":
    build_ui()
