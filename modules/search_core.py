import requests

API_URL = "https://api.core.ac.uk/v3/search/works/"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    params = {"q": query, "limit": limit}
    response = requests.get(API_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("results", []):
        authors = item.get("authors") or []
        results.append({
            "id": str(item.get("id")),
            "title": item.get("title") or "",
            "authors": ", ".join(a.get("name", "") for a in authors),
            "year": item.get("yearPublished"),
            "abstract": item.get("abstract") or "",
            "pdf_url": item.get("downloadUrl"),
            "source": "core",
        })
    return results
