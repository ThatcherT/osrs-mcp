"""Core DPS calculation engine - simplified port of weirdgloop/osrs-dps-calc."""
import math
from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster, DpsResult
from osrs_mcp.dps.constants import (
    MELEE_PRAYERS, RANGED_PRAYERS, MAGIC_PRAYERS,
    POTIONS, STANCES, STANCE_STR_BONUS, SPECIAL_EQUIPMENT,
)


def boost_level(base: int, potion: str) -> int:
    """Apply potion boost to a base level."""
    flat, pct = POTIONS.get(potion, (0, 0))
    return base + flat + math.floor(base * pct / 100)


def effective_melee_attack(stats: PlayerStats, prayer: str, stance: str,
                           potion: str) -> int:
    """Calculate effective melee attack level."""
    boosted = boost_level(stats.attack, potion)
    prayer_data = MELEE_PRAYERS.get(prayer, (1, 1, 1, 1))
    atk_num, atk_den = prayer_data[0], prayer_data[1]
    effective = math.floor(boosted * atk_num / atk_den)
    effective += STANCES.get(stance, 0) + 8
    return effective


def effective_melee_strength(stats: PlayerStats, prayer: str, stance: str,
                             potion: str) -> int:
    """Calculate effective melee strength level."""
    boosted = boost_level(stats.strength, potion)
    prayer_data = MELEE_PRAYERS.get(prayer, (1, 1, 1, 1))
    str_num, str_den = prayer_data[2], prayer_data[3]
    effective = math.floor(boosted * str_num / str_den)
    effective += STANCE_STR_BONUS.get(stance, 0) + 8
    return effective


def effective_ranged_level(stats: PlayerStats, prayer: str, stance: str,
                           potion: str) -> int:
    """Calculate effective ranged level (used for both accuracy and damage)."""
    boosted = boost_level(stats.ranged, potion)
    prayer_data = RANGED_PRAYERS.get(prayer, (1, 1, 1, 1))
    # For ranged, accuracy and strength use the same prayer multiplier
    num, den = prayer_data[0], prayer_data[1]
    effective = math.floor(boosted * num / den)
    effective += STANCES.get(stance, 0) + 8
    return effective


def effective_ranged_strength(stats: PlayerStats, prayer: str, stance: str,
                              potion: str) -> int:
    """Calculate effective ranged strength level."""
    boosted = boost_level(stats.ranged, potion)
    prayer_data = RANGED_PRAYERS.get(prayer, (1, 1, 1, 1))
    str_num, str_den = prayer_data[2], prayer_data[3]
    effective = math.floor(boosted * str_num / str_den)
    effective += STANCE_STR_BONUS.get(stance, 0) + 8
    return effective


def effective_magic_level(stats: PlayerStats, prayer: str, potion: str) -> int:
    """Calculate effective magic level."""
    boosted = boost_level(stats.magic, potion)
    prayer_data = MAGIC_PRAYERS.get(prayer, (1, 1))
    num, den = prayer_data[0], prayer_data[1]
    effective = math.floor(boosted * num / den)
    effective += 9  # magic always +8 +1 for accurate stance
    return effective


def attack_roll(effective_level: int, equipment_bonus: int) -> int:
    """Calculate maximum attack roll."""
    return effective_level * (equipment_bonus + 64)


def defence_roll(npc_def_level: int, npc_style_bonus: int) -> int:
    """Calculate NPC maximum defence roll."""
    return (npc_def_level + 9) * (npc_style_bonus + 64)


def hit_chance(atk_roll: int, def_roll: int) -> float:
    """Standard OSRS accuracy formula."""
    if atk_roll > def_roll:
        return 1.0 - (def_roll + 2) / (2 * (atk_roll + 1))
    else:
        return atk_roll / (2 * (def_roll + 1))


def melee_max_hit(effective_str: int, str_bonus: int) -> int:
    """Calculate melee max hit."""
    return math.floor((effective_str * (str_bonus + 64) + 320) / 640)


