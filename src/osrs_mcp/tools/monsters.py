from osrs_mcp.server import mcp
from osrs_mcp.api.wiki_bucket import (
    get_monster_info as _get_monster_info,
    get_monster_drops as _get_monster_drops,
    get_drop_sources as _get_drop_sources,
    get_drop_sources_bulk as _get_drop_sources_bulk,
    bucket_query,
    MONSTER_FIELDS,
)
from osrs_mcp.util.categories import expand_category, list_categories


@mcp.tool()
async def monster_info(monster_name: str) -> dict:
    """Get detailed stats for an OSRS monster/boss (combat level, HP, attack/defence stats, weaknesses, slayer info).

    The response includes elemental_weakness and elemental_weakness_percent if applicable.
    Elemental weakness means using a matching standard spellbook spell (Strike/Bolt/Blast/Wave/Surge)
    grants +X% magic accuracy AND +X% magic damage, where X = elemental_weakness_percent.
    The four elements are Fire, Water, Earth, and Air. This does NOT affect melee/ranged, does NOT
    apply to powered staves (Trident, Tumeken's shadow), and does NOT apply to non-elemental spells
    (Ice Barrage, Flames of Zamorak, etc.). Dragon Hunter Lance/Crossbow bonuses are separate from
    elemental weakness — they are special effects that work against any dragon regardless of element.

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
async def drop_sources(item_name: str) -> list[dict] | dict:
    """Find all monsters/NPCs that drop a specific item, or search by category.

    Supports category keywords for bulk lookups:
    - "herb seeds" — all 14 herb seeds (Guam through Torstol)
    - "tree seeds" — Acorn, Willow, Maple, Yew, Magic, Spirit seeds
    - "fruit tree seeds" — Apple through Dragonfruit tree seeds
    - "rune items" — Death, Blood, Nature, Law, Soul, Wrath runes
    - "bolt tips" — Opal through Onyx bolt tips

    Also supports comma-separated items: "Ranarr seed, Snapdragon seed"

    For categories/multiple items, returns monsters sorted by how many of the
    queried items they drop (best sources first).

    Args:
        item_name: Item name, category keyword, or comma-separated item list.
    """
    items = expand_category(item_name)

    if len(items) == 1:
        # Single item: existing behavior
        sources = await _get_drop_sources(items[0])
        if not sources:
            return [{"error": f"No drop sources found for '{items[0]}'.",
                      "available_categories": list_categories()}]
        return sources

    # Multiple items / category: bulk lookup
    monster_items = await _get_drop_sources_bulk(items)
    if not monster_items:
        return [{"error": f"No drop sources found for '{item_name}'.",
                  "available_categories": list_categories()}]

    results = []
    for monster, matched_items in monster_items.items():
        results.append({
            "monster": monster,
            "drops_matched": len(matched_items),
            "items": matched_items,
        })
    return {
        "query": item_name,
        "items_searched": len(items),
        "monsters_found": len(results),
        "sources": results,
    }


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
