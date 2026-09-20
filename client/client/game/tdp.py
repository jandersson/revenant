"""Spending Time Development Points on stats — the model behind ;tdp.

A stat rises one point per TRAIN (typed twice, in that stat's training
room) at a TDP cost the game states before it spends: the stat's own
command (AGILITY, STRENGTH, ...) quotes the next point and TDP PROJECT
<stat> <goal> quotes the whole climb. This module reads those answers
and INFO, turns ;tdp's words into goals, and knows the cost formula
Elanthipedia gives (Attributes: 3 x value, plus the race's modifier x
value // 2, integer math; 15 x value from 100 up) — the game's quote
is what the script trusts, the formula is what the tests and the
estimate rest on. Captured 2026-09-12 on a Dwarf at Agility 8: "It
will cost you 28 TDPs to raise your Agility from 8 to 9" (3 x 8 + 1 x
4: the Dwarf's +1 on Agility) and "It will cost you 132 TDPs to reach
12 points in Agility" (28 + 31 + 35 + 38). Model: docs/training.md.
"""

import re

STATS = (
    "Strength",
    "Reflex",
    "Agility",
    "Charisma",
    "Discipline",
    "Wisdom",
    "Intelligence",
    "Stamina",
)
_STAT_LINE = re.compile(rf"({'|'.join(STATS)})\s*:\s*(\d+)")
_TDPS_INFO = re.compile(r"TDPs\s*:\s*(\d+)")
_RACE = re.compile(r"Race:\s*([A-Za-z' ]+?)\s\s")
_GUILD = re.compile(r"Guild:\s*([A-Za-z ]+?)\s*$", re.MULTILINE)
# Where a guild's points go when the plan says "auto" (#230): tiers of
# (stats, floor) taken in order — the lowest stat of a tier that is
# still under its floor is the next point — and past the tiers the
# lowest of all eight, so growth stays balanced. The Paladin's tiers
# are Elanthipedia's Paladin new player guide: Strength and Stamina
# equally to about 15 (the plate's burden), then Reflex, Agility and
# Discipline to about 15 (evasion, parry, shields), then the rest. A
# guild without a table goes straight to the balanced rule.
GUILD_TIERS = {
    "Paladin": (
        (("Strength", "Stamina"), 15),
        (("Reflex", "Agility", "Discipline"), 15),
    ),
}
# Every race's starting stats since January 2008, when rolls went away
# (Elanthipedia: Attributes). DR3 assumes them for every character
# when it recalculates TDPs, so a stat below its start is worth raising
# first: the point comes back twice over at the next recalculation
# (captured 2026-09-12 on a DR1-era Dwarf, #165).
STARTING_STATS = {
    "Dwarf": (10, 8, 8, 10, 12, 10, 10, 12),
    "Elf": (8, 12, 12, 12, 8, 10, 10, 8),
    "Elothean": (8, 12, 10, 10, 10, 12, 12, 6),
    "Gnome": (4, 14, 12, 10, 10, 10, 14, 6),
    "Gor'Tog": (16, 8, 10, 10, 10, 6, 6, 14),
    "Halfling": (6, 12, 14, 10, 8, 8, 10, 12),
    "Human": (10, 10, 10, 10, 10, 10, 10, 10),
    "Kaldar": (12, 10, 10, 12, 10, 8, 8, 10),
    "Prydaen": (10, 14, 10, 12, 8, 6, 10, 10),
    "Rakash": (10, 12, 8, 10, 12, 8, 6, 14),
    "S'Kra Mur": (12, 12, 10, 10, 10, 8, 8, 10),
}
# "You have 347 TDPs." (TDP) / "You currently have 347 TDPs available." (AGILITY)
_TDPS_HAVE = re.compile(r"You (?:currently )?have (-?\d+) TDPs")
# "Your base Agility is eight (8)."
_BASE = re.compile(r"Your base (\w+) is [A-Za-z\- ]+\((\d+)\)")
# "It will cost you 28 TDPs to raise your Agility from 8 to 9."
_NEXT = re.compile(r"cost you (\d+) TDPs to raise your (\w+) from (\d+) to (\d+)")
# "It will cost you 132 TDPs to reach 12 points in Agility."
_PROJECT = re.compile(r"cost you (\d+) TDPs to reach (\d+) points in (\w+)")

