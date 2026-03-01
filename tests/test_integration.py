"""Integration tests using real local data (equipment.json, monsters.json).

No API calls — these tests verify that data loading, variant resolution,
bank enrichment, gear selection, and DPS ranking all work end-to-end.
"""
import pytest

from osrs_mcp.util.data import load_equipment, find_equipment_by_name, find_monster_by_name
from osrs_mcp.tools.player import _enrich_bank_item, _best_per_slot
from osrs_mcp.tools.dps import (
    _detect_combat_style, _best_armor_for_style, _parse_gear,
    _monster_to_obj,
)
from osrs_mcp.dps.types import PlayerStats
from osrs_mcp.dps.calc import calculate_melee_dps, calculate_ranged_dps


class TestEquipmentVariantResolution:
    """Verify barrows and other variant items resolve through the fallback."""

    def test_dharoks_greataxe_resolves(self):
        equip = load_equipment()
        item = equip.get("dharok's greataxe")
        assert item is not None
        assert item.get("slot") == "2h"
        assert int(item.get("acrush", 0)) == 95
        assert int(item.get("str", 0)) == 105

    def test_karils_leathertop_resolves(self):
        equip = load_equipment()
        item = equip.get("karil's leathertop")
        assert item is not None
        assert item.get("slot") == "body"

    def test_dharoks_platebody_resolves(self):
        equip = load_equipment()
        item = equip.get("dharok's platebody")
        assert item is not None
        assert item.get("slot") == "body"

    def test_find_equipment_by_name_dharoks(self):
        item = find_equipment_by_name("Dharok's greataxe")
        assert item is not None
        assert item.get("slot") == "2h"


class TestBankItemEnrichment:
    """Verify _enrich_bank_item adds slot and bonuses correctly."""

    def test_normal_item_enriched(self):
        equipment = load_equipment()
        bank_item = {"item_id": 1127, "name": "Rune platebody", "quantity": 1}
        enriched = _enrich_bank_item(bank_item, equipment)
        assert enriched.get("slot") == "body"
        bonuses = enriched.get("bonuses")
        assert isinstance(bonuses, dict)
        assert bonuses.get("dstab", 0) > 0  # rune platebody has defensive stats

    def test_variant_item_enriched(self):
        equipment = load_equipment()
        bank_item = {"item_id": 4720, "name": "Dharok's platebody", "quantity": 1}
        enriched = _enrich_bank_item(bank_item, equipment)
        assert enriched.get("slot") == "body"

    def test_non_equipment_item_unchanged(self):
        equipment = load_equipment()
        bank_item = {"item_id": 995, "name": "Coins", "quantity": 1000}
        enriched = _enrich_bank_item(bank_item, equipment)
        assert "slot" not in enriched
        assert "bonuses" not in enriched


class TestBISGearSelection:
    """Verify _best_per_slot picks the correct best item."""

    def test_dharoks_over_rune_for_dstab(self):
        """Dharok's platebody should beat Rune platebody for dstab."""
        equipment = load_equipment()
        items = []
        for name in ["Rune platebody", "Dharok's platebody"]:
            bank_item = {"item_id": 0, "name": name, "quantity": 1}
            enriched = _enrich_bank_item(bank_item, equipment)
            if enriched.get("slot"):
                items.append(enriched)

        by_slot = {"body": items}
        result = _best_per_slot(by_slot, "dstab")
        assert "body" in result
        assert result["body"]["name"] == "Dharok's platebody"

    def test_best_per_slot_melee_str(self):
        """When optimizing for str, should pick highest melee_str item."""
        equipment = load_equipment()
        items = []
        for name in ["Rune platebody", "Fighter torso"]:
            bank_item = {"item_id": 0, "name": name, "quantity": 1}
            enriched = _enrich_bank_item(bank_item, equipment)
            if enriched.get("slot"):
                items.append(enriched)

        by_slot = {"body": items}
        result = _best_per_slot(by_slot, "str")
        # Fighter torso has str bonus, rune platebody does not
        if "body" in result:
            assert result["body"]["name"] == "Fighter torso"


