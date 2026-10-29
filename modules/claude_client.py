import anthropic

DEFAULT_MODEL = "claude-sonnet-5"


def get_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def call_claude(client, prompt: str, max_tokens: int = 4096) -> str:
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
