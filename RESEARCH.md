# OSRS MCP Server - Research Findings

## Executive Summary

There is a rich ecosystem of OSRS data APIs and tools. The key finding is that **an existing OSRS MCP server exists** ([JayArrowz/mcp-osrs](https://github.com/JayArrowz/mcp-osrs)) but it only covers wiki search and static cache data -- it doesn't integrate with the rich community APIs. There's a significant opportunity to build something much more comprehensive.

The fundamental constraint is: **Jagex's official API only exposes skills/XP/boss KCs**. Everything else (bank contents, quest status, collection log items, achievement diaries) is only accessible through RuneLite plugins that read data from the game client.

---

## Data Sources Available

### Tier 1: Public APIs (No Auth Required)

#### 1. OSRS Wiki Bucket API (Structured Game Data)
**This is the most important API for game metadata.**

- **Endpoint:** `https://oldschool.runescape.wiki/api.php?action=bucket&format=json&formatversion=2&query=<URL-encoded query>`
- **Query syntax:** Chainable Lua-like DSL:
  ```
  bucket('infobox_monster')
    .select('name','combat_level','hitpoints','max_hit')
    .where('name','Abyssal demon')
    .limit(500)
    .offset(0)
    .run()
  ```
- **Operators:** `=`, `!=`, `>`, `<`, `>=`, `<=`, `bucket.Or()`, `bucket.And()`, `bucket.Not()`, `bucket.Null()`
- **Joins:** `bucket('infobox_item').join('infobox_bonuses', 'infobox_item.page_name_sub', 'infobox_bonuses.page_name_sub').select(...)`
- **Limits:** Default 500, max 5000 per query. Paginate with `.offset(n)`
- **MANDATORY: Custom User-Agent header required** (default `python-requests`, `curl`, etc. are BLOCKED)

##### 40 Available Data Buckets

| Bucket | Use Case |
|--------|----------|
| `infobox_item` | Item metadata: ID, name, examine, weight, alch values, buy limit, tradeable (~16,125 items) |
| `infobox_bonuses` | Equipment combat stats: atk/def bonuses, str/rstr/mdmg/prayer, slot, speed |
| `infobox_monster` | Monster stats: combat level, HP, max hit, all offensive/defensive stats, slayer info, elemental weakness (54 fields) |
| `infobox_spell` | Spell data: runes, levels, effects |
| `quest` | Quest data: requirements, rewards |
| `dropsline` | Individual drop entries: item, rate, quantity |
| `drop_table_sources` | Sources for shared drop tables |
| `logs` | Collection log data |
| `combat_achievement` | Combat achievement details |
| `money_making_guide` | Money making methods |
| `recipe` | Crafting/cooking/etc recipes |
| `recommended_equipment` | Recommended gear setups |
| `storeline` | Shop inventories |
| `infobox_activity` | Minigame/activity info |
| `infobox_npc` | NPC data |
| `infobox_construction` | Construction furniture |
| `infobox_location` | Location/area data |
| `mine` | Mining site data |
| `dependency_list` | Dependency/requirement lists |
| Others: `bountytaskline`, `exchange`, `feedback`, `infobox_grid_master_unlock`, `infobox_pure`, `infobox_scenery`, `infobox_ship_part`, `interface`, `item_id`, `locline`, `map`, `music`, `music_map`, `npc_id`, `object_id`, `seachart`, `sound_effect`, `transcript`, `update`, `varbit` |

##### Key Bucket Field Details

**infobox_bonuses fields:** `astab`, `aslash`, `acrush`, `arange`, `amagic` (attack), `dstab`, `dslash`, `dcrush`, `drange`, `dmagic` (defence), `str`, `rstr`, `mdmg`, `prayer`, `speed`, `slot`, `combatstyle`

**infobox_monster fields (54):** `name`, `id`, `combat_level`, `hitpoints`, `max_hit`, `attack_level`, `strength_level`, `defence_level`, `ranged_level`, `magic_level`, all attack/defence bonuses, `slayer_level`, `slayer_experience`, `slayer_category`, `assigned_by`, `attack_style`, `attack_speed`, `flat_armour`, `size`, `freeze_resistance`, `elemental_weakness`, `elemental_weakness_percent`, `poison_immune`, `venom_immune`, `thrall_immune`, `cannon_immune`, `burn_immune`, `attribute`, etc.

#### 2. OSRS Wiki Real-Time Prices API (GE Prices)
**Crowdsourced from RuneLite users -- the gold standard for GE prices.**

- **Base URL:** `https://prices.runescape.wiki/api/v1/osrs`
- **Endpoints:**

| Endpoint | Description | Notes |
|----------|-------------|-------|
| `/latest` | Current high/low instant-buy/sell for ALL items | Single request returns ~3,700 items |
| `/latest?id=4151` | Single item price | |
| `/mapping` | Item metadata: name, ID, examine, alch values, buy limits, icons | |
| `/5m` | 5-minute average prices + volume | `?timestamp=` optional |
| `/1h` | 1-hour averages + volume | `?timestamp=` optional |
| `/timeseries?id=4151&timestep=1h` | Historical (up to 365 points) | timestep: `5m`, `1h`, `6h`, `24h` |

- **MANDATORY: Custom User-Agent header required**
- Do NOT loop individual item requests -- use bulk endpoints

#### 3. Weird Gloop Exchange History API (Daily GE Prices)

- **Base URL:** `https://api.weirdgloop.org/exchange/history/osrs/`
- **Endpoints:** `/latest` (100 items), `/all` (1 item, complete history), `/sample` (1 item, 150 sampled points), `/last90d`
- **Query by:** `?id=4151|49430` or `?name=Abyssal%20whip`
- **Bulk dump:** `https://chisel.weirdgloop.org/gazproj/gazbot/os_dump.json`

#### 4. Jagex Hiscores API (Player Stats)

- **JSON endpoint:** `https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player={username}`
- **Game mode variants:** `hiscore_oldschool`, `_ironman`, `_hardcore_ironman`, `_ultimate`, `_deadman`, `_seasonal`
- **Returns:** 24 skills (rank, level, XP) + 89 activities (rank, score) including all boss KCs
- **Does NOT expose:** Bank, quests, collection log items, achievement diaries, inventory

#### 5. Wise Old Man API (Player Tracking)

- **Base URL:** `https://api.wiseoldman.net/v2`
- **Rate limits:** 20 req/60s (100/60s with API key via Discord)
- **Key endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `GET /players/:username` | Full player details |
| `POST /players/:username` | Track/update player (fetches from Hiscores) |
| `GET /players/:username/gained?period=week` | Stat gains over time |
| `GET /players/:username/records` | Personal records |
| `GET /players/:username/snapshots` | Historical snapshots |
| `GET /players/:username/achievements` | Unlocked achievements |
| `GET /players/:username/competitions` | Competition participations |
| `GET /players/:username/groups` | Group memberships |

- **Client libs:** `@wise-old-man/utils` (npm), `wom.py` (Python)

#### 6. TempleOSRS API (Most Comprehensive Single API)

- **Base URL:** `https://templeosrs.com/api/`
- **38+ endpoints** covering almost everything
- **Key endpoints:**

| Endpoint | Purpose |
|----------|---------|
| `/player_stats.php?player=X&bosses=1` | Stats with boss KCs |
| `/player_gains.php?player=X&time=Y` | Gains over time |
| `/player_datapoints.php?player=X` | Historical snapshots |
| `/collection-log/player_collection_log.php?player=X` | **Collection log data** (replaced collectionlog.net) |
| `/collection-log/player_recent_items.php?player=X` | Recent collection log items |
| `/collection-log/items.php` | All collection log items |
| `/collection-log/categories.php` | All categories |
| `/rates/ehb_rates.php?rate=main` | EHP/EHB rates |
| `/pets/leaderboard.php` | Pet leaderboard |

#### 7. MediaWiki API (Raw Wiki Content)

- **Endpoint:** `https://oldschool.runescape.wiki/api.php`
- **Actions:** `action=query` (search), `action=parse` (HTML), `action=query&prop=revisions` (wikitext)
- Useful for getting full wiki page content when structured Bucket data isn't enough

### Tier 2: Data That Requires RuneLite Plugin

These data types are NOT available via any public API -- they require reading from the game client:

| Data | How to Access |
|------|---------------|
| **Bank contents** | RuneLite `getItemContainer(InventoryID.BANK)` |
| **Quest completion** | RuneLite `Quest.getState(Client)` + varbits |
| **Achievement diaries** | RuneLite varbits |
| **Current equipment** | RuneLite `getItemContainer(InventoryID.EQUIPMENT)` |
| **Current inventory** | RuneLite `getItemContainer(InventoryID.INVENTORY)` |
| **Detailed collection log** | TempleOSRS (via their RuneLite plugin upload) |

**Existing RuneLite plugins that export data:**
- **Dink** (pajlads/DinkPlugin) -- Webhook notifications for 20+ event types (loot, levels, collection log, quests, etc.) to Discord or custom server
- **httpplug** (slyautomation/httpplug) -- Local HTTP server on port 8080 exposing game data
- **WikiSync** -- Uploads quest/diary/skill data to wiki servers (private API, not for third-party use)
- **Bank Memory Plugin** -- Remembers and compares bank contents locally
- **CA Export** -- Exports combat achievements to JSON file

**Best approach for live account data:** Either:
1. Use a Dink webhook to capture events in real-time and store them
2. Build/use a RuneLite plugin with a local HTTP server (httpplug pattern)
3. Accept Hiscores-only data (skills, boss KCs) via WOM/TempleOSRS APIs

---

## DPS Calculation Reference

### The Gold Standard: weirdgloop/osrs-dps-calc

- **GitHub:** [github.com/weirdgloop/osrs-dps-calc](https://github.com/weirdgloop/osrs-dps-calc)
- **Live tool:** [tools.runescape.wiki/osrs-dps/](https://tools.runescape.wiki/osrs-dps/)
- **License:** GPL-3.0 (fully open source)
- **Stack:** TypeScript, Next.js, Tailwind CSS, Jest
- **Last updated:** Feb 25, 2026 (actively maintained)

#### How It Gets Data
Python scripts query the Wiki Bucket API:
- `scripts/generateEquipment.py` → `cdn/json/equipment.json`
- `scripts/generateMonsters.py` → `cdn/json/monsters.json`
- Also: `cdn/json/spells.json`, `cdn/json/equipment_aliases.json`

#### DPS Formula Pipeline
1. `getDps()` → `getDpt()` (damage per tick)
2. `getDpt()` = `getExpectedDamage()` / `getExpectedAttackSpeed()`
3. `getExpectedDamage()` = `getDistribution().getExpectedDamage()` + `getDoTExpected()`

**Core accuracy formula:**
- If `atk_roll > def_roll`: `hit_chance = 1 - (def_roll + 2) / (2 * (atk_roll + 1))`
- Else: `hit_chance = atk_roll / (2 * (def_roll + 1))`

Where:
- `atk_roll = effectiveAttackLevel * (equipmentBonus + 64)`
- `def_roll = (targetDefence + 9) * (targetStyleDefenceBonus + 64)`

#### Handles All Edge Cases
- Special attacks (Dragon claws multi-hit distribution, etc.)
- Prayers (multiplicative strength/accuracy factors)
- Potions (skill boosts)
- Set effects (Void Knight, Slayer Helm, Salve Amulet, Dharok's, Inquisitor's, etc.)
- NPC-specific transforms (Zulrah, Corp Beast, Vampyres, Kraken)
- Raid scaling (ToA invocation, CoX CM, party size)
- 40+ helper methods for detecting gear sets

### Other DPS Calculators

| Tool | Open Source | Notes |
|------|------------|-------|
| Gearscape (gearscape.net) | No | Vue/Vuetify, closed source, best-in-slot finder |
| Bitterkoekje's Spreadsheet | Viewable | The original formula reference (Google Sheets) |
| LlemonDuck/dps-calculator | Yes | RuneLite plugin (Java) |
| OSRS Genie | No | Web-based, based on Bitterkoekje's |

---

## Existing OSRS MCP Server

### JayArrowz/mcp-osrs
- **GitHub:** [github.com/JayArrowz/mcp-osrs](https://github.com/JayArrowz/mcp-osrs)
- **19 tools:** 3 wiki tools + 13 game data search tools + 3 file tools
- **Architecture:** TypeScript/Node.js, bundles local TSV cache data files
- **What it lacks:** No WOM, no TempleOSRS, no real-time prices, no collection logs, no player-specific data, no DPS calculations, no Bucket API integration

---

## Static Game Data Packages

### osrs-db (npm)
- **GitHub:** [github.com/wvanderp/osrs-db](https://github.com/wvanderp/osrs-db)
- **npm:** `npm install osrs-db`
- Machine-readable JSON with full TypeScript types
- Covers items, NPCs, objects, quests
- Auto-updated from game cache

### osrsreboxed-db (Maintained Fork of OSRSBox)
- **GitHub:** [github.com/0xNeffarion/osrsreboxed-db](https://github.com/0xNeffarion/osrsreboxed-db)
- 20K+ items (27+ properties each, including equipment stats)
- 2.5K+ monsters (44 properties each, includes full drop tables)
- All prayers with stats/drain rates
- Available as Python package or static JSON files

---

## Recommended Architecture for OSRS MCP Server

### Data Source Strategy by Use Case

| User Question | Data Sources Needed |
|---------------|-------------------|
| "What bosses can I kill?" | Hiscores (player stats) + Wiki Bucket (boss requirements, monster stats) + Wiki Bucket (recommended_equipment) |
| "What should I do to get maple seeds?" | Wiki Bucket (dropsline for drop sources) + Wiki Bucket (infobox_monster for monster stats) + Prices API (current value) |
| "What's my best gear for Vorkath?" | Hiscores (player stats) + Wiki Bucket (infobox_bonuses for equipment) + DPS calc formulas + Wiki Bucket (infobox_monster for Vorkath stats) |
| "What quests should I do next?" | Wiki Bucket (quest requirements/rewards) + player quest status (RuneLite only OR manual input) |
| "What's my collection log progress?" | TempleOSRS collection log API |
| "How much is my bank worth?" | Bank data (RuneLite only) + Prices API |

### Proposed MCP Tools

1. **Player tools:** Lookup stats, gains, records, achievements (via WOM + Hiscores)
2. **Item tools:** Search items, get stats/bonuses, check prices (via Bucket + Prices API)
3. **Monster tools:** Search monsters, get stats/drops/requirements (via Bucket + dropsline)
4. **Quest tools:** Search quests, check requirements (via Bucket quest)
5. **Collection log tools:** Check progress (via TempleOSRS)
6. **DPS tools:** Calculate DPS for player+gear vs monster (reference weirdgloop formulas)
7. **Drop source tools:** Find where items drop (via Bucket dropsline)
8. **Money making tools:** Suggest methods (via Bucket money_making_guide + Prices)
9. **Wiki search:** Full-text wiki search for anything else (via MediaWiki API)

### Critical Requirements
- **User-Agent header** on ALL wiki/prices API requests (mandatory, will be blocked otherwise)
- **Rate limiting** -- no official limits but be respectful
- **Player username configuration** -- store RSN for personalized queries
- **Caching** -- cache Bucket API responses (game data changes slowly, only on game updates)