def ranged_max_hit(effective_str: int, ranged_str_bonus: int) -> int:
    """Calculate ranged max hit."""
    return math.floor((effective_str * (ranged_str_bonus + 64) + 320) / 640)


def magic_max_hit(base_max: int, magic_dmg_pct: int) -> int:
    """Calculate magic max hit with damage bonus."""
    return math.floor(base_max * (100 + magic_dmg_pct) / 100)


def apply_special_multiplier(value: int, equip_key: str, is_accuracy: bool) -> int:
    """Apply special equipment multiplier (slayer helm, salve, void, etc.)."""
    mod = SPECIAL_EQUIPMENT.get(equip_key)
    if mod is None:
        return value
    if is_accuracy:
        return math.floor(value * mod[0] / mod[1])
    else:
        return math.floor(value * mod[2] / mod[3])


def calculate_melee_dps(
    stats: PlayerStats,
    gear: GearSetup,
    monster: Monster,
    attack_type: str = "slash",  # stab, slash, crush
    stance: str = "accurate",
    prayer: str = "piety",
    potion: str = "super_combat",
    on_slayer_task: bool = False,
    special_equipment: str | None = None,
) -> DpsResult:
    """Calculate melee DPS against a monster."""
    # Effective levels
    eff_atk = effective_melee_attack(stats, prayer, stance, potion)
    eff_str = effective_melee_strength(stats, prayer, stance, potion)

    # Equipment bonus for chosen attack type
    equip_bonus_map = {"stab": gear.astab, "slash": gear.aslash, "crush": gear.acrush}
    equip_bonus = equip_bonus_map.get(attack_type, gear.aslash)

    # Attack and defence rolls
    atk = attack_roll(eff_atk, equip_bonus)
    npc_def_map = {"stab": monster.dstab, "slash": monster.dslash, "crush": monster.dcrush}
    npc_def_bonus = npc_def_map.get(attack_type, monster.dslash)
    def_r = defence_roll(monster.defence_level, npc_def_bonus)

    # Max hit
    max_h = melee_max_hit(eff_str, gear.melee_str)

    # Apply special equipment
    if on_slayer_task:
        atk = apply_special_multiplier(atk, "slayer_helm", True)
        max_h = apply_special_multiplier(max_h, "slayer_helm", False)

    if special_equipment:
        if special_equipment in ("dragon_hunter_lance",) and monster.attribute == "dragon":
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)
        elif "salve" in special_equipment and monster.attribute == "undead":
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)
        elif "void" in special_equipment:
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)

    acc = hit_chance(atk, def_r)
    speed = gear.speed
    dps = (acc * max_h / 2) / (speed * 0.6)
    ttk = monster.hitpoints / dps if dps > 0 else float("inf")

    return DpsResult(
        weapon="melee",
        attack_style=attack_type,
        max_hit=max_h,
        accuracy=round(acc, 4),
        dps=round(dps, 3),
        attack_speed=speed,
        ttk_seconds=round(ttk, 1),
        details={
            "effective_attack": eff_atk,
            "effective_strength": eff_str,
            "attack_roll": atk,
            "defence_roll": def_r,
        },
    )


