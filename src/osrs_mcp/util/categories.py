"""Item category definitions for bulk lookups."""

ITEM_CATEGORIES: dict[str, list[str]] = {
    "herb seeds": [
        "Guam seed", "Marrentill seed", "Tarromin seed", "Harralander seed",
        "Ranarr seed", "Toadflax seed", "Irit seed", "Avantoe seed",
        "Kwuarm seed", "Snapdragon seed", "Cadantine seed", "Lantadyme seed",
        "Dwarf weed seed", "Torstol seed",
    ],
    "tree seeds": [
        "Acorn", "Willow seed", "Maple seed", "Yew seed",
        "Magic seed", "Spirit seed",
    ],
    "fruit tree seeds": [
        "Apple tree seed", "Banana tree seed", "Orange tree seed",
        "Curry tree seed", "Pineapple seed", "Papaya tree seed",
        "Palm tree seed", "Dragonfruit tree seed",
    ],
    "rune items": [
        "Death rune", "Blood rune", "Nature rune", "Law rune",
        "Soul rune", "Wrath rune",
    ],
    "bolt tips": [
        "Opal bolt tips", "Jade bolt tips", "Pearl bolt tips",
        "Topaz bolt tips", "Sapphire bolt tips", "Emerald bolt tips",
        "Ruby bolt tips", "Diamond bolt tips", "Dragonstone bolt tips",
        "Onyx bolt tips",
    ],
}


def expand_category(input_str: str) -> list[str]:
    """Expand a category name, comma-separated list, or single item into a list of items.

    - "herb seeds" -> 14 herb seed items
    - "Ranarr seed, Snapdragon seed" -> ["Ranarr seed", "Snapdragon seed"]
    - "Abyssal whip" -> ["Abyssal whip"]
    """
    lower = input_str.strip().lower()

    # Check category match
    if lower in ITEM_CATEGORIES:
        return ITEM_CATEGORIES[lower]

    # Check comma-separated list
    if "," in input_str:
        return [item.strip() for item in input_str.split(",") if item.strip()]

    # Single item
    return [input_str.strip()]


def list_categories() -> dict[str, int]:
    """Return category names with their item counts."""
    return {name: len(items) for name, items in ITEM_CATEGORIES.items()}
