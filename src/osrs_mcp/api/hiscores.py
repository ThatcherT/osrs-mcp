from osrs_mcp.api.base import get_client
from osrs_mcp.cache import cache
from osrs_mcp.config import get_config

HISCORES_URL = "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json"

# Ironman hiscores endpoints — if a player appears here, they are that mode.
# Checked most restrictive first so we get the most specific type.
IRONMAN_URLS = {
    "ultimate": "https://secure.runescape.com/m=hiscore_oldschool_ultimate/index_lite.json",
    "hardcore": "https://secure.runescape.com/m=hiscore_oldschool_hardcore_ironman/index_lite.json",
    "ironman": "https://secure.runescape.com/m=hiscore_oldschool_ironman/index_lite.json",
}

SKILL_NAMES = [
    "Overall", "Attack", "Defence", "Strength", "Hitpoints", "Ranged",
    "Prayer", "Magic", "Cooking", "Woodcutting", "Fletching", "Fishing",
    "Firemaking", "Crafting", "Smithing", "Mining", "Herblore", "Agility",
    "Thieving", "Slayer", "Farming", "Runecrafting", "Hunter", "Construction",
]

# Boss/activity order from the hiscores JSON response
ACTIVITY_NAMES = [
    "League Points", "Deadman Points", "Bounty Hunter - Hunter",
    "Bounty Hunter - Rogue", "Bounty Hunter (Legacy) - Hunter",
    "Bounty Hunter (Legacy) - Rogue", "Clue Scrolls (all)", "Clue Scrolls (beginner)",
    "Clue Scrolls (easy)", "Clue Scrolls (medium)", "Clue Scrolls (hard)",
    "Clue Scrolls (elite)", "Clue Scrolls (master)", "LMS - Rank",
    "PvP Arena - Rank", "Soul Wars Zeal", "Rifts closed", "Colosseum Glory",
    "Abyssal Sire", "Alchemical Hydra", "Amoxliatl", "Araxxor",
    "Artio", "Barrows Chests",
    "Bryophyta", "Callisto", "Cal'varion", "Cerberus",
    "Chambers of Xeric", "Chambers of Xeric: Challenge Mode",
    "Chaos Elemental", "Chaos Fanatic", "Commander Zilyana",
    "Corporeal Beast", "Crazy Archaeologist", "Dagannoth Prime",
    "Dagannoth Rex", "Dagannoth Supreme", "Deranged Archaeologist",
    "Duke Sucellus", "General Graardor", "Giant Mole",
    "Grotesque Guardians", "Hespori", "Hueycoatl",
    "K'ril Tsutsaroth", "Kalphite Queen",
    "King Black Dragon", "Kraken", "Kree'Arra", "Lunar Chests",
    "Mimic", "Nex", "Nightmare", "Phosani's Nightmare",
    "Obor", "Phantom Muspah", "Sarachnis", "Scorpia", "Scurrius",
    "Skotizo", "Sol Heredit", "Spindel", "Tempoross",
    "The Gauntlet", "The Corrupted Gauntlet", "The Leviathan",
    "The Whisperer", "Theatre of Blood",
    "Theatre of Blood: Hard Mode", "Thermonuclear Smoke Devil",
    "Tombs of Amascut", "Tombs of Amascut: Expert Mode",
    "TzKal-Zuk", "TzTok-Jad", "Vardorvis", "Venenatis", "Vet'ion",
    "Vorkath", "Wintertodt", "Zalcano", "Zulrah",
]


async def fetch_hiscores(username: str) -> dict:
    """Fetch player stats from Jagex Hiscores API."""
    cache_key = f"hiscores:{username.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    client = get_client()
    resp = await client.get(HISCORES_URL, params={"player": username})
    resp.raise_for_status()
    data = resp.json()

    skills = {}
    for entry in data.get("skills", []):
        skills[entry["name"]] = {
            "rank": entry.get("rank", -1),
            "level": entry.get("level", 1),
            "xp": entry.get("xp", 0),
        }

    activities = {}
    for entry in data.get("activities", []):
        score = entry.get("score", -1)
        if score > 0:
            activities[entry["name"]] = {
                "rank": entry.get("rank", -1),
                "score": score,
            }

    # Detect account type by checking ironman hiscores
    account_type = await detect_account_type(username)

    result = {
        "username": username,
        "account_type": account_type,
        "skills": skills,
        "activities": activities,
    }
    cache.set(cache_key, result, ttl=600)
    return result


async def detect_account_type(username: str) -> str:
    """Detect if a player is an ironman by checking ironman hiscores.

    Returns one of: "ultimate", "hardcore", "ironman", "group_ironman", "normal".
    Checks most restrictive first (UIM > HCIM > IM > normal).
    Group ironman cannot be detected via API — uses config.json account_types.
    """
    cache_key = f"account_type:{username.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # Check config overrides first (needed for group_ironman — no API endpoint)
    cfg = get_config()
    override = cfg.account_types.get(username.lower())
    if override:
        cache.set(cache_key, override, ttl=3600)
        return override

    client = get_client()
    # Check most restrictive first
    for mode, url in IRONMAN_URLS.items():
        try:
            resp = await client.get(url, params={"player": username})
            if resp.status_code == 200:
                cache.set(cache_key, mode, ttl=3600)
                return mode
        except Exception:
            pass

    cache.set(cache_key, "normal", ttl=3600)
    return "normal"
