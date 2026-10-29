import requests

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def search(query: str, api_key: str = None, limit: int = 10) -> list:
    params = {"query": query, "format": "json", "pageSize": limit}
    response = requests.get(API_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = []
    for item in data.get("resultList", {}).get("result", []):
        results.append({
            "id": item.get("id"),
            "title": item.get("title") or "",
            "authors": item.get("authorString") or "",
            "year": int(item["pubYear"]) if item.get("pubYear") else None,
            "abstract": item.get("abstractText") or "",
            "pdf_url": None,
            "source": "europepmc",
        })
    return results
