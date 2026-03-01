import pytest
import httpx
import respx

from osrs_mcp.cache import cache
from osrs_mcp.dps.types import PlayerStats, GearSetup, Monster


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the global cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def maxed_stats():
    return PlayerStats()  # defaults to 99 all


@pytest.fixture
def mid_level_stats():
    return PlayerStats(
        attack=75, strength=75, defence=75,
        ranged=75, magic=75, hitpoints=75, prayer=70,
    )


@pytest.fixture
def whip_gear():
    """Abyssal whip stats."""
    return GearSetup(aslash=82, melee_str=82, speed=4)


@pytest.fixture
def rapier_gear():
    """Ghrazi rapier stats."""
    return GearSetup(astab=94, aslash=55, melee_str=89, speed=4)


@pytest.fixture
def tbow_gear():
    """Twisted bow stats (base, without passive)."""
    return GearSetup(arange=70, ranged_str=20, speed=5)


@pytest.fixture
def trident_gear():
    """Trident of the swamp stats."""
    return GearSetup(amagic=25, magic_dmg=15, speed=4)


@pytest.fixture
def abyssal_demon():
    return Monster(
        name="Abyssal demon",
        combat_level=124,
        hitpoints=150,
        defence_level=135,
        magic_level=1,
        dstab=20, dslash=20, dcrush=20,
        drange=20, dmagic=0,
        attribute="demon",
    )


@pytest.fixture
def vorkath():
    return Monster(
        name="Vorkath",
        combat_level=732,
        hitpoints=750,
        defence_level=214,
        magic_level=150,
        dstab=26, dslash=108, dcrush=108,
        drange=26, dmagic=240,
        size=7,
        attribute="dragon",
    )


@pytest.fixture
def giant_rat():
    """Low-level monster for sanity checks."""
    return Monster(
        name="Giant rat",
        combat_level=3,
        hitpoints=5,
        defence_level=2,
        dstab=0, dslash=0, dcrush=0,
        drange=0, dmagic=0,
    )


@pytest.fixture
def undead_monster():
    return Monster(
        name="Revenant imp",
        combat_level=7,
        hitpoints=10,
        defence_level=4,
        dstab=0, dslash=0, dcrush=0,
        drange=0, dmagic=0,
        attribute="undead",
    )


# --- Mock API response data ---

MOCK_HISCORES_RESPONSE = {
    "skills": [
        {"id": 0, "name": "Overall", "rank": 100000, "level": 2000, "xp": 200000000},
        {"id": 1, "name": "Attack", "rank": 50000, "level": 99, "xp": 13034431},
        {"id": 2, "name": "Defence", "rank": 50000, "level": 99, "xp": 13034431},
        {"id": 3, "name": "Strength", "rank": 50000, "level": 99, "xp": 13034431},
        {"id": 4, "name": "Hitpoints", "rank": 50000, "level": 99, "xp": 13034431},
        {"id": 5, "name": "Ranged", "rank": 50000, "level": 99, "xp": 13034431},
        {"id": 6, "name": "Prayer", "rank": 50000, "level": 77, "xp": 1500000},
        {"id": 7, "name": "Magic", "rank": 50000, "level": 99, "xp": 13034431},
    ],
    "activities": [
        {"id": 0, "name": "Vorkath", "rank": 1000, "score": 500},
        {"id": 1, "name": "Zulrah", "rank": 2000, "score": 300},
        {"id": 2, "name": "Wintertodt", "rank": -1, "score": -1},
    ],
}

MOCK_PRICES_MAPPING = [
    {"id": 4151, "name": "Abyssal whip", "examine": "A weapon from the Abyss.",
     "members": True, "lowalch": 72000, "highalch": 108000, "limit": 70},
    {"id": 11802, "name": "Armadyl godsword", "examine": "A very powerful sword.",
     "members": True, "lowalch": None, "highalch": None, "limit": 8},
    {"id": 1333, "name": "Rune scimitar", "examine": "A razor-sharp scimitar.",
     "members": False, "lowalch": 9600, "highalch": 14400, "limit": 70},
]

