from modules import search_semanticscholar, search_core, search_pubmed, search_europepmc

PROVIDERS = {
    "semanticscholar": search_semanticscholar,
    "core": search_core,
    "pubmed": search_pubmed,
    "europepmc": search_europepmc,
}


def aggregate(query: str, sources: list, api_keys: dict = None) -> list:
    api_keys = api_keys or {}
    merged = []
    seen_titles = set()
    for source in sources:
        provider_module = PROVIDERS.get(source)
        if provider_module is None:
            continue
        try:
            results = provider_module.search(query, api_keys.get(source))
        except Exception:
            results = []
        for item in results:
            key = item["title"].strip().lower()
            if key and key not in seen_titles:
                seen_titles.add(key)
                merged.append(item)
    return merged
