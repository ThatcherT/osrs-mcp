"""Prayer, potion, and special equipment modifiers for DPS calculations."""

# Prayer multipliers: (attack_mult, strength_mult)
# Values are numerator/denominator pairs to keep integer math
MELEE_PRAYERS = {
    "none": (1, 1, 1, 1),  # atk_num, atk_den, str_num, str_den
    "burst_of_strength": (1, 1, 21, 20),
    "clarity_of_thought": (21, 20, 1, 1),
    "superhuman_strength": (1, 1, 23, 20),
    "improved_reflexes": (23, 20, 1, 1),
    "ultimate_strength": (1, 1, 27, 20),
    "incredible_reflexes": (27, 20, 1, 1),
    "chivalry": (3, 2, 23, 15),  # 1.15 atk, 1.18 str → approximated
    "piety": (6, 5, 123, 100),  # 1.20 atk, 1.23 str
}

RANGED_PRAYERS = {
    "none": (1, 1, 1, 1),
    "sharp_eye": (21, 20, 21, 20),
    "hawk_eye": (23, 20, 23, 20),
    "eagle_eye": (27, 20, 27, 20),
    "rigour": (6, 5, 123, 100),  # 1.20 atk, 1.23 str
}

MAGIC_PRAYERS = {
    "none": (1, 1),  # accuracy_num, accuracy_den
    "mystic_will": (21, 20),
    "mystic_lore": (23, 20),
    "mystic_might": (27, 20),
    "augury": (6, 5),  # 1.25 → use 5/4? Actually augury is 1.25
}

# Potion boosts: (flat_add, level_percent_add)
# Boosted level = base + flat + floor(base * percent / 100)
POTIONS = {
    "none": (0, 0),
    "attack_potion": (3, 10),
    "super_attack": (5, 15),
    "super_strength": (5, 15),
    "super_combat": (5, 15),  # applies to atk, str, def
    "ranging_potion": (4, 10),
    "super_ranging": (5, 15),  # divine ranging
    "magic_potion": (4, 0),
    "imbued_heart": (1, 10),
    "saturated_heart": (2, 10),
    "overload": (6, 16),  # CoX overload+
    "smelling_salts": (11, 16),  # ToA
}

# Attack style stance bonuses
# (attack_type, attack_bonus, strength_bonus)
# attack_type: "stab", "slash", "crush", "ranged", "magic"
STANCES = {
    "accurate": 3,     # +3 to effective attack level
    "aggressive": 0,   # +3 to effective strength level (handled in str calc)
    "controlled": 1,   # +1 to both attack and strength effective levels
    "defensive": 0,    # +3 to effective defence level, nothing for offense
    "longrange": 0,    # ranged: +3 def, nothing for offense
    "rapid": 0,        # ranged: -1 attack speed
}

STANCE_STR_BONUS = {
    "accurate": 0,
    "aggressive": 3,
    "controlled": 1,
    "defensive": 0,
    "longrange": 0,
    "rapid": 0,
}

# Special equipment multipliers
# (accuracy_mult_num, accuracy_mult_den, damage_mult_num, damage_mult_den)
SPECIAL_EQUIPMENT = {
    "slayer_helm": (7, 6, 7, 6),          # 7/6 = ~1.1667
    "slayer_helm_i": (7, 6, 7, 6),        # also works for ranged/magic when imbued
    "salve_amulet": (7, 6, 7, 6),         # 7/6
    "salve_amulet_e": (6, 5, 6, 5),       # 1.20
    "salve_amulet_i": (7, 6, 7, 6),       # also for ranged/magic
    "salve_amulet_ei": (6, 5, 6, 5),      # 1.20 for all styles
    "void_melee": (11, 10, 11, 10),        # 1.10
    "void_ranged": (11, 10, 11, 10),       # 1.10
    "void_magic": (29, 20, 1, 1),          # 1.45 acc, no dmg bonus
    "elite_void_melee": (11, 10, 11, 10),  # same as void
    "elite_void_ranged": (11, 10, 23, 20), # 1.10 acc, 1.125 → approx 1.15
    "elite_void_magic": (29, 20, 21, 20),  # 1.45 acc, 2.5% dmg
    "dragon_hunter_lance": (6, 5, 6, 5),   # 1.20 vs dragons
    "dragon_hunter_crossbow": (13, 10, 5, 4),  # 1.30 acc, 1.25 dmg vs dragons
}
