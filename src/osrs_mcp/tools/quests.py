from osrs_mcp.server import mcp
from osrs_mcp.api.wiki_bucket import get_quest_info as _get_quest_info
from osrs_mcp.api.wiki_search import search_wiki


@mcp.tool()
async def quest_info(quest_name: str) -> dict:
    """Get details about an OSRS quest. Returns bucket data plus a wiki link for full info.

    Args:
        quest_name: The quest name (e.g. "Dragon Slayer II", "Recipe for Disaster").
    """
    result = await _get_quest_info(quest_name)
    # Always include wiki link since bucket data is limited
    wiki_url = f"https://oldschool.runescape.wiki/w/{quest_name.replace(' ', '_')}"
    if result is None:
        # Try wiki search as fallback
        search_results = await search_wiki(quest_name + " quest")
        return {
            "note": f"Quest '{quest_name}' not found in structured data.",
            "wiki_url": wiki_url,
            "search_results": search_results[:5],
        }
    result["wiki_url"] = wiki_url
    return result
