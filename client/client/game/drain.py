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

What a bucket is worth — the ranks the pool will turn into — is the
other half (docs/experience.md, "What a mindstate is worth", #332). A rank
n costs 200 + n bits (Elanthipedia: Experience, reverse-engineered
from CONVERT), and the page gives the pool's size in bits: 15000,
12750 or 10500 * r / (r + 900) + 1000, 850 or 700 by placement, times
(1000 + i + d) / 1000 for Intelligence's and Discipline's scores. A
bucket would be a 34th of that. It is not: 375 clean drain runs of
the same Paladin (ranks 10-100, Intelligence and Discipline 8-16,
no REXP, drained at the fitted speed so nothing flowed in) hold
BUCKET_K / rank of it, K = 8.35 — 7.7 primary, 8.0 secondary, 8.5
tertiary, and 8.3-8.6 in every band of twenty ranks — with a median
error of 4.5 %. At rank 50 that is 3.2 % of a rank per bucket for a
primary skill, 2.4 % tertiary; at rank 90, 1.8 %. The same K held
below rank 10, down to rank 2.7 (eleven runs, K 7.0-8.4): a bucket
there is worth several of the page's. Under RANK_FLOOR (3), the lowest
rank measured, the rank is taken as 3. Three early runs read K 22-26
— about 3 x 8.35 — from the Paladin's first days, before ;xp flagged
REXP, which triples what a drain buys (REXP_FACTOR). Above rank 100 it
is not established: two other characters' runs at ranks 145-485 with
Intelligence 30-65 read K 30-41, about three times the fit again, and
their REXP use at the time is unknown.
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


# What a bucket is worth (fitted 2026-09-26, see the module docstring).
BUCKET_K = 8.35  # a bucket holds K / rank of the page's pool / 34
RANK_FLOOR = 3  # the lowest rank the fit reached; lower ranks count as it
BUCKETS = 34
REXP_FACTOR = 3  # rested experience: each drained bit is worth three
_POOL_BASE = {
    "primary": (15000, 1000),
    "secondary": (12750, 850),
    "tertiary": (10500, 700),
}


def rank_cost(rank):
    """Bits from rank to rank + 1 (Elanthipedia: Experience)."""
    return 200 + int(rank)


def intelligence_score(value):
    """Elanthipedia: (x-10)*60/10 under 30, ((x-30)*30+1200)/10 to 60,
    ((x-60)*15+2100)/10 above."""
    if value < 30:
        return (value - 10) * 60 / 10
    if value <= 60:
        return ((value - 30) * 30 + 1200) / 10
    return ((value - 60) * 15 + 2100) / 10


def discipline_score(value):
    """Elanthipedia: (x-10)*20/10 under 30, ((x-30)*10+400)/10 to 60,
    ((x-60)*5+700)/10 above."""
    if value < 30:
        return (value - 10) * 20 / 10
    if value <= 60:
        return ((value - 30) * 10 + 400) / 10
    return ((value - 60) * 5 + 700) / 10


def pool_bits(tier, rank, intelligence=10, discipline=10):
    """The page's pool size in bits for a skill of that placement."""
    scale, floor = _POOL_BASE[tier]
    base = scale * rank / (rank + 900) + floor
    stats = 1000 + intelligence_score(intelligence) + discipline_score(discipline)
    return stats / 1000 * base


def bits_per_bucket(tier, rank, intelligence=10, discipline=10):
    """Bits one mindstate bucket turns into: the page's pool / 34,
    scaled by BUCKET_K / rank, the rank no lower than RANK_FLOOR."""
    scale = BUCKET_K / max(float(rank), RANK_FLOOR)
    return scale * pool_bits(tier, rank, intelligence, discipline) / BUCKETS


def ranks_from(
    mindstate,
    skill,
    rank,
    percent,
    guild,
    intelligence=10,
    discipline=10,
    rexp=False,
):
    """The rank and percent the skill should stand at once `mindstate`
    buckets have drained, as (rank, percent); None when the placement
    is unknown. Bucket by bucket, so a rank crossed on the way costs
    its own 200 + n and the next bucket is worth the new rank's share."""
    tier = placement(skill, guild)
    if tier is None:
        return None
    rank, into = int(rank), rank_cost(rank) * int(percent) / 100
    for _ in range(max(0, int(mindstate))):
        into += bits_per_bucket(tier, rank, intelligence, discipline) * (
            REXP_FACTOR if rexp else 1
        )
        while into >= rank_cost(rank):
            into -= rank_cost(rank)
            rank += 1
    return rank, int(into / rank_cost(rank) * 100)
