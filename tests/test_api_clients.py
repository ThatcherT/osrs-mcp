"""Tests for API clients with mocked HTTP responses."""
import pytest
import httpx
import respx

from osrs_mcp.cache import cache
from osrs_mcp.api import hiscores, wiki_prices, wiki_bucket, wiki_search, wiseoldman
from tests.conftest import (
    MOCK_HISCORES_RESPONSE, MOCK_PRICES_MAPPING, MOCK_PRICES_LATEST,
    MOCK_BUCKET_MONSTER, MOCK_BUCKET_DROPS, MOCK_BUCKET_DROP_SOURCES,
    MOCK_BUCKET_ITEM_JOIN, MOCK_BUCKET_QUEST, MOCK_BUCKET_MONEY_MAKING,
    MOCK_WIKI_SEARCH, MOCK_WOM_GAINS,
)


# === Hiscores API ===

class TestHiscoresAPI:
    @respx.mock
    async def test_fetch_hiscores(self):
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=MOCK_HISCORES_RESPONSE)
        )
        result = await hiscores.fetch_hiscores("TestPlayer")
        assert result["username"] == "TestPlayer"
        assert result["skills"]["Attack"]["level"] == 99
        assert result["skills"]["Prayer"]["level"] == 77
        assert result["activities"]["Vorkath"]["score"] == 500
        assert "Wintertodt" not in result["activities"]  # score=-1 filtered

    @respx.mock
    async def test_hiscores_caching(self):
        route = respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json=MOCK_HISCORES_RESPONSE)
        )
        await hiscores.fetch_hiscores("CachedPlayer")
        await hiscores.fetch_hiscores("CachedPlayer")
        assert route.call_count == 1  # Second call should use cache

    @respx.mock
    async def test_hiscores_404(self):
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await hiscores.fetch_hiscores("NonexistentPlayer")


# === Prices API ===

class TestPricesAPI:
    @respx.mock
    async def test_fetch_mapping(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        result = await wiki_prices.fetch_mapping()
        assert len(result) == 3
        assert result[0]["name"] == "Abyssal whip"

    @respx.mock
    async def test_fetch_latest_prices(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_LATEST)
        )
        result = await wiki_prices.fetch_latest_prices()
        assert "4151" in result
        assert result["4151"]["high"] == 1350000

    @respx.mock
    async def test_search_items_by_name(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        results = await wiki_prices.search_items_by_name("whip")
        assert len(results) == 1
        assert results[0]["name"] == "Abyssal whip"

    @respx.mock
    async def test_search_items_case_insensitive(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        results = await wiki_prices.search_items_by_name("RUNE")
        assert any("Rune" in r["name"] for r in results)

    @respx.mock
    async def test_search_items_max_25(self):
        # Create many matching items
        big_mapping = [{"id": i, "name": f"Dragon item {i}"} for i in range(50)]
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=big_mapping)
        )
        results = await wiki_prices.search_items_by_name("Dragon")
        assert len(results) == 25

    @respx.mock
    async def test_get_item_price_exact_match(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_LATEST)
        )
        result = await wiki_prices.get_item_price("Abyssal whip")
        assert result is not None
        assert result["name"] == "Abyssal whip"
        assert result["high"] == 1350000
        assert result["low"] == 1320000
        assert result["buy_limit"] == 70

    @respx.mock
    async def test_get_item_price_partial_match(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        respx.get("https://prices.runescape.wiki/api/v1/osrs/latest").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_LATEST)
        )
        result = await wiki_prices.get_item_price("whip")
        assert result is not None
        assert result["name"] == "Abyssal whip"

    @respx.mock
    async def test_get_item_price_not_found(self):
        respx.get("https://prices.runescape.wiki/api/v1/osrs/mapping").mock(
            return_value=httpx.Response(200, json=MOCK_PRICES_MAPPING)
        )
        result = await wiki_prices.get_item_price("Nonexistent item xyz")
        assert result is None


# === Wiki Bucket API ===

