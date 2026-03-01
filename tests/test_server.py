"""Tests for MCP server registration."""


class TestServerRegistration:
    def test_all_15_tools_registered(self):
        from osrs_mcp.server import mcp
        tools = mcp._tool_manager._tools
        assert len(tools) == 15

    def test_expected_tool_names(self):
        from osrs_mcp.server import mcp
        tool_names = set(mcp._tool_manager._tools.keys())
        expected = {
            "player_stats", "player_gains",
            "item_info", "search_items", "item_price",
            "monster_info", "monster_drops", "drop_sources", "search_monsters",
            "calc_dps", "compare_weapons",
            "quest_info",
            "search_wiki", "money_making_methods", "boss_requirements",
        }
        assert tool_names == expected

    def test_server_name(self):
        from osrs_mcp.server import mcp
        assert mcp.name == "osrs"
