![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/protocol-MCP-purple)

# osrs-mcp

MCP server that gives Claude live OSRS game data. Player stats, gear lookups, boss setups, DPS calculations, wiki pages, and GE prices from actual game APIs instead of stale training data.

## Quick Start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp config.example.json config.json  # add your RSN(s)
```

Add to Claude Code MCP config (`~/.claude/settings.json`):

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

## Tools

19 tools covering player accounts, items, monsters, bosses, DPS math, and wiki search. Highlights:

| Tool | Purpose |
|---|---|
| `player_stats` | Levels, boss KCs, ironman detection |
| `player_gear` | Best equipment from RuneLite bank data |
| `calc_dps` | DPS calculator with real player stats |
| `boss_setup` | Auto ranks every weapon in your bank vs a boss |
| `compare_weapons` | Side by side weapon DPS comparison |
| `monster_drops` | Full drop table for any monster |
| `item_price` | Live GE price |
| `read_wiki_page` | Fetch wiki content by section |

## Testing

```bash
uv run pytest
```

## Stack

- Python 3.11+, uv
- MCP protocol (`mcp[cli]`)
- httpx for async HTTP
- Pydantic for data validation
- OSRS Wiki API, Wise Old Man API, RuneLite local data
