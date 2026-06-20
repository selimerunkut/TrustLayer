"""Build the LangChain 1.x broker agent (`create_agent` + checkpointer).

Follows repository skills:
- `.agents/skills/ecosystem-primer` — single-purpose agent => LangChain layer
- `.agents/skills/langchain-fundamentals` — `create_agent`, tools, MemorySaver, recursion_limit
- `.agents/skills/langchain-dependencies` — package pins in requirements-conversation.txt
"""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

from coverpilot_conversation.mock_backend import MockBrokerBackend
from coverpilot_conversation.prompts import BROKER_SYSTEM_PROMPT
from coverpilot_conversation.tools import build_broker_tools


def _default_model() -> ChatOpenAI:
    model_name = os.getenv("COVERPILOT_CHAT_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model_name, temperature=0.2)


def build_broker_agent(
    backend: MockBrokerBackend | None = None,
    *,
    model: Any | None = None,
    checkpointer: MemorySaver | None = None,
) -> tuple[Any, MockBrokerBackend]:
    """Return `(compiled_agent, backend)` for `invoke` / Streamlit.

    The compiled graph is LangChain's `create_agent` output (LangGraph-backed). Use
    `config={"configurable": {"thread_id": ...}, "recursion_limit": 25}` on each call.
    """
    be = backend or MockBrokerBackend()
    tools = build_broker_tools(be)
    cp = checkpointer or MemorySaver()
    llm = model or _default_model()
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=BROKER_SYSTEM_PROMPT,
        checkpointer=cp,
    )
    return agent, be
