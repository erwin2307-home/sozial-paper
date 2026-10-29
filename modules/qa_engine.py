from modules import analysis_ragpipeline
from modules.claude_client import call_claude

MAX_CHARS_MODE_A = 400_000


def is_too_long_for_direct(full_text: str) -> bool:
    return len(full_text or "") > MAX_CHARS_MODE_A


def answer_question(full_text: str, question: str, mode: str, client) -> str:
    if mode == "B":
        chunks = analysis_ragpipeline.chunk_text(full_text)
        relevant = analysis_ragpipeline.retrieve_relevant_chunks(chunks, question, top_k=3)
        context = "\n\n".join(relevant)
    else:
        context = full_text
    prompt = (
        "Beantworte die folgende Frage ausschließlich auf Basis des gegebenen Paper-Textauszugs. "
        "Wenn die Antwort nicht im Text steht, sage das explizit.\n\n"
        f"TEXT:\n{context}\n\nFRAGE: {question}"
    )
    return call_claude(client, prompt)