class TestWikiBucketAPI:
    @respx.mock
    async def test_bucket_query(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_MONSTER)
        )
        results = await wiki_bucket.bucket_query(
            "infobox_monster", ["name", "combat_level"],
            where={"name": "Vorkath"}, limit=10,
        )
        assert len(results) == 2
        assert results[0]["name"] == "Vorkath"

    @respx.mock
    async def test_bucket_query_error_returns_empty(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"error": "Field foo not found."})
        )
        results = await wiki_bucket.bucket_query("test", ["foo"])
        assert results == []

    @respx.mock
    async def test_bucket_query_caching(self):
        route = respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": [{"name": "test"}]})
        )
        r1 = await wiki_bucket.bucket_query("test", ["name"], limit=100)
        r2 = await wiki_bucket.bucket_query("test", ["name"], limit=100)
        assert r1 == r2
        assert route.call_count == 1

    @respx.mock
    async def test_get_monster_info_returns_highest_combat(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_MONSTER)
        )
        result = await wiki_bucket.get_monster_info("Vorkath")
        assert result is not None
        assert result["combat_level"] == 732  # Post-quest version (highest)

    @respx.mock
    async def test_get_monster_info_not_found(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": []})
        )
        result = await wiki_bucket.get_monster_info("FakeMonster")
        assert result is None

    @respx.mock
    async def test_get_monster_drops(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_DROPS)
        )
        drops = await wiki_bucket.get_monster_drops("Vorkath")
        assert len(drops) == 3
        assert drops[0]["item_name"] == "Superior dragon bones"

    @respx.mock
    async def test_get_drop_sources(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_DROP_SOURCES)
        )
        sources = await wiki_bucket.get_drop_sources("Abyssal whip")
        assert len(sources) == 2
        assert sources[0]["page_name"] == "Abyssal demon"

    @respx.mock
    async def test_get_item_info_equipment(self):
        """Item with bonuses should return flattened join result."""
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_ITEM_JOIN)
        )
        result = await wiki_bucket.get_item_info("Abyssal whip")
        assert result is not None
        assert result["page_name_sub"] == "Abyssal whip"
        assert result["strength_bonus"] == 82
        assert result["equipment_slot"] == "weapon"

    @respx.mock
    async def test_get_item_info_non_equipment_fallback(self):
        """Non-equipment item falls back to item-only query."""
        # First call (join) returns empty, second call (item-only) returns data
        route = respx.get("https://oldschool.runescape.wiki/api.php")
        route.side_effect = [
            httpx.Response(200, json={"bucket": []}),  # join returns nothing
            httpx.Response(200, json={"bucket": [{"page_name_sub": "Coins", "examine": "Lovely money!"}]}),
        ]
        result = await wiki_bucket.get_item_info("Coins")
        assert result is not None
        assert result["page_name_sub"] == "Coins"

    @respx.mock
    async def test_get_quest_info(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_QUEST)
        )
        result = await wiki_bucket.get_quest_info("Dragon Slayer I")
        assert result is not None
        assert result["official_difficulty"] == "Experienced"

    @respx.mock
    async def test_get_quest_info_not_found(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"bucket": []})
        )
        result = await wiki_bucket.get_quest_info("Fake Quest")
        assert result is None

    @respx.mock
    async def test_get_money_making_methods(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_BUCKET_MONEY_MAKING)
        )
        results = await wiki_bucket.get_money_making_methods()
        assert len(results) == 2

    @respx.mock
    async def test_get_boss_info(self):
        route = respx.get("https://oldschool.runescape.wiki/api.php")
        route.side_effect = [
            httpx.Response(200, json=MOCK_BUCKET_MONSTER),  # monster info
            httpx.Response(200, json=MOCK_BUCKET_DROPS),    # drops
        ]
        result = await wiki_bucket.get_boss_info("Vorkath")
        assert result["monster"] is not None
        assert result["monster"]["combat_level"] == 732
        assert len(result["drops"]) == 3

    @respx.mock
    async def test_bucket_query_all_pagination(self):
        """Test that bucket_query_all paginates correctly."""
        # First page returns 5000 items (full page), second returns fewer
        page1 = [{"name": f"item_{i}"} for i in range(5000)]
        page2 = [{"name": f"item_{i}"} for i in range(5000, 5100)]

        route = respx.get("https://oldschool.runescape.wiki/api.php")
        route.side_effect = [
            httpx.Response(200, json={"bucket": page1}),
            httpx.Response(200, json={"bucket": page2}),
        ]
        results = await wiki_bucket.bucket_query_all("test", ["name"])
        assert len(results) == 5100


# === Wiki Search API ===

class TestWikiSearchAPI:
    @respx.mock
    async def test_search_wiki(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json=MOCK_WIKI_SEARCH)
        )
        results = await wiki_search.search_wiki("fire cape")
        assert len(results) == 2
        assert results[0]["title"] == "Fire cape"
        assert "searchmatch" not in results[0]["snippet"]  # HTML stripped
        assert "oldschool.runescape.wiki" in results[0]["url"]

    @respx.mock
    async def test_search_wiki_empty(self):
        respx.get("https://oldschool.runescape.wiki/api.php").mock(
            return_value=httpx.Response(200, json={"query": {"search": []}})
        )
        results = await wiki_search.search_wiki("xyznonexistent")
        assert results == []


# === Wise Old Man API ===

class TestWiseOldManAPI:
    @respx.mock
    async def test_fetch_player_gains(self):
        respx.get("https://api.wiseoldman.net/v2/players/TestPlayer/gained").mock(
            return_value=httpx.Response(200, json=MOCK_WOM_GAINS)
        )
        result = await wiseoldman.fetch_player_gains("TestPlayer", "week")
        assert result["username"] == "TestPlayer"
        assert result["period"] == "week"
        assert result["skills"]["attack"]["xp_gained"] == 50000
        assert result["skills"]["slayer"]["levels_gained"] == 1
        assert result["bosses"]["vorkath"]["kills_gained"] == 50

    @respx.mock
    async def test_fetch_player_gains_filters_zero_gains(self):
        data = {
            "data": {
                "skills": {
                    "attack": {"experience": {"gained": 0}, "level": {"gained": 0}},
                    "mining": {"experience": {"gained": 500}, "level": {"gained": 0, "start": 50, "end": 50}},
                },
                "bosses": {
                    "vorkath": {"kills": {"gained": 0}},
                    "zulrah": {"kills": {"gained": 10, "start": 5, "end": 15}},
                },
            }
        }
        respx.get("https://api.wiseoldman.net/v2/players/Player2/gained").mock(
            return_value=httpx.Response(200, json=data)
        )
        result = await wiseoldman.fetch_player_gains("Player2", "week")
        assert "attack" not in result["skills"]  # 0 gained, filtered
        assert "mining" in result["skills"]
        assert "vorkath" not in result["bosses"]  # 0 gained, filtered
        assert "zulrah" in result["bosses"]

    @respx.mock
    async def test_fetch_player_gains_tracks_untracked(self):
        """When player returns 404, it should POST to track, then retry."""
        respx.get("https://api.wiseoldman.net/v2/players/NewPlayer/gained").mock(
            side_effect=[
                httpx.Response(404),
                httpx.Response(200, json=MOCK_WOM_GAINS),
            ]
        )
        respx.post("https://api.wiseoldman.net/v2/players/NewPlayer").mock(
            return_value=httpx.Response(200, json={})
        )
        result = await wiseoldman.fetch_player_gains("NewPlayer", "week")
        assert result["username"] == "NewPlayer"
