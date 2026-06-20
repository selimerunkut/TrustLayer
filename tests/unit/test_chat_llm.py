"""Tests for Nebius-first ``build_default_chat_llm`` routing and capacity fallback."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from coverpilot_conversation.chat_llm import (
    build_default_chat_llm,
    is_nebius_capacity_error,
    llm_credentials_configured,
)


def test_llm_credentials_configured(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_credentials_configured() is False
    monkeypatch.setenv("NEBIUS_API_KEY", "x")
    assert llm_credentials_configured() is True


def test_raises_when_no_keys(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="No LLM credentials"):
        build_default_chat_llm()


def test_is_nebius_capacity_error():
    class FakeErr(Exception):
        body = {"detail": "Already borrowed"}

    assert is_nebius_capacity_error(FakeErr("ignored")) is True
    assert is_nebius_capacity_error(RuntimeError("other")) is False


@patch("coverpilot_conversation.chat_llm.BettyChatOpenAI")
@patch("coverpilot_conversation.chat_llm._nebius_reachable", return_value=True)
def test_prefers_nebius_when_probe_succeeds(_reach, mock_chat, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "neb-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("COVERPILOT_LLM_SKIP_NEBIUS_PROBE", "true")
    build_default_chat_llm()
    kwargs = mock_chat.call_args.kwargs
    assert kwargs["api_key"] == "neb-secret"
    assert "tokenfactory" in (kwargs.get("base_url") or "").lower()
    assert kwargs.get("fallback_llm") is not None


@patch("coverpilot_conversation.chat_llm.BettyChatOpenAI")
@patch("coverpilot_conversation.chat_llm._nebius_reachable", return_value=False)
def test_falls_back_to_openai_when_nebius_probe_fails(_reach, mock_chat, monkeypatch):
    monkeypatch.setenv("NEBIUS_API_KEY", "neb-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    build_default_chat_llm()
    kwargs = mock_chat.call_args.kwargs
    assert kwargs["api_key"] == "sk-openai"
    bu = (kwargs.get("base_url") or "").lower()
    assert "tokenfactory" not in bu


@patch("coverpilot_conversation.chat_llm.BettyChatOpenAI")
def test_openai_only_when_no_nebius_key(mock_chat, monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-only")
    build_default_chat_llm()
    kwargs = mock_chat.call_args.kwargs
    assert kwargs["api_key"] == "sk-only"
