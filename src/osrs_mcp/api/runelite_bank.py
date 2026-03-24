"""Read bank contents from RuneLite's local profile data.

RuneLite's Quest Helper plugin stores bank contents in the rsprofile
properties file as itemId,quantity pairs. This module reads that data
and resolves item IDs to names using the prices API mapping.

Supports multiple RuneLite data locations:
- Standalone RuneLite (AppImage): ~/.runelite/
- Jagex Launcher (flatpak): ~/.var/app/com.jagexlauncher.JagexLauncher/data/user_home/.runelite/
- Jagex Launcher (older flatpak): ~/.var/app/com.jagex.Launcher/.runelite/
"""
import re
from pathlib import Path

import json as _json

from osrs_mcp.api.wiki_prices import fetch_mapping
from osrs_mcp.cache import cache

# Pre-generated comprehensive item name map (includes untradeables)
_ITEM_NAMES_FILE = Path(__file__).parent.parent.parent.parent / "data" / "item_names.json"

# All known RuneLite profile directories — standalone + Jagex launcher variants
_RUNELITE_DIRS = [
    Path.home() / ".runelite" / "profiles2",
    Path.home() / ".var" / "app" / "com.jagexlauncher.JagexLauncher" / "data" / "user_home" / ".runelite" / "profiles2",
    Path.home() / ".var" / "app" / "com.jagex.Launcher" / ".runelite" / "profiles2",
]

# Keep for backwards compat — points to standalone dir
RUNELITE_DIR = _RUNELITE_DIRS[0]
RSPROFILE_FILE = RUNELITE_DIR / "$rsprofile--1.properties"


def _read_rsprofile_file(path: Path) -> dict[str, str]:
    """Read a single rsprofile properties file into a dict."""
    if not path.exists():
        return {}
    props = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, _, value = line.partition("=")
                props[key.strip()] = value.strip()
    return props


def _read_all_rsprofiles() -> list[dict[str, str]]:
    """Read rsprofile properties from all known RuneLite directories."""
    all_props = []
    for profiles_dir in _RUNELITE_DIRS:
        rsprofile = profiles_dir / "$rsprofile--1.properties"
        props = _read_rsprofile_file(rsprofile)
        if props:
            all_props.append(props)
    return all_props


def _read_rsprofile() -> dict[str, str]:
    """Read the rsprofile properties file into a dict.

    For backwards compat, merges all known locations into one dict.
    """
    merged = {}
    for props in _read_all_rsprofiles():
        merged.update(props)
    return merged


def get_account_profiles() -> list[dict]:
    """List all RuneLite accounts with display names from all data locations."""
    accounts = {}
    for props in _read_all_rsprofiles():
        for key, value in props.items():
            m = re.match(r"rsprofile\.rsprofile\.([\w-]+)\.displayName", key)
            if m and value:
                profile_hash = m.group(1)
                if value not in accounts:
                    accounts[value] = profile_hash
    return [{"display_name": name, "profile_hash": h} for name, h in accounts.items()]


def _find_profile_hash(username: str) -> str | None:
    """Find the profile hash for a given display name across all locations."""
    username_lower = username.lower()
    best_hash = None
    for props in _read_all_rsprofiles():
        for key, value in props.items():
            m = re.match(r"rsprofile\.rsprofile\.([\w-]+)\.displayName", key)
            if m and value.lower() == username_lower:
                best_hash = m.group(1)
    return best_hash


def _parse_bank_items(raw: str) -> list[tuple[int, int]]:
    """Parse 'id,qty,id,qty,...' string into [(id, qty), ...] pairs."""
    if not raw or raw == "null":
        return []
    parts = raw.split(",")
    items = []
    for i in range(0, len(parts) - 1, 2):
        try:
            item_id = int(parts[i])
            qty = int(parts[i + 1])
            if item_id > 0 and qty > 0:
                items.append((item_id, qty))
        except (ValueError, IndexError):
            continue
    return items


