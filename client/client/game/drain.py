"""How long a skill's pool takes to drain: mindstate buckets per pulse.

A rest is the time the pools take to convert to ranks, and that time is
predictable. Every 200 seconds each skill pulses: it drops a fixed
number of mindstate buckets, set by its skillset placement, until it
clears. The drop is linear: each bucket from 34 down to 1 lasts as long
as the next. So the minutes from one mindstate to a floor are
(mindstate - floor) / rate pulses. ``;train`` prints that estimate when
a rest starts. The rest still ends on the exp window, not on this
estimate.

The rates were fitted from ;xp's per-minute mindstate rows
(history.db), 519 drain-only runs of a Paladin at Wisdom and Discipline
8-15 and ranks 3-75, between 2026-09-04 and 2026-09-23
(docs/experience.md, "How fast a pool drains"):

- primary 1.14 buckets per pulse (34 to 0 in about 100 min)
- secondary 0.91 (about 125 min)
- tertiary 0.65 (about 175 min)

Placement is the guild's skillset table (Elanthipedia, Skillsets). The
Experience page's low-rank exceptions were each tested against the
data. A tertiary skill under 25 ranks drains like a secondary one, as
the page says. A secondary skill under 50 ranks does not drain like a
primary one: 104 such runs drain at the secondary rate. Rank within a
tier and rested experience moved the rate by less than the noise
(REXP triples the ranks a pulse buys, not the buckets it drains).
The mental stats: Intelligence (and Discipline, mostly) size the pool.
A bucket is a share of the pool and so is a pulse, so a bigger pool
holds more experience per bucket without draining faster in buckets:
Intelligence drops out of a rest's length. Wisdom sizes the pulse.
The data cannot measure it (secondary 0.91 at Wisdom 10, 0.90 at 15),
so the factor is GM Armifer's table on the Experience page (10: 100%,
30: 112%, 60: 121%, 90: 125%, 120: 130%), interpolated and scaled so
Wisdom 15 gives the fitted rates. An assumption, not a measurement. A
Wisdom of None uses the fitted rates as they are. Discipline's share
of the pulse ("10% efficiency") is below what the data can see, and
is left out.
"""

PULSE_SECONDS = 200

# GM Armifer, 12/10/2015 (Elanthipedia, Experience): Wisdom's effect
# on the pulse against a Wisdom of 10. Below 10 the first segment's
# slope is carried down.
WISDOM_EFFECT = ((10, 1.00), (30, 1.12), (60, 1.21), (90, 1.25), (120, 1.30))
FITTED_WISDOM = 15  # the Wisdom the rates were fitted at


def wisdom_factor(wisdom):
    """Wisdom's pulse multiplier against the fitted Wisdom of 15."""
    if wisdom is None:
        return 1.0

    def effect(w):
        points = WISDOM_EFFECT
        if w >= points[-1][0]:
            return points[-1][1]
        if w < points[0][0]:
            (x0, y0), (x1, y1) = points[0], points[1]
        else:
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                if x0 <= w <= x1:
                    break
        return y0 + (y1 - y0) * (w - x0) / (x1 - x0)

    return effect(wisdom) / effect(FITTED_WISDOM)


# Buckets drained per pulse, by the tier a skill drains as (fitted, see
# the module docstring).
BUCKETS_PER_PULSE = {"primary": 1.14, "secondary": 0.91, "tertiary": 0.65}

# Each skill's skillset. The guild-only skills sit in the skillset
# their guild's circle table counts them in (Conviction is a Paladin
# armor requirement, and drains at the primary rate with the armor).
SKILLSETS = {
    "Armor": (
        "Shield Usage",
        "Light Armor",
        "Chain Armor",
        "Brigandine",
        "Plate Armor",
        "Defending",
        "Conviction",
    ),
    "Weapon": (
        "Parry Ability",
        "Small Edged",
        "Large Edged",
        "Twohanded Edged",
        "Small Blunt",
        "Large Blunt",
        "Twohanded Blunt",
        "Slings",
        "Bow",
        "Crossbow",
        "Staves",
        "Polearms",
        "Light Thrown",
        "Heavy Thrown",
        "Brawling",
        "Offhand Weapon",
        "Melee Mastery",
        "Missile Mastery",
        "Expertise",
    ),
    "Magic": (
        "Holy Magic",
        "Lunar Magic",
        "Arcane Magic",
        "Life Magic",
        "Elemental Magic",
        "Inner Fire",
        "Inner Magic",
        "Attunement",
        "Arcana",
        "Targeted Magic",
        "Augmentation",
        "Debilitation",
        "Utility",
        "Warding",
        "Sorcery",
        "Astrology",
        "Summoning",
        "Theurgy",
    ),
    "Survival": (
        "Evasion",
        "Athletics",
        "Perception",
        "Stealth",
        "Locksmithing",
        "Thievery",
        "First Aid",
        "Outdoorsmanship",
        "Skinning",
        "Backstab",
        "Instinct",
        "Thanatology",
    ),
    "Lore": (
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
        "Bardic Lore",
        "Empathy",
        "Trading",
    ),
}
SKILLSET_OF = {
    skill.lower(): name for name, skills in SKILLSETS.items() for skill in skills
}

