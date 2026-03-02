"""Expected hours calculator tools — skilling grinds and boss drop grinds."""
import math

from osrs_mcp.server import mcp
from osrs_mcp.api.hiscores import fetch_hiscores
from osrs_mcp.util.xp import xp_for_level, xp_between_levels
from osrs_mcp.util.data import find_skilling_methods, load_skilling_rates


def _geometric_milestones(drop_rate: int) -> dict[str, float]:
    """Probability milestones for a 1/drop_rate drop using geometric distribution.

    Returns kills needed for 50%, 75%, 90%, 99% chance of getting at least one drop.
    P(at least 1 in k kills) = 1 - (1 - 1/n)^k >= target
    Solving: k >= log(1 - target) / log(1 - 1/n)
    """
    if drop_rate <= 1:
        return {"50%": 1, "75%": 1, "90%": 1, "99%": 1}
    p = 1 / drop_rate
    milestones = {}
    for label, target in [("50%", 0.50), ("75%", 0.75), ("90%", 0.90), ("99%", 0.99)]:
        kills = math.ceil(math.log(1 - target) / math.log(1 - p))
        milestones[label] = kills
    return milestones


@mcp.tool()
async def skilling_hours(
    skill: str,
    target_level: int,
    method: str = "",
    xp_per_hour: int = 0,
    current_level: int = 0,
    current_xp: int = 0,
    username: str = "",
) -> dict:
    """Calculate hours needed to reach a target level in a skill.

    If no method or xp_per_hour is provided, returns available training methods
    for the skill at the player's current level.

    Args:
        skill: Skill name (e.g. "fletching", "mining", "agility").
        target_level: Target level (2-99).
        method: Training method name (e.g. "Barbarian fishing"). Looks up XP rate automatically.
        xp_per_hour: Manual XP/hr override. Use this if you know the exact rate.
        current_level: Current level (1-98). Ignored if username is provided.
        current_xp: Current XP in the skill. Ignored if username is provided.
            If both current_level and current_xp are 0 and no username, defaults to level 1.
        username: RSN to fetch current level/XP from hiscores.
    """
    skill_lower = skill.lower().strip()

    # Validate target
    if not 2 <= target_level <= 99:
        return {"error": "target_level must be 2-99."}

    # Resolve current level/XP from hiscores if username given
    if username:
        try:
            data = await fetch_hiscores(username)
            skills = data.get("skills", {})
            # Find skill (case-insensitive)
            for name, info in skills.items():
                if name.lower() == skill_lower:
                    current_level = info.get("level", 1)
                    current_xp = info.get("xp", 0)
                    break
        except Exception:
            pass

    # Default to level 1 if nothing provided
    if current_level <= 0 and current_xp <= 0:
        current_level = 1
        current_xp = 0

    # If current_xp is provided, use it directly; otherwise use level
    if current_xp > 0:
        xp_needed = xp_for_level(target_level) - current_xp
        # Infer current_level from XP for display
        if current_level <= 0:
            for lv in range(99, 0, -1):
                if current_xp >= xp_for_level(lv):
                    current_level = lv
                    break
    else:
        xp_needed = xp_between_levels(current_level, target_level)

    if xp_needed <= 0:
        return {
            "skill": skill_lower,
            "current_level": current_level,
            "target_level": target_level,
            "xp_needed": 0,
            "hours": 0,
            "message": "Already at or above target level.",
        }

    # Resolve XP rate
    rate = xp_per_hour
    method_name = method

    if not rate and method:
        # Look up method in skilling rates (search ALL methods, not level-filtered)
        rates = load_skilling_rates()
        all_methods = rates.get(skill_lower, [])
        for m in all_methods:
            if m["method"].lower() == method.lower():
                rate = m["xp_per_hour"]
                method_name = m["method"]
                break
        if not rate:
            return {
                "error": f"Method '{method}' not found for {skill_lower}.",
                "available_methods": [m["method"] for m in all_methods],
            }

    if not rate:
        # No method or rate specified — return available methods
        available = find_skilling_methods(skill_lower, min_level=current_level)
        if not available:
            rates = load_skilling_rates()
            if skill_lower not in rates:
                return {"error": f"Unknown skill '{skill}'. Check spelling."}
            return {
                "skill": skill_lower,
                "current_level": current_level,
                "target_level": target_level,
                "xp_needed": xp_needed,
                "message": "No methods available at your current level.",
                "all_methods": rates.get(skill_lower, []),
            }
        # Show methods with estimated hours for each
        method_list = []
        for m in available:
            if not m["xp_per_hour"]:
                continue
            hrs = xp_needed / m["xp_per_hour"]
            method_list.append({
                "method": m["method"],
                "xp_per_hour": m["xp_per_hour"],
                "level_req": m["level_req"],
                "hours": round(hrs, 1),
            })
        method_list.sort(key=lambda x: x["hours"])
        return {
            "skill": skill_lower,
            "current_level": current_level,
            "target_level": target_level,
            "xp_needed": xp_needed,
            "methods": method_list,
        }

    hours = xp_needed / rate
    return {
        "skill": skill_lower,
        "current_level": current_level,
        "target_level": target_level,
        "xp_needed": xp_needed,
        "method": method_name or "custom",
        "xp_per_hour": rate,
        "hours": round(hours, 1),
    }


