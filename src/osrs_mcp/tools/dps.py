"""DPS calculator tools."""
from collections import defaultdict
from dataclasses import asdict
from osrs_mcp.server import mcp
from osrs_mcp.config import get_config
from osrs_mcp.api.hiscores import fetch_hiscores
from osrs_mcp.api.wiki_bucket import get_monster_info
from osrs_mcp.api.runelite_bank import get_bank
from osrs_mcp.util.data import (
    find_equipment_by_name, find_monster_by_name, load_equipment,
    get_weapon_speed, find_spell,
)
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
    spell: str = "",
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
        spell: Spell name for magic (e.g. "Iban's Blast", "Fire Surge", "Ice Barrage").
            Auto-resolves max hit and element. Overrides spell_max_hit/spell_element if set.
        spell_max_hit: Base max hit of spell (manual override, e.g. 24 for Fire Surge).
        spell_element: Element of the spell for elemental weakness bonus - "Fire", "Water", "Earth", or "Air".
            Elemental weakness gives +X% accuracy and +X% damage when using a matching standard
            spellbook spell (Strike/Bolt/Blast/Wave/Surge). Does NOT apply to non-elemental spells
            like Flames of Zamorak, Ice Barrage, or powered staves (Trident, Tumeken's shadow).
        username: Username for stats lookup. Empty uses config or maxed stats.
    """
    mon = await _resolve_monster(monster)
    stats = await _get_player_stats(username or None)

    # Auto-resolve spell name to max_hit and element
    if spell and style == "magic":
        spell_data = find_spell(spell)
        if spell_data:
            if not spell_max_hit:
                spell_max_hit = spell_data["max_hit"]
            if not spell_element:
                spell_element = spell_data["element"]

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
    if spell:
        result.weapon = f"{weapon} ({spell})"
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
    spell: str = "",
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
        spell: Spell name for magic (e.g. "Iban's Blast", "Fire Surge"). Auto-resolves max hit and element.
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
                spell=spell, username=username,
            )
            results.append(result)
        except Exception as e:
            results.append({"weapon": weapon, "error": str(e)})

    results.sort(key=lambda r: r.get("dps", 0), reverse=True)
    return results


# ---------------------------------------------------------------------------
# suggest_loadout helpers
# ---------------------------------------------------------------------------

# Slots that hold armor (not weapon/2h/ammo)
_ARMOR_SLOTS = {"head", "cape", "neck", "body", "legs", "feet", "hands",
                "shield", "ring"}


def _detect_combat_style(weapon: dict) -> tuple[str, str]:
    """Determine combat style and attack type from a weapon's bonuses.

    Returns (style, attack_type) where:
      style: "melee", "ranged", or "magic"
      attack_type: "stab", "slash", "crush" for melee; "ranged"/"magic" for ranged/magic
    """
    arange = int(weapon.get("arange") or 0)
    amagic = int(weapon.get("amagic") or 0)
    astab = int(weapon.get("astab") or 0)
    aslash = int(weapon.get("aslash") or 0)
    acrush = int(weapon.get("acrush") or 0)

    melee_best = max(astab, aslash, acrush)

    # Magic: highest positive bonus
    if amagic > 0 and amagic >= melee_best and amagic >= arange:
        return ("magic", "magic")

    # Ranged: highest positive bonus
    if arange > 0 and arange >= melee_best:
        return ("ranged", "ranged")

    # Melee: pick the highest melee attack type
    if melee_best <= 0:
        # No positive offensive bonus at all — default slash
        return ("melee", "slash")

    if astab >= aslash and astab >= acrush:
        return ("melee", "stab")
    elif aslash >= acrush:
        return ("melee", "slash")
    else:
        return ("melee", "crush")


def _best_armor_for_style(
    items_by_slot: dict[str, list[dict]],
    style: str,
    is_2h: bool,
) -> list[dict]:
    """Pick best armor item per slot for a given combat style.

    For melee: maximize 'str' (melee strength).
    For ranged: maximize 'rstr' (ranged strength).
    For magic: maximize 'mdmg' (magic damage %).
    Returns list of equipment dicts (with bonuses).
    """
    if style == "ranged":
        stat = "rstr"
    elif style == "magic":
        stat = "mdmg"
    else:
        stat = "str"

    armor = []
    for slot in _ARMOR_SLOTS:
        # 2h weapons can't use a shield
        if is_2h and slot == "shield":
            continue
        items = items_by_slot.get(slot, [])
        best = None
        best_val = -999
        for item in items:
            bonuses = item.get("bonuses", {})
            if not isinstance(bonuses, dict):
                continue
            val = bonuses.get(stat, 0)
            if val > best_val:
                best_val = val
                best = item
        if best is not None:
            armor.append(best)
    return armor


def _detect_special_equipment(
    weapon_name: str, monster: Monster,
) -> str | None:
    """Auto-detect special equipment effects based on weapon name and monster."""
    name_lower = weapon_name.lower()
    if "dragon hunter lance" in name_lower and monster.attribute == "dragon":
        return "dragon_hunter_lance"
    if "dragon hunter crossbow" in name_lower and monster.attribute == "dragon":
        return "dragon_hunter_crossbow"
    if "arclight" in name_lower and monster.attribute == "demon":
        return "arclight"
    if "keris partisan" in name_lower and monster.attribute == "kalphite":
        return "keris_partisan"
    return None


def _analyze_weakness(monster: Monster) -> dict:
    """Analyze monster defence bonuses to find weakest style."""
    defences = {
        "stab": monster.dstab, "slash": monster.dslash, "crush": monster.dcrush,
        "ranged": monster.drange, "magic": monster.dmagic,
    }
    weakest = min(defences, key=defences.get)
    return {
        "defences": defences,
        "weakest_style": weakest,
        "elemental_weakness": monster.elemental_weakness or None,
        "elemental_weakness_percent": monster.elemental_weakness_percent,
    }


def _pick_prayer(style: str, prayer_level: int) -> str:
    """Pick the best available prayer for a style given the player's prayer level."""
    if style == "melee":
        if prayer_level >= 70:
            return "piety"
        if prayer_level >= 60:
            return "chivalry"
        if prayer_level >= 31:
            return "ultimate_strength"
        if prayer_level >= 13:
            return "superhuman_strength"
        if prayer_level >= 4:
            return "burst_of_strength"
        return "none"
    if style == "ranged":
        if prayer_level >= 74:
            return "rigour"
        if prayer_level >= 44:
            return "eagle_eye"
        if prayer_level >= 26:
            return "hawk_eye"
        if prayer_level >= 8:
            return "sharp_eye"
        return "none"
    # magic
    if prayer_level >= 77:
        return "augury"
    if prayer_level >= 45:
        return "mystic_might"
    if prayer_level >= 27:
        return "mystic_lore"
    if prayer_level >= 9:
        return "mystic_will"
    return "none"


def _pick_potion(style: str) -> str:
    """Pick default potion for a style."""
    if style == "melee":
        return "super_combat"
    if style == "ranged":
        return "super_ranging"
    return "saturated_heart"


@mcp.tool()
async def suggest_loadout(
    monster: str,
    username: str = "",
    on_slayer_task: bool = False,
) -> dict:
    """Suggest the best weapon + armor loadouts from your bank against a monster.

    Automatically tests every weapon/2h in your bank, pairs each with the best
    armor for that combat style, runs the DPS calculator, and ranks by DPS.
    Skips magic weapons (too many spell variables). Returns top 10 setups.

    Args:
        monster: Monster name (e.g. "Sarachnis", "Vorkath").
        username: RuneScape username. Leave empty to use configured default.
        on_slayer_task: Whether you are on a slayer task for this monster.
    """
    # Resolve username
    if not username:
        cfg = get_config()
        username = cfg.username or ""
    if not username:
        raise ValueError("No username provided and none configured.")

    # Fetch player stats, bank, monster in parallel-ish
    mon = await _resolve_monster(monster)
    stats = await _get_player_stats(username)
    bank = await get_bank(username)
    if bank is None:
        return {"error": f"No bank data found for '{username}'."}

    # Lazy import to avoid circular import (player.py imports server, server imports dps)
    from osrs_mcp.tools.player import _enrich_bank_item

    # Enrich bank items with equipment data
    equipment = load_equipment()
    enriched = [_enrich_bank_item(item, equipment) for item in bank]

    # Organize by slot
    by_slot: dict[str, list[dict]] = defaultdict(list)
    for item in enriched:
        slot = item.get("slot")
        if slot and isinstance(item.get("bonuses"), dict):
            by_slot[slot].append(item)

    # Collect all weapons/2h from bank
    weapons = by_slot.get("weapon", []) + by_slot.get("2h", [])
    if not weapons:
        return {"error": "No weapons found in bank."}

    results = []
    for weapon_item in weapons:
        bonuses = weapon_item.get("bonuses", {})
        if not isinstance(bonuses, dict):
            continue

        style, attack_type = _detect_combat_style(bonuses)

        # Skip magic weapons
        amagic = int(bonuses.get("amagic") or 0)
        melee_best = max(
            int(bonuses.get("astab") or 0),
            int(bonuses.get("aslash") or 0),
            int(bonuses.get("acrush") or 0),
        )
        arange = int(bonuses.get("arange") or 0)
        if amagic > 0 and amagic > melee_best and amagic > arange:
            continue

        is_2h = weapon_item.get("slot") == "2h"

        # Build gear: weapon + best armor for this style
        armor_items = _best_armor_for_style(by_slot, style, is_2h)

        # Build the full equipment list for _parse_gear
        gear_dicts = [bonuses]  # weapon bonuses
        # Add weapon speed
        weapon_name = weapon_item.get("name", "")
        speed = bonuses.get("speed")
        if speed is None:
            # Try to resolve speed from data
            equip_data = find_equipment_by_name(weapon_name)
            if equip_data:
                speed = equip_data.get("speed")
        if speed is not None:
            gear_dicts[0] = dict(bonuses, speed=speed)

        for armor in armor_items:
            armor_bonuses = armor.get("bonuses", {})
            if isinstance(armor_bonuses, dict):
                gear_dicts.append(armor_bonuses)

        gear_setup = _parse_gear(gear_dicts)

        # Auto-detect special equipment
        special = _detect_special_equipment(weapon_name, mon)

        # Calculate DPS
        try:
            if style == "ranged":
                result = calculate_ranged_dps(
                    stats, gear_setup, mon,
                    stance="rapid", prayer="rigour", potion="super_ranging",
                    on_slayer_task=on_slayer_task,
                    special_equipment=special,
                )
            else:
                result = calculate_melee_dps(
                    stats, gear_setup, mon,
                    attack_type=attack_type, stance="aggressive",
                    prayer="piety", potion="super_combat",
                    on_slayer_task=on_slayer_task,
                    special_equipment=special,
                )
        except Exception:
            continue

        # Build armor summary
        gear_names = [a.get("name", "?") for a in armor_items]

        results.append({
            "weapon": weapon_name,
            "style": style,
            "attack_type": attack_type,
            "dps": result.dps,
            "accuracy": result.accuracy,
            "max_hit": result.max_hit,
            "ttk_seconds": result.ttk_seconds,
            "attack_speed": result.attack_speed,
            "armor": gear_names,
            "special_equipment": special,
        })

    # Sort by DPS descending, take top 10
    results.sort(key=lambda r: r["dps"], reverse=True)
    top = results[:10]

    return {
        "monster": mon.name or monster,
        "monster_hp": mon.hitpoints,
        "username": username,
        "top_loadouts": top,
        "total_weapons_tested": len(results),
        "note": "Melee uses aggressive stance + Piety + super combat. "
                "Ranged uses rapid + Rigour + super ranging. "
                "Magic weapons are excluded (spell choice needed).",
    }


@mcp.tool()
async def boss_setup(
    boss: str,
    username: str = "",
    style: str = "",
    spell: str = "",
    on_slayer_task: bool = False,
    per_kill_overhead: int = 30,
) -> dict:
    """Suggest the best setup for a boss, with magic support, weakness analysis, and KPH.

    Improves on suggest_loadout by adding magic weapon support, kills-per-hour
    estimates, monster weakness analysis, and prayer selection based on your
    actual prayer level.

    Args:
        boss: Boss/monster name (e.g. "Vorkath", "Sarachnis").
        username: RuneScape username. Leave empty to use configured default.
        style: Combat style filter - "melee", "ranged", "magic", or "" for auto
            (auto picks the style the boss is weakest to).
        spell: Spell name for magic (e.g. "Fire Surge", "Iban's Blast"). If style
            is magic or auto-detected, this spell is used for all magic weapons.
        on_slayer_task: Whether you are on a slayer task for this monster.
        per_kill_overhead: Seconds of overhead per kill for banking/eating/travel.
            Used to calculate kills per hour. Default 30.
    """
    # Resolve username
    if not username:
        cfg = get_config()
        username = cfg.username or ""
    if not username:
        raise ValueError("No username provided and none configured.")

    # Fetch monster, stats, bank
    mon = await _resolve_monster(boss)
    stats = await _get_player_stats(username)
    bank = await get_bank(username)
    if bank is None:
        return {"error": f"No bank data found for '{username}'."}

    # Analyze weakness
    weakness = _analyze_weakness(mon)

    # Auto-pick style based on monster's weakest defence
    if not style:
        style = _weakness_to_style(weakness["weakest_style"])

    # Pick prayer + potion based on player's actual prayer level
    prayer = _pick_prayer(style, stats.prayer)
    potion = _pick_potion(style)

    # Resolve spell for magic
    spell_max_hit = 0
    spell_element = ""
    if spell:
        spell_data = find_spell(spell)
        if spell_data:
            spell_max_hit = spell_data["max_hit"]
            spell_element = spell_data["element"]

    # Enrich bank
    from osrs_mcp.tools.player import _enrich_bank_item
    equipment = load_equipment()
    enriched = [_enrich_bank_item(item, equipment) for item in bank]

    # Organize by slot
    by_slot: dict[str, list[dict]] = defaultdict(list)
    for item in enriched:
        slot = item.get("slot")
        if slot and isinstance(item.get("bonuses"), dict):
            by_slot[slot].append(item)

    # Collect weapons
    weapons = by_slot.get("weapon", []) + by_slot.get("2h", [])
    if not weapons:
        return {"error": "No weapons found in bank."}

    # Stance selection
    stance_map = {"melee": "aggressive", "ranged": "rapid", "magic": "accurate"}
    stance = stance_map.get(style, "accurate")

    results = []
    for weapon_item in weapons:
        bonuses = weapon_item.get("bonuses", {})
        if not isinstance(bonuses, dict):
            continue

        w_style, attack_type = _detect_combat_style(bonuses)

        # Filter by requested style
        if w_style != style:
            continue

        is_2h = weapon_item.get("slot") == "2h"

        # Build gear: weapon + best armor for this style
        armor_items = _best_armor_for_style(by_slot, w_style, is_2h)

        # Build the full equipment list for _parse_gear
        gear_dicts = [bonuses]
        weapon_name = weapon_item.get("name", "")
        speed = bonuses.get("speed")
        if speed is None:
            equip_data = find_equipment_by_name(weapon_name)
            if equip_data:
                speed = equip_data.get("speed")
        if speed is not None:
            gear_dicts[0] = dict(bonuses, speed=speed)

        for armor in armor_items:
            armor_bonuses = armor.get("bonuses", {})
            if isinstance(armor_bonuses, dict):
                gear_dicts.append(armor_bonuses)

        gear_setup = _parse_gear(gear_dicts)

        # Auto-detect special equipment
        special = _detect_special_equipment(weapon_name, mon)

        # Calculate DPS
        try:
            if w_style == "magic":
                smh = spell_max_hit or 24
                result = calculate_magic_dps(
                    stats, gear_setup, mon,
                    spell_max_hit=smh,
                    spell_element=spell_element,
                    prayer=prayer, potion=potion,
                    on_slayer_task=on_slayer_task,
                    special_equipment=special,
                )
            elif w_style == "ranged":
                result = calculate_ranged_dps(
                    stats, gear_setup, mon,
                    stance=stance, prayer=prayer, potion=potion,
                    on_slayer_task=on_slayer_task,
                    special_equipment=special,
                )
            else:
                result = calculate_melee_dps(
                    stats, gear_setup, mon,
                    attack_type=attack_type, stance=stance,
                    prayer=prayer, potion=potion,
                    on_slayer_task=on_slayer_task,
                    special_equipment=special,
                )
        except Exception:
            continue

        # Calculate KPH
        ttk = result.ttk_seconds
        if ttk > 0 and ttk != float("inf"):
            kph = round(3600 / (ttk + per_kill_overhead), 1)
        else:
            kph = 0

        gear_names = [a.get("name", "?") for a in armor_items]
        weapon_label = weapon_name
        if w_style == "magic" and spell:
            weapon_label = f"{weapon_name} ({spell})"

        results.append({
            "weapon": weapon_label,
            "style": w_style,
            "attack_type": attack_type,
            "dps": result.dps,
            "accuracy": result.accuracy,
            "max_hit": result.max_hit,
            "ttk_seconds": result.ttk_seconds,
            "kph": kph,
            "attack_speed": result.attack_speed,
            "armor": gear_names,
            "special_equipment": special,
            "prayer": prayer,
            "potion": potion,
        })

    results.sort(key=lambda r: r["dps"], reverse=True)
    top = results[:5]

    return {
        "monster": mon.name or boss,
        "monster_hp": mon.hitpoints,
        "weakness": weakness,
        "username": username,
        "style": style,
        "top_setups": top,
        "total_weapons_tested": len(results),
    }


def _weakness_to_style(weakest_defence: str) -> str:
    """Map a monster's weakest defence bonus name to a combat style."""
    if weakest_defence in ("stab", "slash", "crush"):
        return "melee"
    if weakest_defence == "ranged":
        return "ranged"
    return "magic"
