from osrs_mcp.server import mcp
from osrs_mcp.util.data import load_monsters

# Aliases: steve and kuradal are the same NPC slot as nieve
_MASTER_ALIASES = {
    "steve": "nieve",
    "kuradal": "nieve",
    "konar quo maten": "konar",
}


def _get_slayer_monsters(
    min_level: int = 1,
    max_level: int = 99,
    master: str = "",
) -> list[dict]:
    """Filter local monster data for slayer-assignable monsters.

    Returns monsters with slayer_category set, filtered by level range and master.
    """
    monsters = load_monsters()

    # Normalize master name
    master_lower = master.strip().lower()
    master_lower = _MASTER_ALIASES.get(master_lower, master_lower)

    results: list[dict] = []
    seen_names: set[str] = set()

    for _key, m in monsters.items():
        # Must have a slayer category (i.e. assignable as a task)
        if not m.get("slayer_category"):
            continue

        name = m.get("name", _key.title())
        # Deduplicate by name (some monsters have multiple variants)
        name_lower = name.lower()
        if name_lower in seen_names:
            continue
        seen_names.add(name_lower)

        slayer_level = m.get("slayer_level") or 1
        try:
            slayer_level = int(slayer_level)
        except (ValueError, TypeError):
            slayer_level = 1

        # Filter by level range
        if slayer_level < min_level or slayer_level > max_level:
            continue

        # Filter by master
        if master_lower:
            assigned_by = m.get("assigned_by", [])
            if isinstance(assigned_by, list):
                normalized = [_MASTER_ALIASES.get(a.lower(), a.lower()) for a in assigned_by]
            else:
                normalized = [_MASTER_ALIASES.get(str(assigned_by).lower(), str(assigned_by).lower())]
            if master_lower not in normalized:
                continue

        combat = m.get("combat_level")
        try:
            combat = int(combat) if combat is not None else None
        except (ValueError, TypeError):
            combat = None

        hitpoints = m.get("hitpoints")
        try:
            hitpoints = int(hitpoints) if hitpoints is not None else None
        except (ValueError, TypeError):
            hitpoints = None

        results.append({
            "name": name,
            "slayer_level": slayer_level,
            "combat_level": combat,
            "hitpoints": hitpoints,
            "slayer_category": m.get("slayer_category"),
            "assigned_by": m.get("assigned_by", []),
            "attribute": m.get("attribute"),
            "elemental_weakness": m.get("elemental_weakness"),
        })

    # Sort by slayer level then name
    results.sort(key=lambda x: (x["slayer_level"], x["name"]))
    return results


@mcp.tool()
async def slayer_unlocks(
    level: int = 0,
    username: str = "",
    master: str = "",
    min_level: int = 0,
    max_level: int = 0,
) -> dict:
    """Look up slayer monster unlocks by level, level range, or player account.

    ALWAYS use this tool instead of guessing slayer level requirements from memory.
    Training data frequently gets slayer levels wrong (e.g. Drakes are 84, not 70).

    Usage examples:
    - slayer_unlocks(level=65) — what unlocks at exactly slayer level 65
    - slayer_unlocks(min_level=40, max_level=60) — everything in a level range
    - slayer_unlocks(username="die tmo") — auto-fetch slayer level, show all unlocks
    - slayer_unlocks(username="die tmo", master="duradel") — filter by master too

    Args:
        level: Exact slayer level to check (what unlocks at this level).
        username: Player name — auto-fetches their slayer level and shows all unlocks up to it.
        master: Filter by slayer master (turael, mazchna, vannaka, chaeldar, nieve/steve, duradel, konar, krystilia).
        min_level: Minimum slayer level for range query.
        max_level: Maximum slayer level for range query.
    """
    # Resolve level from player if username given
    actual_min = min_level
    actual_max = max_level
    player_slayer_level = None

    if username:
        from osrs_mcp.api.hiscores import fetch_hiscores
        stats = await fetch_hiscores(username)
        if stats and "skills" in stats:
            slayer_data = stats["skills"].get("Slayer", {})
            player_slayer_level = slayer_data.get("level", 1)
            if not actual_max:
                actual_max = player_slayer_level
            if not actual_min:
                actual_min = 1

    if level and not actual_min and not actual_max:
        # Exact level query
        actual_min = level
        actual_max = level

    if not actual_min:
        actual_min = 1
    if not actual_max:
        actual_max = 99

    monsters = _get_slayer_monsters(
        min_level=actual_min,
        max_level=actual_max,
        master=master,
    )

    # Group by slayer level
    groups: dict[int, list[dict]] = {}
    for m in monsters:
        lvl = m["slayer_level"]
        groups.setdefault(lvl, []).append(m)

    response: dict = {
        "level_range": f"{actual_min}-{actual_max}",
        "total_monsters": len(monsters),
    }
    if player_slayer_level is not None:
        response["player_slayer_level"] = player_slayer_level
        response["username"] = username
    if master:
        response["master_filter"] = master

    response["unlocks_by_level"] = {
        str(lvl): group for lvl, group in sorted(groups.items())
    }

    return response
