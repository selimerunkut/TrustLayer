"""Extract human-visible assistant text from LangGraph / create_agent invoke results."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import AIMessage


def format_assistant_reply_for_display(text: str) -> str:
    """Strip common Markdown for plain chat/TTS (Betty should speak in prose, not docs)."""
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"(?m)^#{1,6}\s+", "", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
    t = re.sub(r"__([^_]+)__", r"\1", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", t)
    t = re.sub(r"(?m)^\s*[-*]\s+", "– ", t)
    t = re.sub(r"(?m)^\s*\d+\.\s+", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


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
