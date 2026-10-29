import json
from modules.report_schema import SCHEMA_FIELDS, build_prompt, parse_response

def test_build_prompt_contains_all_fields_and_context():
    prompt = build_prompt("MEIN PAPERTEXT")
    assert "MEIN PAPERTEXT" in prompt
    for field in SCHEMA_FIELDS:
        assert field in prompt

def test_parse_response_valid_json():
    payload = {f: f"wert-{f}" for f in SCHEMA_FIELDS}
    raw = json.dumps(payload)
    result = parse_response(raw)
    assert result == payload

def test_parse_response_json_embedded_in_extra_text():
    payload = {f: f"wert-{f}" for f in SCHEMA_FIELDS}
    raw = "Hier ist die Analyse:\n" + json.dumps(payload) + "\nEnde."
    result = parse_response(raw)
    assert result == payload

def test_parse_response_missing_fields_filled_with_default():
    raw = json.dumps({"forschungsfrage": "x"})
    result = parse_response(raw)
    assert result["forschungsfrage"] == "x"
    assert result["ergebnisse"] == "nicht angegeben"

def test_parse_response_garbage_returns_all_defaults():
    result = parse_response("kein json hier")
    assert all(v == "nicht angegeben" for v in result.values())
