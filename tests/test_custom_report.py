from unittest.mock import patch

from modules.custom_report import (
    PRESET_TRANSKULTURALITAET,
    LANGUAGE_NAMES,
    extract_questions_from_text,
    build_answer_prompt,
    answer_questions,
)


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


def test_build_answer_prompt_contains_questions_context_and_language():
    prompt = build_answer_prompt(["Frage 1?", "Frage 2?"], "PAPIERTEXT", "en")
    assert "Frage 1?" in prompt
    assert "Frage 2?" in prompt
    assert "PAPIERTEXT" in prompt
    assert LANGUAGE_NAMES["en"] in prompt


def test_answer_questions_calls_claude_and_returns_text():
    with patch("modules.custom_report.call_claude", return_value="Antworttext") as mock_call:
        result = answer_questions(["Frage?"], "PAPIERTEXT", "de", client=object())
    assert result == "Antworttext"
    prompt_used = mock_call.call_args[0][1]
    assert "PAPIERTEXT" in prompt_used
