"""Tests for the DPS calculator engine."""
import math
import pytest
from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster, DpsResult
from osrs_mcp.dps.calc import (
    boost_level,
    effective_melee_attack, effective_melee_strength,
    effective_ranged_level, effective_ranged_strength,
    effective_magic_level,
    attack_roll, defence_roll, hit_chance,
    melee_max_hit, ranged_max_hit, magic_max_hit,
    apply_special_multiplier,
    calculate_melee_dps, calculate_ranged_dps, calculate_magic_dps,
)


# === Potion boost tests ===

class TestBoostLevel:
    def test_no_potion(self):
        assert boost_level(99, "none") == 99

    def test_super_combat(self):
        # 99 + 5 + floor(99 * 15 / 100) = 99 + 5 + 14 = 118
        assert boost_level(99, "super_combat") == 118

    def test_super_combat_low_level(self):
        # 70 + 5 + floor(70 * 15 / 100) = 70 + 5 + 10 = 85
        assert boost_level(70, "super_combat") == 85

    def test_ranging_potion(self):
        # 99 + 4 + floor(99 * 10 / 100) = 99 + 4 + 9 = 112
        assert boost_level(99, "ranging_potion") == 112

    def test_saturated_heart(self):
        # 99 + 2 + floor(99 * 10 / 100) = 99 + 2 + 9 = 110
        assert boost_level(99, "saturated_heart") == 110

    def test_overload(self):
        # 99 + 6 + floor(99 * 16 / 100) = 99 + 6 + 15 = 120
        assert boost_level(99, "overload") == 120

    def test_smelling_salts(self):
        # 99 + 11 + floor(99 * 16 / 100) = 99 + 11 + 15 = 125
        assert boost_level(99, "smelling_salts") == 125

    def test_unknown_potion_no_boost(self):
        assert boost_level(99, "banana_juice") == 99

    def test_magic_potion(self):
        # 99 + 4 + floor(99 * 0 / 100) = 103
        assert boost_level(99, "magic_potion") == 103

    def test_imbued_heart(self):
        # 99 + 1 + floor(99 * 10 / 100) = 109
        assert boost_level(99, "imbued_heart") == 109


# === Effective level tests ===

class TestEffectiveMeleeAttack:
    def test_maxed_piety_super_combat_accurate(self, maxed_stats):
        # boosted = 118, piety atk = floor(118 * 6/5) = floor(141.6) = 141
        # effective = 141 + 3(accurate) + 8 = 152
        result = effective_melee_attack(maxed_stats, "piety", "accurate", "super_combat")
        assert result == 152

    def test_maxed_no_prayer_no_pot_accurate(self, maxed_stats):
        # boosted = 99, floor(99 * 1/1) = 99
        # effective = 99 + 3 + 8 = 110
        result = effective_melee_attack(maxed_stats, "none", "accurate", "none")
        assert result == 110

    def test_aggressive_stance(self, maxed_stats):
        # aggressive gives +0 to attack, +3 to strength
        # boosted = 118, piety = floor(118*6/5) = 141
        # effective = 141 + 0 + 8 = 149
        result = effective_melee_attack(maxed_stats, "piety", "aggressive", "super_combat")
        assert result == 149

    def test_controlled_stance(self, maxed_stats):
        # controlled = +1 to both atk and str
        # 141 + 1 + 8 = 150
        result = effective_melee_attack(maxed_stats, "piety", "controlled", "super_combat")
        assert result == 150

    def test_mid_level(self, mid_level_stats):
        # boosted = 75 + 5 + floor(75*15/100) = 75+5+11 = 91
        # piety = floor(91 * 6/5) = floor(109.2) = 109
        # effective = 109 + 3 + 8 = 120
        result = effective_melee_attack(mid_level_stats, "piety", "accurate", "super_combat")
        assert result == 120


