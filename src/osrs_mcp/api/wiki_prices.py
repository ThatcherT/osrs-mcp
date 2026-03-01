from osrs_mcp.api.base import get_client
from osrs_mcp.cache import cache

PRICES_BASE = "https://prices.runescape.wiki/api/v1/osrs"


async def fetch_mapping() -> list[dict]:
    """Fetch item ID -> name mapping (cached 1 hour)."""
    cached = cache.get("prices:mapping")
    if cached is not None:
        return cached

    client = get_client()
    resp = await client.get(f"{PRICES_BASE}/mapping")
    resp.raise_for_status()
    data = resp.json()
    cache.set("prices:mapping", data, ttl=3600)
    return data


async def fetch_latest_prices() -> dict:
    """Fetch latest prices for all items."""
    cached = cache.get("prices:latest")
    if cached is not None:
        return cached

    client = get_client()
    resp = await client.get(f"{PRICES_BASE}/latest")
    resp.raise_for_status()
    data = resp.json().get("data", {})
    cache.set("prices:latest", data, ttl=60)
    return data


async def search_items_by_name(query: str) -> list[dict]:
    """Search items by name using the mapping endpoint."""
    mapping = await fetch_mapping()
    query_lower = query.lower()
    results = []
    for item in mapping:
        if query_lower in item.get("name", "").lower():
            results.append(item)
    return results[:25]


async def get_item_price(item_name: str) -> dict | None:
    """Get price for an item by name."""
    mapping = await fetch_mapping()
    # Find exact match first, then partial
    item_id = None
    item_meta = None
    name_lower = item_name.lower()

    for item in mapping:
        if item.get("name", "").lower() == name_lower:
            item_id = str(item["id"])
            item_meta = item
            break

    if item_id is None:
        for item in mapping:
            if name_lower in item.get("name", "").lower():
                item_id = str(item["id"])
                item_meta = item
                break

    if item_id is None:
        return None

    prices = await fetch_latest_prices()
    price_data = prices.get(item_id, {})

    return {
        "id": item_meta["id"],
        "name": item_meta["name"],
        "high": price_data.get("high"),
        "low": price_data.get("low"),
        "highTime": price_data.get("highTime"),
        "lowTime": price_data.get("lowTime"),
        "examine": item_meta.get("examine", ""),
        "highalch": item_meta.get("highalch"),
        "lowalch": item_meta.get("lowalch"),
        "buy_limit": item_meta.get("limit"),
        "members": item_meta.get("members", False),
    }