class TestWeaponStyleDetection:
    """Verify _detect_combat_style identifies weapon types correctly."""

    def test_dragon_scimitar_is_melee_slash(self):
        item = find_equipment_by_name("Dragon scimitar")
        assert item is not None
        style, attack_type = _detect_combat_style(item)
        assert style == "melee"
        assert attack_type == "slash"

    def test_rune_crossbow_is_ranged(self):
        item = find_equipment_by_name("Rune crossbow")
        assert item is not None
        style, attack_type = _detect_combat_style(item)
        assert style == "ranged"
        assert attack_type == "ranged"

    def test_bone_mace_is_melee_crush(self):
        item = find_equipment_by_name("Bone mace")
        assert item is not None
        style, attack_type = _detect_combat_style(item)
        assert style == "melee"
        assert attack_type == "crush"

    def test_abyssal_whip_is_melee_slash(self):
        item = find_equipment_by_name("Abyssal whip")
        assert item is not None
        style, attack_type = _detect_combat_style(item)
        assert style == "melee"
        assert attack_type == "slash"

    def test_dharoks_greataxe_is_melee_slash(self):
        """Dharok's greataxe: aslash=103 > acrush=95, so slash."""
        item = find_equipment_by_name("Dharok's greataxe")
        assert item is not None
        style, attack_type = _detect_combat_style(item)
        assert style == "melee"
        assert attack_type == "slash"


class TestSuggestLoadoutRanking:
    """Test DPS ranking with known weapons against a known monster.

    Uses real equipment data but constructs the DPS comparison manually
    (no API calls needed).
    """

    def _build_sarachnis(self) -> "Monster":
        """Sarachnis from local data or hardcoded."""
        local = find_monster_by_name("Sarachnis")
        if local:
            return _monster_to_obj(local)
        # Fallback: hardcoded Sarachnis stats
        from osrs_mcp.dps.types import Monster
        return Monster(
            name="Sarachnis",
            combat_level=318,
            hitpoints=400,
            defence_level=100,
            dstab=0, dslash=0, dcrush=-10,
            drange=0, dmagic=0,
        )

    def test_dharoks_beats_bone_mace_at_sarachnis(self):
        """Dharok's greataxe should out-DPS Bone mace at Sarachnis."""
        stats = PlayerStats()  # maxed
        mon = self._build_sarachnis()

        # Dharok's greataxe setup
        dh_axe = find_equipment_by_name("Dharok's greataxe")
        assert dh_axe is not None
        dh_gear = _parse_gear([dh_axe])
        dh_style, dh_type = _detect_combat_style(dh_axe)
        dh_result = calculate_melee_dps(
            stats, dh_gear, mon,
            attack_type=dh_type, stance="aggressive",
            prayer="piety", potion="super_combat",
        )

        # Bone mace setup
        bone = find_equipment_by_name("Bone mace")
        assert bone is not None
        bone_gear = _parse_gear([bone])
        bone_style, bone_type = _detect_combat_style(bone)
        bone_result = calculate_melee_dps(
            stats, bone_gear, mon,
            attack_type=bone_type, stance="aggressive",
            prayer="piety", potion="super_combat",
        )

        assert dh_result.dps > bone_result.dps, (
            f"Dharok's greataxe ({dh_result.dps}) should beat "
            f"Bone mace ({bone_result.dps}) at Sarachnis"
        )

    def test_whip_beats_bone_mace_at_sarachnis(self):
        """Abyssal whip should out-DPS Bone mace at Sarachnis."""
        stats = PlayerStats()
        mon = self._build_sarachnis()

        whip = find_equipment_by_name("Abyssal whip")
        assert whip is not None
        whip_gear = _parse_gear([whip])
        _, whip_type = _detect_combat_style(whip)
        whip_result = calculate_melee_dps(
            stats, whip_gear, mon,
            attack_type=whip_type, stance="aggressive",
            prayer="piety", potion="super_combat",
        )

        bone = find_equipment_by_name("Bone mace")
        assert bone is not None
        bone_gear = _parse_gear([bone])
        _, bone_type = _detect_combat_style(bone)
        bone_result = calculate_melee_dps(
            stats, bone_gear, mon,
            attack_type=bone_type, stance="aggressive",
            prayer="piety", potion="super_combat",
        )

        assert whip_result.dps > bone_result.dps

    def test_ranged_weapon_detected_and_calculates(self):
        """Rune crossbow should produce valid ranged DPS."""
        stats = PlayerStats()
        mon = self._build_sarachnis()

        rcb = find_equipment_by_name("Rune crossbow")
        assert rcb is not None
        rcb_gear = _parse_gear([rcb])
        style, _ = _detect_combat_style(rcb)
        assert style == "ranged"

        result = calculate_ranged_dps(
            stats, rcb_gear, mon,
            stance="rapid", prayer="rigour", potion="super_ranging",
        )
        assert result.dps > 0
        assert result.accuracy > 0