def calculate_ranged_dps(
    stats: PlayerStats,
    gear: GearSetup,
    monster: Monster,
    stance: str = "rapid",
    prayer: str = "rigour",
    potion: str = "super_ranging",
    on_slayer_task: bool = False,
    special_equipment: str | None = None,
) -> DpsResult:
    """Calculate ranged DPS against a monster."""
    eff_atk = effective_ranged_level(stats, prayer, stance, potion)
    eff_str = effective_ranged_strength(stats, prayer, stance, potion)

    atk = attack_roll(eff_atk, gear.arange)
    def_r = defence_roll(monster.defence_level, monster.drange)

    max_h = ranged_max_hit(eff_str, gear.ranged_str)

    if on_slayer_task:
        atk = apply_special_multiplier(atk, "slayer_helm_i", True)
        max_h = apply_special_multiplier(max_h, "slayer_helm_i", False)

    if special_equipment:
        if special_equipment == "dragon_hunter_crossbow" and monster.attribute == "dragon":
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)
        elif "salve" in special_equipment and monster.attribute == "undead":
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)
        elif "void" in special_equipment:
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)

    acc = hit_chance(atk, def_r)
    speed = gear.speed
    if stance == "rapid":
        speed = max(1, speed - 1)
    dps = (acc * max_h / 2) / (speed * 0.6)
    ttk = monster.hitpoints / dps if dps > 0 else float("inf")

    return DpsResult(
        weapon="ranged",
        attack_style="ranged",
        max_hit=max_h,
        accuracy=round(acc, 4),
        dps=round(dps, 3),
        attack_speed=speed,
        ttk_seconds=round(ttk, 1),
        details={
            "effective_ranged_atk": eff_atk,
            "effective_ranged_str": eff_str,
            "attack_roll": atk,
            "defence_roll": def_r,
        },
    )


def calculate_magic_dps(
    stats: PlayerStats,
    gear: GearSetup,
    monster: Monster,
    spell_max_hit: int = 24,  # base max hit of the spell
    spell_element: str = "",  # "Fire", "Water", "Earth", "Air"
    prayer: str = "augury",
    potion: str = "saturated_heart",
    on_slayer_task: bool = False,
    special_equipment: str | None = None,
) -> DpsResult:
    """Calculate magic DPS against a monster.

    Elemental weakness: If the spell element matches the monster's elemental
    weakness, the player gains +X% accuracy and +X% damage where X is the
    monster's elemental_weakness_percent. Per the wiki formula:
      max_hit = floor(floor(base * (1 + magic_dmg%)) * (1 + slayer%))
                + floor(base * elemental_weakness%)
    And accuracy roll is multiplied by (1 + elemental_weakness%).
    """
    eff_atk = effective_magic_level(stats, prayer, potion)

    atk = attack_roll(eff_atk, gear.amagic)
    def_r = defence_roll(monster.magic_level, monster.dmagic)

    max_h = magic_max_hit(spell_max_hit, gear.magic_dmg)

    if on_slayer_task:
        atk = apply_special_multiplier(atk, "slayer_helm_i", True)
        max_h = apply_special_multiplier(max_h, "slayer_helm_i", False)

    if special_equipment:
        if "salve" in special_equipment and monster.attribute == "undead":
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)
        elif "void" in special_equipment:
            atk = apply_special_multiplier(atk, special_equipment, True)
            max_h = apply_special_multiplier(max_h, special_equipment, False)

    # Elemental weakness bonus: +X% acc and +floor(base * X%) damage
    elem_pct = 0
    if (spell_element and monster.elemental_weakness
            and spell_element.lower() == monster.elemental_weakness.lower()
            and monster.elemental_weakness_percent > 0):
        elem_pct = monster.elemental_weakness_percent
        atk = math.floor(atk * (100 + elem_pct) / 100)
        max_h += math.floor(spell_max_hit * elem_pct / 100)

    acc = hit_chance(atk, def_r)
    speed = gear.speed
    dps = (acc * max_h / 2) / (speed * 0.6)
    ttk = monster.hitpoints / dps if dps > 0 else float("inf")

    return DpsResult(
        weapon="magic",
        attack_style="magic",
        max_hit=max_h,
        accuracy=round(acc, 4),
        dps=round(dps, 3),
        attack_speed=speed,
        ttk_seconds=round(ttk, 1),
        details={
            "effective_magic": eff_atk,
            "attack_roll": atk,
            "defence_roll": def_r,
            "spell_base_max": spell_max_hit,
            "elemental_weakness": monster.elemental_weakness or "none",
            "elemental_weakness_percent": elem_pct,
        },
    )
