from osrs_mcp.api.base import get_client
from osrs_mcp.cache import cache

WIKI_API = "https://oldschool.runescape.wiki/api.php"


def _build_query(bucket: str, fields: list[str], where: dict | None = None,
                 limit: int = 500, offset: int = 0) -> str:
    """Build a Bucket API query string."""
    parts = [f"bucket('{bucket}')"]
    if fields:
        field_str = ",".join(f"'{f}'" for f in fields)
        parts.append(f".select({field_str})")
    if where:
        for key, value in where.items():
            escaped = str(value).replace("'", "\\'")
            parts.append(f".where('{key}','{escaped}')")
    parts.append(f".limit({limit})")
    if offset > 0:
        parts.append(f".offset({offset})")
    parts.append(".run()")
    return "".join(parts)


async def bucket_query(bucket: str, fields: list[str], where: dict | None = None,
                       limit: int = 500, offset: int = 0,
                       cache_ttl: int = 300) -> list[dict]:
    """Execute a Bucket API query."""
    query = _build_query(bucket, fields, where, limit, offset)
    cache_key = f"bucket:{query}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = get_client()
    params = {
        "action": "bucket",
        "format": "json",
        "formatversion": "2",
        "query": query,
    }
    resp = await client.get(WIKI_API, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data and isinstance(data["error"], str):
        return []

    results = data.get("bucket", [])
    cache.set(cache_key, results, ttl=cache_ttl)
    return results


async def bucket_query_all(bucket: str, fields: list[str], where: dict | None = None,
                           cache_ttl: int = 300) -> list[dict]:
    """Execute a Bucket API query, paginating to get all results."""
    all_results = []
    offset = 0
    while True:
        page = await bucket_query(bucket, fields, where, limit=5000, offset=offset,
                                  cache_ttl=cache_ttl)
        all_results.extend(page)
        if len(page) < 5000:
            break
        offset += 5000
    return all_results


async def bucket_join_query(primary: str, secondary: str,
                            join_left: str, join_right: str,
                            fields: list[str], where: dict | None = None,
                            limit: int = 500, cache_ttl: int = 300) -> list[dict]:
    """Execute a Bucket API join query."""
    field_str = ",".join(f"'{f}'" for f in fields)
    where_parts = ""
    if where:
        for key, value in where.items():
            escaped = str(value).replace("'", "\\'")
            where_parts += f".where('{key}','{escaped}')"

    query = (f"bucket('{primary}')"
             f".join('{secondary}','{join_left}','{join_right}')"
             f".select({field_str})"
             f"{where_parts}"
             f".limit({limit}).run()")

    cache_key = f"bucket_join:{query}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = get_client()
    params = {
        "action": "bucket",
        "format": "json",
        "formatversion": "2",
        "query": query,
    }
    resp = await client.get(WIKI_API, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data and isinstance(data["error"], str):
        return []

    results = data.get("bucket", [])
    cache.set(cache_key, results, ttl=cache_ttl)
    return results


# === Actual field names verified against the live API ===
# infobox_item: page_name, page_name_sub, examine, weight, quest, tradeable,
#               value, buy_limit, item_id, image
# infobox_bonuses: page_name, page_name_sub, combat_style, prayer_bonus,
#                  stab_attack_bonus, slash_attack_bonus, crush_attack_bonus,
#                  range_attack_bonus, magic_attack_bonus,
#                  stab_defence_bonus, slash_defence_bonus, crush_defence_bonus,
#                  range_defence_bonus, magic_defence_bonus,
#                  ranged_strength_bonus, magic_damage_bonus, strength_bonus,
#                  equipment_slot
# infobox_monster: page_name, page_name_sub, name, combat_level, hitpoints,
#                  attack_level, strength_level, defence_level, ranged_level,
#                  magic_level, attack_bonus, strength_bonus, magic_attack_bonus,
#                  stab_defence_bonus, slash_defence_bonus, crush_defence_bonus,
#                  range_defence_bonus, magic_defence_bonus, max_hit,
#                  slayer_level, slayer_experience, slayer_category, assigned_by,
#                  attack_style, attack_speed, size, attribute,
#                  poison_immune, venom_immune, elemental_weakness,
#                  elemental_weakness_percent, flat_armour, freeze_resistance, id
# dropsline: page_name, page_name_sub, item_name (limited - no rarity/quantity)
# infobox_spell: page_name, page_name_sub, spellbook

ITEM_FIELDS = [
    "page_name_sub", "examine", "weight", "quest", "tradeable",
    "value", "buy_limit", "item_id",
]

BONUSES_FIELDS = [
    "page_name_sub", "stab_attack_bonus", "slash_attack_bonus",
    "crush_attack_bonus", "range_attack_bonus", "magic_attack_bonus",
    "stab_defence_bonus", "slash_defence_bonus", "crush_defence_bonus",
    "range_defence_bonus", "magic_defence_bonus",
    "strength_bonus", "ranged_strength_bonus", "magic_damage_bonus",
    "prayer_bonus", "equipment_slot", "combat_style",
]

MONSTER_FIELDS = [
    "name", "combat_level", "hitpoints", "max_hit",
    "attack_level", "strength_level", "defence_level",
    "ranged_level", "magic_level",
    "attack_bonus", "strength_bonus", "magic_attack_bonus",
    "stab_defence_bonus", "slash_defence_bonus", "crush_defence_bonus",
    "range_defence_bonus", "magic_defence_bonus",
    "slayer_level", "slayer_experience", "slayer_category",
    "assigned_by", "attack_style", "attack_speed",
    "size", "attribute",
    "poison_immune", "venom_immune",
    "elemental_weakness", "elemental_weakness_percent",
    "flat_armour", "freeze_resistance",
]


async def get_item_info(item_name: str) -> dict | None:
    """Get item info from infobox_item joined with infobox_bonuses."""
    # Try joined query first (for equipment)
    join_fields = [f"infobox_item.{f}" for f in ITEM_FIELDS] + \
                  [f"infobox_bonuses.{f}" for f in BONUSES_FIELDS if f != "page_name_sub"]

    results = await bucket_join_query(
        "infobox_item", "infobox_bonuses",
        "infobox_item.page_name_sub", "infobox_bonuses.page_name_sub",
        fields=join_fields,
        where={"infobox_item.page_name_sub": item_name},
        limit=5,
    )
    if results:
        return _flatten_result(results[0])

    # Fall back to item-only query (non-equipment items)
    results = await bucket_query(
        "infobox_item",
        fields=ITEM_FIELDS,
        where={"page_name_sub": item_name},
        limit=5,
    )
    return results[0] if results else None


async def get_monster_info(monster_name: str) -> dict | None:
    """Get monster info from infobox_monster. Returns highest combat level version."""
    results = await bucket_query(
        "infobox_monster",
        fields=MONSTER_FIELDS,
        where={"name": monster_name},
        limit=10,
    )
    if not results:
        return None
    # Return the version with the highest combat level (boss version, not quest)
    best = results[0]
    for r in results[1:]:
        try:
            if int(r.get("combat_level") or 0) > int(best.get("combat_level") or 0):
                best = r
        except (ValueError, TypeError):
            pass
    return best


async def get_monster_drops(monster_name: str) -> list[dict]:
    """Get drop table for a monster (item names only - rarity not available via bucket)."""
    return await bucket_query(
        "dropsline",
        fields=["item_name"],
        where={"page_name": monster_name},
        limit=500,
    )


async def get_drop_sources(item_name: str) -> list[dict]:
    """Get all monsters that drop an item."""
    return await bucket_query(
        "dropsline",
        fields=["page_name"],
        where={"item_name": item_name},
        limit=500,
    )


async def get_quest_info(quest_name: str) -> dict | None:
    """Get quest details. Note: bucket has limited fields, falls back to wiki parse."""
    results = await bucket_query(
        "quest",
        fields=["page_name_sub", "start_point", "official_difficulty"],
        where={"page_name_sub": quest_name},
        limit=5,
    )
    return results[0] if results else None


async def get_money_making_methods(skill: str | None = None,
                                    min_profit: int | None = None) -> list[dict]:
    """Get money making method names from bucket (profit data requires wiki parse)."""
    results = await bucket_query(
        "money_making_guide",
        fields=["page_name_sub"],
        limit=500,
    )
    return results[:50]


async def get_boss_info(boss_name: str) -> dict:
    """Get comprehensive boss info including stats."""
    monster = await get_monster_info(boss_name)
    drops = await get_monster_drops(boss_name)

    return {
        "monster": monster,
        "drops": drops[:30],
    }


def _flatten_result(row: dict) -> dict:
    """Flatten prefixed field names (e.g. 'infobox_item.examine' -> 'examine')."""
    flat = {}
    for key, val in row.items():
        short = key.split(".")[-1] if "." in key else key
        flat[short] = val
    return flat
