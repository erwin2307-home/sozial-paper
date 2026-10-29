from unittest.mock import patch
from modules.qa_engine import is_too_long_for_direct, answer_question, MAX_CHARS_MODE_A

def test_is_too_long_for_direct_false_under_limit():
    assert is_too_long_for_direct("x" * 100) is False

def test_is_too_long_for_direct_true_over_limit():
    assert is_too_long_for_direct("x" * (MAX_CHARS_MODE_A + 1)) is True

def test_answer_question_mode_a_uses_full_text_as_context():
    with patch("modules.qa_engine.call_claude", return_value="Antwort") as mock_call:
        result = answer_question("VOLLTEXT HIER", "Was ist die Methode?", "A", client=object())
    assert result == "Antwort"
    prompt_used = mock_call.call_args[0][1]
    assert "VOLLTEXT HIER" in prompt_used
    assert "Was ist die Methode?" in prompt_used

def test_answer_question_mode_b_uses_retrieved_chunks_not_full_text():
    long_text = "Satz eins. " * 500
    with patch("modules.qa_engine.call_claude", return_value="Antwort") as mock_call:
        result = answer_question(long_text, "Was ist die Stichprobe?", "B", client=object())
    assert result == "Antwort"
    prompt_used = mock_call.call_args[0][1]
    assert len(prompt_used) < len(long_text)
