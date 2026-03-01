from dataclasses import dataclass, field


@dataclass
class PlayerStats:
    attack: int = 99
    strength: int = 99
    defence: int = 99
    ranged: int = 99
    magic: int = 99
    hitpoints: int = 99
    prayer: int = 99


@dataclass
class GearSetup:
    """Equipment bonuses aggregated from all worn gear."""
    astab: int = 0
    aslash: int = 0
    acrush: int = 0
    arange: int = 0
    amagic: int = 0
    dstab: int = 0
    dslash: int = 0
    dcrush: int = 0
    drange: int = 0
    dmagic: int = 0
    melee_str: int = 0
    ranged_str: int = 0
    magic_dmg: int = 0  # percentage (e.g. 15 = 15%)
    prayer: int = 0
    speed: int = 4  # attack speed in ticks


@dataclass
class Monster:
    name: str = ""
    combat_level: int = 0
    hitpoints: int = 1
    defence_level: int = 0
    magic_level: int = 0
    dstab: int = 0
    dslash: int = 0
    dcrush: int = 0
    drange: int = 0
    dmagic: int = 0
    size: int = 1
    attribute: str = ""  # "dragon", "demon", "undead", etc.
    flat_armour: int = 0
    elemental_weakness: str = ""  # "Fire", "Water", "Earth", "Air", or ""
    elemental_weakness_percent: int = 0  # 0-100, bonus acc% + dmg% for matching spells


@dataclass
class DpsResult:
    weapon: str = ""
    attack_style: str = ""
    max_hit: int = 0
    accuracy: float = 0.0
    dps: float = 0.0
    attack_speed: int = 4
    ttk_seconds: float = 0.0  # time to kill based on monster HP
    details: dict = field(default_factory=dict)
