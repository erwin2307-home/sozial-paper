import requests

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    search_params = {"db": "pubmed", "term": query, "retmax": limit, "retmode": "json"}
    if api_key:
        search_params["api_key"] = api_key
    search_resp = requests.get(ESEARCH_URL, params=search_params, timeout=15)
    search_resp.raise_for_status()
    ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    summary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    if api_key:
        summary_params["api_key"] = api_key
    summary_resp = requests.get(ESUMMARY_URL, params=summary_params, timeout=15)
    summary_resp.raise_for_status()
    summary_data = summary_resp.json().get("result", {})
    results = []
    for pmid in ids:
        item = summary_data.get(pmid)
        if not item:
            continue
        authors = ", ".join(a.get("name", "") for a in item.get("authors", []))
        results.append({
            "id": pmid,
            "title": item.get("title") or "",
            "authors": authors,
            "year": _extract_year(item.get("pubdate", "")),
            "abstract": "",
            "pdf_url": None,
            "source": "pubmed",
        })
    return results


def _extract_year(pubdate: str):
    digits = "".join(ch for ch in pubdate[:4] if ch.isdigit())
    return int(digits) if digits else None
