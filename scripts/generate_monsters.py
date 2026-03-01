#!/usr/bin/env python3
"""Fetch all monsters with combat stats from the Wiki Bucket API."""
import asyncio
import json
from pathlib import Path

import httpx

WIKI_API = "https://oldschool.runescape.wiki/api.php"
USER_AGENT = "osrs-mcp/0.1.0 - monster data generator"
OUTPUT = Path(__file__).parent.parent / "data" / "monsters.json"

# Verified field names for infobox_monster
FIELDS = [
    "name", "combat_level", "hitpoints", "max_hit",
    "attack_level", "strength_level", "defence_level",
    "ranged_level", "magic_level",
    "attack_bonus", "strength_bonus", "magic_attack_bonus",
    "stab_defence_bonus", "slash_defence_bonus", "crush_defence_bonus",
    "range_defence_bonus", "magic_defence_bonus",
    "slayer_level", "slayer_experience", "slayer_category",
    "assigned_by", "attack_style", "attack_speed",
    "size", "attribute",
    "elemental_weakness", "elemental_weakness_percent",
    "flat_armour", "freeze_resistance",
]


async def fetch_page(client: httpx.AsyncClient, offset: int) -> list[dict]:
    field_str = ",".join(f"'{f}'" for f in FIELDS)
    query = (
        f"bucket('infobox_monster')"
        f".select({field_str})"
        f".limit(5000).offset({offset}).run()"
    )
    resp = await client.get(WIKI_API, params={
        "action": "bucket", "format": "json", "formatversion": "2", "query": query,
    })
    resp.raise_for_status()
    data = resp.json()
    if "error" in data and isinstance(data["error"], str):
        print(f"  API error: {data['error']}")
        return []
    return data.get("bucket", [])


async def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    all_monsters = []
    offset = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=60.0
    ) as client:
        while True:
            print(f"Fetching offset {offset}...")
            page = await fetch_page(client, offset)
            all_monsters.extend(page)
            print(f"  Got {len(page)} monsters (total: {len(all_monsters)})")
            if len(page) < 5000:
                break
            offset += 5000

    # Index by name (lowercase) for fast lookup
    # Map API field names to DPS calc field names
    field_map = {
        "stab_defence_bonus": "dstab",
        "slash_defence_bonus": "dslash",
        "crush_defence_bonus": "dcrush",
        "range_defence_bonus": "drange",
        "magic_defence_bonus": "dmagic",
    }

    monsters = {}
    for m in all_monsters:
        name = m.get("name")
        if not name:
            continue

        # Parse numeric fields
        for field in FIELDS:
            if field in m and m[field] is not None:
                try:
                    m[field] = int(m[field])
                except (ValueError, TypeError):
                    pass

        # Add short defence field names for DPS calc compatibility
        for long_name, short_name in field_map.items():
            if long_name in m:
                m[short_name] = m[long_name]

        key = name.lower()
        # Keep highest combat level version if dupes
        if key not in monsters or (m.get("combat_level") or 0) > (monsters[key].get("combat_level") or 0):
            monsters[key] = m

    with open(OUTPUT, "w") as f:
        json.dump(monsters, f, separators=(",", ":"))

    print(f"Wrote {len(monsters)} monsters to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
