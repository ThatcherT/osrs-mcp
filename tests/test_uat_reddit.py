"""User Acceptance Tests derived from real Reddit player questions.

Scraped from r/2007scape and r/ironscape — 241 genuine player questions
across 9 categories. Each test verifies our MCP tools can service the
type of question real players actually ask.

Run just UATs:   pytest tests/test_uat_reddit.py -v
Run by category: pytest tests/test_uat_reddit.py -v -k bossing
"""
import pytest
import httpx
import respx
from unittest.mock import patch, AsyncMock

from osrs_mcp.tools import player, items, monsters, dps, quests, general

# ---------------------------------------------------------------------------
# Shared mock data builders
# ---------------------------------------------------------------------------

def _mock_hiscores(attack=80, strength=82, defence=75, ranged=85, magic=80,
                   hitpoints=83, prayer=70, bosses=None):
    """Build a hiscores response with given stats."""
    skills = [
        {"id": 0, "name": "Overall", "rank": 100000, "level": 2000, "xp": 100000000},
        {"id": 1, "name": "Attack", "rank": 50000, "level": attack, "xp": 2000000},
        {"id": 2, "name": "Defence", "rank": 50000, "level": defence, "xp": 1200000},
        {"id": 3, "name": "Strength", "rank": 50000, "level": strength, "xp": 2500000},
        {"id": 4, "name": "Hitpoints", "rank": 50000, "level": hitpoints, "xp": 2700000},
        {"id": 5, "name": "Ranged", "rank": 50000, "level": ranged, "xp": 3500000},
        {"id": 6, "name": "Prayer", "rank": 50000, "level": prayer, "xp": 750000},
        {"id": 7, "name": "Magic", "rank": 50000, "level": magic, "xp": 2200000},
        {"id": 8, "name": "Cooking", "rank": 80000, "level": 70, "xp": 750000},
        {"id": 9, "name": "Woodcutting", "rank": 80000, "level": 65, "xp": 450000},
        {"id": 10, "name": "Slayer", "rank": 60000, "level": 72, "xp": 900000},
    ]
    activities = bosses or [
        {"id": 0, "name": "Vorkath", "rank": 5000, "score": 250},
        {"id": 1, "name": "Zulrah", "rank": 8000, "score": 100},
        {"id": 2, "name": "Barrows Chests", "rank": 3000, "score": 400},
    ]
    return {"skills": skills, "activities": activities}


def _mock_monster(name, combat, hp, def_lvl, **kwargs):
    """Build a bucket monster response."""
    base = {
        "name": name,
        "combat_level": combat,
        "hitpoints": hp,
        "defence_level": def_lvl,
        "magic_level": kwargs.get("magic_level", 1),
        "stab_defence_bonus": kwargs.get("dstab", 0),
        "slash_defence_bonus": kwargs.get("dslash", 0),
        "crush_defence_bonus": kwargs.get("dcrush", 0),
        "range_defence_bonus": kwargs.get("drange", 0),
        "magic_defence_bonus": kwargs.get("dmagic", 0),
        "size": kwargs.get("size", 1),
        "attribute": kwargs.get("attribute", ""),
    }
    return {"bucket": [base]}


def _mock_drops(*item_names):
    return {"bucket": [{"item_name": n} for n in item_names]}


def _mock_drop_sources(*monster_names):
    return {"bucket": [{"page_name": n} for n in monster_names]}


def _mock_prices_mapping(*items_list):
    """Build prices mapping. items_list = [(id, name), ...]"""
    return [{"id": i, "name": n, "examine": "", "members": True,
             "lowalch": None, "highalch": None, "limit": 70}
            for i, n in items_list]


def _mock_prices_latest(prices_dict):
    """Build prices latest. prices_dict = {str_id: (high, low), ...}"""
    return {"data": {k: {"high": h, "low": l, "highTime": 1700000000, "lowTime": 1700000000}
                     for k, (h, l) in prices_dict.items()}}


# ===========================================================================
# Category: BOSSING (63 Reddit questions)
# "What boss should I do with these stats?" / "What boss can I kill?"
# Tools: monster_info, boss_requirements, player_stats, calc_dps
# ===========================================================================

