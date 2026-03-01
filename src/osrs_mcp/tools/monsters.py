from osrs_mcp.server import mcp
from osrs_mcp.api.wiki_bucket import (
    get_monster_info as _get_monster_info,
    get_monster_drops as _get_monster_drops,
    get_drop_sources as _get_drop_sources,
    bucket_query,
    MONSTER_FIELDS,
)


@mcp.tool()
async def monster_info(monster_name: str) -> dict:
    """Get detailed stats for an OSRS monster/boss (combat level, HP, attack/defence stats, weaknesses, slayer info).

    Args:
        monster_name: The monster name (e.g. "Vorkath", "Abyssal demon", "General Graardor").
    """
    result = await _get_monster_info(monster_name)
    if result is None:
        return {"error": f"Monster '{monster_name}' not found. Try search_monsters for suggestions."}
    return result


@mcp.tool()
async def monster_drops(monster_name: str) -> list[dict]:
    """Get the drop table for a monster (item names that it drops).

    Args:
        monster_name: The monster name (e.g. "Vorkath", "Zulrah").
    """
    drops = await _get_monster_drops(monster_name)
    if not drops:
        return [{"error": f"No drops found for '{monster_name}'."}]
    return drops


@mcp.tool()
async def drop_sources(item_name: str) -> list[dict]:
    """Find all monsters/NPCs that drop a specific item.

    Args:
        item_name: The item name (e.g. "Abyssal whip", "Dragon bones", "Maple seed").
    """
    sources = await _get_drop_sources(item_name)
    if not sources:
        return [{"error": f"No drop sources found for '{item_name}'."}]
    return sources


@mcp.tool()
async def search_monsters(query: str) -> list[dict]:
    """Search for monsters by name.

    Args:
        query: Search text (e.g. "dragon", "demon", "boss").
    """
    results = await bucket_query(
        "infobox_monster",
        fields=["name", "combat_level", "hitpoints", "slayer_level", "slayer_category"],
        limit=500,
    )
    query_lower = query.lower()
    matches = [r for r in results if query_lower in r.get("name", "").lower()]
    # Deduplicate by name, keep first
    seen = set()
    deduped = []
    for m in matches:
        name = m.get("name", "")
        if name not in seen:
            seen.add(name)
            deduped.append(m)
    return deduped[:25]
