from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from modules import essay
from modules.library_state import Paper


def _full():
    return Paper(id="f", title="Volltext-Studie", authors="Max Muster, Eva Bei", year=2021, full_text="Volltextinhalt")


def _abstract_only():
    return Paper(id="a", title="Abstract-Studie", authors="Anna Test", abstract="Nur Abstract")


def test_fixed_texts_are_authors_files_without_heading_line():
    assert essay.ABSTRACT_TEXT.startswith("Ich bin eine muslimische Frau")
    assert essay.ABSTRACT_TEXT.endswith("weiterschreibt.")
    assert essay.SCHLUSSWORT_TEXT.startswith("Methodisch wurde diese Arbeit")
    assert essay.SCHLUSSWORT_TEXT.endswith("durch die vorliegende Arbeit.")


def test_prompt_contains_all_sources_and_marks_abstract_only():
    prompt = essay.build_prompt(["Frage eins?"], [_full(), _abstract_only()], "de")
    assert "Frage eins?" in prompt
    assert "Volltextinhalt" in prompt
    assert "Nur Abstract" in prompt
    assert "Max Muster et al., 2021" in prompt
    assert "Anna Test, o. J." in prompt
    assert "NUR ABSTRACT" in prompt


def test_prompt_forbids_invented_sources_and_personal_experiences():
    prompt = essay.build_prompt(["F?"], [_full()], "de")
    assert "keine Quellen" in prompt
    assert "keine persönlichen Erfahrungen" in prompt


def test_prompt_skips_papers_without_text():
    prompt = essay.build_prompt(["F?"], [_full(), Paper(id="x", title="Leeres Paper")], "de")
    assert "Leeres Paper" not in prompt


def test_long_papers_are_reduced_to_budget_with_relevant_passages():
    filler = "unwichtig " * 100_000
    paper = Paper(id="l", title="Lang", full_text=filler + "Transkulturalitaet ist zentral. " * 50)
    prompt = essay.build_prompt(["Was ist Transkulturalitaet?"], [paper, _full()], "de")
    assert len(prompt) < essay.MAX_SOURCE_CHARS + 5000
    assert "Transkulturalitaet ist zentral" in prompt
    assert "Volltextinhalt" in prompt


def test_references_list_marks_abstract_only_and_skips_textless():
    refs = essay.build_references([_full(), _abstract_only(), Paper(id="x", title="Leer")])
    assert "Max Muster, Eva Bei (2021). Volltext-Studie." in refs
    assert "Anna Test (o. J.). Abstract-Studie. [nur Abstract ausgewertet]" in refs
    assert "Leer" not in refs


def test_sections_start_with_abstract_and_end_with_schlusswort():
    sections = essay.build_sections("Antworttext", [_full()], "")
    assert [s[0] for s in sections] == ["Abstract", "Hauptteil", "Literaturverzeichnis", "Schlusswort"]
    assert sections[0][1] == essay.ABSTRACT_TEXT
    assert sections[1][1] == "Antworttext"
    assert sections[-1][1] == essay.SCHLUSSWORT_TEXT


def test_sections_place_personal_text_before_references():
    sections = essay.build_sections("Antworttext", [_full()], "  Mein Text  ")
    assert [s[0] for s in sections] == [
        "Abstract", "Hauptteil", "Persönliche Ergänzung", "Literaturverzeichnis", "Schlusswort",
    ]
    assert sections[2][1] == "Mein Text"


def test_generate_body_requests_long_answer_from_claude():
    client = MagicMock()
    client.messages.create.return_value.content = [SimpleNamespace(type="text", text="[[ANTWORT 1]]\nAntwort")]
    assert essay.generate_body(["F?"], [_full()], "de", client) == "Frage 1: F?\n\nAntwort"
    assert client.messages.create.call_args.kwargs["max_tokens"] == essay.MAX_OUTPUT_TOKENS


def _answers(*numbers):
    return "\n".join(f"[[ANTWORT {n}]]\nAntwort {n}" for n in numbers)


def test_generate_body_shows_every_question_with_its_answer_in_order():
    with patch("modules.essay.call_claude", return_value=_answers(1, 2)):
        body = essay.generate_body(["Erste?", "Zweite?"], [_full()], "de", client=object())
    assert body == "Frage 1: Erste?\n\nAntwort 1\n\nFrage 2: Zweite?\n\nAntwort 2"


def test_generate_body_removes_markdown_from_answers():
    raw = "[[ANTWORT 1]]\n## Begriff\n\n**Fett** und *kursiv* und __auch__, 2 * 3 bleibt.\n\n* Punkt\n- Punkt"
    with patch("modules.essay.call_claude", return_value=raw):
        body = essay.generate_body(["F?"], [_full()], "de", client=object())
    assert body == "Frage 1: F?\n\nBegriff\n\nFett und kursiv und auch, 2 * 3 bleibt.\n\n- Punkt\n- Punkt"


def test_prompt_asks_for_plain_text_without_markdown():
    assert "kein Markdown" in essay.build_prompt(["F?"], [_full()], "de")


def test_generate_body_asks_again_for_skipped_question():
    with patch("modules.essay.call_claude", side_effect=[_answers(1), _answers(2)]) as mock_call:
        body = essay.generate_body(["Erste?", "Zweite?"], [_full()], "de", client=object())
    assert "Antwort 2" in body
    retry_prompt = mock_call.call_args_list[1][0][1]
    assert "2. Zweite?" in retry_prompt
    assert "Erste?" not in retry_prompt


def test_generate_body_marks_question_still_unanswered_after_retry():
    with patch("modules.essay.call_claude", side_effect=[_answers(1), "kein Marker"]):
        body = essay.generate_body(["Erste?", "Zweite?"], [_full()], "de", client=object())
    assert f"Frage 2: Zweite?\n\n{essay.MISSING_ANSWER}" in body


def test_generate_body_splits_many_questions_into_batches():
    questions = [f"Frage {n}?" for n in range(1, essay.QUESTIONS_PER_CALL + 2)]
    calls = [_answers(*range(1, essay.QUESTIONS_PER_CALL + 1)), _answers(essay.QUESTIONS_PER_CALL + 1)]
    with patch("modules.essay.call_claude", side_effect=calls) as mock_call:
        body = essay.generate_body(questions, [_full()], "de", client=object())
    assert mock_call.call_count == 2
    assert essay.MISSING_ANSWER not in body


def test_prompt_demands_complete_marked_answer_for_each_question():
    prompt = essay.build_prompt(["F?"], [_full()], "de")
    assert "[[ANTWORT 1]]" in prompt
    assert "vollständig" in prompt


def test_prompt_uses_personal_perspective_only_when_requested():
    assert essay.PERSPECTIVE_INSTRUCTION not in essay.build_prompt(["F?"], [_full()], "de")
    tailored = essay.build_prompt(["F?"], [_full()], "de", personal_perspective=True)
    assert essay.PERSPECTIVE_INSTRUCTION in tailored
    for term in ("Frau", "Muslimin", "Diskriminierung", "neurologisch"):
        assert term in essay.PERSPECTIVE_INSTRUCTION
    assert "keine persönlichen Erfahrungen" in tailored


def test_generate_body_passes_personal_perspective_to_prompt():
    with patch("modules.essay.call_claude", return_value=_answers(1)) as mock_call:
        essay.generate_body(["F?"], [_full()], "de", client=object(), personal_perspective=True)
    assert essay.PERSPECTIVE_INSTRUCTION in mock_call.call_args[0][1]
