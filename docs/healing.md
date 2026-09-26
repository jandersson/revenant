# Healing

Stop the bleeding with `;tend`, heal wounds with herbs through `;heal`, and go to an NPC healer (`;heal npc`) or a player Empath for what herbs cannot touch. An Empath character heals others with `;empath`.

## What heals what

| Damage | Answer |
| --- | --- |
| External bleeding | `;tend` |
| Internal bleeding | magic (an Empath) |
| Fresh wounds, external or internal | herbs (`;heal`), or an NPC healer |
| Nerve damage ("twitching") | an NPC healer |
| Scars | a player Empath; NPC healers leave them |

The wound readings themselves are in [wounds.md](wounds.md).

## ;tend

```
;tend         watch: tend every bleeder, worst first, whenever bleeding starts
;tend once    one check-and-tend pass
```

It trains First Aid as it goes and leaves internal bleeders alone.

## ;heal: herbs

```
;heal              HEALTH, then use a carried herb for each wound
;heal list         the plan: wounds, herbs, the shop; nothing used
;heal buy          fetch coins from the teller, buy the missing herbs, use them
;heal floor=minor  treat only wounds this bad or worse (default insignificant)
```

- One herb per wound area and kind, one use per run; it heals over time.
- In the Crossing the herbalist is Mauriga's Botanicals, 812–1000 Kronars a herb. The Alchemy Society's herbs are crafting stock, not remedies.
- A bleeder is reported, not treated: run `;tend`.

## ;heal npc: the hospital

```
;heal npc          the nearest NPC healer
;heal quentin      a healer by name (quentin, arthianna, fraethis)
```

It walks to the healer, sets DEMEANOR FRIENDLY EMPATH (left friendly after), lies down, and lets the healer work part by part; then stands, reads HEALTH and says what was paid and what is left.

- The healer takes the province's coins, per part; foreign coins are exchanged first. An empty purse stops it before the walk.
- Healers: Shard's Quentin, Riverhaven's Fraethis, Leth Deriel's Arthianna. The Crossing has none, and Knife Clan's Dokt only sells herb cookies now.
- **Caveat:** healers leave scars and minor wounds. Eating a herb first can also make the healer skip that part.

## Player Empaths

Ask aloud in the Empaths' Guild courtyard (`;go2 5713` in the Crossing). An Empath who touches you heals everything, scars and internal damage included, usually for free. This is never automated: the ask is yours.

## ;empath: healing as an Empath

```
;empath Uthmor           TOUCH, take every wound, touch again for bared scars, heal yourself
;empath Uthmor take      the transfers only
;empath self             Heal Wounds and Heal Scars on yourself, worst first
;empath ... mana=15      mana per cast (default 15)
```

- Bleeding first, then the worst wounds, fresh before scars; taking fresh wounds bares scars, so it touches again (up to three rounds).
- It stops when mana drops below a fifth, or the patient is gone or refuses the touch.

`;stop <name>` ends any of these at once; `;heal return` and `;empath return` finish the step in hand first.
