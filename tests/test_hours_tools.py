"""Tests for the expected hours calculator tools."""
import math
import pytest
import respx
import httpx

from osrs_mcp.tools.hours import skilling_hours, boss_grind_hours, _geometric_milestones
from osrs_mcp.util.xp import xp_for_level, xp_between_levels


# === Geometric milestones ===

class TestGeometricMilestones:
    def test_1_in_128(self):
        m = _geometric_milestones(128)
        # 50% chance: ceil(log(0.5)/log(127/128)) ≈ 89
        assert m["50%"] == 89
        assert m["75%"] < m["90%"] < m["99%"]

    def test_1_in_1(self):
        """Guaranteed drop should need 1 kill for all milestones."""
        m = _geometric_milestones(1)
        assert m["50%"] == 1
        assert m["99%"] == 1

    def test_1_in_5000(self):
        m = _geometric_milestones(5000)
        # 50% ≈ 3466, 99% ≈ 23025
        assert 3400 < m["50%"] < 3500
        assert m["99%"] > 20000

    def test_milestones_monotonically_increasing(self):
        m = _geometric_milestones(512)
        assert m["50%"] < m["75%"] < m["90%"] < m["99%"]


# === skilling_hours tool ===

class TestSkillingHours:
    async def test_basic_calculation(self):
        result = await skilling_hours(
            skill="fletching", target_level=70,
            current_level=30, xp_per_hour=150000,
        )
        assert "error" not in result
        assert result["skill"] == "fletching"
        assert result["current_level"] == 30
        assert result["target_level"] == 70
        assert result["xp_needed"] == xp_between_levels(30, 70)
        expected_hours = xp_between_levels(30, 70) / 150000
        assert abs(result["hours"] - round(expected_hours, 1)) < 0.1

    async def test_already_at_target(self):
        result = await skilling_hours(
            skill="attack", target_level=50,
            current_level=60, xp_per_hour=50000,
        )
        assert result["xp_needed"] == 0
        assert result["hours"] == 0

    async def test_no_method_returns_available(self):
        """When no method or xp_per_hour given, return method list."""
        result = await skilling_hours(
            skill="mining", target_level=99, current_level=50,
        )
        assert "methods" in result
        assert len(result["methods"]) > 0
        # Each method should have hours estimate
        for m in result["methods"]:
            assert "hours" in m
            assert "xp_per_hour" in m
            assert m["hours"] > 0

    async def test_method_lookup(self):
        """Providing a method name looks up its XP rate."""
        result = await skilling_hours(
            skill="agility", target_level=70, current_level=60,
            method="Seers' Village rooftop",
        )
        assert "error" not in result
        assert result["xp_per_hour"] == 46000
        assert result["hours"] > 0

    async def test_invalid_method(self):
        result = await skilling_hours(
            skill="mining", target_level=99, current_level=50,
            method="Nonexistent method",
        )
        assert "error" in result
        assert "available_methods" in result

    async def test_invalid_target_level(self):
        result = await skilling_hours(
            skill="attack", target_level=100, current_level=50,
        )
        assert "error" in result

    async def test_unknown_skill(self):
        result = await skilling_hours(
            skill="sailing", target_level=99, current_level=1,
        )
        assert "error" in result

    async def test_current_xp_overrides_level(self):
        """When current_xp is given, it's used instead of current_level."""
        xp_at_50 = xp_for_level(50)
        result = await skilling_hours(
            skill="cooking", target_level=70,
            current_xp=xp_at_50, xp_per_hour=200000,
        )
        expected_xp = xp_for_level(70) - xp_at_50
        assert result["xp_needed"] == expected_xp

    async def test_default_level_1(self):
        result = await skilling_hours(
            skill="fletching", target_level=50, xp_per_hour=100000,
        )
        assert result["current_level"] == 1
        assert result["xp_needed"] == xp_for_level(50)

    @respx.mock
    async def test_with_username(self):
        """Fetching stats from hiscores."""
        respx.get("https://secure.runescape.com/m=hiscore_oldschool/index_lite.json").mock(
            return_value=httpx.Response(200, json={
                "skills": [
                    {"id": 0, "name": "Overall", "rank": 1, "level": 1500, "xp": 50000000},
                    {"id": 11, "name": "Crafting", "rank": 1, "level": 65, "xp": 449428},
                ],
                "activities": [],
            })
        )
        # Mock ironman check endpoints to return 404 (normal account)
        for url in [
            "https://secure.runescape.com/m=hiscore_oldschool_ultimate/index_lite.json",
            "https://secure.runescape.com/m=hiscore_oldschool_hardcore_ironman/index_lite.json",
            "https://secure.runescape.com/m=hiscore_oldschool_ironman/index_lite.json",
        ]:
            respx.get(url).mock(return_value=httpx.Response(404))

        result = await skilling_hours(
            skill="crafting", target_level=99,
            username="testplayer", xp_per_hour=180000,
        )
        assert result["current_level"] == 65
        expected_xp = xp_for_level(99) - 449428
        assert result["xp_needed"] == expected_xp

    async def test_methods_sorted_by_hours(self):
        """Available methods should be sorted fastest first."""
        result = await skilling_hours(
            skill="construction", target_level=99, current_level=77,
        )
        assert "methods" in result
        hours_list = [m["hours"] for m in result["methods"]]
        assert hours_list == sorted(hours_list)

    async def test_methods_filtered_by_level(self):
        """Methods with level_req above current level should be excluded."""
        result = await skilling_hours(
            skill="agility", target_level=99, current_level=45,
        )
        assert "methods" in result
        for m in result["methods"]:
            assert m["level_req"] <= 45


