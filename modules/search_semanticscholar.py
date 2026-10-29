import requests

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,openAccessPdf",
    }
    headers = {"x-api-key": api_key} if api_key else {}
    response = requests.get(API_URL, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("data", []):
        results.append({
            "id": item.get("paperId"),
            "title": item.get("title") or "",
            "authors": ", ".join(a.get("name", "") for a in item.get("authors", [])),
            "year": item.get("year"),
            "abstract": item.get("abstract") or "",
            "pdf_url": (item.get("openAccessPdf") or {}).get("url"),
            "source": "semanticscholar",
        })
    return results
