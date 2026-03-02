"""Tests for cache, config, data utilities, and query builder."""
import time
import json
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from osrs_mcp.cache import TTLCache
from osrs_mcp.api.wiki_bucket import _build_query, _flatten_result
from osrs_mcp.util.data import get_weapon_speed, WEAPON_SPEEDS, WEAPON_SPEED_OVERRIDES


# === TTLCache tests ===

class TestTTLCache:
    def test_set_and_get(self):
        c = TTLCache(default_ttl=60)
        c.set("key", "value")
        assert c.get("key") == "value"

    def test_get_missing_key(self):
        c = TTLCache()
        assert c.get("nonexistent") is None

    def test_ttl_expiration(self):
        c = TTLCache(default_ttl=1)
        c.set("key", "value", ttl=0)  # Expire immediately
        # Sleep briefly to ensure expiration
        time.sleep(0.01)
        assert c.get("key") is None

    def test_custom_ttl(self):
        c = TTLCache(default_ttl=1)
        c.set("short", "a", ttl=0)
        c.set("long", "b", ttl=3600)
        time.sleep(0.01)
        assert c.get("short") is None
        assert c.get("long") == "b"

    def test_overwrite(self):
        c = TTLCache()
        c.set("key", "first")
        c.set("key", "second")
        assert c.get("key") == "second"

    def test_clear(self):
        c = TTLCache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_stores_various_types(self):
        c = TTLCache()
        c.set("list", [1, 2, 3])
        c.set("dict", {"a": 1})
        c.set("none", None)
        c.set("int", 42)
        assert c.get("list") == [1, 2, 3]
        assert c.get("dict") == {"a": 1}
        assert c.get("none") is None  # Can't distinguish from missing
        assert c.get("int") == 42


# === Config tests ===

