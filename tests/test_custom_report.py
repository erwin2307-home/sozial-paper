from unittest.mock import patch

from modules.custom_report import PRESET_TRANSKULTURALITAET, extract_questions_from_text


def test_preset_transkulturalitaet_has_three_items():
    assert len(PRESET_TRANSKULTURALITAET) == 3
    assert all(isinstance(q, str) and q.strip() for q in PRESET_TRANSKULTURALITAET)


def test_extract_questions_from_text_parses_json_array():
    with patch("modules.custom_report.call_claude", return_value='["Frage 1?", "Frage 2?"]'):
        result = extract_questions_from_text("roher Text mit Fragen", client=object())
    assert result == ["Frage 1?", "Frage 2?"]


def test_extract_questions_from_text_json_embedded_in_extra_text():
    raw = 'Hier sind die Fragen:\n["Frage A?", "Frage B?"]\nEnde.'
    with patch("modules.custom_report.call_claude", return_value=raw):
        result = extract_questions_from_text("roher Text", client=object())
    assert result == ["Frage A?", "Frage B?"]


def test_extract_questions_from_text_garbage_returns_empty_list():
    with patch("modules.custom_report.call_claude", return_value="kein json hier"):
        result = extract_questions_from_text("roher Text", client=object())
    assert result == []


def test_extract_questions_prompt_demands_every_question_and_subtask():
    with patch("modules.custom_report.call_claude", return_value="[]") as mock_call:
        extract_questions_from_text("roher Text", client=object())
    prompt = mock_call.call_args[0][1]
    assert "Unterfrage" in prompt
    assert "Tabelle" in prompt
    assert "roher Text" in prompt
