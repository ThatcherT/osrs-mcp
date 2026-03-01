from osrs_mcp.api.base import get_client

WIKI_API = "https://oldschool.runescape.wiki/api.php"


async def search_wiki(query: str, limit: int = 10) -> list[dict]:
    """Search the OSRS Wiki using MediaWiki search API."""
    client = get_client()
    resp = await client.get(WIKI_API, params={
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
        "formatversion": "2",
    })
    resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("query", {}).get("search", []):
        results.append({
            "title": item["title"],
            "snippet": item.get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", ""),
            "url": f"https://oldschool.runescape.wiki/w/{item['title'].replace(' ', '_')}",
        })
    return results
