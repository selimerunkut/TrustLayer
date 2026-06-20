from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent

from backend.tools import validate_broker_tools
from coverpilot_conversation.prompts import BROKER_SYSTEM_PROMPT

DEFAULT_BROKER_MODEL = "gpt-5.4-mini"


def build_broker(*, model: Any = DEFAULT_BROKER_MODEL, tools: Sequence[Any]) -> Any:
    validate_broker_tools(tools)
    return create_agent(
        model=model,
        tools=list(tools),
        system_prompt=BROKER_SYSTEM_PROMPT,
    )
