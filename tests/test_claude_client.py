from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.claude_client import call_claude, get_client, DEFAULT_MODEL, EmptyResponseError


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


# A real ThinkingBlock has no .text attribute, so reading it raises AttributeError.
_THINKING_BLOCK = SimpleNamespace(type="thinking", thinking="")


def _response(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def test_call_claude_returns_text_from_response():
    client = Mock()
    client.messages.create.return_value = _response([_text_block("Antworttext")])
    result = call_claude(client, "Frage?")
    assert result == "Antworttext"


def test_call_claude_skips_thinking_block_before_text():
    client = Mock()
    client.messages.create.return_value = _response([_THINKING_BLOCK, _text_block("Antworttext")])
    assert call_claude(client, "Frage?") == "Antworttext"


def test_call_claude_joins_multiple_text_blocks():
    client = Mock()
    client.messages.create.return_value = _response([_text_block("Teil 1. "), _THINKING_BLOCK, _text_block("Teil 2.")])
    assert call_claude(client, "Frage?") == "Teil 1. Teil 2."


def test_call_claude_raises_when_output_was_cut_off():
    client = Mock()
    client.messages.create.return_value = _response([_text_block("Halber Sa")], stop_reason="max_tokens")
    with pytest.raises(EmptyResponseError):
        call_claude(client, "Frage?")


def test_call_claude_raises_on_refusal_without_text():
    client = Mock()
    client.messages.create.return_value = _response([], stop_reason="refusal")
    with pytest.raises(EmptyResponseError):
        call_claude(client, "Frage?")


def test_call_claude_uses_default_model_and_prompt():
    client = Mock()
    client.messages.create.return_value = _response([_text_block("ok")])
    call_claude(client, "Mein Prompt")
    _, kwargs = client.messages.create.call_args
    assert kwargs["model"] == DEFAULT_MODEL
    assert kwargs["messages"] == [{"role": "user", "content": "Mein Prompt"}]

def test_get_client_builds_anthropic_client(monkeypatch):
    created = {}

    class FakeAnthropic:
        def __init__(self, api_key):
            created["api_key"] = api_key

    monkeypatch.setattr("modules.claude_client.anthropic.Anthropic", FakeAnthropic)
    client = get_client("my-key")
    assert created["api_key"] == "my-key"
    assert isinstance(client, FakeAnthropic)
