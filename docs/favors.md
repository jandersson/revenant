# Favors

`;favors` earns one favor by the orb run, so a death is never a zero-favor DEPART. Canon is Elanthipedia's [Favors](https://elanthipedia.play.net/Favors) and [Immortals](https://elanthipedia.play.net/Immortals) pages.

## Using it

```
;favors [immortal]   the whole run; default Truffenyi
;favors done         you finished a puzzle room by hand: resume
;favors abort        end the run
```

Start anywhere within walking range of the Crossing. You need unabsorbed experience: with nothing learning, the script refuses.

## The run

1. **An orb you already carry comes first.** With one in hand or in a container, the script finishes that orb instead of praying for another.
2. **The grotto** (Siergelde Stone Grotto, map 1420): KNEEL, PRAY three times, SAY a neutral Immortal, STAND, GET ORB ON ALTAR.
3. **The puzzles** (GO ARCH, the easier set). Each puzzle ends by teleporting you back to the grotto.
4. **Filling:** RUB MY ORB until "your sacrifice is properly prepared". RUB spends only what the orb needs; HUG would dump the whole pool.
5. **The offer:** PUT MY ORB ON ALTAR at the Crossing's Resurrection Creche (map 5865).

The neutral Immortals: Chadatru, Damaris, Eluned, Everild, Faenella, Glythtide, Hav'roth, Hodierna, Kertigen, Meraud, Tamsine, Truffenyi, Urrem'tier.

## Puzzle rooms it solves

| Room | Solution |
| --- | --- |
| choking plant | OPEN WINDOW until it opens, GO WINDOW |
| empty vase | GET NUTFLOWER, GO PATH |
| empty font | GET JUG, POUR JUG IN FONT, GO STAIR, GO DOOR |
| dirty altar | GET SPONGE, CLEAN ALTAR WITH SPONGE, GO STAIR, GO DOOR |
| unlit candles | GET TINDER, LIGHT CANDLE, GO STAIR, GO DOOR |

- A puzzle that needs a free hand gets one (STOW, SHEATHE or PUT the other item); failing that, the room is left to you.
- A room it does not know (levers, say) is left to you; the script resumes once you are back on the map.
- DROP MY ORB abandons the puzzles: the orb is destroyed and you are teleported out.

## Orb rules

- Carry at most two unfilled orbs; experience fed to a third is wasted.
- An orb left off your person shatters. The script never stows it.

## Caveat

The sponge and tinder rooms come from the wiki and have not been seen in play. Any answer the script does not recognise is echoed as `favors: unrecognized ...`; report it so it can be added.
