from unittest.mock import MagicMock

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
    client.messages.create.return_value.content = [MagicMock(text="Antwort")]
    assert essay.generate_body(["F?"], [_full()], "de", client) == "Antwort"
    assert client.messages.create.call_args.kwargs["max_tokens"] == essay.MAX_OUTPUT_TOKENS
