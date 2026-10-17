# The Trader's kiosk

A Trader's Prosperity in Absentia (PRIA) spell grows a crystal kiosk that buys tied gem pouches and bundles from other players while its owner is elsewhere, as long as the owner stays logged in. It pays them the item's value plus the owner's markup; the owner takes the purchases out later and sells them to a gem shop or a tannery, where a Trader's bonus pays more than the value.

## Casting

- PRIA, 30 to 100 mana, circle 60, after Stellar Collector. Learned from the Negotiants in the Crossing Traders' Guild.
- Hold the clear tessera when you CAST. It is the kiosk's ledger: lose it and the kiosk's money and purchases are gone.
- The kiosk limit is six per room.
- A cast at 30 mana lasts about an hour, at 44 about 97 roisaen; POWER says how long yours has left. Casting again while it stands refreshes it ("...as the spell pattern is refreshed") rather than growing a second.
- Its look is random per cast: "a ___ crystalline kiosk" with a crystal habit in the blank (heptagonally symmetrical, jaggedly dendritic, fibrous, euhedral, lamellar, stellate, spindly and acicular), kept through a refresh. An altered look (the Iridius plinth, a custom description) stays. Kiosks are named by their place in the room's listing (SECOND KIOSK), never by an adjective, and the order shifts as others cast: find yours by STUDY ("your kiosk").
- RELEASE PRIA ends it at once: "You sense the Prosperity in Absentia spell dissipate." and the kiosk shatters; the reserve and what it bought carry over, as at an expiry.
- When it ends ("...shatters into evaporating mist.") nothing is lost: the reserve and what it bought stay on the tessera and appear in your next kiosk. The markup starts at 0% again.
- It buys while you are in another room: at +60%, beside two kiosks at 55%, it took eight sales in its first half hour with its owner away. But QUIT and it shatters at once ("...shatters and evaporates into iridescent mist."), the spell left on you ("You sense the Prosperity in Absentia spell upon you"). It does not come back at login: cast again for a new kiosk, the ledger intact.

## The owner's verbs

STUDY your kiosk to list them, with what it has bought and holds. Hold the tessera for anything that moves money.

| Verb | Does |
|---|---|
| PULL / PUSH | markup up / down 5%, from −10% to +80% |
| POKE | puts every Kronar you carry into its reserve (up to 1,000 platinum); asks you to repeat it within 10 seconds |
| TOUCH | takes the whole reserve back into your purse; asks you to repeat it within 10 seconds |
| RUB | switches TAP between pouches and bundles |
| TAP | hands you what it bought as one crystalline pouch or bundle (up to 500 platinum of value) |

From any room, ASK MY TESSERA ABOUT REPORT (tessera held, 6 s roundtime) gives the same figures and where the kiosk stands.

The kiosk works in Kronars in every province.

## Selling to a kiosk

- A pouch's value is its APPRAISE total ("worth a total of about 512921 Kronars"): a kiosk at 55% quoted 795,027, that times 1.55 to the copper.
- Hold the tied pouch or bundle and GIVE KIOSK (SECOND KIOSK, ...). The first GIVE quotes, "...will purchase the pouch for ... based on the markup of 80%."; the same GIVE within 10 seconds sells. Naming the item (GIVE POUCH TO KIOSK) is refused.
- STUDY any kiosk to see its markup; a Trader also sees its owner. No one but the owner sees its reserve, but the first GIVE's quote is the lesser of the price and the reserve, so an item worth more reads it.
- A kiosk short of coin buys part of the item: it pays its whole reserve and hands the item back, still tied, worth exactly the part it did not pay for. Under 1 gold left, it refuses.
- The reserve can change between the quote and the sale when someone else sells first.
- A kiosk never buys a crystalline pouch or bundle another kiosk made, nor an untied one ("isn't tied").
- A full sale hands the pouch back empty ("Retrieving your now empty ..."), a spare for the next gems.
- Lich's `sell-loot` sells to kiosks (`sell_loot_trader`), and the beta `kiosk.lic` keeps one cast and funded; both are dr-scripts work.

## ;kiosk

`;kiosk` keeps yours standing from its room (the profile's `kiosk_room`, Grisgonda's by default), a pass every five minutes:

