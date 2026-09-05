# Bibliography

Every feature that draws on someone else's work is listed here with what it drew on. Revenant borrows shapes, grammars and game knowledge from the DragonRealms community, and this file is where that debt is written down, feature by feature.

The rule for the list: an entry names a specific source that a script, module or doc actually used — a Lich script whose grammar was ported, a wiki page whose table was encoded — not a general resemblance. Features built only from captured game traffic (`;sheet`, `;survey`, `;fight`, `;antiidle`) have no entry. When a feature picks up a new source, add it here in the same commit.

## Scripts and modules

| Feature | Draws on | How |
|---|---|---|
| `;lnet`, `chat/` | rcuhljr's [Genie LNet plugin](https://github.com/rcuhljr/genie-lnet-plugin/), [lnet.lic](https://github.com/elanthia-online/scripts/blob/master/scripts/lnet.lic) (Lich's LNet client, in elanthia-online/scripts) and the [LNet server](https://lnet.lichproject.org) | `chat/` began as a rough Python port of the Genie plugin; the protocol notes, login handshake, ping replies and pinned CA follow lnet.lic 1.15, and the `;chat` / `;reply` / `;who` grammar is a 1:1 port of it. Replies to `;who` and `;stats` are Ruby Marshal, read by `chat/rmarshal.py`. |
| `;go2`, `client/walker.py`, `client/mapdb.py`, the Map dock | [elanthia-online/mapdb-backup-dr](https://github.com/elanthia-online/mapdb-backup-dr), the community map maintained for Lich | The map is downloaded on first use and consumed as data: rooms, exits, travel times, tags and the embedded-Ruby edges that translate to plain commands. `;go2` is named after Lich's go2 and does the same job. See [movement.md](movement.md). |
| `;tend` | Lich's DragonRealms commons — [common-healing](https://github.com/elanthia-online/lich-5/tree/main/lib/dragonrealms/commons) and its data file (DRCH), now inside lich-5 — and [Elanthipedia: Damage](https://elanthipedia.play.net/Damage#Bleeding_Levels) | Bleed levels, their rates and the wound wordings. |
| `client/wounds.py`, `;hunt`'s wound floor | [Elanthipedia: Damage](https://elanthipedia.play.net/Damage) | The wound wording tables per body area, severity and kind, generated verbatim into `client/wounds_data.py` by `tools/wound_tables.py`. See [wounds.md](wounds.md). |
| `;wealth` | Lich's DragonRealms commons — [common-money](https://github.com/elanthia-online/lich-5/tree/main/lib/dragonrealms/commons), now inside lich-5 | The balance-statement grammar ("1 platinum, 3 gold …") and the currency table. |
| `;athletics`, `client/climbs.py` | Elanthipedia's Climbing and Swimming list and [Athletics](https://elanthipedia.play.net/Athletics) | The climbing spots, their rank bands, the armed-climb column and the spot conditions, keyed to community-map room ids. |
| `;circle`, `client/circles.py`, beholder's Circle-gates view | Each guild's Elanthipedia page, e.g. [Thief](https://elanthipedia.play.net/Thief) | The circle requirement tables for all eleven circled guilds and the slot / soft-requirement model. See [circles.md](circles.md) for the validation against guildleaders. |
| `;clock`, `client/eltime.py`, the Clocks dock | [Elanthipedia: Time](https://elanthipedia.play.net/Time), [Xibar](https://elanthipedia.play.net/Xibar), [Yavash](https://elanthipedia.play.net/Yavash), [Katamba](https://elanthipedia.play.net/Katamba) | The Elanthian calendar, anlas, the moons' phase periods, and each moon's rise-to-rise and above-horizon times. See [eltime.md](eltime.md). |
| `;deathwatch` | Elanthipedia's Death and Depart command pages | The depart variants, their costs in favors and what each keeps. See [death.md](death.md) for where the wiki and captured traffic disagree. |
| `;favors` | [Elanthipedia: Favors](https://elanthipedia.play.net/Favors) and [Immortals](https://elanthipedia.play.net/Immortals) | The favor-orb ritual, the grotto puzzles and the Thirteen's aspect table. See [favors.md](favors.md). |
| `;hunt`, `client/profile.py` | [Elanthipedia: Rat](https://elanthipedia.play.net/Rat), [Skinning](https://elanthipedia.play.net/Skinning), [Gem pouch](https://elanthipedia.play.net/Gem_pouch), [Combat 101](https://elanthipedia.play.net/Combat_101) | The rat's level, loot and skins; what SKIN needs in hand; the pouch commands; the attack, retreat and stance grammar. See [hunting.md](hunting.md). |
| `;mechlore` | Elanthipedia's Mechanical Lore pages | The free entry method to training the skill. |
| `;xp`, the Experience dock, beholder | [Elanthipedia: Experience](https://elanthipedia.play.net/Experience) | Mindstates, the learning-rate model and the exp window's columns. See [experience.md](experience.md). |
| `client/xml_data.py`, [protocol.md](protocol.md) | The [Wrayth protocol](https://gswiki.play.net/Wrayth_protocol) page on the GemStone wiki | The tag grammar the parser implements; DragonRealms' own stream, component and indicator ids come from captured traffic. |
| [combat.md](combat.md) | [Elanthipedia: Combat 101](https://elanthipedia.play.net/Combat_101), [Stance](https://elanthipedia.play.net/Stance) | The engagement and retreat model the walker's burst-through follows. |
| `launcher/` | [Lich](https://github.com/elanthia-online/lich-5) and [ProfanityFE](https://github.com/elanthia-online/ProfanityFE) | Starts the Ruby toolchain headless and attaches Profanity; a bridge to those projects, not a reimplementation. |

## Whole-project influences

- **Lich** — the session-and-scripts split, the `;` command language, `;help` as the manual, `;stop`, and the detachable-client idea behind `revenant --attach` all follow Lich's shape. [why-python.md](why-python.md) records what the Python retelling buys and costs.
- **dr-scripts** — the reference for what a script library grows into; the tiered layout described in [scripting.md](scripting.md) is a reaction to it as much as a copy.
- **Pylanthia** — [robbintt/pylanthia](https://github.com/robbintt/pylanthia), the other Python DragonRealms client, an early inspiration.
- **Elanthipedia** — every mechanic above was researched there first; the `docs/*.md` model files say where the wiki and captured traffic disagree, and the fixtures side with the traffic.
