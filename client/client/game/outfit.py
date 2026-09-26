"""The essentials a new character is outfitted with, as data (#341).

Each entry is one thing a character should wear or carry, the way to
tell it is already there, and the errand that buys it: the shop's
community-map room, the BUY and WEAR commands, the price and currency,
and the profile keys to set once it is worn. `;outfit` reads the
INVENTORY worn list, buys what is missing and puts it on.

The first entry is the worn skinning knife. SKIN wants one hand free,
and a held knife fills it ("You must have one hand free to skin." —
Sable's hunt fetched one into the hand the weapon left, failed, stowed
it and skinned with the sword each kill, 2026-09-26); a worn one is
used where it sits, "as long as you have one free hand" (Elanthipedia:
Skinning), and any worn knife gives the skinning bonus of a "skinning
knife" (Elanthipedia: Skinning knife). dr-scripts' new-character.lic
buys a new character's knife at the same shop.
Tobb's Smithy at Knife Clan sells a wrist-worn one for 500 Kronars
(Elanthipedia: Tobb's Smithy); Lanival's was bought there — "You
decide to purchase the knife, and pay the sales clerk 500 Kronars.",
"The sales clerk hands you your skinning knife.", "You attach a small
steel skinning knife with a leather-wrapped hilt to your wrist."
(captured 2026-09-13). Bought, the profile's `skin_knife` is cleared
so ;hunt stops fetching a held one.
"""

ESSENTIALS = (
    {
        "name": "worn skinning knife",
        # Any worn knife gives the bonus: a worn-list line naming one is it.
        "worn_words": ("knife",),
        "shop": 6206,
        "shop_name": "Tobb's Smithy at Knife Clan",
        "buy": "buy skinning knife",
        "wear": "wear my skinning knife",
        "price": 500,
        "currency": "Kronars",
        "profile": {"skin_knife": ""},
    },
)

# BUY's answers: the purchase, and what refuses it (the shop wordings
# every catalog shop shares; the purse ones are the wiki's Buy command).
BOUGHT = ("you decide to purchase",)
BUY_REFUSALS = (
    "don't have enough",
    "can't afford",
    "cannot afford",
    "what were you referring",
    "buy what",
    "not for sale",
)
# WEAR's success: "You attach ... to your wrist." (captured) and the
# common put-on shapes.
WORN = ("you attach", "you put", "you slide", "you strap", "you sling", "you wear")


def worn_items(answer):
    """The worn list INVENTORY prints — the indented lines after "Your
    worn items are:" — lower-cased; [] when the answer has none."""
    items = []
    listing = False
    for line in str(answer or "").splitlines():
        if "your worn items are" in line.lower():
            listing = True
            continue
        if listing:
            if line.startswith((" ", "\t")) and line.strip():
                items.append(line.strip().lower())
            elif line.strip():
                break
    return items


def has(essential, worn):
    """True when a worn line names the essential."""
    return any(word in line for line in worn for word in essential["worn_words"])


def missing(worn, essentials=ESSENTIALS):
    """The essentials the worn list lacks, in catalog order."""
    return [essential for essential in essentials if not has(essential, worn)]


def bought(answer):
    lowered = str(answer or "").lower()
    return any(line in lowered for line in BOUGHT) and not any(
        line in lowered for line in BUY_REFUSALS
    )


def put_on(answer):
    return any(line in str(answer or "").lower() for line in WORN)


def parse_args(words):
    """`check` lists what is missing and buys nothing; `stay` stays at
    the last shop rather than walking back."""
    lowered = {str(word).lower() for word in words or []}
    return {"check": "check" in lowered, "back": "stay" not in lowered}
