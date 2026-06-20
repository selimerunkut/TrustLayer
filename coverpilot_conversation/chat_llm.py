"""Betty chat LLM: Nebius Token Factory (OpenAI-compatible) first, OpenAI fallback.

Uses LangChain ``ChatOpenAI`` with a custom ``base_url`` for Nebius. See Nebius docs:
set ``NEBIUS_API_KEY`` and optionally ``NEBIUS_CHAT_MODEL``, ``NEBIUS_BASE_URL``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

_DEFAULT_NEBIUS_BASE = "https://api.tokenfactory.nebius.com/v1/"
_DEFAULT_NEBIUS_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"


def llm_credentials_configured() -> bool:
    """True if either Nebius or OpenAI API key is present (non-empty)."""
    return bool(os.getenv("NEBIUS_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip())


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    return u if u.endswith("/") else f"{u}/"


def _nebius_reachable(api_key: str, base_url: str, *, timeout: float = 5.0) -> bool:
    """Lightweight check against Nebius OpenAI-compatible API (``models.list``)."""
    if os.getenv("COVERPILOT_LLM_SKIP_NEBIUS_PROBE", "").strip().lower() in ("1", "true", "yes"):
        logger.debug("Skipping Nebius probe (COVERPILOT_LLM_SKIP_NEBIUS_PROBE is set).")
        return True
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        client.models.list()
        return True
    except Exception as exc:
        logger.debug("Nebius reachability check failed: %s", exc)
        return False


def build_default_chat_llm() -> ChatOpenAI:
    """Return ``ChatOpenAI`` for Betty: Nebius when configured and reachable, else OpenAI.

    Logs at INFO when Nebius is selected, INFO when OpenAI is used because Nebius key
    is absent, WARNING when falling back to OpenAI after a failed Nebius probe.
    """
    max_tokens = int(os.getenv("COVERPILOT_MAX_OUTPUT_TOKENS", "800"))
    mt = max(200, max_tokens)
    temperature = float(os.getenv("COVERPILOT_CHAT_TEMPERATURE", "0.7"))

    neb_key = os.getenv("NEBIUS_API_KEY", "").strip()
    oai_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = _normalize_base_url(os.getenv("NEBIUS_BASE_URL", _DEFAULT_NEBIUS_BASE))

    if neb_key:
        if _nebius_reachable(neb_key, base_url):
            model = os.getenv("NEBIUS_CHAT_MODEL", _DEFAULT_NEBIUS_MODEL).strip() or _DEFAULT_NEBIUS_MODEL
            logger.info("Betty LLM: Nebius Token Factory (model=%s)", model)
            return ChatOpenAI(
                model=model,
                api_key=neb_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=mt,
            )
        if oai_key:
            model_oai = os.getenv("COVERPILOT_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
            logger.warning(
                "Nebius unavailable or probe failed (%s); falling back to OpenAI (model=%s).",
                base_url,
                model_oai,
            )
            return ChatOpenAI(
                model=model_oai,
                api_key=oai_key,
                temperature=temperature,
                max_tokens=mt,
            )
        model = os.getenv("NEBIUS_CHAT_MODEL", _DEFAULT_NEBIUS_MODEL).strip() or _DEFAULT_NEBIUS_MODEL
        logger.warning(
            "Nebius probe failed and OPENAI_API_KEY is not set; continuing with Nebius anyway "
            "(model=%s) — requests may fail.",
            model,
        )
        return ChatOpenAI(
            model=model,
            api_key=neb_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=mt,
        )

    if oai_key:
        model_oai = os.getenv("COVERPILOT_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
        logger.info("NEBIUS_API_KEY not set; using OpenAI for Betty LLM (model=%s).", model_oai)
        return ChatOpenAI(
            model=model_oai,
            api_key=oai_key,
            temperature=temperature,
            max_tokens=mt,
        )

    raise ValueError(
        "No LLM credentials: set NEBIUS_API_KEY (preferred) or OPENAI_API_KEY in the environment."
    )


def describe_llm_route(llm: Any) -> str:
    """Short label for UI/debug (does not expose secrets)."""
    try:
        bu = getattr(llm, "openai_api_base", None) or getattr(llm, "base_url", None) or ""
        if "nebius" in str(bu).lower() or "tokenfactory" in str(bu).lower():
            return "nebius"
        return "openai"
    except Exception:
        return "unknown"
