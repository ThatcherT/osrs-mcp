"""DPS calculator tools."""
from dataclasses import asdict
from osrs_mcp.server import mcp
from osrs_mcp.config import get_config
from osrs_mcp.api.hiscores import fetch_hiscores
from osrs_mcp.api.wiki_bucket import get_monster_info
from osrs_mcp.util.data import find_equipment_by_name, find_monster_by_name
from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster, DpsResult
from osrs_mcp.dps.calc import (
    calculate_melee_dps, calculate_ranged_dps, calculate_magic_dps,
)


def _parse_gear(gear_items: list[dict]) -> GearSetup:
    """Aggregate equipment bonuses from a list of worn items."""
    g = GearSetup()
    for item in gear_items:
        g.astab += int(item.get("astab") or 0)
        g.aslash += int(item.get("aslash") or 0)
        g.acrush += int(item.get("acrush") or 0)
        g.arange += int(item.get("arange") or 0)
        g.amagic += int(item.get("amagic") or 0)
        g.dstab += int(item.get("dstab") or 0)
        g.dslash += int(item.get("dslash") or 0)
        g.dcrush += int(item.get("dcrush") or 0)
        g.drange += int(item.get("drange") or 0)
        g.dmagic += int(item.get("dmagic") or 0)
        g.melee_str += int(item.get("str") or 0)
        g.ranged_str += int(item.get("rstr") or 0)
        g.magic_dmg += int(item.get("mdmg") or 0)
        g.prayer += int(item.get("prayer") or 0)
        speed = item.get("speed")
        if speed is not None:
            g.speed = int(speed)
    return g


def _monster_to_obj(data: dict) -> Monster:
    """Convert monster dict to Monster dataclass.

    Handles both local data (dstab) and API data (stab_defence_bonus) field names.
    """
    def _int(key: str, *alt_keys: str) -> int:
        val = data.get(key)
        for k in alt_keys:
            if val is None:
                val = data.get(k)
        if val is None:
            return 0
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    return Monster(
        name=data.get("name", ""),
        combat_level=_int("combat_level"),
        hitpoints=max(1, _int("hitpoints")),
        defence_level=_int("defence_level"),
        magic_level=_int("magic_level"),
        dstab=_int("dstab", "stab_defence_bonus"),
        dslash=_int("dslash", "slash_defence_bonus"),
        dcrush=_int("dcrush", "crush_defence_bonus"),
        drange=_int("drange", "range_defence_bonus"),
        dmagic=_int("dmagic", "magic_defence_bonus"),
        size=max(1, _int("size")),
        attribute=str(data.get("attribute") or ""),
        flat_armour=_int("flat_armour"),
        elemental_weakness=str(data.get("elemental_weakness") or ""),
        elemental_weakness_percent=_int("elemental_weakness_percent"),
    )


async def _get_player_stats(username: str | None) -> PlayerStats:
    """Get player stats from hiscores or use maxed defaults."""
    if not username:
        cfg = get_config()
        username = cfg.username or None

    if username:
        try:
            data = await fetch_hiscores(username)
            skills = data.get("skills", {})
            return PlayerStats(
                attack=skills.get("Attack", {}).get("level", 99),
                strength=skills.get("Strength", {}).get("level", 99),
                defence=skills.get("Defence", {}).get("level", 99),
                ranged=skills.get("Ranged", {}).get("level", 99),
                magic=skills.get("Magic", {}).get("level", 99),
                hitpoints=skills.get("Hitpoints", {}).get("level", 99),
                prayer=skills.get("Prayer", {}).get("level", 99),
            )
        except Exception:
            pass

    return PlayerStats()  # defaults to 99 all


async def _resolve_monster(monster_name: str) -> Monster:
    """Look up monster from local data or API."""
    local = find_monster_by_name(monster_name)
    if local:
        return _monster_to_obj(local)

    api_data = await get_monster_info(monster_name)
    if api_data:
        return _monster_to_obj(api_data)

    raise ValueError(f"Monster '{monster_name}' not found.")


def _resolve_gear(gear_names: list[str]) -> list[dict]:
    """Look up equipment items by name from local data."""
    items = []
    for name in gear_names:
        equip = find_equipment_by_name(name.strip())
        if equip:
            items.append(equip)
    return items


