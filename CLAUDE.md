# OSRS MCP Server — Claude Code Instructions

## Golden Rule
**ALWAYS use the MCP tools to answer OSRS questions. Never rely on training data alone.**
Your training data is outdated and often wrong about specific stats, prices, drop rates, and meta.
The MCP tools have live data — use them.

## Before Answering Any OSRS Question
1. **Check the player's account first.** Call `player_stats` to get their levels, boss KCs, and account type (normal/ironman/hardcore/ultimate). This tells you what content they can actually do.
2. **Check their gear.** Call `player_gear` to see their best-in-slot equipment per stat. Use `player_bank(search="item name")` to check for specific items. Don't recommend items they already have.
3. **Check account type implications:**
   - **Ironman/Hardcore/Ultimate**: Cannot use the Grand Exchange or trade. All gear must come from drops, crafting, or shops. Never suggest "buy X from the GE" for these accounts.
   - **Group Ironman** (`group_ironman`): Can only trade within their group (not other players or GE). Gear must be obtained as drops, crafted, from shops, or traded within the group.
   - **Normal**: Can trade and use the GE freely.

## Configured Accounts
The user has 3 accounts: `die tmo`, `31k elite`, `thatcher98`. If they say "my ironman" they mean whichever account `player_stats` reports as ironman/hardcore/ultimate.

## How to Use Tools

### For gear/progression questions:
1. `player_stats(username)` — get their levels + account type
2. `player_gear(username, optimize="str")` — see their best gear for a specific stat
3. `monster_info(boss)` — check boss stats and weaknesses
4. `calc_dps(monster, weapon)` — calculate actual DPS with their stats
5. `boss_requirements(boss)` — get boss info + drops

### For "what boss should I do?" questions:
1. Get their stats with `player_stats`
2. Get their best gear with `player_gear(username)` for an overview, or `player_gear(username, optimize="aslash")` for a specific setup
3. Look up specific bosses with `monster_info` and `boss_requirements`
4. Calculate DPS with `calc_dps` using their actual stats and gear

### For "what should I wear?" questions:
- Use `player_gear(username, optimize=stat)` to get the best item per slot
- Pick the stat based on the boss: high-defence bosses → accuracy stat (aslash, acrush, astab); low-defence bosses → strength stat (str, rstr); magic → amagic
- The loadout is built from items actually in their bank — no guessing

### For item/drop questions:
- `drop_sources(item)` — what monsters drop this item
- `monster_drops(monster)` — what a monster drops
- `item_info(item)` — full item details and bonuses
- `item_price(item)` — current GE price

### For DPS/weapon comparisons:
- `compare_weapons(monster, "weapon1,weapon2,weapon3")` — side-by-side DPS comparison
- Always use the player's actual stats, not maxed defaults

## Important Game Mechanics
- **Elemental weakness**: Only affects standard spellbook elemental spells (Strike/Bolt/Blast/Wave/Surge). Does NOT affect powered staves (Trident, Tumeken's Shadow), Ice Barrage, or non-elemental spells. Does NOT affect melee or ranged.
- **Dragon Hunter Lance/Crossbow**: Bonus damage/accuracy vs dragons. Separate from elemental weakness.
- **Slayer helm**: 16.67% melee boost (or 15% ranged/mage with imbue) on task only.
- Equipment with `bonuses: "none (no combat stats)"` has zero offensive and defensive stats — don't describe it as "defensive" or "offensive".
