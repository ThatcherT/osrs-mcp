"""Tests for MCP server registration."""


class TestServerRegistration:
    def test_all_24_tools_registered(self):
        from osrs_mcp.server import mcp
        tools = mcp._tool_manager._tools
        assert len(tools) == 24

    def test_expected_tool_names(self):
        from osrs_mcp.server import mcp
        tool_names = set(mcp._tool_manager._tools.keys())
        expected = {
            "player_stats", "player_gains", "player_bank", "player_gear",
            "item_info", "search_items", "item_price",
            "monster_info", "monster_drops", "drop_sources", "search_monsters",
            "calc_dps", "compare_weapons", "suggest_loadout", "boss_setup",
            "quest_info",
            "search_wiki", "money_making_methods", "boss_requirements",
            "read_wiki_page", "resource_sources",
            "skilling_hours", "boss_grind_hours",
            "slayer_unlocks",
        }
        assert tool_names == expected

    def test_server_name(self):
        from osrs_mcp.server import mcp
        assert mcp.name == "osrs"