# TRAIN's answers, captured 2026-09-12 (Crossing's Academy of Agility,
# a Dwarf at 8 with 347 TDPs). The first TRAIN quotes and asks for a
# second: "You consult with the teachers and together decide that it
# will take 28 moon cycles until you successfully train your agility
# to 9 ranks.  There is also a fee of 56 Kronars to complete this
# training. / That would leave you 319 time development points
# afterward.  If this is OK, you will need to STUDY once again to get
# your new rank." The second spends: "(You now have 319 time
# development points.) / The trainer notes how young you are and that
# you should keep some coins to help you get equipped.  So, the cost
# of 56 Kronars is added to your Provincial debt. / (Your debt has
# increased by 56 Kronars.) / After what seems an astonishing amount
# of time, you find you have completed your training in agility. /
# Your attempts to train are praiseworthy, but you must find both the
# proper place and the proper teacher first." — that last line rides
# along after a completed training, so "done" must be read before
# "refused"; on its own (the wrong room) it is the refusal. The fee is
# 2 Kronars per TDP and goes on the provincial debt when the character
# carries no coins.
TRAIN_OUTCOMES = (
    ("done", ("completed your training",)),
    ("refused", ("must find both the proper place", "cannot", "unable", "not enough")),
    ("confirm", ("once again", "again", "confirm")),
)


def stat_name(word):
    """The stat a word names, by unambiguous prefix ("agi" → "Agility"),
    or None."""
    word = (word or "").strip().lower()
    if not word:
        return None
    matches = [stat for stat in STATS if stat.lower().startswith(word)]
    return matches[0] if len(matches) == 1 else None


_CIRCLE = re.compile(r"Circle:\s*(\d+)")


def parse_info(text):
    """{"stats": {name: value}, "tdps": int or None, "race": str or None,
    "guild": str or None, "circle": int or None} from INFO."""
    tdps = _TDPS_INFO.search(text)
    race = _RACE.search(text)
    guild = _GUILD.search(text)
    circle = _CIRCLE.search(text)
    return {
        "stats": {name: int(value) for name, value in _STAT_LINE.findall(text)},
        "tdps": int(tdps.group(1)) if tdps else None,
        "race": race.group(1).strip() if race else None,
        "guild": guild.group(1).strip() if guild else None,
        "circle": int(circle.group(1)) if circle else None,
    }


def plan_goals(entries, stats):
    """[(stat, target)] from a training plan's `tdp` list — "stamina 30",
    "strength 30" — or None for "auto" (the guild's tiers, next_stat).
    Raises ValueError for an entry that names no stat or no number."""
    goals = []
    for entry in entries or []:
        words = str(entry).split()
        if len(words) == 1 and words[0].lower() == "auto":
            return None
        if len(words) != 2 or not words[1].isdigit():
            raise ValueError(f"{entry!r}: write it as '<stat> <target>' or 'auto'")
        stat = stat_name(words[0])
        if stat is None:
            raise ValueError(f"{entry!r}: {words[0]!r} names no stat")
        goals.append((stat, int(words[1])))
    return goals


def next_stat(stats, goals=None, guild=None):
    """The stat the next point goes to, as (name, value): with `goals`
    ([(stat, target)]) the first still under its target, None once all
    are met; with goals None (auto) the guild's tiers (GUILD_TIERS),
    then the lowest of all eight (#230)."""
    if goals is not None:
        for stat, target in goals:
            value = stats.get(stat)
            if value is not None and value < target:
                return stat, value
        return None
    for names, floor in GUILD_TIERS.get(guild or "", ()):
        under = [
            (stats[name], index, name)
            for index, name in enumerate(names)
            if name in stats and stats[name] < floor
        ]
        if under:
            value, _, name = min(under)  # ties go to the tier's listed order
            return name, value
    known = [
        (stats[name], index, name) for index, name in enumerate(STATS) if name in stats
    ]
    if not known:
        return None
    value, _, name = min(known)
    return name, value
    known = [(stats[name], name) for name in STATS if name in stats]
    if not known:
        return None
    value, name = min(known)
    return name, value


