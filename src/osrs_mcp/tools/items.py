from osrs_mcp.server import mcp
from osrs_mcp.api.wiki_bucket import get_item_info
from osrs_mcp.api.wiki_prices import search_items_by_name, get_item_price, fetch_latest_prices


@mcp.tool()
async def item_info(item_name: str) -> dict:
    """Get detailed information about an OSRS item including stats, bonuses, and current GE price.

    Args:
        item_name: The item name (e.g. "Abyssal whip", "Dragon scimitar").
    """
    info = await get_item_info(item_name)
    if info is None:
        return {"error": f"Item '{item_name}' not found. Try search_items for suggestions."}

    # Also fetch price if tradeable
    price = await get_item_price(item_name)
    if price:
        info["ge_price_high"] = price.get("high")
        info["ge_price_low"] = price.get("low")
        info["buy_limit"] = price.get("buy_limit")

    return info


@mcp.tool()
async def search_items(query: str) -> list[dict]:
    """Search for OSRS items by name. Returns matching items with IDs and basic info.

    Args:
        query: Search text (e.g. "dragon", "whip", "rune platebody").
    """
    return await search_items_by_name(query)


@mcp.tool()
async def item_price(item_name: str) -> dict:
    """Get the current Grand Exchange price for an item.

    Args:
        item_name: The item name (e.g. "Abyssal whip").
    """
    result = await get_item_price(item_name)
    if result is None:
        return {"error": f"Item '{item_name}' not found in GE."}
    return result
