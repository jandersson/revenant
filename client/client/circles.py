"""What gates the next circle: Thief requirements computed from ranks.

The guild's circle requirements are a fixed table (Elanthipedia), so
revenant computes the gate list locally from the character sheet the
same way the guildleader does — ``;circle`` (scripts/circle.py) reads
the latest ;sheet snapshot and prints what to train, with have/need
ranks. The table, its evidence, and one known anomaly are recorded in
docs/circles.md; a captured ASK <guildleader> ABOUT CIRCLE validates
the computation gate for gate.

Model: a requirement is either a named skill (Thievery, Stealth, Parry
Ability, Inner Magic) or a slot ("3rd Survival" = your third-best
survival skill). Ranks required to advance TO circle C sum the
per-circle rates across the table's circle bands up to C. Slots are
filled best-first by (rank, percent); Thievery and Stealth are soft
requirements — they also count toward survival slots. Only Thief is
encoded; other guilds are a table away.
"""

# Per-circle rank rates by circle band (Elanthipedia "Thief",
# Circle Requirements). A requirement is ("named", skill) or
# (set, slot-number).
BAND_TOPS = (10, 30, 70, 100, 150)  # the last band is open-ended

THIEF_REQUIREMENTS = {
    ("named", "Thievery"): (2, 3, 3, 4, 4, 10),
    ("named", "Stealth"): (2, 2, 3, 3, 4, 10),
    ("survival", 1): (4, 4, 5, 5, 6, 15),
    ("survival", 2): (4, 4, 4, 5, 6, 15),
    ("survival", 3): (3, 4, 4, 5, 6, 15),
    ("survival", 4): (3, 4, 4, 5, 6, 15),
    ("survival", 5): (3, 4, 4, 4, 5, 13),
    ("survival", 6): (2, 3, 4, 4, 5, 13),
    ("survival", 7): (2, 3, 3, 4, 5, 13),
    ("survival", 8): (1, 2, 2, 3, 3, 8),
    ("named", "Parry Ability"): (1, 2, 2, 3, 3, 8),
    ("weapon", 1): (3, 3, 4, 4, 5, 13),
    ("weapon", 2): (1, 2, 3, 3, 4, 10),
    ("lore", 1): (1, 2, 3, 3, 4, 10),
    ("lore", 2): (1, 2, 2, 3, 3, 8),
    ("lore", 3): (1, 1, 2, 2, 3, 8),
    ("armor", 1): (2, 2, 2, 3, 3, 8),
    ("named", "Inner Magic"): (1, 2, 3, 3, 4, 10),
    ("magic", 1): (1, 2, 2, 3, 3, 10),
    ("magic", 2): (0, 0, 2, 2, 4, 8),
}

# The guildleader phrases magic slots as "Supernatural" for Thieves.
SLOT_WORDS = {
    "survival": "Survival",
    "weapon": "Weapon",
    "lore": "Lore",
    "armor": "Armor",
    "magic": "Supernatural",
}

# Which skills can fill each set's slots. Thievery and Stealth appear
# under survival deliberately (the soft requirement); Parry Ability,
# the Masteries, and Inner Magic are named requirements, never slot
# fillers — docs/circles.md records the assignment assumptions.
SLOT_SKILLS = {
    "survival": (
        "Athletics",
        "Backstab",
        "Evasion",
        "First Aid",
        "Locksmithing",
        "Outdoorsmanship",
        "Perception",
        "Skinning",
        "Stealth",
        "Thievery",
    ),
    "weapon": (
        "Bow",
        "Brawling",
        "Crossbow",
        "Heavy Thrown",
        "Large Blunt",
        "Large Edged",
        "Light Thrown",
        "Offhand Weapon",
        "Polearms",
        "Slings",
        "Small Blunt",
        "Small Edged",
        "Staves",
        "Twohanded Blunt",
        "Twohanded Edged",
    ),
    "lore": (
        "Alchemy",
        "Appraisal",
        "Enchanting",
        "Engineering",
        "Forging",
        "Mechanical Lore",
        "Outfitting",
        "Performance",
        "Scholarship",
        "Tactics",
        "Trading",
    ),
    "armor": ("Light Armor", "Heavy Armor"),
    "magic": ("Augmentation", "Debilitation", "Utility", "Warding"),
}


def required_ranks(rates, circle):
    """Ranks required to hold a circle: the per-circle rate summed
    across bands up to it (matches the table's Cumulative column)."""
    total, floor = 0, 0
    for band, rate in zip(BAND_TOPS + (None,), rates):
        top = circle if band is None else min(circle, band)
        if top > floor:
            total += rate * (top - floor)
            floor = top
    return total


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def gates(ranks, circle, requirements=THIEF_REQUIREMENTS):
    """The unmet requirements for advancing from `circle` to the next.

    ranks: {skill: (rank, percent)} — a ;sheet snapshot's roster.
    Returns [{category, label, skill, have, need}] in table order.
    Slots fill best-first by (rank, percent); equal-rank ties may sit
    in different slots than the game shows, but the same requirements
    come out unmet either way.
    """
    target = circle + 1
    by_set = {}
    for name, rates in SLOT_SKILLS.items():
        trained = [
            (skill, ranks[skill][0], ranks[skill][1])
            for skill in rates
            if skill in ranks
        ]
        trained.sort(key=lambda entry: (-entry[1], -entry[2], entry[0]))
        by_set[name] = trained
    unmet = []
    for key, rates in requirements.items():
        need = required_ranks(rates, target)
        if not need:
            continue
        kind, which = key
        if kind == "named":
            label, skill = which, which
            have = ranks.get(which, (0, 0))[0]
            category = (
                "survival"
                if which in SLOT_SKILLS["survival"]
                else ("weapon" if which == "Parry Ability" else "magic")
            )
        else:
            filled = by_set[kind]
            label = f"{_ordinal(which)} {SLOT_WORDS[kind]}"
            if which <= len(filled):
                skill, have, _ = filled[which - 1]
            else:
                skill, have = None, 0  # nothing trained for this slot yet
            category = kind
        if have < need:
            unmet.append(
                {
                    "category": category,
                    "label": label,
                    "skill": skill,
                    "have": have,
                    "need": need,
                }
            )
    return unmet


def describe(unmet, target):
    """;circle's report: one line per knowledge set, guildleader style,
    with have/need ranks."""
    if not unmet:
        return [f"nothing gates circle {target} — go see your guildleader"]
    lines = [f"gates to circle {target}:"]
    for category in ("armor", "weapon", "magic", "survival", "lore"):
        entries = [gate for gate in unmet if gate["category"] == category]
        if not entries:
            continue
        # Slots first, named requirements after — the guildleader's own
        # order ("1st Weapon (Small Edged), Parry").
        entries.sort(key=lambda gate: gate["label"] == gate["skill"])
        parts = []
        for gate in entries:
            name = gate["label"]
            if gate["skill"] and gate["skill"] != gate["label"]:
                name += f" ({gate['skill']})"
            parts.append(f"{name} {gate['have']}/{gate['need']}")
        lines.append(f"  {category}: " + ", ".join(parts))
    return lines
