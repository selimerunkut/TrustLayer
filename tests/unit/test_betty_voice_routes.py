from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_voice_embed_template_exists():
    p = Path("app/voice_embed.html")
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "__BETTY_API_BASE__" in text
    assert "__THREAD_ID__" in text
    assert "/api/betty/voice-chat" in text


def test_voice_chat_returns_503_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post(
        "/api/betty/voice-chat",
        json={
            "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "message": "Hello Betty",
            "crm_customer_id": "vasiliy",
        },
    )
    assert r.status_code == 503
