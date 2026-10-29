from unittest.mock import patch
from modules.analysis_direct import analyze
from modules.report_schema import SCHEMA_FIELDS


def test_analyze_calls_claude_with_full_text_and_returns_parsed_report():
    fake_raw = "{" + ", ".join(f'"{f}": "x"' for f in SCHEMA_FIELDS) + "}"
    with patch("modules.analysis_direct.call_claude", return_value=fake_raw) as mock_call:
        result = analyze("VOLLTEXT DES PAPERS", client=object())
    assert result["forschungsfrage"] == "x"
    prompt_used = mock_call.call_args[0][1]
    assert "VOLLTEXT DES PAPERS" in prompt_used