class TestConfig:
    def test_default_config(self):
        with patch("osrs_mcp.config.Path.exists", return_value=False):
            # Reset the cached config
            import osrs_mcp.config as cfg_mod
            cfg_mod._config = None
            config = cfg_mod.get_config()
            assert config.username == ""
            assert "osrs-mcp" in config.user_agent
            cfg_mod._config = None  # Reset for other tests

    def test_config_from_file(self):
        mock_data = json.dumps({
            "username": "TestUser",
            "user_agent": "test-agent/1.0",
        })
        import osrs_mcp.config as cfg_mod
        cfg_mod._config = None
        with patch("osrs_mcp.config.Path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=mock_data)):
            config = cfg_mod.get_config()
            assert config.username == "TestUser"
            assert config.user_agent == "test-agent/1.0"
        cfg_mod._config = None

    def test_config_singleton(self):
        import osrs_mcp.config as cfg_mod
        cfg_mod._config = None
        with patch("osrs_mcp.config.Path.exists", return_value=False):
            c1 = cfg_mod.get_config()
            c2 = cfg_mod.get_config()
            assert c1 is c2
        cfg_mod._config = None


# === Query builder tests ===

class TestBuildQuery:
    def test_simple_query(self):
        q = _build_query("infobox_monster", ["name", "hitpoints"])
        assert q == "bucket('infobox_monster').select('name','hitpoints').limit(500).run()"

    def test_with_where(self):
        q = _build_query("infobox_monster", ["name"], where={"name": "Vorkath"})
        assert ".where('name','Vorkath')" in q

    def test_with_offset(self):
        q = _build_query("infobox_monster", ["name"], limit=5000, offset=5000)
        assert ".limit(5000)" in q
        assert ".offset(5000)" in q

    def test_no_offset_when_zero(self):
        q = _build_query("infobox_monster", ["name"], offset=0)
        assert ".offset(" not in q

    def test_escapes_single_quotes(self):
        q = _build_query("quest", ["name"], where={"name": "Cook's Assistant"})
        assert "Cook\\'s Assistant" in q

    def test_empty_fields(self):
        q = _build_query("test_bucket", [])
        assert ".select(" not in q

    def test_multiple_where_clauses(self):
        q = _build_query("test", ["a"], where={"x": "1", "y": "2"})
        assert ".where('x','1')" in q
        assert ".where('y','2')" in q


class TestFlattenResult:
    def test_flattens_prefixed_keys(self):
        row = {
            "infobox_item.page_name_sub": "Abyssal whip",
            "infobox_item.examine": "A weapon.",
            "infobox_bonuses.strength_bonus": 82,
        }
        flat = _flatten_result(row)
        assert flat["page_name_sub"] == "Abyssal whip"
        assert flat["examine"] == "A weapon."
        assert flat["strength_bonus"] == 82

    def test_unprefixed_keys_pass_through(self):
        row = {"name": "test", "combat_level": 100}
        flat = _flatten_result(row)
        assert flat == row

    def test_empty_dict(self):
        assert _flatten_result({}) == {}


# === Weapon speed tests ===

class TestGetWeaponSpeed:
    def test_override_takes_priority(self):
        assert get_weapon_speed("Abyssal whip", "whip") == 4
        assert get_weapon_speed("Toxic blowpipe", "bow") == 3  # override wins

    def test_combat_style_fallback(self):
        assert get_weapon_speed("Some custom whip", "whip") == 4
        assert get_weapon_speed("Some halberd", "halberd") == 5
        assert get_weapon_speed("Some 2h sword", "2h sword") == 6

    def test_unknown_returns_none(self):
        assert get_weapon_speed("Unknown weapon", "unknown_style") is None

    def test_known_overrides(self):
        """Verify key weapons have correct speeds."""
        assert get_weapon_speed("Twisted bow", "") == 5
        assert get_weapon_speed("Dragon hunter crossbow", "") == 5
        assert get_weapon_speed("Scythe of vitur", "") == 5
        assert get_weapon_speed("Elder maul", "") == 6
        assert get_weapon_speed("Dragon claws", "") == 4
        assert get_weapon_speed("Osmumten's fang", "") == 5

    def test_case_insensitive(self):
        assert get_weapon_speed("ABYSSAL WHIP", "") == 4
        assert get_weapon_speed("abyssal whip", "") == 4

    def test_weapon_speed_table_consistency(self):
        """All weapon speeds should be positive integers."""
        for name, speed in WEAPON_SPEEDS.items():
            assert isinstance(speed, int) and speed > 0, f"{name}: {speed}"
        for name, speed in WEAPON_SPEED_OVERRIDES.items():
            assert isinstance(speed, int) and speed > 0, f"{name}: {speed}"


# === Data loader tests ===

class TestDataLoaders:
    def test_find_equipment_by_name_from_real_data(self):
        """Test against actual generated data files."""
        from osrs_mcp.util.data import find_equipment_by_name
        whip = find_equipment_by_name("Abyssal whip")
        if whip is not None:  # Only if data files exist
            assert whip["name"] == "Abyssal whip"
            assert "aslash" in whip or "str" in whip
            assert "speed" in whip  # Should be injected

    def test_find_equipment_case_insensitive(self):
        from osrs_mcp.util.data import find_equipment_by_name
        lower = find_equipment_by_name("abyssal whip")
        upper = find_equipment_by_name("Abyssal whip")
        # Both should find the same item (or both None if no data)
        if lower is not None:
            assert lower["name"] == upper["name"]

    def test_find_monster_by_name_from_real_data(self):
        from osrs_mcp.util.data import find_monster_by_name
        vorkath = find_monster_by_name("Vorkath")
        if vorkath is not None:
            assert vorkath["name"] == "Vorkath"
            assert vorkath["hitpoints"] == 750

    def test_find_monster_not_found(self):
        from osrs_mcp.util.data import find_monster_by_name
        assert find_monster_by_name("NonexistentMonster12345") is None

    def test_find_equipment_not_found(self):
        from osrs_mcp.util.data import find_equipment_by_name
        assert find_equipment_by_name("NonexistentItem12345") is None

    def test_load_spells(self):
        from osrs_mcp.util.data import load_spells
        spells = load_spells()
        if spells:  # Only if data files exist
            assert "fire surge" in spells or "Fire Surge" in spells

    def test_find_spell_returns_required_weapons(self):
        from osrs_mcp.util.data import find_spell
        result = find_spell("Iban's Blast")
        assert result is not None
        assert "required_weapons" in result
        assert "iban's staff" in result["required_weapons"]

    def test_find_spell_no_required_weapons_for_standard(self):
        from osrs_mcp.util.data import find_spell
        result = find_spell("Fire Surge")
        assert result is not None
        assert "required_weapons" not in result
