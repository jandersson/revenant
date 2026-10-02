# Experience

What DragonRealms' experience system means for training, and what `;xp` logs. The canon is [Elanthipedia's Experience page](https://elanthipedia.play.net/Experience).

## The model

1. **In.** An accepted action fills the skill's pool. An action too easy for your ranks adds nothing; a travel climb awards at most once per 45–60 s (`climb practice` is exempt).
2. **The pool.** The mindstate (0–34, clear to mind lock) is how full it is.
3. **Out.** Every 200 s the pool pulses into ranks, whatever you do.

So a mind-locked skill learns nothing more (`;athletics` pauses at 34 until below 28), and a low mindstate that stays flat means the spot is outgrown.

## Rested experience

Rested experience (REXP) triples the ranks each pulse buys while it burns.

- **Banking:** 1 minute per 2 minutes without draining: offline, idle, or in deep sleep.
- **Caps:** Standard 4 h, Premium 6 h, Platinum 8 h, per 23:30 h cycle.
- **Burn:** 20 s per skill group that pulses with experience; train fewer groups to stretch it.
- **Sleep:** SLEEP once still drains and burns; SLEEP twice banks.
- **Online rests burn it:** a rest in the game spends the bank while the pools only drain; `;train`'s `rest_mode` `logout` logs out for the rest instead ([training.md](training.md)).

The EXP footer states it; the Experience dock shows it. Some accounts get
the exp window's footer empty: then only EXP answers carry it (`;sheet`'s
EXP ALL at login and every three hours, any EXP typed).

## How fast a pool drains

Linearly: each pulse removes a fixed number of mindstate buckets by the skill's tier (`client/game/drain.py`, fitted from `;xp`'s rows).

| Tier | Buckets a pulse | 34 to 0 |
| --- | --- | --- |
| primary | 1.14 | ~100 min |
| secondary | 0.91 | ~125 min |
| tertiary | 0.65 | ~175 min |

- The tier is the guild's skillset placement; a tertiary skill under 25 ranks drains as secondary.
- Within a tier, rank, Intelligence and REXP do not change the rate; Wisdom scales it by the wiki's table (assumed, not measured).
- `;train` guesses a rest's length from this; the rest still ends on the exp window.
- **Caveat:** fitted on one Paladin only.

## What a mindstate is worth

A bucket is worth `8.35 / rank` of the wiki's pool size over 34: a full primary pool at rank 50 is about one rank. `drain.ranks_from` computes it; `tools/experience_fit.py` refits it. Unproven above rank 100.

## What `;xp` logs

Autostarted; writes `~/.revenant/history.db` every minute:

| Table | Rows |
| --- | --- |
| `mindstate` | rank, percent, mindstate per skill; `is_rexp` 1 while REXP burns (the window's footer fell within the last 11 minutes; with only EXP answers, the last one still had more to spend than minutes since), NULL when unknown |
| `rested` | the footer's stored, usable and refresh minutes, on change and on every EXP answer; `source` `window` or `exp` |

Beholder plots them. `;stop xp` opts a session out; `REVENANT_NO_XP=1` turns off the autostart.

**Caveat:** older rows flag only the minutes the footer fell, and read a spent
cycle ("Usable This Cycle: none") as NULL. For history, derive REXP from
`rested`: it burns while the lesser of stored and usable is above 0 and a pool drains.
