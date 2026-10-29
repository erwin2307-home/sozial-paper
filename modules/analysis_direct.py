from modules import report_schema
from modules.claude_client import call_claude


def analyze(full_text: str, client) -> dict:
    prompt = report_schema.build_prompt(full_text)
    raw = call_claude(client, prompt)
    return report_schema.parse_response(raw)
