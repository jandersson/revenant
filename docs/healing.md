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

## The hospital: Shard's NPC healer Quentin, and `;heal npc`

Every province has a hospital with an NPC Empath who heals for the
province's coins, part by part ([Elanthipedia:
Hospital](https://elanthipedia.play.net/Hospital)): Shard's is
[Quentin](https://elanthipedia.play.net/Quentin) in Quentin's
Healerium off Yavash Circle (map room 8908, tagged `npchealer`),
Riverhaven's Fraethis (the Riverhaven Hospital's tending chamber,
8720; "won't heal eye wounds"), Leth Deriel's Arthianna for Zoluren;
the Crossing has none. It is what heals nerve damage and internal
scars — the "twitching" of five backfires, which no herb a shop sells
touches (2026-09-21) — and the wiki warns that a herb eaten first
makes the Empath ignore that part's remaining wounds.

Captured 2026-09-19 (#218), a circle-5 Paladin driven by hand:

```
The healer Quentin looks towards you, and you pull away.
[Change your overall DEMEANOR or your DEMEANOR towards EMPATHS if you wish the healer Quentin to heal you.]
You now regard empaths with a friendly demeanor.
Quentin glances oddly at you and then touches your nervous system, snickering all the while.  After a moment it feels better.
[72 Dokoras are taken from you.]
Roundtime:  2 seconds.
```

The price is per part and by the wound (chest 54, neck 30, a leg 24,
the nerves 72 that day); minor abrasions and scars were left. `;heal
npc` is that visit: INFO first (an empty purse stops it before the
walk — `;bank` exchanges foreign coins into the province's at the
money-changer), the walk to the nearest `npchealer` room (Knife
Clan's retired Dokt excluded), DEMEANOR FRIENDLY EMPATH — left
friendly afterwards, the operator's choice — LIE DOWN, the touches
until twenty quiet seconds, STAND, HEALTH, and what was taken and
what is left said. The hospital page's own lines ("Elys approaches
you and touches you.", "Your nervous system tingles for a moment,
then suddenly feels a bit better.") are in the table for the other
towns' healers, uncaptured.

## Empaths

Player Empaths heal by touch and take the wounds onto themselves; the
Crossing guild is where to find one, and asking works. Captured
2026-09-11 in `[Empaths' Guild, Courtyard Garden]` (map room 5713, uid
14002 — a `;go2 5713` from anywhere in town), a circle-1 Paladin with
minor abrasions from the felled tree, names replaced with the
synthetic cast:

```
You say, "Hey folks - anyone able to remove the bruises from my rat hunting attempts."
Sable whispers, "need healing?"
Sable rests her hand on your arm with a soft smile.
You feel a warmth radiate from Sable's touch.
You have a brief sensation that leaves your wounds tingling.
Your external head, neck, right arm, left arm, right leg, left leg, chest, abdomen and back wounds feel fully healed.
Your internal head, neck, right arm, left arm, right leg, left leg, chest, abdomen and back wounds feel fully healed.
Your external head, neck, right arm, left arm, right leg, left leg, chest, abdomen and back scars feel fully healed.
Your internal head, neck, right arm, left arm, right leg, left leg, chest, abdomen and back scars feel fully healed.
Sable whispers, "what was once yours is now mine"
Gushing geysers of bright blue and white energy spring up from under Sable's feet, enwreathing her body with a cool glow.  Her body twists and shakes as flesh and bone regrow immediately, leaving Sable completely healed.
```

One sentence aloud in the courtyard, an offer by whisper within a
minute, a touch, and four lines that say every area and every kind
is clean — the Empath's "what was once yours is now mine" is literal:
the wounds went to her, and she cleared them off herself a moment
later. Free, complete, internal damage and scars included, which no
herb or cookie matches for a circle 1. The four "feel fully healed"
lines are the signal a script would watch for; the guild courtyard is
where to send `;go2` for it. Not data, not automated: an Empath is a
person, and the ask is a sentence, not a command.

## The healing script: ;heal

`;heal` (scripts/heal.py, #198) reads HEALTH through `wounds.py`, points
a bleeder at `;tend`, and for every wound at the floor or worse
(`insignificant` by default, `floor=minor` to leave scratches to close
on their own) asks `remedies(area, kind)` for the first herb the town
sells, else the table's first — one EAT per herb per run, since a herb
heals its part over time. `;heal list` prints the plan with each
herb's shop; `;heal buy` reads INFO for the coins carried, WITHDRAWs the
shortfall against the wiki's prices at the nearest teller, walks to the
herbalist (map tag `herbalist`: Mauriga's Botanicals, room 8259), and
ORDERs then OFFERs each missing herb the way HELP SHOPS describes a
catalog merchant (Grek's knife, 2026-09-14: "I can let that go for a
mere 375 kronars." / "Well done! Here, take your knife."), then eats
it. [Mauriga's Botanicals](https://elanthipedia.play.net/Mauriga's_Botanicals)
lists jadice, plovik, nilos, hulnik, nemoih, georin and sufil at 812 to
875 Kronars and yelith, ithor, muljin, junliar, blocil and riolur at
937 to 1000 (2026-09-14); the [Alchemy Society](https://elanthipedia.play.net/Alchemy_Society_(Crossing))
sells dried herbs in 25-piece lots for crafting, not for eating.
Captured on the first buy, 2026-09-14: the quote "That is a very wise
selection.  I can give the root to you for 875 kronars.", the sale
"Mauriga smiles as she hands you your purchase.", with both hands full
"Mauriga notices that your hands are full, and places it on the
counter instead." — the first run bought three herbs before eating
any, and two landed on the counter out of EAT's reach, so the script
now orders by the herb's stem ("plovik leaf" on her catalog refused
"plovik leaves"), eats each on the spot and stows the rest — out of
stock "I'm so sorry to disappoint you, but I don't have that reagent
in stock." (plovik and aloe that day), and EAT's "You eat a portion
of a nemoih root." What an eaten herb says as it heals is still to
capture; an answer outside the tables is echoed as unrecognized.

The first plan, from the badger-hunting Paladin's HEALTH of
2026-09-14 (minor abrasions to the head and left arm, external and
internal minor damage to the left leg, tiny scratches to the chest,
minor twitching): jadice flower for both limbs, nemoih root for the
head, plovik leaves for the chest, yelith root for the leg's internal
damage, and aloe leaves for the skin — the last one no shop in town
stocks, which the script says.