# Elanthipedia, Skillsets: each guild's placement, in the page's column
# order Armor, Lore, Magic, Survival, Weapon (1 primary, 2 secondary,
# 3 tertiary).
_ORDER = ("Armor", "Lore", "Magic", "Survival", "Weapon")
_TIERS = {
    "Barbarian": (2, 3, 3, 2, 1),
    "Bard": (3, 1, 2, 3, 2),
    "Cleric": (3, 2, 1, 3, 2),
    "Commoner": (2, 2, 2, 2, 2),
    "Empath": (3, 1, 2, 2, 3),
    "Moon Mage": (3, 2, 1, 2, 3),
    "Necromancer": (3, 2, 2, 1, 3),
    "Paladin": (1, 2, 3, 3, 2),
    "Ranger": (2, 3, 3, 1, 2),
    "Thief": (3, 2, 3, 1, 2),
    "Trader": (2, 1, 3, 2, 3),
    "Warrior Mage": (3, 2, 1, 3, 2),
}
PLACEMENT = {guild: dict(zip(_ORDER, tiers)) for guild, tiers in _TIERS.items()}
TIER_NAMES = {1: "primary", 2: "secondary", 3: "tertiary"}
TERTIARY_AS_SECONDARY_BELOW = 25  # ranks; wiki and data agree


def placement(skill, guild):
    """ "primary", "secondary" or "tertiary" for the skill in the guild's
    skillset table, or None for a skill or guild the table lacks."""
    skillset = SKILLSET_OF.get(str(skill).strip().lower())
    tiers = PLACEMENT.get(str(guild or "").strip().title())
    if skillset is None or tiers is None:
        return None
    return TIER_NAMES[tiers[skillset]]


def drain_tier(skill, rank, guild):
    """The tier the skill drains as at this rank: its placement, except
    a tertiary skill under 25 ranks drains as secondary. None when the
    placement is unknown."""
    tier = placement(skill, guild)
    if tier == "tertiary" and rank < TERTIARY_AS_SECONDARY_BELOW:
        return "secondary"
    return tier


def minutes_to(mindstate, floor, skill, rank, guild, wisdom=None):
    """Minutes for the skill to drain from mindstate to floor (0 when it
    is already there), or None when the placement is unknown. A pulse
    lands up to 200 s after any moment, so the true time runs up to
    about three minutes longer."""
    tier = drain_tier(skill, rank, guild)
    if tier is None:
        return None
    buckets = max(0, int(mindstate) - int(floor))
    rate = BUCKETS_PER_PULSE[tier] * wisdom_factor(wisdom)
    return buckets / rate * PULSE_SECONDS / 60


def rest_estimate(experience, skills, floor, guild, wisdom=None):
    """(minutes, skill) for the slowest of the skills to drain to floor,
    from the exp window's {skill: {"rank", "mindstate"}}; skills the
    window lacks are clear. (0, None) when all are at the floor
    already; None when a skill above the floor has no known
    placement."""
    by_name = {
        str(name).strip().lower(): entry
        for name, entry in (experience or {}).items()
        if isinstance(entry, dict) and str(name) != str(name).lower()
    }
    slowest = (0, None)
    for skill in skills:
        entry = by_name.get(skill.strip().lower())
        if not entry:
            continue
        mindstate = int(entry.get("mindstate", 0))
        if mindstate <= floor:
            continue
        minutes = minutes_to(
            mindstate, floor, skill, int(entry.get("rank", 0)), guild, wisdom
        )
        if minutes is None:
            return None
        if minutes > slowest[0]:
            slowest = (minutes, skill)
    return slowest
