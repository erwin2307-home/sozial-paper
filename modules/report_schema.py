import json
import re

SCHEMA_FIELDS = [
    "forschungsfrage",
    "theoretischer_rahmen",
    "methodik",
    "stichprobe",
    "datenerhebung",
    "ergebnisse",
    "limitationen",
    "implikationen",
]


def build_prompt(context_text: str) -> str:
    fields_list = "\n".join(f'- "{field}"' for field in SCHEMA_FIELDS)
    return (
        "Du bist Sozialwissenschaftlerin und analysierst ein wissenschaftliches Paper "
        "exakt anhand des folgenden Textauszugs.\n\n"
        f"TEXT:\n{context_text}\n\n"
        "Antworte ausschließlich mit einem JSON-Objekt mit genau diesen Schlüsseln:\n"
        f"{fields_list}\n"
        "Fülle jedes Feld mit einer präzisen, auf den Text gestützten Antwort auf Deutsch. "
        "Wenn eine Information im Text fehlt, schreibe \"nicht angegeben\"."
    )


def parse_response(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    json_str = match.group(0) if match else raw_text
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        data = {}
    return {field: data.get(field, "nicht angegeben") for field in SCHEMA_FIELDS}
