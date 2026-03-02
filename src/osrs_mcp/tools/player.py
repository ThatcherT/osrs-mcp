from osrs_mcp.server import mcp
from osrs_mcp.config import get_config
from osrs_mcp.api.hiscores import fetch_hiscores, detect_account_type
from osrs_mcp.api.wiseoldman import fetch_player_gains
from osrs_mcp.api.runelite_bank import get_bank, get_account_profiles
from osrs_mcp.util.data import load_equipment


def _resolve_username(username: str | None) -> str:
    if username:
        return username
    cfg = get_config()
    if cfg.username:
        return cfg.username
    raise ValueError("No username provided and none configured in config.json")


@mcp.tool()
async def player_stats(username: str = "") -> dict:
    """Get a player's skills, levels, XP, and boss kill counts from the OSRS Hiscores.

    Also detects account type (normal, ironman, hardcore, ultimate).
    IMPORTANT: Ironman/hardcore/ultimate/group_ironman accounts cannot use the Grand Exchange
    or trade with other players (group ironmen can only trade within their group).
    Never suggest buying items from the GE for these accounts.
    All gear must be obtained as drops, crafted, or from shops.

    Args:
        username: RuneScape username. Leave empty to use configured default.
    """
    name = _resolve_username(username or None)
    return await fetch_hiscores(name)


@mcp.tool()
async def player_gains(username: str = "", period: str = "week") -> dict:
    """Get a player's XP gains and boss KC gains over a time period via Wise Old Man.

    Args:
        username: RuneScape username. Leave empty to use configured default.
        period: Time period - one of: day, week, month, year, 6h, 5min.
    """
    name = _resolve_username(username or None)
    return await fetch_player_gains(name, period)


_BONUS_KEYS = ("astab", "aslash", "acrush", "arange", "amagic",
                "dstab", "dslash", "dcrush", "drange", "dmagic",
                "str", "rstr", "mdmg", "prayer")


def _enrich_bank_item(item: dict, equipment: dict) -> dict:
    """Add equipment slot and combat bonuses to a bank item if it's equipment.

    For charged/degradeable items (e.g. Crystal shield, Sanguinesti staff) the
    base name often has all-zero stats while the ``name#active`` variant holds
    the real combat bonuses.  When the base item has no offensive/defensive
    stats we fall back to the ``#active`` variant automatically.
    """
    name_lower = item["name"].lower()
    equip = equipment.get(name_lower)
    if equip is None:
        return item

    slot = equip.get("slot")
    if not slot:
        return item

    # If the base item has all-zero combat stats, try the #active variant
    has_stats = any(equip.get(k) for k in _BONUS_KEYS)
    if not has_stats:
        active = equipment.get(f"{name_lower}#active")
        if active and active.get("slot"):
            equip = active

    item = dict(item)
    item["slot"] = slot

    # Only add bonuses that are non-zero
    bonuses = {}
    for key in _BONUS_KEYS:
        val = equip.get(key)
        if val and val != 0:
            bonuses[key] = val
    speed = equip.get("speed")
    if speed:
        bonuses["speed"] = speed

    if bonuses:
        item["bonuses"] = bonuses
    else:
        item["bonuses"] = "none (no combat stats)"

    return item


_STAT_ALIASES = {
    # Friendly names -> bonus key
    "melee strength": "str", "melee str": "str", "strength": "str",
    "ranged strength": "rstr", "ranged str": "rstr",
    "magic damage": "mdmg", "magic str": "mdmg",
    "stab attack": "astab", "stab": "astab",
    "slash attack": "aslash", "slash": "aslash",
    "crush attack": "acrush", "crush": "acrush",
    "ranged attack": "arange", "ranged": "arange", "range": "arange",
    "magic attack": "amagic", "magic": "amagic",
    "prayer": "prayer",
    # Direct keys work too
    "astab": "astab", "aslash": "aslash", "acrush": "acrush",
    "arange": "arange", "amagic": "amagic",
    "str": "str", "rstr": "rstr", "mdmg": "mdmg",
}

_SLOT_ORDER = ["head", "cape", "neck", "body", "legs", "feet", "hands",
               "shield", "weapon", "2h", "ammo", "ring"]


def _best_per_slot(items_by_slot: dict[str, list[dict]], stat: str) -> dict:
    """For each slot, find the single best item for the given stat.

    Returns the item with the highest value for ``stat`` in each slot,
    even if all values are negative (the least-negative item wins).
    Only skips a slot if it has no items with valid bonuses at all.
    """
    result = {}
    for slot in _SLOT_ORDER:
        items = items_by_slot.get(slot, [])
        best = None
        best_val = None
        for item in items:
            bonuses = item.get("bonuses", {})
            if not isinstance(bonuses, dict):
                continue
            val = bonuses.get(stat, 0)
            if best_val is None or val > best_val:
                best_val = val
                best = item
        if best is not None:
            result[slot] = {"name": best["name"], stat: best_val,
                            "bonuses": best["bonuses"]}
    return result


