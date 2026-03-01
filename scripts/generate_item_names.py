#!/usr/bin/env python3
"""Fetch all item IDs and names from the Wiki Bucket API for bank name resolution.

This generates a comprehensive id->name map that includes untradeables,
quest items, noted variants, and everything else the prices API doesn't cover.
"""
import asyncio
import json
from pathlib import Path

import httpx

WIKI_API = "https://oldschool.runescape.wiki/api.php"
USER_AGENT = "osrs-mcp/0.1.0 - item name generator"
OUTPUT = Path(__file__).parent.parent / "data" / "item_names.json"


async def fetch_page(client: httpx.AsyncClient, offset: int) -> list[dict]:
    query = (
        f"bucket('infobox_item')"
        f".select('page_name_sub','item_id')"
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

    # Build id -> name map (int keys as strings for JSON)
    id_map = {}
    for item in all_items:
        raw_id = item.get("item_id")
        name = item.get("page_name_sub")
        if raw_id is None or not name:
            continue
        # item_id can be a list (e.g. ['10828']) or a scalar
        ids = raw_id if isinstance(raw_id, list) else [raw_id]
        # Strip variant suffixes like #New, #Half for cleaner names
        clean = name.split("#")[0] if "#" in name else name
        for rid in ids:
            try:
                iid = int(rid)
                if str(iid) not in id_map:
                    id_map[str(iid)] = clean
            except (ValueError, TypeError):
                pass

    # Add well-known items that might not be in the bucket
    id_map.setdefault("995", "Coins")
    id_map.setdefault("6529", "Tokkul")

    with open(OUTPUT, "w") as f:
        json.dump(id_map, f, separators=(",", ":"))

    print(f"\nWrote {len(id_map)} item names to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main())
