from rank_bm25 import BM25Okapi

from modules import report_schema
from modules.claude_client import call_claude


def chunk_text(full_text: str, chunk_size: int = 1500, overlap: int = 200) -> list:
    if not full_text:
        return []
    chunks = []
    start = 0
    n = len(full_text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(full_text[start:end])
        if end == n:
            break
        start = end - overlap
    return chunks


def retrieve_relevant_chunks(chunks: list, query: str, top_k: int = 5) -> list:
    if not chunks:
        return []
    tokenized_chunks = [c.lower().split() for c in chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    scores = bm25.get_scores(query.lower().split())
    ranked_indices = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked_indices[:top_k]]


def analyze(full_text: str, client) -> dict:
    chunks = chunk_text(full_text)
    query = " ".join(report_schema.SCHEMA_FIELDS)
    relevant = retrieve_relevant_chunks(chunks, query, top_k=8)
    prompt = report_schema.build_prompt("\n\n".join(relevant))
    raw = call_claude(client, prompt)
    return report_schema.parse_response(raw)
