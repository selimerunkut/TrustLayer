from langchain_core.messages import AIMessage

from coverpilot_conversation.message_extract import extract_last_ai_text


def test_extract_last_ai_text_plain_string():
    r = {"messages": [AIMessage(content="Hello")]}
    assert extract_last_ai_text(r) == "Hello"


def test_extract_last_ai_text_takes_last_ai():
    r = {"messages": [AIMessage(content="a"), AIMessage(content="b")]}
    assert extract_last_ai_text(r) == "b"


def test_extract_last_ai_text_blocks():
    r = {
        "messages": [
            AIMessage(
                content=[
                    {"type": "text", "text": "Line one"},
                    {"type": "text", "text": "Line two"},
                ]
            )
        ]
    }
    out = extract_last_ai_text(r)
    assert "Line one" in out and "Line two" in out
