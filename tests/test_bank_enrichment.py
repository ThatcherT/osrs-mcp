"""Tests for bank item enrichment, placeholder filtering, and boss_setup helpers."""
import pytest
from unittest.mock import patch, AsyncMock

from osrs_mcp.tools.player import _enrich_bank_item
from osrs_mcp.tools.dps import (
    _analyze_weakness, _pick_prayer, _pick_potion, _weakness_to_style,
    _detect_combat_style, _weapon_can_cast,
)
from osrs_mcp.dps.types import Monster


# === _enrich_bank_item ===


class TestEnrichBankItem:
    """Test the bank item enrichment function."""

    def _equip(self, **kwargs):
        """Helper to build a minimal equipment entry."""
        base = {"slot": "head", "astab": 0, "aslash": 0, "acrush": 0,
                "arange": 0, "amagic": 0, "dstab": 0, "dslash": 0,
                "dcrush": 0, "drange": 0, "dmagic": 0, "str": 0,
                "rstr": 0, "mdmg": 0, "prayer": 0}
        base.update(kwargs)
        return base

    def test_basic_enrichment(self):
        equipment = {"dragon scimitar": self._equip(slot="weapon", aslash=67, str=66)}
        item = {"item_id": 4587, "name": "Dragon scimitar", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        assert result["slot"] == "weapon"
        assert result["bonuses"]["aslash"] == 67
        assert result["bonuses"]["str"] == 66

    def test_unknown_item_not_enriched(self):
        equipment = {}
        item = {"item_id": 99999, "name": "Unknown item (99999)", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        assert "slot" not in result
        assert "bonuses" not in result

    def test_zero_stats_shows_none(self):
        """Items with a slot but all-zero stats get 'none' bonuses."""
        equipment = {"ring of dueling": self._equip(slot="ring")}
        item = {"item_id": 2552, "name": "Ring of dueling", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        assert result["slot"] == "ring"
        assert result["bonuses"] == "none (no combat stats)"

    def test_active_fallback_for_charged_item(self):
        """When base item has 0 stats and #active exists, use active stats."""
        equipment = {
            "crystal shield": self._equip(slot="shield"),  # all zeros
            "crystal shield#active": self._equip(
                slot="shield", dstab=51, dslash=54, dcrush=53, drange=80,
                arange=-10, amagic=-10,
            ),
        }
        item = {"item_id": 4224, "name": "Crystal shield", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        assert result["slot"] == "shield"
        assert isinstance(result["bonuses"], dict)
        assert result["bonuses"]["drange"] == 80
        assert result["bonuses"]["dslash"] == 54

    def test_active_fallback_crystal_helm(self):
        equipment = {
            "crystal helm": self._equip(slot="head"),
            "crystal helm#active": self._equip(
                slot="head", arange=9, dstab=12, dslash=8, dcrush=14,
                drange=18, dmagic=10, prayer=2, amagic=-10,
            ),
        }
        item = {"item_id": 23971, "name": "Crystal helm", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        assert result["bonuses"]["drange"] == 18
        assert result["bonuses"]["prayer"] == 2

    def test_no_active_variant_stays_zero(self):
        """Items with 0 stats and no #active variant stay as 'none'."""
        equipment = {"gas mask": self._equip(slot="head")}
        item = {"item_id": 4164, "name": "Gas mask", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        assert result["bonuses"] == "none (no combat stats)"

    def test_nonzero_base_not_overridden(self):
        """Items that already have stats should NOT be overridden by #active."""
        equipment = {
            "abyssal whip": self._equip(slot="weapon", aslash=82, str=82),
            "abyssal whip#active": self._equip(slot="weapon", aslash=999, str=999),
        }
        item = {"item_id": 4151, "name": "Abyssal whip", "quantity": 1}
        result = _enrich_bank_item(item, equipment)
        # Should use base stats, not #active
        assert result["bonuses"]["aslash"] == 82
        assert result["bonuses"]["str"] == 82


# === get_bank placeholder/noted filtering ===


class TestGetBank:
    """Test bank item resolution and filtering."""

    @pytest.fixture
    def mock_id_map(self):
        return {
            995: "Coins",
            4151: "Abyssal whip",
            4224: "Crystal shield",
            22981: "Ferocious gloves",  # base item
            # 22982 is the noted variant (id + 1), NOT in map
        }

    async def test_known_items_resolved(self, mock_id_map):
        raw = [(995, 50000), (4151, 1)]
        with patch("osrs_mcp.api.runelite_bank.get_bank_raw", return_value=raw), \
             patch("osrs_mcp.api.runelite_bank._build_id_map", new_callable=AsyncMock, return_value=mock_id_map):
            from osrs_mcp.api.runelite_bank import get_bank
            bank = await get_bank("testplayer")
            names = [i["name"] for i in bank]
            assert "Coins" in names
            assert "Abyssal whip" in names

    async def test_placeholders_filtered_out(self, mock_id_map):
        """Unresolvable IDs (placeholders) are dropped entirely."""
        raw = [(995, 50000), (14182, 1), (15717, 1)]
        with patch("osrs_mcp.api.runelite_bank.get_bank_raw", return_value=raw), \
             patch("osrs_mcp.api.runelite_bank._build_id_map", new_callable=AsyncMock, return_value=mock_id_map):
            from osrs_mcp.api.runelite_bank import get_bank
            bank = await get_bank("testplayer")
            assert len(bank) == 1  # only Coins
            assert bank[0]["name"] == "Coins"

    async def test_noted_variant_resolved(self, mock_id_map):
        """ID that is base_item + 1 resolves as noted variant."""
        raw = [(22982, 1)]  # Ferocious gloves noted (22981 + 1)
        with patch("osrs_mcp.api.runelite_bank.get_bank_raw", return_value=raw), \
             patch("osrs_mcp.api.runelite_bank._build_id_map", new_callable=AsyncMock, return_value=mock_id_map):
            from osrs_mcp.api.runelite_bank import get_bank
            bank = await get_bank("testplayer")
            assert len(bank) == 1
            assert bank[0]["name"] == "Ferocious gloves (noted)"

    async def test_no_bank_data_returns_none(self):
        with patch("osrs_mcp.api.runelite_bank.get_bank_raw", return_value=None):
            from osrs_mcp.api.runelite_bank import get_bank
            assert await get_bank("nobody") is None

    async def test_sorted_by_quantity_desc(self, mock_id_map):
        raw = [(4151, 1), (995, 50000), (4224, 3)]
        with patch("osrs_mcp.api.runelite_bank.get_bank_raw", return_value=raw), \
             patch("osrs_mcp.api.runelite_bank._build_id_map", new_callable=AsyncMock, return_value=mock_id_map):
            from osrs_mcp.api.runelite_bank import get_bank
            bank = await get_bank("testplayer")
            qtys = [i["quantity"] for i in bank]
            assert qtys == sorted(qtys, reverse=True)


# === boss_setup helpers ===


class TestAnalyzeWeakness:
    """Test _analyze_weakness monster defence analysis."""

    def test_weakest_is_magic(self):
        mon = Monster(name="Sarachnis", dstab=100, dslash=100, dcrush=100,
                      drange=100, dmagic=-20)
        result = _analyze_weakness(mon)
        assert result["weakest_style"] == "magic"
        assert result["defences"]["magic"] == -20

    def test_weakest_is_stab(self):
        mon = Monster(name="Dragon", dstab=10, dslash=80, dcrush=80,
                      drange=80, dmagic=80)
        result = _analyze_weakness(mon)
        assert result["weakest_style"] == "stab"

    def test_elemental_weakness_included(self):
        mon = Monster(name="Ice troll", elemental_weakness="Fire",
                      elemental_weakness_percent=30)
        result = _analyze_weakness(mon)
        assert result["elemental_weakness"] == "Fire"
        assert result["elemental_weakness_percent"] == 30

    def test_no_elemental_weakness(self):
        mon = Monster(name="Goblin")
        result = _analyze_weakness(mon)
        assert result["elemental_weakness"] is None
        assert result["elemental_weakness_percent"] == 0


class TestPickPrayer:
    """Test prayer selection based on style and prayer level."""

    def test_melee_piety(self):
        assert _pick_prayer("melee", 70) == "piety"
        assert _pick_prayer("melee", 99) == "piety"

    def test_melee_chivalry(self):
        assert _pick_prayer("melee", 60) == "chivalry"
        assert _pick_prayer("melee", 69) == "chivalry"

    def test_melee_ultimate_strength(self):
        assert _pick_prayer("melee", 31) == "ultimate_strength"
        assert _pick_prayer("melee", 59) == "ultimate_strength"

    def test_melee_superhuman_strength(self):
        assert _pick_prayer("melee", 13) == "superhuman_strength"
        assert _pick_prayer("melee", 30) == "superhuman_strength"

    def test_melee_burst_of_strength(self):
        assert _pick_prayer("melee", 4) == "burst_of_strength"
        assert _pick_prayer("melee", 12) == "burst_of_strength"

    def test_melee_no_prayer(self):
        assert _pick_prayer("melee", 3) == "none"
        assert _pick_prayer("melee", 1) == "none"

    def test_ranged_rigour(self):
        assert _pick_prayer("ranged", 74) == "rigour"

    def test_ranged_eagle_eye(self):
        assert _pick_prayer("ranged", 44) == "eagle_eye"
        assert _pick_prayer("ranged", 73) == "eagle_eye"

    def test_ranged_hawk_eye(self):
        assert _pick_prayer("ranged", 26) == "hawk_eye"
        assert _pick_prayer("ranged", 43) == "hawk_eye"

    def test_ranged_sharp_eye(self):
        assert _pick_prayer("ranged", 8) == "sharp_eye"
        assert _pick_prayer("ranged", 25) == "sharp_eye"

    def test_ranged_no_prayer(self):
        assert _pick_prayer("ranged", 7) == "none"

    def test_magic_augury(self):
        assert _pick_prayer("magic", 77) == "augury"

    def test_magic_mystic_might(self):
        assert _pick_prayer("magic", 45) == "mystic_might"
        assert _pick_prayer("magic", 76) == "mystic_might"

    def test_magic_mystic_lore(self):
        assert _pick_prayer("magic", 27) == "mystic_lore"
        assert _pick_prayer("magic", 44) == "mystic_lore"

    def test_magic_mystic_will(self):
        assert _pick_prayer("magic", 9) == "mystic_will"
        assert _pick_prayer("magic", 26) == "mystic_will"

    def test_magic_no_prayer(self):
        assert _pick_prayer("magic", 8) == "none"


class TestPickPotion:
    def test_melee(self):
        assert _pick_potion("melee") == "super_combat"

    def test_ranged(self):
        assert _pick_potion("ranged") == "super_ranging"

    def test_magic(self):
        assert _pick_potion("magic") == "saturated_heart"


class TestWeaknessToStyle:
    def test_stab(self):
        assert _weakness_to_style("stab") == "melee"

    def test_slash(self):
        assert _weakness_to_style("slash") == "melee"

    def test_crush(self):
        assert _weakness_to_style("crush") == "melee"

    def test_ranged(self):
        assert _weakness_to_style("ranged") == "ranged"

    def test_magic(self):
        assert _weakness_to_style("magic") == "magic"


class TestDetectCombatStyleMagic:
    """Test that _detect_combat_style properly detects magic weapons."""

    def test_magic_weapon(self):
        weapon = {"amagic": 20, "astab": 0, "aslash": 0, "acrush": 0, "arange": 0}
        assert _detect_combat_style(weapon) == ("magic", "magic")

    def test_magic_with_melee_lower(self):
        weapon = {"amagic": 15, "astab": 10, "aslash": 10, "acrush": 10, "arange": 5}
        assert _detect_combat_style(weapon) == ("magic", "magic")

    def test_melee_beats_magic(self):
        weapon = {"amagic": 5, "astab": 0, "aslash": 82, "acrush": 0, "arange": 0}
        assert _detect_combat_style(weapon) == ("melee", "slash")


class TestKphCalculation:
    """Test the KPH formula used in boss_setup."""

    def test_basic_kph(self):
        """60s TTK + 30s overhead = 90s per kill = 40 KPH."""
        ttk = 60
        overhead = 30
        kph = round(3600 / (ttk + overhead), 1)
        assert kph == 40.0

    def test_fast_kill(self):
        """10s TTK + 30s overhead = 40s per kill = 90 KPH."""
        ttk = 10
        overhead = 30
        kph = round(3600 / (ttk + overhead), 1)
        assert kph == 90.0

    def test_zero_overhead(self):
        """120s TTK + 0s overhead = 30 KPH."""
        ttk = 120
        overhead = 0
        kph = round(3600 / (ttk + overhead), 1)
        assert kph == 30.0


class TestWeaponCanCast:
    """Test spell-weapon compatibility checking."""

    def test_no_requirements(self):
        """Standard spells can be cast with any weapon."""
        spell = {"name": "Fire Surge", "max_hit": 24, "element": "Fire"}
        assert _weapon_can_cast("Ancient staff", spell) is True
        assert _weapon_can_cast("Staff of air", spell) is True

    def test_ibans_blast_requires_ibans_staff(self):
        spell = {"name": "Iban's Blast", "max_hit": 25, "required_weapons": ["iban's staff"]}
        assert _weapon_can_cast("Iban's staff", spell) is True
        assert _weapon_can_cast("Iban's staff (u)", spell) is True
        assert _weapon_can_cast("Ancient staff", spell) is False
        assert _weapon_can_cast("Staff of air", spell) is False

    def test_god_spell_zamorak(self):
        spell = {"name": "Flames of Zamorak", "max_hit": 20,
                 "required_weapons": ["zamorak staff", "staff of the dead"]}
        assert _weapon_can_cast("Zamorak staff", spell) is True
        assert _weapon_can_cast("Staff of the dead", spell) is True
        assert _weapon_can_cast("Toxic staff of the dead", spell) is True
        assert _weapon_can_cast("Saradomin staff", spell) is False

    def test_god_spell_saradomin(self):
        spell = {"name": "Saradomin Strike", "max_hit": 20,
                 "required_weapons": ["saradomin staff", "staff of light"]}
        assert _weapon_can_cast("Saradomin staff", spell) is True
        assert _weapon_can_cast("Staff of light", spell) is True
        assert _weapon_can_cast("Guthix staff", spell) is False

    def test_magic_dart(self):
        spell = {"name": "Magic Dart", "max_hit": 19,
                 "required_weapons": ["slayer's staff", "staff of the dead",
                                      "staff of light", "staff of balance"]}
        assert _weapon_can_cast("Slayer's staff", spell) is True
        assert _weapon_can_cast("Slayer's staff (e)", spell) is True
        assert _weapon_can_cast("Staff of the dead", spell) is True
        assert _weapon_can_cast("Ancient staff", spell) is False

    def test_case_insensitive(self):
        spell = {"name": "Iban's Blast", "max_hit": 25, "required_weapons": ["iban's staff"]}
        assert _weapon_can_cast("IBAN'S STAFF", spell) is True
        assert _weapon_can_cast("iban's staff (u)", spell) is True