def below_start(race, stats):
    """{stat: racial start} for every stat under the race's starting
    value — the points DR3's recalculation hands back; {} for an
    unknown race."""
    starts = STARTING_STATS.get(race or "")
    if not starts:
        return {}
    return {
        stat: start
        for stat, start in zip(STATS, starts)
        if stats.get(stat) is not None and stats[stat] < start
    }


def parse_tdps(text):
    """The TDPs on hand from a TDP or a stat command's answer, or None."""
    match = _TDPS_HAVE.search(text)
    return int(match.group(1)) if match else None


def parse_stat_answer(text):
    """What a stat's own command says: {"stat", "value", "next_cost",
    "tdps"}, each None when its line is missing."""
    base = _BASE.search(text)
    nxt = _NEXT.search(text)
    stat = base.group(1) if base else (nxt.group(2) if nxt else None)
    value = int(base.group(2)) if base else (int(nxt.group(3)) if nxt else None)
    return {
        "stat": stat_name(stat) if stat else None,
        "value": value,
        "next_cost": int(nxt.group(1)) if nxt else None,
        "tdps": parse_tdps(text),
    }


def parse_project(text):
    """{"stat", "goal", "cost"} from TDP PROJECT's answer, or None."""
    match = _PROJECT.search(text)
    if not match:
        return None
    return {
        "stat": stat_name(match.group(3)),
        "goal": int(match.group(2)),
        "cost": int(match.group(1)),
    }


def point_cost(value, modifier=0):
    """TDPs to raise a stat from `value` to `value + 1`, per the wiki's
    formula: 3 x value below 100 (15 x value from 100), plus the race's
    modifier x value // 2 (a bonus is negative). The 100+ multiplier is
    the wiki's word; only values under 100 are captured."""
    scale = 3 if value < 100 else 15
    return scale * value + modifier * (value // 2)


def cost_to(value, goal, modifier=0):
    """TDPs to raise a stat from `value` up to `goal`."""
    return sum(point_cost(step, modifier) for step in range(value, goal))


def modifier_from(value, next_cost):
    """The race's modifier on a stat, read off the game's quoted next
    cost (28 at Agility 8 → +1); 0 when the value is too small to tell."""
    half = value // 2
    if not half:
        return 0
    return (next_cost - point_cost(value)) // half


def parse_goals(words, stats):
    """[(stat, goal)] from ;tdp's words: "agility 12" (to 12),
    "strength +2" (two points), a bare "agility" (one point). Raises
    ValueError for a word that names no stat, a stat INFO gave no
    value for, a goal not above the stat's value, or a goal with no
    stat before it."""

    def value_of(stat):
        value = stats.get(stat)
        if value is None:
            raise ValueError(f"{stat}: INFO gave no value for it")
        return value

    goals, current = [], None
    for word in words:
        stat = stat_name(word)
        if stat is not None:
            if current is not None:
                goals.append((current, value_of(current) + 1))
            current = stat
            continue
        if current is None:
            raise ValueError(f"{word!r}: name a stat first")
        value = value_of(current)
        if word.startswith("+"):
            goal = value + int(word[1:] or 1)
        elif word.isdigit():
            goal = int(word)
        else:
            raise ValueError(f"{word!r}: neither a stat nor a number")
        if goal <= value:
            raise ValueError(f"{current} is already {value}; the goal must be higher")
        goals.append((current, goal))
        current = None
    if current is not None:
        goals.append((current, value_of(current) + 1))
    return goals


def affordable(value, goal, next_cost, tdps):
    """How many of the points from value to goal the TDPs on hand buy,
    stepping the wiki's formula from the game's quoted next cost."""
    modifier = modifier_from(value, next_cost)
    bought, left = 0, tdps
    for step in range(value, goal):
        cost = next_cost if step == value else point_cost(step, modifier)
        if cost > left:
            break
        left -= cost
        bought += 1
    return bought
