"""Betty chat LLM: Nebius Token Factory (OpenAI-compatible) first, OpenAI fallback.

Uses LangChain ``ChatOpenAI`` with a custom ``base_url`` for Nebius. See Nebius docs:
set ``NEBIUS_API_KEY`` and optionally ``NEBIUS_CHAT_MODEL``, ``NEBIUS_BASE_URL``.

Nebius large models (e.g. Qwen3-235B) can return HTTP 400 ``Already borrowed`` when
multiple requests hit the provider concurrently (typed chat + voice). ``BettyChatOpenAI``
serializes Nebius calls, retries once, then falls back to OpenAI when configured.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import nullcontext
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

_DEFAULT_NEBIUS_BASE = "https://api.tokenfactory.nebius.com/v1/"
_DEFAULT_NEBIUS_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
_NEBIUS_INVOKE_LOCK = threading.Lock()


def llm_credentials_configured() -> bool:
    """True if either Nebius or OpenAI API key is present (non-empty)."""
    return bool(os.getenv("NEBIUS_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip())


def _normalize_base_url(url: str) -> str:
    u = (url or "").strip()
    return u if u.endswith("/") else f"{u}/"


def _uses_nebius_base(base_url: str | None) -> bool:
    bu = str(base_url or "").lower()
    return "nebius" in bu or "tokenfactory" in bu


def is_nebius_capacity_error(exc: BaseException) -> bool:
    """True when Nebius (or compatible) rejects a concurrent in-flight request."""
    text = str(exc).lower()
    if "already borrowed" in text:
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        detail = str(body.get("detail", "")).lower()
        if "already borrowed" in detail:
            return True
    return False


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


def _openai_fallback_llm(*, temperature: float, max_tokens: int) -> ChatOpenAI | None:
    oai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not oai_key:
        return None
    model_oai = os.getenv("COVERPILOT_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    return ChatOpenAI(
        model=model_oai,
        api_key=oai_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class BettyChatOpenAI(ChatOpenAI):
    """ChatOpenAI with Nebius concurrency guard and OpenAI fallback."""

    fallback_llm: ChatOpenAI | None = None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        use_lock = _uses_nebius_base(getattr(self, "openai_api_base", None) or getattr(self, "base_url", None))
        last_exc: BaseException | None = None
        for attempt in range(2):
            try:
                with _NEBIUS_INVOKE_LOCK if use_lock else nullcontext():
                    return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            except Exception as exc:
                last_exc = exc
                if not use_lock or not is_nebius_capacity_error(exc):
                    raise
                if attempt == 0:
                    logger.warning(
                        "Nebius returned 'Already borrowed'; retrying after brief delay (attempt %s).",
                        attempt + 1,
                    )
                    time.sleep(float(os.getenv("COVERPILOT_NEBIUS_RETRY_SECONDS", "1.0")))
                    continue
                break

        fallback = self.fallback_llm
        if fallback is not None and last_exc is not None:
            logger.warning(
                "Nebius capacity error persisted; falling back to OpenAI (%s).",
                getattr(fallback, "model_name", "openai"),
            )
            return fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("BettyChatOpenAI failed without an exception")


def build_default_chat_llm() -> BettyChatOpenAI:
    """Return Betty LLM: Nebius when configured and reachable, else OpenAI.

    When Nebius is primary, ``OPENAI_API_KEY`` (if set) is kept as a runtime fallback
    for capacity errors such as ``Already borrowed``.
    """
    max_tokens = int(os.getenv("COVERPILOT_MAX_OUTPUT_TOKENS", "800"))
    mt = max(200, max_tokens)
    temperature = float(os.getenv("COVERPILOT_CHAT_TEMPERATURE", "0.7"))

    neb_key = os.getenv("NEBIUS_API_KEY", "").strip()
    oai_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = _normalize_base_url(os.getenv("NEBIUS_BASE_URL", _DEFAULT_NEBIUS_BASE))
    fallback = _openai_fallback_llm(temperature=temperature, max_tokens=mt)

    if neb_key:
        if _nebius_reachable(neb_key, base_url):
            model = os.getenv("NEBIUS_CHAT_MODEL", _DEFAULT_NEBIUS_MODEL).strip() or _DEFAULT_NEBIUS_MODEL
            logger.info("Betty LLM: Nebius Token Factory (model=%s)", model)
            return BettyChatOpenAI(
                model=model,
                api_key=neb_key,
                base_url=base_url,
                temperature=temperature,
                max_tokens=mt,
                fallback_llm=fallback,
            )
        if oai_key:
            model_oai = os.getenv("COVERPILOT_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
            logger.warning(
                "Nebius unavailable or probe failed (%s); falling back to OpenAI (model=%s).",
                base_url,
                model_oai,
            )
            return BettyChatOpenAI(
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
        return BettyChatOpenAI(
            model=model,
            api_key=neb_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=mt,
        )

    if oai_key:
        model_oai = os.getenv("COVERPILOT_CHAT_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
        logger.info("NEBIUS_API_KEY not set; using OpenAI for Betty LLM (model=%s).", model_oai)
        return BettyChatOpenAI(
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
