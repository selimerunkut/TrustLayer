"""Streamlit shell for Betty (TrustLayer) — LangChain `create_agent` demo."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Allow `streamlit run streamlit_app.py` from this directory without installing a package.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

import streamlit as st
from langchain_core.messages import AIMessage

from coverpilot_conversation.agent import build_broker_agent


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
    return "(No assistant text in this turn — the model may have only issued tool calls. Check LangSmith or widen the UI.)"


def main() -> None:
    st.set_page_config(page_title="TrustLayer — Betty (demo broker)", page_icon="✈️")
    st.title("TrustLayer — Betty, insurance broker (demo)")
    st.caption(
        "LangChain 1.x `create_agent` + CRM lookup + mock policy tools. "
        "Set `OPENAI_API_KEY` (see `.env.example`)."
    )

    if not os.getenv("OPENAI_API_KEY"):
        st.warning(
            "Missing `OPENAI_API_KEY`. Export it in your shell before `streamlit run`, "
            "or use Streamlit secrets."
        )

    if "crm_customer_id" not in st.session_state:
        st.session_state.crm_customer_id = "vasiliy"

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "agent_bundle" not in st.session_state:
        agent, backend = build_broker_agent()
        st.session_state.agent_bundle = (agent, backend)
    if "chat_lines" not in st.session_state:
        st.session_state.chat_lines = []  # list[tuple[Literal["user","assistant"], str]]

    agent, backend = st.session_state.agent_bundle

    for role, text in st.session_state.chat_lines:
        with st.chat_message(role):
            st.markdown(text)

    with st.sidebar:
        st.subheader("Session")
        st.code(st.session_state.thread_id, language="text")
        crm = st.text_input(
            "CRM session customer id",
            value=st.session_state.crm_customer_id,
            help="Used when the agent calls lookup_customer_profile with an empty string. Demo default: vasiliy.",
        )
        st.session_state.crm_customer_id = (crm or "vasiliy").strip().lower()
        backend.session_customer_id = st.session_state.crm_customer_id

        if st.button("New conversation (new thread)"):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.chat_lines = []
            # Fresh agent + backend so mock wallet/drafts reset per conversation
            agent, backend = build_broker_agent()
            backend.session_customer_id = st.session_state.crm_customer_id
            st.session_state.agent_bundle = (agent, backend)
            st.rerun()
        st.subheader("Mock backend (debug)")
        st.code(backend.snapshot_json(), language="json")

    config = {
        "configurable": {"thread_id": st.session_state.thread_id},
        "recursion_limit": int(os.getenv("COVERPILOT_RECURSION_LIMIT", "25")),
    }

    user_text = st.chat_input("Describe your trip and what you want protected…")
    if user_text:
        st.session_state.chat_lines.append(("user", user_text))
        with st.spinner("Broker is thinking…"):
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_text}]},
                config=config,
            )
        reply = _extract_assistant_text(result)
        st.session_state.chat_lines.append(("assistant", reply))
        st.rerun()


if __name__ == "__main__":
    main()
