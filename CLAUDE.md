# OSRS MCP Server — Claude Code Instructions

## Golden Rule
**You have OSRS MCP tools available in this session. USE THEM to answer OSRS questions.**
The tools are registered as MCP tools (e.g. `player_stats`, `boss_setup`, `calc_dps`, etc.).
Call them directly — do NOT try to answer OSRS questions by reading source code or using training data.
Your training data is outdated and often wrong about specific stats, prices, drop rates, and meta.
The MCP tools have live data — use them.

**This is a codebase for the MCP server AND the server is running as a connected MCP tool provider.**
When the user asks an OSRS gameplay question, call the MCP tools. Do not say "I don't have the tools connected" —
they ARE connected. Check `/mcp` if unsure.

## Rules — Never Guess
1. Any specific number (level requirement, drop rate, XP rate, price, KPH) **MUST** come from a tool call. Never state numbers from memory.
2. Never list monster drops without calling `monster_drops()` or `drop_sources()`.
3. Never state slayer level requirements without calling `monster_info()` or `slayer_unlocks()`. Training data frequently gets these wrong (e.g. Drakes are 84 Slayer, not 70).
4. Never recommend boss gear without reading `read_wiki_page("Boss/Strategies")` first.
5. Never describe training methods or XP rates without checking wiki or skilling tools.
6. Never state GE prices without calling `item_price()`.
7. If uncertain about any fact, say "let me check" and use the appropriate tool.
8. Never fill knowledge gaps with training data — say "I couldn't find that in the tools" instead of guessing.

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
3. `read_wiki_page("Boss/Strategies")` — read the wiki's recommended equipment and strategy. **Do this before recommending any gear for a boss.** Training data about what's "good" at a specific boss is often wrong.
4. `monster_info(boss)` — check boss stats and weaknesses
5. `calc_dps(monster, weapon, spell="Iban's Blast")` — calculate actual DPS with their stats. Use `spell` param for magic.
6. `boss_requirements(boss)` — get boss info + drops

### For "what boss should I do?" questions:
1. Get their stats with `player_stats`
2. Get their best gear with `player_gear(username)` for an overview, or `player_gear(username, optimize="aslash")` for a specific setup
3. Read wiki strategy pages with `read_wiki_page("Boss/Strategies")` — check recommended stats, gear, and mechanics
4. Look up specific bosses with `monster_info` and `boss_requirements`
5. Calculate DPS with `calc_dps` using their actual stats and gear

### For "what should I wear?" / boss gear questions:
- **Always read the wiki first**: `read_wiki_page("Boss Name/Strategies", "Recommended equipment")` or the relevant strategy section. The wiki's recommended gear is maintained by experienced players and accounts for boss-specific mechanics (e.g. ToA bosses hit through defence so Barrows melee armour is bad there, even though it's normally good mid-game gear).
- **Never fill gear gaps from training data.** If the wiki doesn't recommend an item, don't recommend it. If you don't know what to suggest for a slot, say so — don't guess.
- Use `player_gear(username, optimize=stat)` to see what they actually own
- Cross-reference wiki recommendations against their bank to find the best gear they have that the wiki actually endorses

### For item/drop questions:
- `drop_sources(item)` — what monsters drop this item
- `drop_sources("herb seeds")` — bulk lookup by category (also: "tree seeds", "fruit tree seeds", "rune items", "bolt tips")
- `drop_sources("Ranarr seed, Snapdragon seed")` — comma-separated bulk lookup
- `monster_drops(monster)` — what a monster drops
- `item_info(item)` — full item details and bonuses
- `item_price(item)` — current GE price
- **NEVER state that a monster drops a specific item without verifying with `monster_drops()` or `drop_sources()`.** Training data is full of wrong drop attributions (e.g. Blood shard comes from Vyrewatch Sentinels, not Undead Druids). Always verify.

### For "where do I get X?" questions:
- `resource_sources(item)` — reads the wiki's "Item sources" table which has every source (monsters, skilling, thieving, shops, minigames) with level, quantity, and drop rate
- `resource_sources("herb seeds")` — works with categories too (adds bulk drop table lookup)
- Use this instead of `drop_sources` when you need complete source data with drop rates

### For slayer questions:
- `slayer_unlocks(level=65)` — what unlocks at exactly slayer level 65
- `slayer_unlocks(min_level=40, max_level=60)` — range of unlocks
- `slayer_unlocks(username="die tmo")` — auto-fetch slayer level, show all their unlocks
- `slayer_unlocks(master="duradel")` — filter by master
- **NEVER guess slayer level requirements.** Always use `slayer_unlocks()` or `monster_info()`.

### For "what's my KPH?" / boss setup questions:
1. `boss_setup(boss, username)` — tests every weapon in their bank, picks best prayer/potion for their level, shows top 5 setups with DPS + KPH + weakness analysis
2. Can filter by style: `boss_setup(boss, username, style="ranged")`
3. For magic setups: `boss_setup(boss, username, style="magic", spell="Fire Surge")`

### For DPS/weapon comparisons:
- `compare_weapons(monster, "weapon1,weapon2,weapon3")` — side-by-side DPS comparison
- For magic: use `spell` param, e.g. `calc_dps(monster, weapon, style="magic", spell="Iban's Blast")`
- Always use the player's actual stats, not maxed defaults

## Important Game Mechanics
- **Spell weapon requirements**: Some spells require a specific weapon equipped. Iban's Blast needs Iban's staff, god spells need their god staff (or Staff of the dead for Zamorak), Magic Dart needs Slayer's staff or SotD. The DPS tools enforce this — `calc_dps` returns an error and `boss_setup` skips incompatible combos.
- **Elemental weakness**: Only affects standard spellbook elemental spells (Strike/Bolt/Blast/Wave/Surge). Does NOT affect powered staves (Trident, Tumeken's Shadow), Ice Barrage, or non-elemental spells. Does NOT affect melee or ranged.
- **Dragon Hunter Lance/Crossbow**: Bonus damage/accuracy vs dragons. Separate from elemental weakness.
- **Slayer helm**: 16.67% melee boost (or 15% ranged/mage with imbue) on task only.
- Equipment with `bonuses: "none (no combat stats)"` has zero offensive and defensive stats — don't describe it as "defensive" or "offensive".