- PRIA at 30 mana with the tessera held, refreshed with 2 roisaen left (a refresh throws away what is left). A logout shatters the kiosk but leaves the spell up, so after a login it casts again.
- The markup PULLed or PUSHed to `markup=` (55).
- The other kiosks' markups STUDYed every 15 minutes and said when one moves; the price stays `markup=`.
- `;kiosk cutthroat`: when a kiosk at the same markup lists ahead of yours, yours is RELEASEd, grown again first in the room and PULLed back up; not under half a mana bar, nor twice in 15 minutes.
- The reserve topped up to `reserve=` (100 platinum) through `;bank keep=` and POKE once it falls under `floor=` (50).
- Pouches and bundles TAPped once the kiosk holds `tap=` (20 platinum) of them, and sold with Finesse up, the pay banked at once; never while Trading is mind-locked.
- Finesse at the most mana it takes: DISCERN's estimate the first time, 3% lower after each strain warning, and the level that took is kept for the next cast.

`;kiosk status` reads the tessera's report from anywhere; `;kiosk return` ends the run and leaves the kiosk up. The one caveat: POKE puts in every Kronar you carry, so the top-up only ever runs after `;bank`.

## The money

The kiosk stores value, not cost: what it pays ÷ (1 + markup). TAP hands it out (RUB first for bundles); pouches sell at a gem shop, bundles at a tannery, each for the stored value times the Trader's bonus: capped at 50%, plus a tenth of the circle while Finesse is up, give or take 10%, never more than 60% (Elanthipedia: Trader gem selling bonus). Without Finesse a pouch fetched +41%; with Finesse at 72 mana a bundle fetched +60%, the cap, and at the minimum +49%: the bonus follows Finesse's mana. It is not always the cap: a pouch of 1.9 platinum fetched +53% with Finesse at 74. Cast Finesse before the first appraisal: the buyer's figure for an item is fixed, and asking again gets the same number. The gem shop keeps the gems and hands back the empty pouch; the tannery hands back the rope.

| Markup | Seller gets | Owner's margin, resale at 1.5× (no Finesse) | at 1.6× (Finesse) |
|---|---|---|---|
| −10% | 0.9 × value | +67% | +78% |
| 0% | 1.0 × value | +50% | +60% |
| +40% | 1.4 × value | +7% | +14% |
| +60% | 1.6 × value | −6% | break-even |
| +80% | 1.8 × value | −17% | −11% |

## Which kiosk a seller picks

A seller running dr-scripts' `sell-loot` STUDYs every kiosk and sells to the highest markup; on a tie, to the kiosk listed first in the room. When that one runs out of coin it moves to the next.

- A newly grown kiosk is listed first; a refreshed one keeps its place.
- So a Trader who keeps his kiosk up and funded, growing it again each time it ends, always beats the kiosks at the same markup by position alone.
- Measured at 55% beside such a kiosk: listed first, ours took all 11 sales in 39 minutes; listed second after the other was grown again, 1 of the next 4.
- To take first place, end your kiosk (RELEASE PRIA) and grow a new one; it lasts until another kiosk is grown.
- A kiosk at the same markup but listed behind gets only what the first cannot pay for: while the first is out of coin, its owner is offline, or in the seconds before it is grown again.
- One step above the rest takes every sale while its reserve lasts. At +60% that is break-even with Finesse (the 1.6× cap); each 5% below 60 is about 3% margin, but only on the sales it wins.

## Training

Sales to the kiosk teach the owner nothing. Reselling what it bought does, at the buyer's quote (ASK ... TO APPRAISE) rather than the SELL, and not in proportion to its worth: at rank 767 a 72-platinum pouch at the gem shop took Trading from clear to 18/34, a 25-platinum bundle at the tannery from 2 to 17/34. Casting the kiosk trains Utility, Finesse Augmentation.

## The dataset

`uv run python tools/kiosk_backfill.py` reads the game logs into three history.db tables; a rerun adds only what is new.

| Table | One row per |
|---|---|
| `kiosk_sales` | sale seen at any kiosk in the room: kiosk, owner when known, seller, pouch or bundle |
| `kiosk_readings` | STUDY: markup, and for your own kiosk the reserve and what it stores |
| `kiosk_resales` | TAP and its sale: stored value, quote, pay, Finesse and its mana, Trading before and after |

A sale's amount is not in the log: the reserve's fall between two readings is what the sellers were paid.
