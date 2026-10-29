from unittest.mock import Mock
from modules.claude_client import call_claude, get_client, DEFAULT_MODEL

def test_call_claude_returns_text_from_response():
    client = Mock()
    client.messages.create.return_value = Mock(content=[Mock(text="Antworttext")])
    result = call_claude(client, "Frage?")
    assert result == "Antworttext"

def test_call_claude_uses_default_model_and_prompt():
    client = Mock()
    client.messages.create.return_value = Mock(content=[Mock(text="ok")])
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
