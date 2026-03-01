# OSRS MCP Server

MCP server that gives Claude live OSRS data — player stats, gear, boss info, wiki pages, DPS calculations, and more. Ask it things like "what boss should I do next?" or "what's my best setup for Vorkath?" and it'll look up your actual account and answer with real data instead of guessing.

## Getting Started

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> && cd osrs-wiki-mcp
uv sync
cp config.example.json config.json  # edit with your RSN
```

Edit `config.json`:
```json
{
    "username": "your_rsn",
    "accounts": ["your_rsn", "your_alt"],
    "user_agent": "osrs-mcp/0.1.0 - your_contact_info"
}
```

Add to your Claude Code MCP config (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "osrs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/osrs-wiki-mcp", "osrs-mcp"]
    }
  }
}
```

Restart Claude Code. The 19 tools will be available immediately.

## Tools

| Tool | What it does |
|---|---|
| `player_stats` | Levels, boss KCs, account type (ironman detection) |
| `player_gear` | Best equipment per slot from RuneLite bank data |
| `player_bank` | Search bank contents |
| `player_gains` | Recent XP/KC gains via Wise Old Man |
| `monster_info` | Monster stats and weaknesses |
| `monster_drops` | What a monster drops |
| `drop_sources` | What monsters drop an item |
| `search_monsters` | Find monsters by name |
| `item_info` | Item stats and bonuses |
| `item_price` | Live GE price |
| `search_items` | Find items by name |
| `calc_dps` | DPS calculator with your stats and gear |
| `compare_weapons` | Side-by-side weapon DPS comparison |
| `suggest_loadout` | Auto-rank every weapon in your bank vs a boss |
| `boss_requirements` | Boss info + drops |
| `quest_info` | Quest requirements and details |
| `read_wiki_page` | Fetch wiki page content by section |
| `search_wiki` | Search the OSRS Wiki |
| `money_making_methods` | Money making methods from the wiki |

## Bank Data (Optional)

`player_gear`, `player_bank`, and `suggest_loadout` read your bank from RuneLite's local data. To set this up:

1. Install the **Quest Helper** plugin in RuneLite
2. Open your bank in-game with the plugin enabled
3. Bank data is saved locally — no API needed

Without this, the tools that need bank data will tell you it's unavailable. Everything else works without it.