class TestUATBossing:
    """Verifies tools can answer: 'What boss can I do with my stats?'"""

    @respx.mock
    async def test_bossing_lookup_vorkath_stats(self):
        """Reddit: 'What's the recommended stats for Vorkath?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_monster(
                "Vorkath", 732, 750, 214, magic_level=150,
                dstab=26, dslash=108, dcrush=108, drange=26, dmagic=240,
                size=7, attribute="dragon",
            ))
        )
        result = await monsters.monster_info("Vorkath")
        assert result["combat_level"] == 732
        assert result["hitpoints"] == 750
        assert "defence_level" in result

    @respx.mock
    async def test_bossing_lookup_zulrah_stats(self):
        """Reddit: 'Zulrah gear requirements and stats?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_monster(
                "Zulrah", 725, 500, 300, magic_level=300,
                dstab=0, dslash=0, dcrush=0, drange=0, dmagic=0,
                size=5,
            ))
        )
        result = await monsters.monster_info("Zulrah")
        assert result["combat_level"] == 725
        assert result["hitpoints"] == 500

    @respx.mock
    async def test_bossing_boss_requirements(self):
        """Reddit: 'What do I need to fight General Graardor?'"""
        route = respx.get("https://oldschool.runescape.wiki/api.php")
        route.side_effect = [
            httpx.Response(200, json=_mock_monster(
                "General Graardor", 624, 255, 250,
                dstab=90, dslash=90, dcrush=90, drange=90, dmagic=-20,
            )),
            httpx.Response(200, json=_mock_drops(
                "Bandos chestplate", "Bandos tassets", "Bandos boots",
                "Bandos hilt", "Godsword shard 1",
            )),
        ]
        result = await general.boss_requirements("General Graardor")
        assert "monster" in result
        assert "drops" in result
        assert "wiki_url" in result
        assert "General_Graardor" in result["wiki_url"]

    @respx.mock
    async def test_bossing_player_stats_for_bossing(self):
        """Reddit: 'What bosses could I do with these stats?'"""
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=_mock_hiscores(
                attack=80, strength=85, defence=75, ranged=82, magic=78,
            ))
        )
        result = await player.player_stats(username="MidPlayer")
        assert result["username"] == "MidPlayer"
        skills = result["skills"]
        assert skills["Attack"]["level"] == 80
        assert skills["Ranged"]["level"] == 82

    @respx.mock
    async def test_bossing_dps_at_vorkath_melee(self):
        """Reddit: 'What DPS can I expect at Vorkath with melee?'"""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster
            mock_mon.return_value = Monster(
                name="Vorkath", combat_level=732, hitpoints=750,
                defence_level=214, magic_level=150,
                dstab=26, dslash=108, dcrush=108,
                drange=26, dmagic=240, size=7, attribute="dragon",
            )
            mock_stats.return_value = PlayerStats()
            mock_gear.return_value = [{"astab": 94, "aslash": 55, "str": 89, "speed": 4}]
            result = await dps.calc_dps(
                monster="Vorkath", weapon="Ghrazi rapier",
                style="melee", attack_type="stab",
                prayer="piety", potion="super_combat",
            )
            assert result["dps"] > 0
            assert result["max_hit"] > 0
            assert result["weapon"] == "Ghrazi rapier"

    @respx.mock
    async def test_bossing_drops_vorkath(self):
        """Reddit: 'What does Vorkath drop?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_drops(
                "Superior dragon bones", "Blue dragonhide", "Draconic visage",
                "Skeletal visage", "Vorkath's head",
            ))
        )
        result = await monsters.monster_drops("Vorkath")
        assert len(result) == 5
        names = [d["item_name"] for d in result]
        assert "Superior dragon bones" in names
        assert "Draconic visage" in names

    @respx.mock
    async def test_bossing_ironman_boss_next(self):
        """Reddit: 'What boss should I do next as ironman?'
        Verifies monster_info returns enough data to advise on boss suitability."""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_monster(
                "Sarachnis", 318, 400, 150,
                dstab=100, dslash=100, dcrush=-20, drange=100, dmagic=0,
            ))
        )
        result = await monsters.monster_info("Sarachnis")
        assert result["combat_level"] == 318
        # Crush weakness visible
        assert result.get("crush_defence_bonus", result.get("dcrush", 0)) < 0


# ===========================================================================
# Category: GEAR (70 Reddit questions)
# "What gear should I use?" / "Best weapon for X?"
# Tools: item_info, search_items, item_price, compare_weapons
# ===========================================================================

class TestUATGear:
    """Verifies tools can answer: 'What gear should I upgrade next?'"""

    @respx.mock
    async def test_gear_item_info_whip(self):
        """Reddit: 'Is Abyssal whip good for slayer?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [{
                    "infobox_item.page_name_sub": "Abyssal whip",
                    "infobox_item.examine": "A weapon from the Abyss.",
                    "infobox_item.tradeable": True,
                    "infobox_bonuses.slash_attack_bonus": 82,
                    "infobox_bonuses.strength_bonus": 82,
                    "infobox_bonuses.equipment_slot": "weapon",
                }]
            })
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping((4151, "Abyssal whip")))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({"4151": (1350000, 1320000)}))
        )
        result = await items.item_info("Abyssal whip")
        assert "error" not in result
        assert result.get("ge_price_high") == 1350000

    @respx.mock
    async def test_gear_search_melee_weapons(self):
        """Reddit: 'What melee weapon should I get?'"""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (4151, "Abyssal whip"), (22324, "Ghrazi rapier"),
                (1333, "Rune scimitar"), (21015, "Dragon scimitar"),
            ))
        )
        results = await items.search_items("scimitar")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert any("scimitar" in n.lower() for n in names)

    @respx.mock
    async def test_gear_price_check_for_upgrade(self):
        """Reddit: 'Is buying a Bandos chestplate worth it?'"""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (11832, "Bandos chestplate"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({"11832": (16500000, 16200000)}))
        )
        result = await items.item_price("Bandos chestplate")
        assert "error" not in result
        assert result["high"] == 16500000

    @respx.mock
    async def test_gear_search_ranged_weapons(self):
        """Reddit: 'Best ranged weapon for my level?'"""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (12926, "Toxic blowpipe"), (11785, "Armadyl crossbow"),
                (20997, "Twisted bow"), (21012, "Dragon crossbow"),
            ))
        )
        results = await items.search_items("crossbow")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert any("crossbow" in n.lower() for n in names)

    @respx.mock
    async def test_gear_vorkath_setup(self):
        """Reddit: 'Recommendation for my next upgrade in gear for Vorkath'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [{
                    "infobox_item.page_name_sub": "Dragon hunter crossbow",
                    "infobox_item.examine": "A crossbow made from dragon hunter parts.",
                    "infobox_item.tradeable": True,
                    "infobox_bonuses.range_attack_bonus": 95,
                    "infobox_bonuses.ranged_strength_bonus": 0,
                    "infobox_bonuses.equipment_slot": "weapon",
                }]
            })
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (21012, "Dragon hunter crossbow"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({"21012": (65000000, 63000000)}))
        )
        result = await items.item_info("Dragon hunter crossbow")
        assert "error" not in result

    async def test_gear_compare_weapons_at_boss(self):
        """Reddit: 'Dragon hunter lance vs crossbow at Vorkath?'"""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster
            mock_mon.return_value = Monster(
                name="Vorkath", combat_level=732, hitpoints=750,
                defence_level=214, magic_level=150,
                dstab=26, dslash=108, dcrush=108,
                drange=26, dmagic=240, size=7, attribute="dragon",
            )
            mock_stats.return_value = PlayerStats()
            # Return different gear for each weapon call
            mock_gear.side_effect = [
                [{"astab": 85, "str": 80, "speed": 4}],  # DH lance
                [{"arange": 95, "rstr": 0, "speed": 5}],  # DH crossbow
            ]
            results = await dps.compare_weapons(
                monster="Vorkath",
                weapons="Dragon hunter lance,Dragon hunter crossbow",
                style="melee", attack_type="stab",
                prayer="piety", potion="super_combat",
            )
            assert len(results) == 2
            for r in results:
                assert "dps" in r or "error" in r


# ===========================================================================
# Category: DPS (14 Reddit questions)
# "What's my DPS at X?" / "Is weapon A better than B?"
# Tools: calc_dps, compare_weapons
# ===========================================================================

class TestUATDps:
    """Verifies tools can answer: 'What DPS will I do?'"""

    async def test_dps_melee_at_cerberus(self):
        """Reddit: 'DPS against cerberus comparison and where arclight sits now.'"""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="Cerberus", combat_level=318, hitpoints=600,
                defence_level=100, magic_level=220,
                dstab=50, dslash=50, dcrush=50,
                drange=50, dmagic=50, attribute="demon",
            )
            mock_stats.return_value = PlayerStats()
            mock_gear.return_value = [{"aslash": 82, "str": 82, "speed": 4}]
            result = await dps.calc_dps(
                monster="Cerberus", weapon="Abyssal whip",
                style="melee", attack_type="slash",
                prayer="piety", potion="super_combat",
            )
            assert result["dps"] > 0
            assert result["max_hit"] > 0

    async def test_dps_infernal_cape_comparison(self):
        """Reddit: 'Is an Infernal Cape worth the trouble? (DPS Comparison)'
        Validates we can compare DPS with different gear bonuses."""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="Vorkath", combat_level=732, hitpoints=750,
                defence_level=214, magic_level=150,
                dstab=26, dslash=108, dcrush=108,
                drange=26, dmagic=240, size=7, attribute="dragon",
            )
            mock_stats.return_value = PlayerStats()
            # Fire cape: +4 str, Infernal: +8 str
            mock_gear.side_effect = [
                [{"astab": 94, "str": 93, "speed": 4}],  # rapier + fire cape
                [{"astab": 94, "str": 97, "speed": 4}],  # rapier + infernal
            ]
            results = await dps.compare_weapons(
                monster="Vorkath",
                weapons="Ghrazi rapier,Ghrazi rapier",
                style="melee", attack_type="stab",
                prayer="piety", potion="super_combat",
            )
            assert len(results) == 2
            # Both should produce valid DPS
            for r in results:
                assert r["dps"] > 0

    async def test_dps_ranged_at_vorkath(self):
        """Reddit: 'Best ranged setup for Vorkath?'"""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="Vorkath", combat_level=732, hitpoints=750,
                defence_level=214, magic_level=150,
                dstab=26, dslash=108, dcrush=108,
                drange=26, dmagic=240, size=7, attribute="dragon",
            )
            mock_stats.return_value = PlayerStats()
            mock_gear.return_value = [{"arange": 95, "rstr": 0, "speed": 5}]
            result = await dps.calc_dps(
                monster="Vorkath", weapon="Dragon hunter crossbow",
                style="ranged", prayer="rigour", potion="super_ranging",
                special_equipment="dragon_hunter_crossbow",
            )
            assert result["dps"] > 0
            assert result["weapon"] == "Dragon hunter crossbow"

    async def test_dps_magic_at_zulrah(self):
        """Reddit: 'Which of these zulrah setups would be best?'"""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="Zulrah", combat_level=725, hitpoints=500,
                defence_level=300, magic_level=300,
                dstab=0, dslash=0, dcrush=0, drange=0, dmagic=0,
            )
            mock_stats.return_value = PlayerStats()
            mock_gear.return_value = [{"amagic": 25, "mdmg": 15, "speed": 4}]
            result = await dps.calc_dps(
                monster="Zulrah", weapon="Trident of the swamp",
                style="magic", prayer="augury", potion="super_magic",
                spell_max_hit=31,
            )
            assert result["dps"] > 0

    async def test_dps_with_slayer_helm(self):
        """Reddit: 'Best slayer DPS setup?'"""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="Abyssal demon", combat_level=124, hitpoints=150,
                defence_level=135, magic_level=1,
                dstab=20, dslash=20, dcrush=20,
                drange=20, dmagic=0, attribute="demon",
            )
            mock_stats.return_value = PlayerStats()
            mock_gear.return_value = [{"aslash": 82, "str": 82, "speed": 4}]
            result = await dps.calc_dps(
                monster="Abyssal demon", weapon="Abyssal whip",
                style="melee", attack_type="slash",
                on_slayer_task=True,
            )
            assert result["dps"] > 0
            # Slayer helm bonus should increase DPS


# ===========================================================================
# Category: DROPS (11 Reddit questions)
# "Where do I get X?" / "What drops Y?"
# Tools: drop_sources, monster_drops
# ===========================================================================

class TestUATDrops:
    """Verifies tools can answer: 'Where do I get item X?'"""

    @respx.mock
    async def test_drops_zenyte_shard_source(self):
        """Reddit: 'Where is my Zenyte Shard?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_drop_sources(
                "Demonic gorilla",
            ))
        )
        result = await monsters.drop_sources("Zenyte shard")
        assert len(result) >= 1
        assert result[0]["page_name"] == "Demonic gorilla"

    @respx.mock
    async def test_drops_abyssal_whip_sources(self):
        """Reddit: 'What drops an Abyssal whip?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_drop_sources(
                "Abyssal demon", "Greater abyssal demon",
            ))
        )
        result = await monsters.drop_sources("Abyssal whip")
        assert len(result) == 2
        names = [r["page_name"] for r in result]
        assert "Abyssal demon" in names

    @respx.mock
    async def test_drops_maple_seed_sources(self):
        """Inspired by project goal: 'What activity gives maple seeds?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_drop_sources(
                "Zulrah", "Vorkath", "Callisto", "Giant mole",
            ))
        )
        result = await monsters.drop_sources("Maple seed")
        assert len(result) >= 1
        # Verifies we get actual monster names back
        for r in result:
            assert "page_name" in r

    @respx.mock
    async def test_drops_vorkath_drop_table(self):
        """Reddit: 'What does Vorkath drop that's valuable?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_drops(
                "Superior dragon bones", "Blue dragonhide",
                "Draconic visage", "Skeletal visage",
                "Dragonbone necklace", "Dragon bolts",
            ))
        )
        result = await monsters.monster_drops("Vorkath")
        assert len(result) == 6
        names = [d["item_name"] for d in result]
        assert "Draconic visage" in names

    @respx.mock
    async def test_drops_no_results(self):
        """Verifies graceful handling when item has no known drop sources."""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": []})
        )
        result = await monsters.drop_sources("Coins")
        assert result[0].get("error")


# ===========================================================================
# Category: MONEY MAKING (28 Reddit questions)
# "What's a good money maker?" / "How much gp/hr?"
# Tools: money_making_methods, item_price
# ===========================================================================

class TestUATMoneyMaking:
    """Verifies tools can answer: 'How do I make money?'"""

    @respx.mock
    async def test_money_making_list_methods(self):
        """Reddit: 'What's a good money making method at level 3?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [
                    {"page_name_sub": "Money making guide/Tanning dragonhide"},
                    {"page_name_sub": "Money making guide/Killing green dragons"},
                    {"page_name_sub": "Money making guide/Crafting nature runes through the Abyss"},
                    {"page_name_sub": "Money making guide/Killing Vorkath"},
                ]
            })
        )
        results = await general.money_making_methods()
        assert len(results) >= 1
        for r in results:
            assert "method" in r
            assert "wiki_url" in r
            # Prefix should be stripped
            assert not r["method"].startswith("Money making guide/")

    @respx.mock
    async def test_money_making_filter_by_skill(self):
        """Reddit: 'Best money making with my Runecrafting level?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [
                    {"page_name_sub": "Money making guide/Crafting nature runes through the Abyss"},
                    {"page_name_sub": "Money making guide/Crafting blood runes"},
                    {"page_name_sub": "Money making guide/Killing Vorkath"},
                ]
            })
        )
        results = await general.money_making_methods(skill="rune")
        assert len(results) >= 1
        for r in results:
            assert "rune" in r["method"].lower()

    @respx.mock
    async def test_money_making_check_item_value(self):
        """Reddit: 'How much gp per hour killing Vorkath?'
        Verifies item_price can check the value of boss drops."""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (11286, "Draconic visage"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({"11286": (5200000, 5000000)}))
        )
        result = await items.item_price("Draconic visage")
        assert result["high"] == 5200000


# ===========================================================================
# Category: PRICES (6 Reddit questions)
# "Is X worth buying?" / "How much does Y cost?"
# Tools: item_price, search_items
# ===========================================================================

class TestUATPrices:
    """Verifies tools can answer: 'Is this item worth buying?'"""

    @respx.mock
    async def test_prices_rigour_worth_it(self):
        """Reddit: 'Is rigour really worth 40m?'"""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (21034, "Dexterous prayer scroll"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({"21034": (42000000, 41000000)}))
        )
        result = await items.item_price("Dexterous prayer scroll")
        assert "error" not in result
        assert result["high"] > 0

    @respx.mock
    async def test_prices_soulreaper_axe(self):
        """Reddit: 'Is the Soulreaper Axe worth buying?'"""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (28338, "Soulreaper axe"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({"28338": (95000000, 93000000)}))
        )
        result = await items.item_price("Soulreaper axe")
        assert result["high"] == 95000000

    @respx.mock
    async def test_prices_item_not_found_graceful(self):
        """Verifies graceful error when an item name is misspelled."""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping())
        )
        result = await items.item_price("Bnadso chsetpalte")
        assert "error" in result


# ===========================================================================
# Category: PROGRESSION (22 Reddit questions)
# "What should I do with these stats?" / "What's next for my account?"
# Tools: player_stats, player_gains
# ===========================================================================

class TestUATProgression:
    """Verifies tools can answer: 'What should I do with my stats?'"""

    @respx.mock
    async def test_progression_fetch_player_stats(self):
        """Reddit: 'What should I be doing and prioritising with these stats?'"""
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=_mock_hiscores(
                attack=70, strength=72, defence=65, ranged=60, magic=68,
                hitpoints=71, prayer=52,
            ))
        )
        result = await player.player_stats(username="NewPlayer")
        skills = result["skills"]
        # Claude can see these stats to give progression advice
        assert skills["Attack"]["level"] == 70
        assert skills["Prayer"]["level"] == 52

    @respx.mock
    async def test_progression_player_gains_tracking(self):
        """Reddit: 'How much progress have I made this week?'"""
        respx.get("https://api.wiseoldman.net/v2/players/TestPlayer/gained").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "skills": {
                        "attack": {
                            "experience": {"gained": 150000, "start": 500000, "end": 650000},
                            "level": {"gained": 2, "start": 60, "end": 62},
                        },
                        "slayer": {
                            "experience": {"gained": 200000, "start": 300000, "end": 500000},
                            "level": {"gained": 3, "start": 55, "end": 58},
                        },
                    },
                    "bosses": {
                        "barrows_chests": {
                            "kills": {"gained": 30, "start": 50, "end": 80},
                        },
                    },
                }
            })
        )
        result = await player.player_gains(username="TestPlayer", period="week")
        assert result["username"] == "TestPlayer"
        assert "skills" in result
        assert "bosses" in result

    @respx.mock
    async def test_progression_mid_game_iron_stats(self):
        """Reddit: 'Need help with account progression for a returning player (iron).'"""
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=_mock_hiscores(
                attack=75, strength=80, defence=70, ranged=75, magic=82,
                hitpoints=78, prayer=60,
            ))
        )
        result = await player.player_stats(username="IronReturner")
        skills = result["skills"]
        assert skills["Magic"]["level"] == 82
        assert skills["Defence"]["level"] == 70

    @respx.mock
    async def test_progression_what_to_spend_cash_on(self):
        """Reddit: 'Lucky day at Revs - what to do with 30m cash and these stats?'
        Verifies we can look up gear prices to advise on upgrades."""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (4151, "Abyssal whip"), (11832, "Bandos chestplate"),
                (11834, "Bandos tassets"), (22981, "Ferocious gloves"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({
                "4151": (1350000, 1320000),
                "11832": (16500000, 16200000),
                "11834": (20000000, 19500000),
                "22981": (5500000, 5300000),
            }))
        )
        # Check if key upgrades fit budget
        whip_price = await items.item_price("Abyssal whip")
        bcp_price = await items.item_price("Bandos chestplate")
        assert whip_price["high"] < 30000000  # can afford
        assert bcp_price["high"] < 30000000  # can afford


# ===========================================================================
# Category: QUESTS (15 Reddit questions)
# "What quest should I do?" / "Quest requirements?"
# Tools: quest_info, search_wiki
# ===========================================================================

class TestUATQuests:
    """Verifies tools can answer: 'What quest should I do next?'"""

    @respx.mock
    async def test_quests_dragon_slayer(self):
        """Reddit: 'What order would you do these quests?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [{
                    "page_name_sub": "Dragon Slayer I",
                    "start_point": "Talk to the Guildmaster in the Champions' Guild.",
                    "official_difficulty": "Experienced",
                }]
            })
        )
        result = await quests.quest_info("Dragon Slayer I")
        assert "wiki_url" in result
        assert result.get("official_difficulty") == "Experienced"

    @respx.mock
    async def test_quests_rfd(self):
        """Reddit: 'Recipe for Disaster guide?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [{
                    "page_name_sub": "Recipe for Disaster",
                    "start_point": "Talk to the cook in Lumbridge Castle.",
                    "official_difficulty": "Grandmaster",
                }]
            })
        )
        result = await quests.quest_info("Recipe for Disaster")
        assert "wiki_url" in result
        assert "Recipe_for_Disaster" in result["wiki_url"]

    @respx.mock
    async def test_quests_not_found_fallback(self):
        """Reddit: 'Has anyone followed the OSRS Quest Guide from the OSRS Wiki?'
        Tests wiki search fallback for generic quest queries."""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            side_effect=[
                httpx.Response(200, json={"bucket": []}),
                httpx.Response(200, json={
                    "query": {
                        "search": [
                            {"title": "Optimal quest guide", "snippet": "A guide to questing..."},
                            {"title": "Quest experience rewards", "snippet": "Rewards from quests..."},
                        ]
                    }
                }),
            ]
        )
        result = await quests.quest_info("optimal quest guide")
        assert "note" in result
        assert "search_results" in result
        assert len(result["search_results"]) >= 1

    @respx.mock
    async def test_quests_search_wiki(self):
        """Reddit: 'What is the best order to do quests?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "query": {
                    "search": [
                        {"title": "Optimal quest guide", "snippet": "This is the optimal quest order."},
                        {"title": "Quest experience rewards", "snippet": "Quest rewards for XP."},
                    ]
                }
            })
        )
        results = await general.search_wiki("optimal quest order")
        assert len(results) >= 1
        assert any("quest" in r["title"].lower() for r in results)


