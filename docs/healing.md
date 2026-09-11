# The healing model the scripts assume

What heals what, for a low-circle character without an Empath at
hand: bleeding is stopped by tending, wounds and scars are treated by
herbs matched to the body area and the kind of damage, and the herbs
are bought in shops or, at Knife Clan, eaten as cookies. `;tend` does
the first today; `client/game/herbs.py` holds the second as data for
the healing script still to be written; this file records the sources
and what was captured, so it is not relearned. The wound vocabulary
itself is [wounds.md](wounds.md).

## Bleeding first

A bleeder kills a low-circle character faster than any wound. TEND
binds external bleeders and trains First Aid; internal bleeders take
hundreds of ranks and are left for magic. `;tend` watches the bleeding
indicator and tends worst-first (rates and responses from Lich's
healing commons and [Elanthipedia: Damage](https://elanthipedia.play.net/Damage);
model in [wounds.md](wounds.md)).

## Herbs: area and kind

Elanthipedia's [Healing herbs](https://elanthipedia.play.net/Healing_herbs)
table gives each herb a body part, a location (internal, external, or
both) and a type (wounds or scars). `tools/herb_tables.py` generates
`client/game/herbs_data.py` from it, and `client/game/herbs.py` maps
the wiki's parts onto HEALTH's areas: "all" treats every area,
"torso" the chest, abdomen and back, "face" the head, "skinnerve" the
skin. `remedies(area, kind)` answers a parsed wound — `remedies("limb",
"external")` lists the herbs for fresh external wounds to a limb —
specific-part herbs first, cure-alls after. `sources(herb)` and
`sources_in(herb, "Crossing")` are the wiki's shop table: in the
Crossing, the Alchemy Society stocks most herb products, Mauriga's
Botanicals a few (hulnik, muljin, sufil, yelith, blocil), Fenwyrthie's
Curio Shop cebi and hisan.

Eating a herb heals the matching damage over time; the wiki's
foraging columns (ranks, season, time, terrain) ride along in the
data for a forager script someday. Costs are not in the table.

## Knife Clan's kitchen: the retired NPC healer

Dokt, once the NPC healer for Knife Clan, no longer heals. Captured
2026-09-11 in `[Knife Clan, Healer's Kitchen]` (map room 6218, tagged
`dokt` and `npchealer`; the room "smells of baked goods with fading
notes of an antiseptic"):

```
Dokt grunts.  "I'm done with poultices and salves.  Herbs still work, though.  Just...in a nicer shape now."
Dokt rocks from heel to toe and back while stretching his limbs and grimacing.  He looks around and says, "Healing is in my blood.  I can't give it up, but it was well beyond time leave the scalpels to others."
A glass counter reads:
"These remedy-infused cookies are ideal for your external wounds."
On the glass counter you see a crisped jadice cookie, a spiced bark hulnik cookie, a honey-glazed nilos cookie and a toasted plovik cookie.
```

Elanthipedia's [Dokt](https://elanthipedia.play.net/Dokt) page agrees:
"the former NPC healer for Knife Clan", "now a baker selling herbal
remedy cookies". The four cookies are the four herbs for external
wounds of the limbs (jadice), back (hulnik), abdomen (nilos) and
chest (plovik) — `herbs.KITCHEN_COOKIES` — and nothing on the counter
treats the head, the neck, scars or internal damage. What is not
captured: the price of a cookie and the purchase grammar (LOOK shows
"nothing unusual"; a bare ORDER answers "Order what?"; the character
had no coins to try further). The lesson for the walker's sitting,
scratched Paladin: minor abrasions close on their own, and a cookie
run is a Kronar problem before it is a healing one.

## Empaths

Player Empaths heal by touch and take the wounds onto themselves; the
Crossing guild is where to find one. Not data, not automated, and the
only answer to internal damage a low-circle character has besides
time.

## What a healing script would do

Read HEALTH through `wounds.py`, tend any bleeder, then for each
wound at or above a floor ask `remedies(area, kind)`, check the
inventory snapshot for one in the sack, and eat it or say which shop
sells it. Everything it needs is in the two modules; the script and
the eat-and-wait wordings are the part still to capture.
