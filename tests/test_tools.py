"""Tests for MCP tool functions."""
import pytest
import httpx
import respx
from unittest.mock import patch, AsyncMock

from osrs_mcp.tools import player, items, monsters, dps, quests, general
from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster
from tests.conftest import (
    MOCK_HISCORES_RESPONSE, MOCK_PRICES_MAPPING, MOCK_PRICES_LATEST,
    MOCK_BUCKET_MONSTER, MOCK_BUCKET_DROPS, MOCK_BUCKET_DROP_SOURCES,
    MOCK_BUCKET_ITEM_JOIN, MOCK_BUCKET_QUEST, MOCK_BUCKET_MONEY_MAKING,
    MOCK_WIKI_SEARCH, MOCK_WOM_GAINS,
)


# === Player tools ===

class TestPlayerStats:
    @respx.mock
    async def test_player_stats_with_username(self):
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=MOCK_HISCORES_RESPONSE)
        )
        result = await player.player_stats(username="TestPlayer")
        assert result["username"] == "TestPlayer"
        assert result["skills"]["Attack"]["level"] == 99

    async def test_player_stats_no_username_no_config(self):
        with patch("osrs_mcp.tools.player.get_config") as mock_cfg:
            mock_cfg.return_value.username = ""
            with pytest.raises(ValueError, match="No username"):
                await player.player_stats(username="")

    @respx.mock
    async def test_player_stats_from_config(self):
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=MOCK_HISCORES_RESPONSE)
        )
        with patch("osrs_mcp.tools.player.get_config") as mock_cfg:
            mock_cfg.return_value.username = "ConfigUser"
            result = await player.player_stats(username="")
            assert result["username"] == "ConfigUser"


class TestPlayerGains:
    @respx.mock
    async def test_player_gains(self):
        respx.get("https://api.wiseoldman.net/v2/players/TestPlayer/gained").mock(
            return_value=httpx.Response(200, json=MOCK_WOM_GAINS)
        )
        result = await player.player_gains(username="TestPlayer", period="week")
        assert result["username"] == "TestPlayer"
        assert "skills" in result
        assert "bosses" in result


# === Item tools ===

class TestItemInfo:
    @respx.mock
    async def test_item_info_found(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_ITEM_JOIN)
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_LATEST)
        )
        result = await items.item_info("Abyssal whip")
        assert "page_name_sub" in result or "error" not in result

    @respx.mock
    async def test_item_info_not_found(self):
        # Both join and fallback return empty
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            side_effect=[
                httpx.Response(200, json={"bucket": []}),
                httpx.Response(200, json={"bucket": []}),
            ]
        )
        result = await items.item_info("NonexistentItem12345")
        assert "error" in result


class TestSearchItems:
    @respx.mock
    async def test_search_items(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        results = await items.search_items("scimitar")
        assert len(results) == 1
        assert results[0]["name"] == "Rune scimitar"


class TestItemPrice:
    @respx.mock
    async def test_item_price_found(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_LATEST)
        )
        result = await items.item_price("Abyssal whip")
        assert result["high"] == 1350000

    @respx.mock
    async def test_item_price_not_found(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        result = await items.item_price("FakeItem")
        assert "error" in result


# === Monster tools ===

class TestMonsterInfo:
    @respx.mock
    async def test_monster_info_found(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_MONSTER)
        )
        result = await monsters.monster_info("Vorkath")
        assert result["combat_level"] == 732

    @respx.mock
    async def test_monster_info_not_found(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": []})
        )
        result = await monsters.monster_info("FakeMonster")
        assert "error" in result


class TestMonsterDrops:
    @respx.mock
    async def test_monster_drops(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_DROPS)
        )
        result = await monsters.monster_drops("Vorkath")
        assert len(result) == 3
        assert result[0]["item_name"] == "Superior dragon bones"

    @respx.mock
    async def test_monster_drops_empty(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": []})
        )
        result = await monsters.monster_drops("FakeMonster")
        assert result[0].get("error")


class TestDropSources:
    @respx.mock
    async def test_drop_sources(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_DROP_SOURCES)
        )
        result = await monsters.drop_sources("Abyssal whip")
        assert len(result) == 2
        assert result[0]["page_name"] == "Abyssal demon"

    @respx.mock
    async def test_drop_sources_empty(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": []})
        )
        result = await monsters.drop_sources("FakeItem")
        assert result[0].get("error")


class TestSearchMonsters:
    @respx.mock
    async def test_search_monsters(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [
                    {"name": "Blue dragon", "combat_level": 111},
                    {"name": "Red dragon", "combat_level": 152},
                    {"name": "Green dragon", "combat_level": 79},
                    {"name": "Blue dragon", "combat_level": 111},  # duplicate
                    {"name": "Goblin", "combat_level": 2},
                ]
            })
        )
        results = await monsters.search_monsters("dragon")
        assert len(results) == 3  # Deduplicated
        names = [r["name"] for r in results]
        assert "Goblin" not in names
        assert "Blue dragon" in names

    @respx.mock
    async def test_search_monsters_no_match(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [{"name": "Goblin", "combat_level": 2}]
            })
        )
        results = await monsters.search_monsters("zzzznothing")
        assert results == []