MOCK_PRICES_LATEST = {
    "data": {
        "4151": {"high": 1350000, "low": 1320000, "highTime": 1700000000, "lowTime": 1700000000},
        "11802": {"high": 8500000, "low": 8200000, "highTime": 1700000000, "lowTime": 1700000000},
        "1333": {"high": 15000, "low": 14800, "highTime": 1700000000, "lowTime": 1700000000},
    }
}

MOCK_BUCKET_MONSTER = {
    "bucket": [
        {
            "name": "Vorkath",
            "combat_level": 392,
            "hitpoints": 460,
            "defence_level": 164,
            "magic_level": 150,
            "stab_defence_bonus": 26,
            "slash_defence_bonus": 108,
            "crush_defence_bonus": 108,
            "range_defence_bonus": 26,
            "magic_defence_bonus": 240,
            "size": 7,
            "attribute": "dragon",
        },
        {
            "name": "Vorkath",
            "combat_level": 732,
            "hitpoints": 750,
            "defence_level": 214,
            "magic_level": 150,
            "stab_defence_bonus": 26,
            "slash_defence_bonus": 108,
            "crush_defence_bonus": 108,
            "range_defence_bonus": 26,
            "magic_defence_bonus": 240,
            "size": 7,
            "attribute": "dragon",
        },
    ]
}

MOCK_BUCKET_DROPS = {
    "bucket": [
        {"item_name": "Superior dragon bones"},
        {"item_name": "Blue dragonhide"},
        {"item_name": "Rune longsword"},
    ]
}

MOCK_BUCKET_DROP_SOURCES = {
    "bucket": [
        {"page_name": "Abyssal demon"},
        {"page_name": "Greater abyssal demon"},
    ]
}

MOCK_BUCKET_ITEM_JOIN = {
    "bucket": [
        {
            "infobox_item.page_name_sub": "Abyssal whip",
            "infobox_item.examine": "A weapon from the Abyss.",
            "infobox_item.weight": 0.453,
            "infobox_item.tradeable": True,
            "infobox_item.value": 120001,
            "infobox_bonuses.stab_attack_bonus": 0,
            "infobox_bonuses.slash_attack_bonus": 82,
            "infobox_bonuses.strength_bonus": 82,
            "infobox_bonuses.equipment_slot": "weapon",
        }
    ]
}

MOCK_BUCKET_QUEST = {
    "bucket": [
        {
            "page_name_sub": "Dragon Slayer I",
            "start_point": "Talk to the Guildmaster in the Champions' Guild.",
            "official_difficulty": "Experienced",
        }
    ]
}

MOCK_BUCKET_MONEY_MAKING = {
    "bucket": [
        {"page_name_sub": "Money making guide/Crafting nature runes through the Abyss"},
        {"page_name_sub": "Money making guide/Killing Vorkath"},
    ]
}

MOCK_WIKI_SEARCH = {
    "query": {
        "search": [
            {
                "title": "Fire cape",
                "snippet": 'The <span class="searchmatch">fire</span> <span class="searchmatch">cape</span> is a reward.',
            },
            {
                "title": "TzTok-Jad",
                "snippet": 'The final boss of the Fight Caves.',
            },
        ]
    }
}

MOCK_WOM_GAINS = {
    "data": {
        "skills": {
            "attack": {
                "experience": {"gained": 50000, "start": 1000000, "end": 1050000},
                "level": {"gained": 0, "start": 70, "end": 70},
            },
            "slayer": {
                "experience": {"gained": 100000, "start": 500000, "end": 600000},
                "level": {"gained": 1, "start": 60, "end": 61},
            },
        },
        "bosses": {
            "vorkath": {
                "kills": {"gained": 50, "start": 100, "end": 150},
            },
        },
    }
}