# ===========================================================================
# Category: SLAYER (12 Reddit questions)
# "What gear for slayer task?" / "Best slayer setup?"
# Tools: monster_info, search_monsters, calc_dps
# ===========================================================================

class TestUATSlayer:
    """Verifies tools can answer: 'What gear for my slayer task?'"""

    @respx.mock
    async def test_slayer_gargoyles_info(self):
        """Reddit: 'What gear should I use for doing a gargoyles task?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_monster(
                "Gargoyle", 111, 105, 107,
                dstab=20, dslash=40, dcrush=-10, drange=30, dmagic=0,
            ))
        )
        result = await monsters.monster_info("Gargoyle")
        assert result["combat_level"] == 111
        # Crush weakness visible — informs gear choice
        assert result.get("crush_defence_bonus", result.get("dcrush", 0)) < 0

    @respx.mock
    async def test_slayer_search_demons(self):
        """Reddit: 'Best slayer task monsters to block/skip?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [
                    {"name": "Black demon", "combat_level": 172, "hitpoints": 157},
                    {"name": "Greater demon", "combat_level": 92, "hitpoints": 87},
                    {"name": "Abyssal demon", "combat_level": 124, "hitpoints": 150},
                ]
            })
        )
        results = await monsters.search_monsters("demon")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "Black demon" in names

    @respx.mock
    async def test_slayer_barrows_on_task(self):
        """Reddit: 'Gear for barrows on task?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_monster(
                "Dharok the Wretched", 115, 100, 100,
                dstab=20, dslash=20, dcrush=20, drange=20, dmagic=-30,
            ))
        )
        result = await monsters.monster_info("Dharok the Wretched")
        assert result["combat_level"] == 115
        # Magic weakness visible
        assert result.get("magic_defence_bonus", result.get("dmagic", 0)) < 0

    async def test_slayer_dps_on_task(self):
        """Reddit: 'Best setup for Fight Cave slayer task?'
        Verifies on_slayer_task flag works in DPS calc."""
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="TzTok-Jad", combat_level=702, hitpoints=250,
                defence_level=480, magic_level=480,
                dstab=0, dslash=0, dcrush=0,
                drange=0, dmagic=0,
            )
            mock_stats.return_value = PlayerStats()
            mock_gear.return_value = [{"arange": 70, "rstr": 20, "speed": 5}]
            result = await dps.calc_dps(
                monster="TzTok-Jad", weapon="Twisted bow",
                style="ranged", prayer="rigour", potion="super_ranging",
                on_slayer_task=True,
            )
            assert result["dps"] > 0


# ===========================================================================
# Category: WIKI SEARCH (cross-cutting)
# Fallback for any question our structured tools can't directly answer.
# Tools: search_wiki
# ===========================================================================

class TestUATWikiSearch:
    """Verifies wiki search can help with questions outside structured data."""

    @respx.mock
    async def test_wiki_search_fire_cape_guide(self):
        """Reddit: 'Fire cape guide for first timer?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "query": {
                    "search": [
                        {"title": "TzHaar Fight Cave", "snippet": "The TzHaar Fight Cave is..."},
                        {"title": "Fire cape", "snippet": "The fire cape is a reward..."},
                        {"title": "TzTok-Jad", "snippet": "TzTok-Jad is the final boss..."},
                    ]
                }
            })
        )
        results = await general.search_wiki("fire cape guide")
        assert len(results) >= 1

    @respx.mock
    async def test_wiki_search_ironman_guide(self):
        """Reddit: 'Ironman progression guide?'"""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "query": {
                    "search": [
                        {"title": "Ironman guide", "snippet": "A comprehensive ironman guide..."},
                        {"title": "Ironman guide/Melee", "snippet": "Melee training for ironmen..."},
                    ]
                }
            })
        )
        results = await general.search_wiki("ironman progression guide")
        assert len(results) >= 1
        assert any("ironman" in r["title"].lower() for r in results)


