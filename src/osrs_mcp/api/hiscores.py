from osrs_mcp.api.base import get_client
from osrs_mcp.cache import cache

HISCORES_URL = "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json"

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

    result = {"username": username, "skills": skills, "activities": activities}
    cache.set(cache_key, result, ttl=600)
    return result