@mcp.tool()
async def calc_dps(
    monster: str,
    weapon: str,
    style: str = "melee",
    attack_type: str = "slash",
    stance: str = "accurate",
    prayer: str = "piety",
    potion: str = "super_combat",
    gear: str = "",
    on_slayer_task: bool = False,
    special_equipment: str = "",
    spell_max_hit: int = 0,
    spell_element: str = "",
    username: str = "",
) -> dict:
    """Calculate DPS against a monster with given setup.

    Args:
        monster: Monster name (e.g. "Vorkath", "Abyssal demon").
        weapon: Weapon name (e.g. "Abyssal whip", "Toxic blowpipe").
        style: Combat style - "melee", "ranged", or "magic".
        attack_type: For melee: "stab", "slash", or "crush". Ignored for ranged/magic.
        stance: Stance - "accurate", "aggressive", "controlled", "defensive", "rapid", "longrange".
        prayer: Prayer name (e.g. "piety", "rigour", "augury", "none").
        potion: Potion (e.g. "super_combat", "super_ranging", "none").
        gear: Comma-separated gear names (e.g. "Fighter torso,Bandos tassets,Primordial boots").
        on_slayer_task: Whether you are on a slayer task for this monster.
        special_equipment: Special equipment effect (e.g. "dragon_hunter_lance", "salve_amulet_ei").
        spell_max_hit: Base max hit of spell (for magic only, e.g. 24 for Fire Surge).
        spell_element: Element of the spell for elemental weakness bonus - "Fire", "Water", "Earth", or "Air".
            Elemental weakness gives +X% accuracy and +X% damage when using a matching standard
            spellbook spell (Strike/Bolt/Blast/Wave/Surge). Does NOT apply to non-elemental spells
            like Flames of Zamorak, Ice Barrage, or powered staves (Trident, Tumeken's shadow).
        username: Username for stats lookup. Empty uses config or maxed stats.
    """
    mon = await _resolve_monster(monster)
    stats = await _get_player_stats(username or None)

    # Build gear setup from weapon + other gear
    gear_names = [weapon]
    if gear:
        gear_names.extend(g.strip() for g in gear.split(",") if g.strip())
    gear_items = _resolve_gear(gear_names)
    gear_setup = _parse_gear(gear_items)

    if style == "ranged":
        result = calculate_ranged_dps(
            stats, gear_setup, mon,
            stance=stance, prayer=prayer, potion=potion,
            on_slayer_task=on_slayer_task, special_equipment=special_equipment or None,
        )
    elif style == "magic":
        result = calculate_magic_dps(
            stats, gear_setup, mon,
            spell_max_hit=spell_max_hit or 24,
            spell_element=spell_element,
            prayer=prayer, potion=potion,
            on_slayer_task=on_slayer_task, special_equipment=special_equipment or None,
        )
    else:
        result = calculate_melee_dps(
            stats, gear_setup, mon,
            attack_type=attack_type, stance=stance, prayer=prayer, potion=potion,
            on_slayer_task=on_slayer_task, special_equipment=special_equipment or None,
        )

    result.weapon = weapon
    return asdict(result)


@mcp.tool()
async def compare_weapons(
    monster: str,
    weapons: str,
    style: str = "melee",
    attack_type: str = "slash",
    stance: str = "accurate",
    prayer: str = "piety",
    potion: str = "super_combat",
    gear: str = "",
    on_slayer_task: bool = False,
    username: str = "",
) -> list[dict]:
    """Compare DPS of multiple weapons against the same monster.

    Args:
        monster: Monster name (e.g. "Vorkath").
        weapons: Comma-separated weapon names (e.g. "Abyssal whip,Ghrazi rapier,Blade of saeldor").
        style: Combat style - "melee", "ranged", or "magic".
        attack_type: For melee: "stab", "slash", or "crush".
        stance: Stance name.
        prayer: Prayer name.
        potion: Potion name.
        gear: Comma-separated other gear names (applied to all weapons).
        on_slayer_task: Whether on slayer task.
        username: Username for stats lookup.
    """
    weapon_list = [w.strip() for w in weapons.split(",") if w.strip()]
    results = []
    for weapon in weapon_list:
        try:
            result = await calc_dps(
                monster=monster, weapon=weapon, style=style,
                attack_type=attack_type, stance=stance, prayer=prayer,
                potion=potion, gear=gear, on_slayer_task=on_slayer_task,
                username=username,
            )
            results.append(result)
        except Exception as e:
            results.append({"weapon": weapon, "error": str(e)})

    results.sort(key=lambda r: r.get("dps", 0), reverse=True)
    return results
