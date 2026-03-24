from osrs_mcp.server import mcp
from osrs_mcp.api.wiki_search import search_wiki as _search_wiki
from osrs_mcp.api.wiki_bucket import get_money_making_methods, get_boss_info, get_drop_sources_bulk
from osrs_mcp.api.wiki_page import read_wiki_page as _read_wiki_page
from osrs_mcp.util.categories import expand_category


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


@mcp.tool()
async def resource_sources(item: str) -> dict:
    """Find ALL ways to obtain an item or category of items — PvM drops, skilling,
    thieving, shops, minigames, and more.

    For single items, reads the wiki's "Item sources" table which has every source
    with level requirements, quantities, and drop rates. This is the most complete
    source data available.

    For categories (e.g. "herb seeds"), uses bulk drop table lookups to find
    monsters that drop multiple items in the category, plus wiki data for the
    first item.

    Args:
        item: Item name or category keyword (e.g. "Ranarr seed", "herb seeds", "Magic seed").
    """
    items = expand_category(item)
    query_display = item.strip()

    # For single items, the wiki "Item sources" section is the best data source —
    # it includes every monster, skilling method, shop, and minigame with
    # level, quantity, and rarity columns.
    wiki_lookup = items[0] if len(items) == 1 else query_display
    wiki_url = f"https://oldschool.runescape.wiki/w/{wiki_lookup.replace(' ', '_')}"
    wiki_content = None

    # Try "Item sources" first (standard section on all item pages)
    for section_name in ["Item sources", "Sources", "Obtaining"]:
        result = await _read_wiki_page(wiki_lookup, section_name)
        if result and "error" not in result:
            wiki_content = result
            break

    # If no specific section found, get the intro
    if wiki_content is None:
        result = await _read_wiki_page(wiki_lookup)
        if result and "error" not in result:
            wiki_content = result

    response: dict = {
        "query": query_display,
        "wiki_url": wiki_url,
    }

    if wiki_content:
        response["wiki_sources"] = wiki_content

    # For categories / multiple items, also do bulk drop table lookup
    # to show which monsters drop the most items from the category
    if len(items) > 1:
        monster_items = await get_drop_sources_bulk(items)
        response["bulk_sources"] = [
            {"monster": monster, "drops_matched": len(matched), "items": matched}
            for monster, matched in monster_items.items()
        ]

    if not wiki_content and "bulk_sources" not in response:
        response["wiki_note"] = f"No wiki page found for '{wiki_lookup}'."

    return response
