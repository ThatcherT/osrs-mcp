"""Tests for slayer_unlocks tool."""
import pytest
from unittest.mock import patch, AsyncMock

from osrs_mcp.tools import slayer
from osrs_mcp.tools.slayer import _get_slayer_monsters


class TestGetSlayerMonsters:
    """Test the internal helper using real local data."""

    def test_loads_monsters(self):
        results = _get_slayer_monsters()
        assert len(results) > 0

    def test_all_have_slayer_category(self):
        results = _get_slayer_monsters()
        for m in results:
            assert m["slayer_category"] is not None

    def test_sorted_by_level_then_name(self):
        results = _get_slayer_monsters()
        for i in range(1, len(results)):
            prev, curr = results[i - 1], results[i]
            assert (prev["slayer_level"], prev["name"]) <= (curr["slayer_level"], curr["name"])

    def test_filter_by_level_range(self):
        results = _get_slayer_monsters(min_level=80, max_level=90)
        for m in results:
            assert 80 <= m["slayer_level"] <= 90

    def test_filter_exact_level(self):
        results = _get_slayer_monsters(min_level=65, max_level=65)
        for m in results:
            assert m["slayer_level"] == 65

    def test_filter_by_master(self):
        results = _get_slayer_monsters(master="duradel")
        for m in results:
            assigned = [a.lower() for a in m["assigned_by"]]
            assert "duradel" in assigned

    def test_master_alias_steve_to_nieve(self):
        steve_results = _get_slayer_monsters(master="steve")
        nieve_results = _get_slayer_monsters(master="nieve")
        assert len(steve_results) == len(nieve_results)

    def test_master_case_insensitive(self):
        lower = _get_slayer_monsters(master="duradel")
        upper = _get_slayer_monsters(master="Duradel")
        assert len(lower) == len(upper)

    def test_no_duplicates(self):
        results = _get_slayer_monsters()
        names = [m["name"].lower() for m in results]
        assert len(names) == len(set(names))

    def test_result_shape(self):
        results = _get_slayer_monsters(min_level=1, max_level=1)
        if results:
            m = results[0]
            assert "name" in m
            assert "slayer_level" in m
            assert "combat_level" in m
            assert "hitpoints" in m
            assert "slayer_category" in m
            assert "assigned_by" in m


class TestSlayerUnlocksTool:
    async def test_exact_level(self):
        result = await slayer.slayer_unlocks(level=65)
        assert result["level_range"] == "65-65"
        assert "unlocks_by_level" in result
        # All returned monsters should be exactly level 65
        for lvl, monsters in result["unlocks_by_level"].items():
            assert int(lvl) == 65

    async def test_level_range(self):
        result = await slayer.slayer_unlocks(min_level=40, max_level=60)
        assert result["level_range"] == "40-60"
        for lvl_str in result["unlocks_by_level"]:
            assert 40 <= int(lvl_str) <= 60

    async def test_with_username(self):
        mock_stats = {
            "skills": {
                "Slayer": {"level": 72, "xp": 900000},
            }
        }
        with patch("osrs_mcp.api.hiscores.fetch_hiscores", new_callable=AsyncMock, return_value=mock_stats):
            result = await slayer.slayer_unlocks(username="TestPlayer")
            assert result["player_slayer_level"] == 72
            assert result["username"] == "TestPlayer"
            assert result["level_range"] == "1-72"
            for lvl_str in result["unlocks_by_level"]:
                assert int(lvl_str) <= 72

    async def test_with_master_filter(self):
        result = await slayer.slayer_unlocks(min_level=1, max_level=99, master="duradel")
        assert result["master_filter"] == "duradel"
        assert result["total_monsters"] > 0

    async def test_defaults_full_range(self):
        result = await slayer.slayer_unlocks()
        assert result["level_range"] == "1-99"

    async def test_empty_level_returns_nothing(self):
        result = await slayer.slayer_unlocks(level=99)
        # Level 99 may or may not have monsters, but should work without error
        assert "unlocks_by_level" in result