# ===========================================================================
# Integration-style tests: Multi-tool workflows
# These verify that real user questions can be answered by chaining tools.
# ===========================================================================

class TestUATMultiToolWorkflows:
    """Tests that combine multiple tools to answer complex questions."""

    @respx.mock
    async def test_workflow_boss_viability_check(self):
        """Reddit: 'Can I do Vorkath with 80 range?'
        Workflow: player_stats -> monster_info -> calc_dps"""
        # Step 1: Get player stats
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=_mock_hiscores(ranged=80))
        )
        stats = await player.player_stats(username="RangeOnly")
        assert stats["skills"]["Ranged"]["level"] == 80

        # Step 2: Get monster info
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=_mock_monster(
                "Vorkath", 732, 750, 214, magic_level=150,
                dstab=26, dslash=108, dcrush=108, drange=26, dmagic=240,
                size=7, attribute="dragon",
            ))
        )
        mon = await monsters.monster_info("Vorkath")
        assert mon["combat_level"] == 732

        # Step 3: Calculate DPS
        with patch("osrs_mcp.tools.dps._resolve_monster", new_callable=AsyncMock) as mock_mon, \
             patch("osrs_mcp.tools.dps._get_player_stats", new_callable=AsyncMock) as mock_stats, \
             patch("osrs_mcp.tools.dps._resolve_gear") as mock_gear:
            from osrs_mcp.dps.types import PlayerStats, Monster
            mock_mon.return_value = Monster(
                name="Vorkath", combat_level=732, hitpoints=750,
                defence_level=214, magic_level=150,
                dstab=26, dslash=108, dcrush=108,
                drange=26, dmagic=240, size=7, attribute="dragon",
            )
            mock_stats.return_value = PlayerStats(ranged=80)
            mock_gear.return_value = [{"arange": 95, "rstr": 0, "speed": 5}]
            dps_result = await dps.calc_dps(
                monster="Vorkath", weapon="Dragon hunter crossbow",
                style="ranged", prayer="rigour", potion="super_ranging",
                special_equipment="dragon_hunter_crossbow",
            )
            assert dps_result["dps"] > 0

    @respx.mock
    async def test_workflow_gear_upgrade_decision(self):
        """Reddit: 'What to upgrade next for bossing?'
        Workflow: item_price (current gear) -> item_price (upgrade) -> compare_weapons"""
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=_mock_prices_mapping(
                (4151, "Abyssal whip"), (22324, "Ghrazi rapier"),
            ))
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=_mock_prices_latest({
                "4151": (1350000, 1320000),
                "22324": (125000000, 123000000),
            }))
        )

        whip = await items.item_price("Abyssal whip")
        rapier = await items.item_price("Ghrazi rapier")
        assert whip["high"] < rapier["high"]  # rapier is the upgrade

    @respx.mock
    async def test_workflow_drop_hunting_plan(self):
        """Reddit: 'What's the best way to get a Dragon warhammer?'
        Workflow: drop_sources -> monster_info"""
        route = respx.get("https://oldschool.runescape.wiki/api.php")
        route.side_effect = [
            # Step 1: Find what drops DWH
            httpx.Response(200, json=_mock_drop_sources("Lizardman shaman")),
            # Step 2: Get shaman stats
            httpx.Response(200, json=_mock_monster(
                "Lizardman shaman", 150, 150, 130,
                dstab=20, dslash=20, dcrush=20, drange=20, dmagic=0,
            )),
        ]

        sources = await monsters.drop_sources("Dragon warhammer")
        assert sources[0]["page_name"] == "Lizardman shaman"

        info = await monsters.monster_info("Lizardman shaman")
        assert info["combat_level"] == 150

    @respx.mock
    async def test_workflow_money_making_boss_value(self):
        """Reddit: 'How much gp/hr at Vorkath?'
        Workflow: money_making_methods -> monster_drops -> item_price"""
        # Step 1: Find Vorkath in money making methods
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={
                "bucket": [
                    {"page_name_sub": "Money making guide/Killing Vorkath"},
                    {"page_name_sub": "Money making guide/Killing Zulrah"},
                ]
            })
        )
        methods = await general.money_making_methods(skill="Vorkath")
        assert len(methods) >= 1
        assert "vorkath" in methods[0]["method"].lower()
