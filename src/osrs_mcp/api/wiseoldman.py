from osrs_mcp.api.base import get_client
from osrs_mcp.cache import cache

WOM_BASE = "https://api.wiseoldman.net/v2"


async def fetch_player_gains(username: str, period: str = "week") -> dict:
    """Fetch player gains from Wise Old Man."""
    cache_key = f"wom:gains:{username.lower()}:{period}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = get_client()
    resp = await client.get(
        f"{WOM_BASE}/players/{username}/gained",
        params={"period": period},
    )

    if resp.status_code == 404:
        # Player not tracked yet - try to track them first
        await client.post(f"{WOM_BASE}/players/{username}")
        resp = await client.get(
            f"{WOM_BASE}/players/{username}/gained",
            params={"period": period},
        )

    resp.raise_for_status()
    data = resp.json()

    # Simplify the response - extract meaningful gains
    result = {"username": username, "period": period, "skills": {}, "bosses": {}}

    for skill_name, skill_data in data.get("data", {}).get("skills", {}).items():
        gained = skill_data.get("experience", {}).get("gained", 0)
        if gained > 0:
            result["skills"][skill_name] = {
                "xp_gained": gained,
                "levels_gained": skill_data.get("level", {}).get("gained", 0),
                "start_level": skill_data.get("level", {}).get("start", 0),
                "end_level": skill_data.get("level", {}).get("end", 0),
            }

    for boss_name, boss_data in data.get("data", {}).get("bosses", {}).items():
        gained = boss_data.get("kills", {}).get("gained", 0)
        if gained > 0:
            result["bosses"][boss_name] = {
                "kills_gained": gained,
                "start_kc": boss_data.get("kills", {}).get("start", 0),
                "end_kc": boss_data.get("kills", {}).get("end", 0),
            }

    cache.set(cache_key, result, ttl=300)
    return result
