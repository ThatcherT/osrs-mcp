"""Lazy loaders for pre-generated static JSON data files."""
import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"


# Variant suffixes in order of preference for base-name fallback.
# If "karil's leathertop" is looked up, prefer the #100 or #undamaged variant.
_PREFERRED_VARIANTS = ("#undamaged", "#100")


@lru_cache(maxsize=1)
def load_equipment() -> dict:
    """Load equipment.json keyed by lowercase item name.

    Items with variant suffixes (e.g. "karil's leathertop#100") also get
    registered under their base name ("karil's leathertop") so bank items
    can be matched without knowing the charge/variant state.
    """
    path = DATA_DIR / "equipment.json"
    if not path.exists():
        return {}
    with open(path) as f:
        raw = json.load(f)

    # Build base-name fallbacks for variant items
    # Collect all variants per base name, then pick the best one
    base_candidates: dict[str, list[tuple[str, dict]]] = {}
    for key, val in raw.items():
        if "#" in key:
            base = key.split("#")[0]
            if base not in raw:  # Don't override an exact entry
                base_candidates.setdefault(base, []).append((key, val))

    for base, candidates in base_candidates.items():
        # Pick preferred variant
        best = None
        for pref in _PREFERRED_VARIANTS:
            for cand_key, cand_val in candidates:
                if cand_key.endswith(pref):
                    best = cand_val
                    break
            if best:
                break
        if best is None:
            best = candidates[0][1]  # Fall back to first found
        raw[base] = best

    return raw


@lru_cache(maxsize=1)
def load_monsters() -> dict:
    """Load monsters.json keyed by lowercase monster name."""
    path = DATA_DIR / "monsters.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_spells() -> dict:
    """Load spells.json keyed by lowercase spell name."""
    path = DATA_DIR / "spells.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def find_equipment_by_name(name: str) -> dict | None:
    """Find equipment by name (case-insensitive). Adds weapon speed if known."""
    equipment = load_equipment()
    name_lower = name.lower()
    item = equipment.get(name_lower)
    if item is None:
        # Also try scanning values
        for v in equipment.values():
            if v.get("name", "").lower() == name_lower:
                item = v
                break
    if item is not None and "speed" not in item:
        speed = get_weapon_speed(item.get("name", ""), item.get("combatstyle", ""))
        if speed:
            item = dict(item)
            item["speed"] = speed
    return item


def find_monster_by_name(name: str) -> dict | None:
    """Find monster by name (case-insensitive)."""
    monsters = load_monsters()
    return monsters.get(name.lower())


# Weapon speed by combat style / weapon type (ticks)
# 4 ticks = standard, 5 = slow, 6 = very slow, 3 = fast
WEAPON_SPEEDS = {
    # Combat style -> default speed
    "whip": 4, "stab sword": 4, "slash sword": 4, "scimitar": 4,
    "mace": 4, "spear": 4, "hasta": 4, "halberd": 5,
    "2h sword": 6, "godsword": 6, "battleaxe": 6, "warhammer": 6,
    "pickaxe": 5, "axe": 5, "claws": 4, "dagger": 4,
    "crossbow": 5, "bow": 4, "thrown": 3, "chinchompa": 3,
    "powered staff": 4, "trident": 4, "staff": 5,
    "blowpipe": 3, "ballista": 6,
}

# Specific overrides by item name
WEAPON_SPEED_OVERRIDES = {
    "abyssal whip": 4, "ghrazi rapier": 4, "blade of saeldor": 4,
    "inquisitor's mace": 4, "abyssal tentacle": 4,
    "scythe of vitur": 5, "toxic blowpipe": 3,
    "twisted bow": 5, "armadyl crossbow": 5, "dragon crossbow": 5,
    "zaryte crossbow": 5, "dragon hunter crossbow": 5,
    "toxic staff of the dead": 4, "sanguinesti staff": 4,
    "tumeken's shadow": 5, "trident of the swamp": 4,
    "trident of the seas": 4, "harmonised nightmare staff": 4,
    "dragon hunter lance": 4, "osmumten's fang": 5,
    "saeldor shard": 4,
    "dragon claws": 4, "bandos godsword": 6, "armadyl godsword": 6,
    "zamorak godsword": 6, "saradomin godsword": 6,
    "elder maul": 6, "dragon warhammer": 6,
}


def get_weapon_speed(name: str, combat_style: str) -> int | None:
    """Get weapon attack speed in ticks."""
    name_lower = name.lower()
    if name_lower in WEAPON_SPEED_OVERRIDES:
        return WEAPON_SPEED_OVERRIDES[name_lower]
    style_lower = combat_style.lower() if combat_style else ""
    if style_lower in WEAPON_SPEEDS:
        return WEAPON_SPEEDS[style_lower]
    return None