# === DPS tools ===

class TestCalcDps:
    async def test_calc_dps_with_local_data(self):
        """Test DPS calculation using local data files."""
        from osrs_mcp.util.data import find_equipment_by_name, find_monster_by_name
        whip = find_equipment_by_name("Abyssal whip")
        vorkath = find_monster_by_name("Vorkath")
        if whip is None or vorkath is None:
            pytest.skip("Data files not available")

        result = await dps.calc_dps(
            monster="Vorkath", weapon="Abyssal whip",
            style="melee", attack_type="slash",
            prayer="piety", potion="super_combat",
        )
        assert result["dps"] > 0
        assert result["max_hit"] > 0
        assert result["weapon"] == "Abyssal whip"

    async def test_calc_dps_unknown_monster(self):
        with patch("osrs_mcp.tools.dps.find_monster_by_name", return_value=None), \
             patch("osrs_mcp.tools.dps.get_monster_info", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await dps.calc_dps(monster="FakeMonster", weapon="Abyssal whip")


class TestCompareWeapons:
    async def test_compare_weapons(self):
        from osrs_mcp.util.data import find_equipment_by_name, find_monster_by_name
        whip = find_equipment_by_name("Abyssal whip")
        rapier = find_equipment_by_name("Ghrazi rapier")
        vorkath = find_monster_by_name("Vorkath")
        if not all([whip, rapier, vorkath]):
            pytest.skip("Data files not available")

        results = await dps.compare_weapons(
            monster="Vorkath",
            weapons="Abyssal whip,Ghrazi rapier",
            style="melee", attack_type="slash",
            prayer="piety", potion="super_combat",
        )
        assert len(results) == 2
        # Results sorted by DPS descending
        assert results[0]["dps"] >= results[1]["dps"]

    async def test_compare_weapons_with_error(self):
        """Unknown weapon should return error in result, not crash."""
        with patch("osrs_mcp.tools.dps.find_monster_by_name") as mock_monster:
            mock_monster.return_value = {
                "name": "Test", "combat_level": 100, "hitpoints": 100,
                "defence_level": 50, "magic_level": 1,
                "dstab": 0, "dslash": 0, "dcrush": 0,
                "drange": 0, "dmagic": 0, "size": 1, "attribute": "",
            }
            with patch("osrs_mcp.tools.dps._resolve_gear", return_value=[]):
                results = await dps.compare_weapons(
                    monster="Test", weapons="FakeWeapon1,FakeWeapon2",
                )
                assert len(results) == 2
                # With empty gear, DPS should still compute (just low)
                for r in results:
                    assert "dps" in r or "error" in r


# === Quest tools ===

class TestQuestInfo:
    @respx.mock
    async def test_quest_info_found(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_QUEST)
        )
        result = await quests.quest_info("Dragon Slayer I")
        assert "wiki_url" in result
        assert result["official_difficulty"] == "Experienced"

    @respx.mock
    async def test_quest_info_not_found_fallback(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            side_effect=[
                httpx.Response(200, json={"bucket": []}),  # bucket query
                httpx.Response(200, json=MOCK_WIKI_SEARCH),  # wiki search fallback
            ]
        )
        result = await quests.quest_info("Unknown Quest")
        assert "note" in result
        assert "wiki_url" in result
        assert "search_results" in result


# === General tools ===

class TestSearchWiki:
    @respx.mock
    async def test_search_wiki(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_WIKI_SEARCH)
        )
        results = await general.search_wiki("fire cape")
        assert len(results) == 2
        assert results[0]["title"] == "Fire cape"


class TestMoneyMakingMethods:
    @respx.mock
    async def test_money_making_methods(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_MONEY_MAKING)
        )
        results = await general.money_making_methods()
        assert len(results) == 2
        assert "wiki_url" in results[0]
        # Should strip "Money making guide/" prefix
        assert not results[0]["method"].startswith("Money making guide/")

    @respx.mock
    async def test_money_making_methods_skill_filter(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_MONEY_MAKING)
        )
        results = await general.money_making_methods(skill="Vorkath")
        # Should filter to only methods matching skill
        for r in results:
            assert "vorkath" in r["method"].lower()


class TestBossRequirements:
    @respx.mock
    async def test_boss_requirements(self):
        route = respx.get("https://oldschool.runescape.wiki/api.php")
        route.side_effect = [
            httpx.Response(200, json=MOCK_BUCKET_MONSTER),
            httpx.Response(200, json=MOCK_BUCKET_DROPS),
        ]
        result = await general.boss_requirements("Vorkath")
        assert "monster" in result
        assert "drops" in result
        assert "wiki_url" in result
        assert "Vorkath" in result["wiki_url"]