# === boss_grind_hours tool ===

class TestBossGrindHours:
    async def test_basic_calculation(self):
        result = await boss_grind_hours(
            boss="Zulrah", item="Tanzanite fang",
            drop_rate=128, kills_per_hour=25,
        )
        assert "error" not in result
        assert result["boss"] == "Zulrah"
        assert result["item"] == "Tanzanite fang"
        assert result["drop_rate"] == "1/128"
        assert result["kills_per_hour"] == 25
        assert result["expected_kills"] == 128
        assert result["expected_hours"] == round(128 / 25, 1)

    async def test_milestones_present(self):
        result = await boss_grind_hours(
            boss="Vorkath", item="Skeletal visage",
            drop_rate=5000, kills_per_hour=30,
        )
        assert "milestones" in result
        for label in ["50%", "75%", "90%", "99%"]:
            assert label in result["milestones"]
            assert "kills" in result["milestones"][label]
            assert "hours" in result["milestones"][label]

    async def test_invalid_drop_rate(self):
        result = await boss_grind_hours(
            boss="Zulrah", item="Tanzanite fang",
            drop_rate=0, kills_per_hour=25,
        )
        assert "error" in result

    async def test_no_kills_per_hour_or_weapon(self):
        result = await boss_grind_hours(
            boss="Zulrah", item="Tanzanite fang", drop_rate=128,
        )
        assert "error" in result

    async def test_milestone_hours_consistent(self):
        """Milestone hours should equal milestone kills / kph."""
        kph = 20
        result = await boss_grind_hours(
            boss="Cerberus", item="Primordial crystal",
            drop_rate=512, kills_per_hour=kph,
        )
        for label, data in result["milestones"].items():
            expected_hours = round(data["kills"] / kph, 1)
            assert data["hours"] == expected_hours

    async def test_guaranteed_drop(self):
        """1/1 drop rate should need 1 kill."""
        result = await boss_grind_hours(
            boss="TestBoss", item="Always drops",
            drop_rate=1, kills_per_hour=60,
        )
        assert result["expected_kills"] == 1
        assert result["expected_hours"] == 0.0  # rounds to 0.0

    async def test_expected_hours_formula(self):
        """expected_hours = drop_rate / kills_per_hour."""
        result = await boss_grind_hours(
            boss="GWD", item="Hilt",
            drop_rate=508, kills_per_hour=15,
        )
        assert result["expected_hours"] == round(508 / 15, 1)