class TestEffectiveMeleeStrength:
    def test_maxed_piety_super_combat_accurate(self, maxed_stats):
        # boosted = 118, piety str = floor(118 * 123/100) = floor(145.14) = 145
        # accurate str bonus = 0, effective = 145 + 0 + 8 = 153
        result = effective_melee_strength(maxed_stats, "piety", "accurate", "super_combat")
        assert result == 153

    def test_aggressive_stance(self, maxed_stats):
        # aggressive str = +3
        # 145 + 3 + 8 = 156
        result = effective_melee_strength(maxed_stats, "piety", "aggressive", "super_combat")
        assert result == 156


class TestEffectiveRangedLevel:
    def test_maxed_rigour_super_ranging(self, maxed_stats):
        # boosted = 99 + 5 + floor(99*15/100) = 118
        # rigour = floor(118 * 6/5) = 141
        # rapid stance = +0 atk, effective = 141 + 0 + 8 = 149
        result = effective_ranged_level(maxed_stats, "rigour", "rapid", "super_ranging")
        assert result == 149

    def test_accurate_stance(self, maxed_stats):
        # accurate = +3
        # 141 + 3 + 8 = 152
        result = effective_ranged_level(maxed_stats, "rigour", "accurate", "super_ranging")
        assert result == 152


class TestEffectiveMagicLevel:
    def test_maxed_augury_saturated(self, maxed_stats):
        # boosted = 99 + 2 + floor(99*10/100) = 110
        # augury = floor(110 * 6/5) = floor(132) = 132
        # effective = 132 + 9 = 141
        result = effective_magic_level(maxed_stats, "augury", "saturated_heart")
        assert result == 141

    def test_no_prayer_no_pot(self, maxed_stats):
        # boosted = 99, floor(99*1/1) = 99
        # effective = 99 + 9 = 108
        result = effective_magic_level(maxed_stats, "none", "none")
        assert result == 108


# === Roll tests ===

class TestAttackRoll:
    def test_basic(self):
        # 152 * (82 + 64) = 152 * 146 = 22192
        assert attack_roll(152, 82) == 22192

    def test_zero_bonus(self):
        assert attack_roll(110, 0) == 110 * 64


class TestDefenceRoll:
    def test_basic(self):
        # (214 + 9) * (108 + 64) = 223 * 172 = 38356
        assert defence_roll(214, 108) == 38356

    def test_zero_defence(self):
        # (0 + 9) * (0 + 64) = 576
        assert defence_roll(0, 0) == 576


class TestHitChance:
    def test_atk_greater_than_def(self):
        # atk=30000, def=20000
        # 1.0 - (20002) / (2 * 30001) = 1.0 - 20002/60002
        acc = hit_chance(30000, 20000)
        expected = 1.0 - 20002 / 60002
        assert abs(acc - expected) < 0.0001

    def test_def_greater_than_atk(self):
        # atk=10000, def=20000
        # 10000 / (2 * 20001) = 10000/40002
        acc = hit_chance(10000, 20000)
        expected = 10000 / 40002
        assert abs(acc - expected) < 0.0001

    def test_equal_rolls(self):
        # atk=10000, def=10000, equal so uses else branch
        # 10000 / (2 * 10001) = 10000/20002
        acc = hit_chance(10000, 10000)
        expected = 10000 / 20002
        assert abs(acc - expected) < 0.0001

    def test_zero_atk(self):
        assert hit_chance(0, 1000) == 0.0

    def test_zero_def(self):
        # 1.0 - 2/(2*10001) ≈ 0.9999
        acc = hit_chance(10000, 0)
        assert acc > 0.999


# === Max hit tests ===

class TestMeleeMaxHit:
    def test_basic(self):
        # floor((153 * (82 + 64) + 320) / 640) = floor((153*146+320)/640)
        # = floor((22338+320)/640) = floor(22658/640) = floor(35.40) = 35
        assert melee_max_hit(153, 82) == 35

    def test_zero_str_bonus(self):
        # floor((110 * 64 + 320) / 640) = floor(7360/640) = 11
        assert melee_max_hit(110, 0) == 11


