# First Aid from anatomy charts

`;compendium` trains First Aid and Scholarship from the anatomy charts in a compendium until both mind-lock. First Aid is paid per chart at clarity, Scholarship per study, so it studies the charts at your level while First Aid has room and the slow ones in the time between.

```
;compendium            study until both mind-lock, then hold for the drain
;compendium until=30   stop at that mindstate
;compendium once       end at the lock, or when every chart is resting
```

- A chart is at your level when its wiki rank is at or under your Scholarship: a few studies to clarity. Past it, the game answers "having a difficult time comprehending the advanced text" and the chart is slow (a Boggle, wiki 90, took 39 studies at Scholarship 77), but every study still teaches Scholarship. Only "almost impossible" skips a chart.
- At-level charts go first, hardest first; a chart that proves slow is set aside while one is open. The slow ones fill the time when the others rest or First Aid is locked.
- A chart at clarity rests twenty minutes. Several at-level charts keep First Aid moving.
- The chart table is dr-scripts' (`client/game/anatomy_data.py`, regenerated with `uv run python tools/anatomy_tables.py`); its numbers are half the wiki's up to the race charts.
- The profile's `compendium` names the book when its noun is not "compendium".

## Charts and where to buy them

| Shop | Sells | Coin |
|---|---|---|
| Emmiline's Cottage, Willow Walk, the Crossing (Empaths only) | compendiums (10 charts), the Silver Leucro and the race charts | Kronars |
| Advanced Anatomy, Fang Cove (Estate Holders; through a meeting portal, `premium` in the profile) | compendiums (20 charts), the Rat up to the Cougar, and harder ones | Dokoras |

A shop's BUY takes the item by one word: the creature's noun ("buy eel chart"), the first word of a two-word name ("buy blood chart"), an ordinal for the second of a pair ("buy second blood chart"). Look at the display first.
