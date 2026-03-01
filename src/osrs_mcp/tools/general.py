from osrs_mcp.server import mcp
from osrs_mcp.api.wiki_search import search_wiki as _search_wiki
from osrs_mcp.api.wiki_bucket import get_money_making_methods, get_boss_info
from osrs_mcp.api.wiki_page import read_wiki_page as _read_wiki_page


@mcp.tool()
async def search_wiki(query: str) -> list[dict]:
    """Search the OSRS Wiki for any topic. Use this as a fallback when other tools don't cover what you need.

    Args:
        query: Search query (e.g. "how to get to Zanaris", "fire cape guide").
    """
    return await _search_wiki(query)


@mcp.tool()
async def money_making_methods(skill: str = "", min_profit: int = 0) -> list[dict]:
    """Get money making method names from the OSRS Wiki. Returns method names with wiki links.

    Args:
        skill: Optional filter (currently limited). Leave empty for all.
        min_profit: Currently unused (profit data requires wiki page parsing).
    """
    methods = await get_money_making_methods()
    results = []
    for m in methods:
        name = m.get("page_name_sub", "")
        if name:
            # Strip "Money making guide/" prefix
            display = name.replace("Money making guide/", "")
            if skill and skill.lower() not in display.lower():
                continue
            results.append({
                "method": display,
                "wiki_url": f"https://oldschool.runescape.wiki/w/{name.replace(' ', '_')}",
            })
    return results[:50]


@mcp.tool()
async def boss_requirements(boss_name: str) -> dict:
    """Get comprehensive boss info: stats, drops, and wiki link for gear recommendations.

    Args:
        boss_name: The boss name (e.g. "Vorkath", "Zulrah", "General Graardor").
    """
    info = await get_boss_info(boss_name)
    info["wiki_url"] = f"https://oldschool.runescape.wiki/w/{boss_name.replace(' ', '_')}"
    return info


@mcp.tool()
async def read_wiki_page(page: str, section: str = "") -> dict:
    """Read an OSRS Wiki page. Without a section, returns the table of contents
    and intro so you can see what's available. With a section name or index,
    returns that section's content.

    Use this to look up boss strategies, skilling methods, quest guides,
    game mechanics, and anything else on the wiki.

    Args:
        page: Page title (e.g. "Vorkath", "Dragon Slayer I", "Slayer").
        section: Section name or index number. Leave empty for TOC + intro.
    """
    return await _read_wiki_page(page, section)