class TestRangedMaxHit:
    def test_same_formula_as_melee(self):
        assert ranged_max_hit(149, 20) == melee_max_hit(149, 20)


class TestMagicMaxHit:
    def test_fire_surge_no_bonus(self):
        # floor(24 * 100/100) = 24
        assert magic_max_hit(24, 0) == 24

    def test_fire_surge_with_15pct(self):
        # floor(24 * 115/100) = floor(27.6) = 27
        assert magic_max_hit(24, 15) == 27

    def test_ice_barrage_with_bonus(self):
        # floor(30 * 115/100) = floor(34.5) = 34
        assert magic_max_hit(30, 15) == 34


# === Special equipment multiplier tests ===

class TestApplySpecialMultiplier:
    def test_slayer_helm_accuracy(self):
        # floor(22000 * 7/6) = floor(25666.66) = 25666
        assert apply_special_multiplier(22000, "slayer_helm", True) == 25666

    def test_slayer_helm_damage(self):
        # floor(35 * 7/6) = floor(40.83) = 40
        assert apply_special_multiplier(35, "slayer_helm", False) == 40

    def test_salve_amulet_ei_accuracy(self):
        # floor(22000 * 6/5) = 26400
        assert apply_special_multiplier(22000, "salve_amulet_ei", True) == 26400

    def test_void_melee_damage(self):
        # floor(35 * 11/10) = 38
        assert apply_special_multiplier(35, "void_melee", False) == 38

    def test_dhcb_accuracy(self):
        # floor(22000 * 13/10) = 28600
        assert apply_special_multiplier(22000, "dragon_hunter_crossbow", True) == 28600

    def test_dhcb_damage(self):
        # floor(35 * 5/4) = 43
        assert apply_special_multiplier(35, "dragon_hunter_crossbow", False) == 43

    def test_unknown_key_returns_value(self):
        assert apply_special_multiplier(100, "nonexistent_thing", True) == 100


# === Full DPS calculation tests ===

