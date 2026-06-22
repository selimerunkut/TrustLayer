from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from backend.main import app, create_app
from backend.services.elevenlabs_voice import ElevenLabsTTSHTTPError
from coverpilot_conversation.mock_backend import MockBrokerBackend

client = TestClient(app)


def test_voice_embed_template_exists():
    p = Path("app/voice_embed.html")
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "__BETTY_API_BASE__" in text
    assert "__THREAD_ID__" in text
    assert "__BOOTSTRAP_B64__" in text
    assert "/api/betty/voice-chat" in text
    assert "/api/betty/tts" in text
    assert "/api/betty/voice-ui-turn" in text
    assert "speakWithBrowserTts" not in text


def test_voice_chat_returns_503_without_llm_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    r = client.post(
        "/api/betty/voice-chat",
        json={
            "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "message": "Hello Betty",
            "crm_customer_id": "vasiliy",
        },
    )
    assert r.status_code == 503


def test_voice_chat_rejects_bodies_over_64_kib(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    r = client.post(
        "/api/betty/voice-chat",
        json={
            "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "message": "x" * 70000,
            "crm_customer_id": "vasiliy",
        },
    )
    assert r.status_code == 413
    assert r.json()["detail"] == "Request body too large."


def test_voice_routes_are_rate_limited_per_source(monkeypatch):
    client = TestClient(create_app())
    responses = [
        client.post(
            "/api/betty/voice-ui-turn",
            json={
                "thread_id": f"aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee{i:02d}",
                "user": "Hello Betty",
                "assistant": "Hello traveler",
            },
        )
        for i in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [200] * 10
    assert responses[10].status_code == 429
    assert responses[10].json()["detail"] == "Too many requests."


def test_voice_ui_turn_round_trips_into_transcript(monkeypatch, trustlayer_internal_headers):
    monkeypatch.setenv("TRUSTLAYER_API_TOKEN", "trustlayer-token")
    r = client.post(
        "/api/betty/voice-ui-turn",
        json={
            "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "user": "Hello Betty",
            "assistant": "Hello traveler",
        },
    )
    assert r.status_code == 200

    transcript = client.get(
        "/api/betty/voice-ui-transcript/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        headers=trustlayer_internal_headers,
    )
    assert transcript.status_code == 200
    assert transcript.json()["turns"] == [{"user": "Hello Betty", "assistant": "Hello traveler"}]


def test_tts_route_remains_available_when_elevenlabs_is_configured(monkeypatch, trustlayer_internal_headers):
    monkeypatch.setenv("TRUSTLAYER_API_TOKEN", "trustlayer-token")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "voice-id")
    monkeypatch.setattr(
        "backend.services.elevenlabs_voice.elevenlabs_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.services.elevenlabs_voice.synthesize_speech_mp3",
        lambda text: b"mp3-bytes-are-long-enough-for-test" * 4,
    )

    r = client.post(
        "/api/betty/tts",
        headers=trustlayer_internal_headers,
        json={"text": "Hello Betty"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content.startswith(b"mp3-bytes-are-long-enough-for-test")


def test_tts_route_returns_503_without_elevenlabs(monkeypatch, trustlayer_internal_headers):
    monkeypatch.setenv("TRUSTLAYER_API_TOKEN", "trustlayer-token")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    r = TestClient(create_app()).post(
        "/api/betty/tts",
        headers=trustlayer_internal_headers,
        json={"text": "Hello Betty"},
    )

    assert r.status_code == 503
    assert r.json()["detail"] == "ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set."


def test_tts_route_returns_503_when_voice_id_is_missing(monkeypatch, trustlayer_internal_headers):
    monkeypatch.setenv("TRUSTLAYER_API_TOKEN", "trustlayer-token")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

    r = TestClient(create_app()).post(
        "/api/betty/tts",
        headers=trustlayer_internal_headers,
        json={"text": "Hello Betty"},
    )

    assert r.status_code == 503
    assert r.json()["detail"] == "ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set."


def test_voice_tts_returns_402_for_paid_plan_required(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v")

    with patch(
        "backend.services.elevenlabs_voice.synthesize_speech_mp3",
        side_effect=ElevenLabsTTSHTTPError(
            402,
            {
                "type": "payment_required",
                "code": "paid_plan_required",
                "message": "Free users cannot use library voices via the API.",
            },
        ),
    ):
        r = client.post("/api/betty/tts", json={"text": "Hello Betty"})
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == "paid_plan_required"


def test_browser_voice_posts_keep_working_after_one_time_bootstrap(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")

    class FakeAgent:
        def __init__(self) -> None:
            self.calls: list[tuple[dict[str, object], dict[str, object]]] = []

        def invoke(self, payload: dict[str, object], config: dict[str, object]) -> dict[str, object]:
            self.calls.append((payload, config))
            return {"messages": [AIMessage(content="Hello traveler")]}

    fake_agent = FakeAgent()
    monkeypatch.setattr(
        "coverpilot_conversation.agent.build_broker_agent",
        lambda backend=None, **kwargs: (fake_agent, backend or MockBrokerBackend()),
    )

    client = TestClient(create_app())
    first = client.post(
        "/api/betty/voice-chat",
        json={
            "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "message": "Hello Betty",
            "crm_customer_id": "vasiliy",
            "conversation_bootstrap": "typed chat bootstrap",
        },
    )
    second = client.post(
        "/api/betty/voice-chat",
        json={
            "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "message": "Tell me more",
            "crm_customer_id": "vasiliy",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(fake_agent.calls) == 2
    first_payload = fake_agent.calls[0][0]["messages"][0]["content"]
    second_payload = fake_agent.calls[1][0]["messages"][0]["content"]
    assert "typed chat bootstrap" in first_payload
    assert "Prior typed chat this session" in first_payload
    assert "typed chat bootstrap" not in second_payload
    assert "Prior typed chat this session" not in second_payload
