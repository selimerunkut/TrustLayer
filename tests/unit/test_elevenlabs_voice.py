from unittest.mock import MagicMock, patch

import pytest

from backend.services.elevenlabs_voice import (
    simplify_text_for_speech,
    synthesize_speech_mp3,
    transcribe_audio_bytes,
)


def test_simplify_text_for_speech_strips_markdown():
    raw = "Hello **Betty** — `delay` and\n\n```json\n{\"a\": 1}\n```\nend."
    out = simplify_text_for_speech(raw)
    assert "Betty" in out
    assert "**" not in out
    assert "```" not in out
    assert "delay" in out


@patch.dict(
    "os.environ",
    {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_ID": "v", "ELEVENLABS_TTS_SPEED": "1.1"},
    clear=False,
)
def test_synthesize_speech_mp3_uses_httpx():
    mock_resp = MagicMock()
    mock_resp.content = b"\xff\xfb" + b"x" * 200
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        inst = MagicMock()
        client_cls.return_value.__enter__.return_value = inst
        inst.post.return_value = mock_resp

        data = synthesize_speech_mp3("Hello there", api_key="k", voice_id="v")
        assert len(data) > 100
        inst.post.assert_called_once()
        args, kwargs = inst.post.call_args
        assert "text-to-speech/v" in args[0]
        assert kwargs["json"]["text"] == "Hello there"
        assert kwargs["json"]["voice_settings"]["speed"] == 1.1


@patch.dict("os.environ", {"ELEVENLABS_API_KEY": "k"}, clear=False)
def test_transcribe_parses_text_field():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"text": "  Book insurance  ", "words": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        inst = MagicMock()
        client_cls.return_value.__enter__.return_value = inst
        inst.post.return_value = mock_resp

        t = transcribe_audio_bytes(b"\x00\x01", api_key="k")
        assert t == "Book insurance"


def test_transcribe_raises_when_no_text():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"words": []}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.Client") as client_cls:
        inst = MagicMock()
        client_cls.return_value.__enter__.return_value = inst
        inst.post.return_value = mock_resp

        with pytest.raises(RuntimeError, match="had no transcript"):
            transcribe_audio_bytes(b"abc", api_key="k")