class TestCalculateMeleeDps:
    def test_whip_vs_abyssal_demon(self, maxed_stats, whip_gear, abyssal_demon):
        result = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            attack_type="slash", stance="accurate",
            prayer="piety", potion="super_combat",
        )
        assert isinstance(result, DpsResult)
        assert result.max_hit > 0
        assert 0 < result.accuracy <= 1
        assert result.dps > 0
        assert result.attack_speed == 4
        assert result.ttk_seconds > 0

    def test_rapier_stab_vs_slash(self, maxed_stats, rapier_gear, vorkath):
        stab = calculate_melee_dps(
            maxed_stats, rapier_gear, vorkath,
            attack_type="stab", prayer="piety", potion="super_combat",
        )
        slash = calculate_melee_dps(
            maxed_stats, rapier_gear, vorkath,
            attack_type="slash", prayer="piety", potion="super_combat",
        )
        # Vorkath: dstab=26, dslash=108. Stab should be much better.
        assert stab.accuracy > slash.accuracy
        assert stab.dps > slash.dps

    def test_slayer_task_boosts_dps(self, maxed_stats, whip_gear, abyssal_demon):
        normal = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat", on_slayer_task=False,
        )
        on_task = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat", on_slayer_task=True,
        )
        assert on_task.dps > normal.dps
        assert on_task.max_hit > normal.max_hit

    def test_dhl_vs_dragon(self, maxed_stats, vorkath):
        gear = GearSetup(astab=85, melee_str=80, speed=4)  # DHL-like
        normal = calculate_melee_dps(
            maxed_stats, gear, vorkath,
            attack_type="stab", prayer="piety", potion="super_combat",
        )
        with_dhl = calculate_melee_dps(
            maxed_stats, gear, vorkath,
            attack_type="stab", prayer="piety", potion="super_combat",
            special_equipment="dragon_hunter_lance",
        )
        assert with_dhl.dps > normal.dps  # DHL should boost vs dragon

    def test_dhl_no_effect_vs_non_dragon(self, maxed_stats, abyssal_demon):
        gear = GearSetup(astab=85, melee_str=80, speed=4)
        normal = calculate_melee_dps(
            maxed_stats, gear, abyssal_demon,
            attack_type="stab", prayer="piety", potion="super_combat",
        )
        with_dhl = calculate_melee_dps(
            maxed_stats, gear, abyssal_demon,
            attack_type="stab", prayer="piety", potion="super_combat",
            special_equipment="dragon_hunter_lance",
        )
        assert with_dhl.dps == normal.dps  # DHL has no effect vs demons

    def test_salve_vs_undead(self, maxed_stats, whip_gear, undead_monster):
        normal = calculate_melee_dps(
            maxed_stats, whip_gear, undead_monster,
            prayer="piety", potion="super_combat",
        )
        with_salve = calculate_melee_dps(
            maxed_stats, whip_gear, undead_monster,
            prayer="piety", potion="super_combat",
            special_equipment="salve_amulet_ei",
        )
        assert with_salve.dps > normal.dps

    def test_salve_no_effect_vs_non_undead(self, maxed_stats, whip_gear, abyssal_demon):
        normal = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat",
        )
        with_salve = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat",
            special_equipment="salve_amulet_ei",
        )
        assert with_salve.dps == normal.dps

    def test_void_applies_universally(self, maxed_stats, whip_gear, abyssal_demon):
        normal = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat",
        )
        with_void = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat",
            special_equipment="void_melee",
        )
        assert with_void.dps > normal.dps

    def test_no_prayer_no_potion(self, maxed_stats, whip_gear, giant_rat):
        result = calculate_melee_dps(
            maxed_stats, whip_gear, giant_rat,
            prayer="none", potion="none", stance="accurate",
        )
        assert result.dps > 0
        assert result.accuracy > 0.9  # Should crush a giant rat

    def test_zero_dps_impossible_scenario(self):
        """If gear has 0 strength bonus and effective str is minimal, check no div-by-zero."""
        stats = PlayerStats(attack=1, strength=1, defence=1, ranged=1, magic=1, hitpoints=10, prayer=1)
        gear = GearSetup(speed=4)
        monster = Monster(hitpoints=1000, defence_level=999, dslash=999)
        result = calculate_melee_dps(stats, gear, monster, prayer="none", potion="none")
        assert result.dps >= 0
        assert result.max_hit >= 0

    def test_ttk_calculation(self, maxed_stats, whip_gear, abyssal_demon):
        result = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat",
        )
        # TTK should be hp / dps
        expected_ttk = abyssal_demon.hitpoints / result.dps
        assert abs(result.ttk_seconds - round(expected_ttk, 1)) < 0.2

    def test_details_populated(self, maxed_stats, whip_gear, abyssal_demon):
        result = calculate_melee_dps(
            maxed_stats, whip_gear, abyssal_demon,
            prayer="piety", potion="super_combat",
        )
        assert "effective_attack" in result.details
        assert "effective_strength" in result.details
        assert "attack_roll" in result.details
        assert "defence_roll" in result.details


