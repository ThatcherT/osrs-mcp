"""Tests for the OSRS XP table utility."""
import pytest
from osrs_mcp.util.xp import xp_table, xp_for_level, xp_between_levels


class TestXpTable:
    def test_level_1_is_zero(self):
        assert xp_for_level(1) == 0

    def test_level_2(self):
        assert xp_for_level(2) == 83

    def test_level_10(self):
        assert xp_for_level(10) == 1154

    def test_level_50(self):
        assert xp_for_level(50) == 101_333

    def test_level_70(self):
        assert xp_for_level(70) == 737_627

    def test_level_92_is_halfway(self):
        """Level 92 is approximately half of 99's XP."""
        xp_92 = xp_for_level(92)
        xp_99 = xp_for_level(99)
        assert xp_92 == 6_517_253
        # 92 is roughly half of 99
        assert 0.49 < xp_92 / xp_99 < 0.51

    def test_level_99(self):
        assert xp_for_level(99) == 13_034_431

    def test_table_is_monotonically_increasing(self):
        table = xp_table()
        for i in range(2, 100):
            assert table[i] > table[i - 1]

    def test_table_length(self):
        assert len(xp_table()) == 100


class TestXpForLevel:
    def test_invalid_level_zero(self):
        with pytest.raises(ValueError):
            xp_for_level(0)

    def test_invalid_level_100(self):
        with pytest.raises(ValueError):
            xp_for_level(100)

    def test_invalid_level_negative(self):
        with pytest.raises(ValueError):
            xp_for_level(-1)


class TestXpBetweenLevels:
    def test_30_to_70(self):
        expected = xp_for_level(70) - xp_for_level(30)
        assert xp_between_levels(30, 70) == expected

    def test_1_to_99(self):
        assert xp_between_levels(1, 99) == 13_034_431

    def test_same_level_returns_zero(self):
        assert xp_between_levels(50, 50) == 0

    def test_end_less_than_start_returns_zero(self):
        assert xp_between_levels(70, 30) == 0

    def test_98_to_99(self):
        expected = xp_for_level(99) - xp_for_level(98)
        assert xp_between_levels(98, 99) == expected
        # Last level should be ~1.2M XP
        assert 1_100_000 < expected < 1_300_000

    def test_invalid_start(self):
        with pytest.raises(ValueError):
            xp_between_levels(0, 50)

    def test_invalid_end(self):
        with pytest.raises(ValueError):
            xp_between_levels(50, 100)
