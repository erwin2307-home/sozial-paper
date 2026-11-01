import anthropic

DEFAULT_MODEL = "claude-sonnet-5"


def get_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


class EmptyResponseError(Exception):
    """Claude returned no complete answer; the message is safe to show to the user."""


def call_claude(client, prompt: str, max_tokens: int = 16000) -> str:
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "max_tokens":
        raise EmptyResponseError("Die Antwort wurde wegen ihrer Laenge abgeschnitten. Bitte weniger Fragen oder Quellen verwenden.")
    # The content list can hold non-text blocks such as thinking, in any position.
    text = "".join(block.text for block in response.content if block.type == "text")
    if not text.strip():
        raise EmptyResponseError("Claude hat keine Antwort geliefert. Bitte erneut versuchen.")
    return text