class TestCalculateRangedDps:
    def test_basic_ranged(self, maxed_stats, tbow_gear, vorkath):
        result = calculate_ranged_dps(
            maxed_stats, tbow_gear, vorkath,
            stance="rapid", prayer="rigour", potion="super_ranging",
        )
        assert result.dps > 0
        assert result.attack_style == "ranged"
        assert result.weapon == "ranged"

    def test_rapid_reduces_speed(self, maxed_stats, tbow_gear, vorkath):
        rapid = calculate_ranged_dps(
            maxed_stats, tbow_gear, vorkath,
            stance="rapid", prayer="rigour", potion="super_ranging",
        )
        accurate = calculate_ranged_dps(
            maxed_stats, tbow_gear, vorkath,
            stance="accurate", prayer="rigour", potion="super_ranging",
        )
        # Rapid should be 1 tick faster
        assert rapid.attack_speed == tbow_gear.speed - 1
        assert accurate.attack_speed == tbow_gear.speed

    def test_dhcb_vs_dragon(self, maxed_stats, vorkath):
        gear = GearSetup(arange=95, ranged_str=100, speed=5)
        normal = calculate_ranged_dps(
            maxed_stats, gear, vorkath,
            prayer="rigour", potion="super_ranging",
        )
        with_dhcb = calculate_ranged_dps(
            maxed_stats, gear, vorkath,
            prayer="rigour", potion="super_ranging",
            special_equipment="dragon_hunter_crossbow",
        )
        assert with_dhcb.dps > normal.dps

    def test_slayer_task_ranged(self, maxed_stats, abyssal_demon):
        gear = GearSetup(arange=80, ranged_str=60, speed=3)
        normal = calculate_ranged_dps(
            maxed_stats, gear, abyssal_demon,
            prayer="rigour", potion="super_ranging",
        )
        on_task = calculate_ranged_dps(
            maxed_stats, gear, abyssal_demon,
            prayer="rigour", potion="super_ranging",
            on_slayer_task=True,
        )
        assert on_task.dps > normal.dps

    def test_rapid_speed_minimum_one(self):
        """Speed should never go below 1 tick even if gear speed is 1."""
        stats = PlayerStats()
        gear = GearSetup(arange=50, ranged_str=50, speed=1)
        monster = Monster(hitpoints=100, defence_level=50, drange=0)
        result = calculate_ranged_dps(stats, gear, monster, stance="rapid")
        assert result.attack_speed >= 1


class TestCalculateMagicDps:
    def test_basic_magic(self, maxed_stats, trident_gear, abyssal_demon):
        result = calculate_magic_dps(
            maxed_stats, trident_gear, abyssal_demon,
            spell_max_hit=24, prayer="augury", potion="saturated_heart",
        )
        assert result.dps > 0
        assert result.attack_style == "magic"

    def test_magic_damage_bonus(self, maxed_stats, abyssal_demon):
        no_bonus = calculate_magic_dps(
            maxed_stats, GearSetup(amagic=25, speed=4),
            abyssal_demon, spell_max_hit=24,
        )
        with_bonus = calculate_magic_dps(
            maxed_stats, GearSetup(amagic=25, magic_dmg=15, speed=4),
            abyssal_demon, spell_max_hit=24,
        )
        assert with_bonus.max_hit > no_bonus.max_hit

    def test_magic_uses_npc_magic_level_for_defence(self, maxed_stats, trident_gear):
        """Magic defence roll uses NPC magic level, not defence level."""
        # Monster with high def but low magic
        low_magic = Monster(hitpoints=100, defence_level=300, magic_level=1, dmagic=0)
        high_magic = Monster(hitpoints=100, defence_level=1, magic_level=300, dmagic=0)

        result_low = calculate_magic_dps(maxed_stats, trident_gear, low_magic, spell_max_hit=24)
        result_high = calculate_magic_dps(maxed_stats, trident_gear, high_magic, spell_max_hit=24)

        # Low magic monster should be easier to hit with magic
        assert result_low.accuracy > result_high.accuracy

    def test_slayer_task_magic(self, maxed_stats, trident_gear, abyssal_demon):
        normal = calculate_magic_dps(
            maxed_stats, trident_gear, abyssal_demon, spell_max_hit=24,
        )
        on_task = calculate_magic_dps(
            maxed_stats, trident_gear, abyssal_demon, spell_max_hit=24,
            on_slayer_task=True,
        )
        assert on_task.dps > normal.dps

    def test_details_contain_spell_base_max(self, maxed_stats, trident_gear, abyssal_demon):
        result = calculate_magic_dps(
            maxed_stats, trident_gear, abyssal_demon, spell_max_hit=30,
        )
        assert result.details["spell_base_max"] == 30
