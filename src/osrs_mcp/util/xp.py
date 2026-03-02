"""OSRS XP table math utilities."""
import math
from functools import lru_cache


@lru_cache(maxsize=1)
def xp_table() -> list[int]:
    """Compute the OSRS XP table (index 1-99).

    Returns a list of length 100 where xp_table()[L] is the cumulative XP
    needed to reach level L. Index 0 is 0 (unused placeholder).

    Formula: XP(L) = floor(sum_{n=1}^{L-1} floor(n + 300 * 2^(n/7)) / 4)
    """
    table = [0] * 100
    cumulative = 0
    for level in range(1, 100):
        table[level] = math.floor(cumulative / 4)
        cumulative += math.floor(level + 300 * 2 ** (level / 7))
    return table


def xp_for_level(level: int) -> int:
    """Return the cumulative XP required to reach a given level (1-99).

    Raises ValueError if level is out of range.
    """
    if not 1 <= level <= 99:
        raise ValueError(f"Level must be 1-99, got {level}")
    return xp_table()[level]


def xp_between_levels(start: int, end: int) -> int:
    """Return the XP needed to go from the start of `start` to the start of `end`.

    Both levels are inclusive of their starting XP.
    E.g. xp_between_levels(30, 70) gives XP from level 30 to level 70.
    """
    if not 1 <= start <= 99:
        raise ValueError(f"Start level must be 1-99, got {start}")
    if not 1 <= end <= 99:
        raise ValueError(f"End level must be 1-99, got {end}")
    if end <= start:
        return 0
    return xp_for_level(end) - xp_for_level(start)