@mcp.tool()
async def boss_grind_hours(
    boss: str,
    item: str,
    drop_rate: int,
    kills_per_hour: float = 0,
    weapon: str = "",
    style: str = "melee",
    attack_type: str = "slash",
    prayer: str = "piety",
    potion: str = "super_combat",
    gear: str = "",
    spell: str = "",
    per_kill_overhead: int = 30,
    username: str = "",
) -> dict:
    """Calculate expected hours to get a specific boss drop.

    The drop_rate is REQUIRED — look it up from monster_drops() or the wiki
    before calling this tool. It is the denominator (e.g. 128 for a 1/128 drop).

    If kills_per_hour is provided, uses that directly. Otherwise, if weapon is
    provided, calculates kills/hr using the DPS calculator (adds per_kill_overhead
    seconds per kill for banking, eating, and moving between kills).

    Args:
        boss: Boss name (e.g. "Zulrah", "Vorkath").
        item: Item name you're grinding for (e.g. "Tanzanite fang").
        drop_rate: Drop rate denominator (e.g. 128 for 1/128). REQUIRED.
            Look this up with monster_drops() or read_wiki_page() first.
        kills_per_hour: Manual kills/hr. Use if you know your kill rate.
        weapon: Weapon name for DPS-based kills/hr calculation.
        style: Combat style for DPS calc — "melee", "ranged", or "magic".
        attack_type: For melee: "stab", "slash", or "crush".
        prayer: Prayer for DPS calc (e.g. "piety", "rigour").
        potion: Potion for DPS calc (e.g. "super_combat", "super_ranging").
        gear: Comma-separated gear for DPS calc.
        spell: Spell name for magic DPS calc.
        per_kill_overhead: Extra seconds per kill for banking/eating/setup (default 30).
        username: RSN for stats lookup in DPS calc.
    """
    if drop_rate <= 0:
        return {"error": "drop_rate must be a positive integer (the denominator, e.g. 128)."}

    kph = kills_per_hour

    # Calculate kills/hr from DPS if weapon provided
    if not kph and weapon:
        # Import here to avoid circular imports
        from osrs_mcp.tools.dps import calc_dps
        try:
            dps_result = await calc_dps(
                monster=boss, weapon=weapon, style=style,
                attack_type=attack_type, prayer=prayer, potion=potion,
                gear=gear, spell=spell, username=username,
            )
            ttk = dps_result.get("ttk_seconds", 0)
            if ttk <= 0:
                return {"error": f"Could not calculate kill time for {boss} with {weapon}."}
            seconds_per_kill = ttk + per_kill_overhead
            kph = 3600 / seconds_per_kill
        except Exception as e:
            return {"error": f"DPS calculation failed: {e}"}

    if not kph or kph <= 0:
        return {
            "error": "Provide either kills_per_hour or weapon to calculate kills/hr.",
        }

    # Expected kills = drop_rate (mean of geometric distribution)
    expected_kills = drop_rate
    expected_hours = expected_kills / kph

    # Probability milestones
    milestones = _geometric_milestones(drop_rate)
    milestone_hours = {k: round(v / kph, 1) for k, v in milestones.items()}

    return {
        "boss": boss,
        "item": item,
        "drop_rate": f"1/{drop_rate}",
        "kills_per_hour": round(kph, 1),
        "expected_kills": expected_kills,
        "expected_hours": round(expected_hours, 1),
        "milestones": {
            label: {"kills": kills, "hours": milestone_hours[label]}
            for label, kills in milestones.items()
        },
    }
