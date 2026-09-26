# Circle requirements

`;circle` tells you what gates your next circle — the guildleader's answer — computed locally, with no trip to the guild.

```
;circle          INFO's circle and guild now, the exp window's ranks over the latest ;sheet snapshot
;circle fresh    run ;sheet first, then the gates
```

Beholder's Circle-gates view shows the same. All eleven circled guilds are encoded in `client/client/game/circles.py`, transcribed from each guild's Elanthipedia page; Commoners don't circle.

## How a requirement is read

- A requirement is a **named skill** (Thievery, Inner Fire, Trading...) or a **slot**: "3rd Survival" is your third-best survival skill, whatever it is.
- The ranks needed for circle C are the per-circle rates summed over the wiki's bands (1-10, 11-30, 31-70, 71-100, 101-150, 151+). The tests re-derive each wiki Cumulative column from the rates.
- Slots fill best-first by rank, then percent.
- A guild's named skills stay out of its slots unless the wiki marks them soft (Thief's Stealth, Paladin's Tactics, Ranger's Instinct...).

## Assumptions

- Parry Ability, Expertise, Offhand Weapon and the Masteries never fill a weapon slot.
- Armor slots draw only from Light Armor, Chain Armor, Brigandine and Plate Armor.
- Primary Magic skills (Holy, Lunar, Inner Fire...) never fill a magic slot — the wiki says so. Clerics also exclude Sorcery and Thievery; Moon Mages exclude Thievery.
- Barbarian's single lore slot is read as "1st Lore" (the wiki's two tables disagree).
- Where a wiki rate table and its Cumulative column disagree, the value that fits the most checkpoints wins.

## Caveats

- **Ties:** the game fills an equal-rank slot in an order of its own, so `;circle` names every tied skill: "4th Survival (First Aid, Locksmithing or Outdoorsmanship) 1/2". The set of unmet gates is still right.
- A few high-band rows (Barbarian Expertise and Bard 4th Magic at 71-100, Bard 2nd Lore at 101-150) have no rate that fits the wiki's checkpoints; expect small errors there.
- Around Thief circle 2, `;circle` may list a 2nd Lore gate the guildleader does not.
- Necromancer and Ranger publish no cumulative table, so their encodings carry no cross-check.
