from osrs_mcp.server import mcp
from osrs_mcp.config import get_config
from osrs_mcp.api.hiscores import fetch_hiscores
from osrs_mcp.api.wiseoldman import fetch_player_gains


def _resolve_username(username: str | None) -> str:
    if username:
        return username
    cfg = get_config()
    if cfg.username:
        return cfg.username
    raise ValueError("No username provided and none configured in config.json")


@mcp.tool()
async def player_stats(username: str = "") -> dict:
    """Get a player's skills, levels, XP, and boss kill counts from the OSRS Hiscores.

    Args:
        username: RuneScape username. Leave empty to use configured default.
    """
    name = _resolve_username(username or None)
    return await fetch_hiscores(name)


@mcp.tool()
async def player_gains(username: str = "", period: str = "week") -> dict:
    """Get a player's XP gains and boss KC gains over a time period via Wise Old Man.

    Args:
        username: RuneScape username. Leave empty to use configured default.
        period: Time period - one of: day, week, month, year, 6h, 5min.
    """
    name = _resolve_username(username or None)
    return await fetch_player_gains(name, period)