def get_bank_raw(username: str) -> list[tuple[int, int]] | None:
    """Get raw bank contents (item_id, quantity pairs) for a username.

    Reads from RuneLite Quest Helper's cached bank data across all known
    RuneLite directories (standalone + Jagex launcher). The bank data
    is updated whenever you open your bank in-game with Quest Helper enabled.
    """
    username_lower = username.lower()

    # Search all RuneLite locations, pick the profile with the most items
    best_items = None
    for props in _read_all_rsprofiles():
        for key, value in props.items():
            m = re.match(r"rsprofile\.rsprofile\.([\w-]+)\.displayName", key)
            if m and value.lower() == username_lower:
                profile_hash = m.group(1)
                bank_key = f"questhelper.rsprofile.{profile_hash}.bankitems"
                raw = props.get(bank_key)
                if raw and raw != "null":
                    items = _parse_bank_items(raw)
                    if best_items is None or len(items) > len(best_items):
                        best_items = items

    return best_items


# Common untradeable items not in the GE prices mapping
UNTRADEABLE_ITEMS = {
    995: "Coins",
    6529: "Tokkul",
    29381: "Blessed bone shards",
    29325: "Sunfire splinters",
    29332: "Calcified deposit",
    29338: "Calcified moth",
    29340: "Hallowed crystal shard",
    13573: "Mark of grace",
    13660: "Slayer's enchantment",
    7936: "Pure essence",
    29784: "Stardust",
    8013: "Teleport to house",
    20718: "Graceful token",
    23962: "Herbi",
    21907: "Amethyst",
    4278: "Arrow shaft",
    10976: "Uncut sapphire (noted)",
    10977: "Uncut sapphire (noted)",
    29782: "Numulite",
    13441: "Anglerfish (raw)",
    23182: "Seed box",
    772: "Cabbage seed",
    24942: "Clue scroll (easy)",
    21555: "Molch pearl",
}


async def _build_id_map() -> dict[int, str]:
    """Build item ID to name mapping from local data + prices API + untradeables."""
    cache_key = "bank:id_map"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    id_map: dict[int, str] = {}

    # 1. Load comprehensive local item names (15k+ items including untradeables)
    if _ITEM_NAMES_FILE.exists():
        with open(_ITEM_NAMES_FILE) as f:
            local = _json.load(f)
        for str_id, name in local.items():
            try:
                id_map[int(str_id)] = name
            except ValueError:
                pass

    # 2. Overlay tradeable items from prices API (more up-to-date names)
    try:
        mapping = await fetch_mapping()
        for item in mapping:
            id_map[item["id"]] = item["name"]
    except Exception:
        pass

    # 3. Hardcoded fallbacks for anything still missing
    id_map.update(UNTRADEABLE_ITEMS)

    cache.set(cache_key, id_map, ttl=3600)
    return id_map


async def get_bank(username: str) -> list[dict] | None:
    """Get bank contents with item names resolved.

    Returns list of {item_id, name, quantity} dicts sorted by quantity desc.

    Handles two common quirks of RuneLite's raw bank data:

    * **Bank placeholders** — OSRS stores empty placeholder slots as separate
      internal item IDs (typically in the 14k-19k range) that don't appear in
      any public item database.  These are filtered out.
    * **Noted / charged variants** — Items whose ID is one above a known base
      item (the standard OSRS noted-item pattern) are resolved to the base
      item's name with a "(noted)" suffix.
    """
    raw = get_bank_raw(username)
    if raw is None:
        return None

    id_to_name = await _build_id_map()

    bank = []
    for item_id, qty in raw:
        name = id_to_name.get(item_id)

        if name is None:
            # Try noted-item pattern: base item is id - 1
            base_name = id_to_name.get(item_id - 1)
            if base_name:
                name = f"{base_name} (noted)"
            else:
                # Unresolvable — almost certainly a bank placeholder slot
                continue

        bank.append({
            "item_id": item_id,
            "name": name,
            "quantity": qty,
        })

    bank.sort(key=lambda x: x["quantity"], reverse=True)
    return bank
