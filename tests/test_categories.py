"""Tests for item category expansion."""
from osrs_mcp.util.categories import expand_category, list_categories, ITEM_CATEGORIES


class TestExpandCategory:
    def test_known_category(self):
        result = expand_category("herb seeds")
        assert len(result) == 14
        assert "Guam seed" in result
        assert "Torstol seed" in result

    def test_known_category_case_insensitive(self):
        result = expand_category("Herb Seeds")
        assert len(result) == 14

    def test_known_category_with_whitespace(self):
        result = expand_category("  herb seeds  ")
        assert len(result) == 14

    def test_tree_seeds(self):
        result = expand_category("tree seeds")
        assert len(result) == 6
        assert "Magic seed" in result

    def test_fruit_tree_seeds(self):
        result = expand_category("fruit tree seeds")
        assert len(result) == 8
        assert "Papaya tree seed" in result

    def test_rune_items(self):
        result = expand_category("rune items")
        assert len(result) == 6
        assert "Nature rune" in result

    def test_bolt_tips(self):
        result = expand_category("bolt tips")
        assert len(result) == 10
        assert "Diamond bolt tips" in result

    def test_comma_separated(self):
        result = expand_category("Ranarr seed, Snapdragon seed")
        assert result == ["Ranarr seed", "Snapdragon seed"]

    def test_comma_separated_with_spaces(self):
        result = expand_category("  Ranarr seed ,  Snapdragon seed  ")
        assert result == ["Ranarr seed", "Snapdragon seed"]

    def test_single_item(self):
        result = expand_category("Abyssal whip")
        assert result == ["Abyssal whip"]

    def test_single_item_with_whitespace(self):
        result = expand_category("  Abyssal whip  ")
        assert result == ["Abyssal whip"]

    def test_unknown_category_treated_as_single(self):
        result = expand_category("not a category")
        assert result == ["not a category"]


class TestListCategories:
    def test_returns_all_categories(self):
        result = list_categories()
        assert len(result) == len(ITEM_CATEGORIES)
        assert result["herb seeds"] == 14
        assert result["tree seeds"] == 6
        assert result["bolt tips"] == 10