@mcp.tool()
async def player_gear(username: str = "", optimize: str = "") -> dict:
    """Get a player's best available gear from their bank, optimized for a specific stat.

    When optimize is set, returns the single best item per equipment slot for that
    stat — this is exactly what you need to build a gear loadout for a boss.

    When optimize is empty, returns a summary of the best item per slot for each
    common combat stat (melee str, slash, ranged, magic, prayer) so you can see
    what loadouts are available at a glance.

    Common optimize values:
      "str" or "melee strength" — max melee hit (e.g. low-def bosses like Scurrius)
      "aslash" or "slash" — max slash accuracy (e.g. Vardorvis, weak to slash)
      "acrush" or "crush" — max crush accuracy (e.g. Gargoyles, Kalphite Queen)
      "arange" or "ranged" — max ranged accuracy
      "rstr" or "ranged strength" — max ranged damage
      "amagic" or "magic" — max magic accuracy
      "prayer" — max prayer bonus

    Only includes items in the bank — equipped/inventory items won't appear.
    If key items seem missing, the player may need to bank them and re-open
    their bank with Quest Helper enabled.

    Args:
        username: RuneScape username. Leave empty to use configured default.
        optimize: Stat to optimize for. See common values above. Leave empty for overview.
    """
    name = _resolve_username(username or None)
    bank = await get_bank(name)
    if bank is None:
        profiles = get_account_profiles()
        available = [p["display_name"] for p in profiles]
        return {
            "error": f"No bank data found for '{name}'.",
            "available_accounts": available,
        }

    equipment = load_equipment()
    enriched = [_enrich_bank_item(item, equipment) for item in bank]

    from collections import defaultdict
    by_slot: dict[str, list[dict]] = defaultdict(list)
    for item in enriched:
        slot = item.get("slot")
        if slot and isinstance(item.get("bonuses"), dict):
            by_slot[slot].append(item)

    account_type = await detect_account_type(name)

    if optimize:
        stat = _STAT_ALIASES.get(optimize.lower().strip(), optimize.lower().strip())
        loadout = _best_per_slot(dict(by_slot), stat)
        return {
            "username": name,
            "account_type": account_type,
            "optimized_for": stat,
            "loadout": loadout,
            "note": f"Best item per slot for {stat}. "
                    "Items in inventory/equipped won't appear — bank them first.",
        }

    # Overview mode: show best per slot for key stats
    overview_stats = [
        ("str", "melee strength"),
        ("aslash", "slash attack"),
        ("acrush", "crush attack"),
        ("astab", "stab attack"),
        ("arange", "ranged attack"),
        ("rstr", "ranged strength"),
        ("amagic", "magic attack"),
        ("mdmg", "magic damage"),
        ("prayer", "prayer"),
    ]
    overview = {}
    for stat_key, label in overview_stats:
        loadout = _best_per_slot(dict(by_slot), stat_key)
        if loadout:
            # Compact: just name and value per slot
            compact = {slot: {"name": v["name"], stat_key: v[stat_key]}
                       for slot, v in loadout.items()}
            overview[label] = compact

    return {
        "username": name,
        "account_type": account_type,
        "best_by_stat": overview,
        "note": "Overview of best available item per slot for each combat stat. "
                "Use optimize param for a full loadout for a specific stat. "
                "Items in inventory/equipped won't appear — bank them first.",
    }


@mcp.tool()
async def player_bank(username: str = "", search: str = "") -> dict:
    """Read a player's bank contents from local RuneLite data.

    Reads cached bank data from RuneLite's Quest Helper plugin. The data is
    updated each time the player opens their bank in-game with Quest Helper
    enabled. Returns item names, IDs, quantities, and for equipment items,
    the slot and actual combat bonuses. If bonuses is "none (no combat stats)"
    the item is equippable but provides zero offensive or defensive stats —
    do NOT describe it as defensive or offensive.

    Args:
        username: RuneScape username. Leave empty to use configured default.
        search: Optional search filter — only return items containing this text.
    """
    name = _resolve_username(username or None)
    bank = await get_bank(name)
    if bank is None:
        profiles = get_account_profiles()
        available = [p["display_name"] for p in profiles]
        return {
            "error": f"No bank data found for '{name}'. "
                     f"Make sure Quest Helper is enabled and you've opened your bank in-game.",
            "available_accounts": available,
        }

    if search:
        search_lower = search.lower()
        bank = [item for item in bank if search_lower in item["name"].lower()]

    # Enrich with equipment data and account type
    equipment = load_equipment()
    bank = [_enrich_bank_item(item, equipment) for item in bank]
    account_type = await detect_account_type(name)

    total_items = sum(item["quantity"] for item in bank)
    return {
        "username": name,
        "account_type": account_type,
        "unique_items": len(bank),
        "total_items": total_items,
        "items": bank[:200],  # Cap at 200 to avoid huge responses
        "note": "Bank data from RuneLite Quest Helper cache. Updated when bank is opened in-game."
             + (f" Showing top 200 of {len(bank)} matching items." if len(bank) > 200 else ""),
    }
