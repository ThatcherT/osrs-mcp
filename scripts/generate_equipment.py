#!/usr/bin/env python3
"""Fetch all equipment items with combat bonuses from the Wiki Bucket API."""
import asyncio
import json
from pathlib import Path

import httpx

WIKI_API = "https://oldschool.runescape.wiki/api.php"
USER_AGENT = "osrs-mcp/0.1.0 - equipment data generator"
OUTPUT = Path(__file__).parent.parent / "data" / "equipment.json"

# Verified field names for infobox_item
ITEM_FIELDS = ["infobox_item.page_name_sub", "infobox_item.item_id", "infobox_item.examine"]

# Verified field names for infobox_bonuses
BONUSES_FIELDS = [
    "infobox_bonuses.stab_attack_bonus", "infobox_bonuses.slash_attack_bonus",
    "infobox_bonuses.crush_attack_bonus", "infobox_bonuses.range_attack_bonus",
    "infobox_bonuses.magic_attack_bonus",
    "infobox_bonuses.stab_defence_bonus", "infobox_bonuses.slash_defence_bonus",
    "infobox_bonuses.crush_defence_bonus", "infobox_bonuses.range_defence_bonus",
    "infobox_bonuses.magic_defence_bonus",
    "infobox_bonuses.strength_bonus", "infobox_bonuses.ranged_strength_bonus",
    "infobox_bonuses.magic_damage_bonus", "infobox_bonuses.prayer_bonus",
    "infobox_bonuses.equipment_slot", "infobox_bonuses.combat_style",
]

ALL_FIELDS = ITEM_FIELDS + BONUSES_FIELDS


async def fetch_page(client: httpx.AsyncClient, offset: int) -> list[dict]:
    field_str = ",".join(f"'{f}'" for f in ALL_FIELDS)
    query = (
        f"bucket('infobox_item')"
        f".join('infobox_bonuses','infobox_item.page_name_sub','infobox_bonuses.page_name_sub')"
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
    all_items = []
    offset = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=60.0
    ) as client:
        while True:
            print(f"Fetching offset {offset}...")
            page = await fetch_page(client, offset)
            all_items.extend(page)
            print(f"  Got {len(page)} items (total: {len(all_items)})")
            if len(page) < 5000:
                break
            offset += 5000

    # Index by item name (lowercase) for fast lookup
    equipment = {}
    for item in all_items:
        name = item.get("infobox_item.page_name_sub")
        if not name:
            continue

        # Extract item_id (may be a list)
        raw_id = item.get("infobox_item.item_id")
        if isinstance(raw_id, list):
            item_id = raw_id[0] if raw_id else None
        else:
            item_id = raw_id

        flat = {"name": name}
        if item_id:
            try:
                flat["id"] = int(item_id)
            except (ValueError, TypeError):
                flat["id"] = item_id

        # Map bonuses fields to short names for DPS calc
        field_map = {
            "infobox_bonuses.stab_attack_bonus": "astab",
            "infobox_bonuses.slash_attack_bonus": "aslash",
            "infobox_bonuses.crush_attack_bonus": "acrush",
            "infobox_bonuses.range_attack_bonus": "arange",
            "infobox_bonuses.magic_attack_bonus": "amagic",
            "infobox_bonuses.stab_defence_bonus": "dstab",
            "infobox_bonuses.slash_defence_bonus": "dslash",
            "infobox_bonuses.crush_defence_bonus": "dcrush",
            "infobox_bonuses.range_defence_bonus": "drange",
            "infobox_bonuses.magic_defence_bonus": "dmagic",
            "infobox_bonuses.strength_bonus": "str",
            "infobox_bonuses.ranged_strength_bonus": "rstr",
            "infobox_bonuses.magic_damage_bonus": "mdmg",
            "infobox_bonuses.prayer_bonus": "prayer",
            "infobox_bonuses.equipment_slot": "slot",
            "infobox_bonuses.combat_style": "combatstyle",
        }

        for long_name, short_name in field_map.items():
            val = item.get(long_name)
            if val is not None:
                try:
                    flat[short_name] = int(val)
                except (ValueError, TypeError):
                    flat[short_name] = val

        equipment[name.lower()] = flat

    with open(OUTPUT, "w") as f:
        json.dump(equipment, f, separators=(",", ":"))

    print(f"Wrote {len(equipment)} equipment items to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
