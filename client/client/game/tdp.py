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
# "You have 347 TDPs." (TDP) / "You currently have 347 TDPs available." (AGILITY)
_TDPS_HAVE = re.compile(r"You (?:currently )?have (-?\d+) TDPs")
# "Your base Agility is eight (8)."
_BASE = re.compile(r"Your base (\w+) is [A-Za-z\- ]+\((\d+)\)")
# "It will cost you 28 TDPs to raise your Agility from 8 to 9."
_NEXT = re.compile(r"cost you (\d+) TDPs to raise your (\w+) from (\d+) to (\d+)")
# "It will cost you 132 TDPs to reach 12 points in Agility."
_PROJECT = re.compile(r"cost you (\d+) TDPs to reach (\d+) points in (\w+)")

# TRAIN's answers — assumptions until captured (the wiki quotes none):
# a first TRAIN states the cost and wants a second; the second raises
# the stat; anything else is a refusal. Order matters: a refusal that
# mentions the cost must not read as a prompt to confirm. The script
# trusts none of them alone: it re-asks the stat after every pair.
TRAIN_OUTCOMES = (
    ("refused", ("cannot", "can't", "unable", "not enough", "no training", "must be")),
    ("done", ("increase", "raise", "you feel", "trained", "improve")),
    ("confirm", ("again", "confirm", "cost", "would you like")),
)


def stat_name(word):
    """The stat a word names, by unambiguous prefix ("agi" → "Agility"),
    or None."""
    word = (word or "").strip().lower()
    if not word:
        return None
    matches = [stat for stat in STATS if stat.lower().startswith(word)]
    return matches[0] if len(matches) == 1 else None


def parse_info(text):
    """{"stats": {name: value}, "tdps": int or None} from INFO."""
    tdps = _TDPS_INFO.search(text)
    return {
        "stats": {name: int(value) for name, value in _STAT_LINE.findall(text)},
        "tdps": int(tdps.group(1)) if tdps else None,
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
