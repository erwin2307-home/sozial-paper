import json
import re

from modules.claude_client import call_claude

LANGUAGE_NAMES = {"de": "Deutsch", "en": "English", "tr": "Turkce"}

PRESET_TRANSKULTURALITAET = [
    (
        "Beschreiben Sie in eigenen Worten, was Wolfgang Welsch unter Transkulturalitaet "
        "versteht. Gehen Sie darauf ein, was an diesem Ansatz besonders wichtig erscheint "
        "und worin sich Transkulturalitaet von Vorstellungen unterscheidet, die Kultur als "
        "klar voneinander getrennte Einheiten verstehen."
    ),
    (
        "Reflektieren Sie die Bedeutung des Konzepts der Transkulturalitaet fuer die Soziale "
        "Arbeit: welche Chancen eine transkulturelle Sichtweise fuer die Arbeit mit Menschen "
        "eroeffnet, welche Auswirkungen sie auf den Umgang mit Diversitaet, Zugehoerigkeit "
        "und Unterschiedlichkeit haben koennte, und welche Grenzen oder Herausforderungen "
        "dieser Ansatz hat."
    ),
    (
        "Formulieren Sie abschliessend eine Frage, einen Gedanken oder eine Aussage aus dem "
        "Text, die besonders beschaeftigt, ueberrascht oder irritiert hat."
    ),
]


def extract_questions_from_text(raw_text: str, client) -> list:
    prompt = (
        "Extrahiere alle Fragen oder Aufgabenstellungen aus dem folgenden Text als Liste. "
        "Antworte ausschliesslich mit einem JSON-Array von Strings, ein Eintrag pro Frage/Aufgabe.\n\n"
        f"TEXT:\n{raw_text}"
    )
    raw = call_claude(client, prompt)
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    json_str = match.group(0) if match else raw
    try:
        questions = json.loads(json_str)
    except json.JSONDecodeError:
        questions = []
    return [str(q) for q in questions if str(q).strip()]


def build_answer_prompt(questions: list, context_text: str, language: str) -> str:
    language_name = LANGUAGE_NAMES.get(language, "Deutsch")
    numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
    return (
        "Beantworte die folgenden Fragen auf Basis des gegebenen Paper-Textauszugs, "
        f"in zusammenhaengendem Fliesstext, auf {language_name}. "
        "Gehe auf jede Frage ein, aber ohne die Fragen selbst zu wiederholen oder zu nummerieren.\n\n"
        f"FRAGEN:\n{numbered}\n\n"
        f"TEXT:\n{context_text}"
    )


def answer_questions(questions: list, context_text: str, language: str, client) -> str:
    prompt = build_answer_prompt(questions, context_text, language)
    return call_claude(client, prompt)
