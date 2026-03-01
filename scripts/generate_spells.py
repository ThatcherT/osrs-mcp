#!/usr/bin/env python3
"""Fetch all spells from the Wiki Bucket API."""
import asyncio
import json
from pathlib import Path

import httpx

WIKI_API = "https://oldschool.runescape.wiki/api.php"
USER_AGENT = "osrs-mcp/0.1.0 - spell data generator"
OUTPUT = Path(__file__).parent.parent / "data" / "spells.json"

# Verified field names for infobox_spell (very limited in bucket API)
FIELDS = ["page_name_sub", "spellbook"]


async def fetch_page(client: httpx.AsyncClient, offset: int) -> list[dict]:
    field_str = ",".join(f"'{f}'" for f in FIELDS)
    query = (
        f"bucket('infobox_spell')"
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


# Hardcoded spell max hits since the bucket API doesn't have them
SPELL_MAX_HITS = {
    "wind strike": 2, "water strike": 4, "earth strike": 6, "fire strike": 8,
    "wind bolt": 9, "water bolt": 10, "earth bolt": 11, "fire bolt": 12,
    "wind blast": 13, "water blast": 14, "earth blast": 15, "fire blast": 16,
    "wind wave": 17, "water wave": 18, "earth wave": 19, "fire wave": 20,
    "wind surge": 21, "water surge": 22, "earth surge": 23, "fire surge": 24,
    "iban blast": 25, "magic dart": 19, "flames of zamorak": 20,
    "claws of guthix": 20, "saradomin strike": 20,
    "ice barrage": 30, "blood barrage": 29, "shadow barrage": 28, "smoke barrage": 27,
    "ice blitz": 26, "blood blitz": 25, "shadow blitz": 24, "smoke blitz": 23,
    "ice burst": 22, "blood burst": 21, "shadow burst": 18, "smoke burst": 17,
    "ice rush": 18, "blood rush": 17, "shadow rush": 16, "smoke rush": 15,
}


async def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    all_spells = []
    offset = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT}, timeout=60.0
    ) as client:
        while True:
            print(f"Fetching offset {offset}...")
            page = await fetch_page(client, offset)
            all_spells.extend(page)
            print(f"  Got {len(page)} spells (total: {len(all_spells)})")
            if len(page) < 5000:
                break
            offset += 5000

    # Index by name
    spells = {}
    for s in all_spells:
        name = s.get("page_name_sub")
        if name:
            entry = {
                "name": name,
                "spellbook": s.get("spellbook", ""),
            }
            # Add max hit from our lookup
            max_hit = SPELL_MAX_HITS.get(name.lower())
            if max_hit:
                entry["max_hit"] = max_hit
            spells[name.lower()] = entry

    with open(OUTPUT, "w") as f:
        json.dump(spells, f, separators=(",", ":"))

    print(f"Wrote {len(spells)} spells to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
