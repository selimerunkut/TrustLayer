"""Extract human-visible assistant text from LangGraph / create_agent invoke results."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage


def extract_last_ai_text(result: dict[str, Any]) -> str:
    """Last AIMessage content (handles str or structured content blocks)."""
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
