"""Spend Time Development Points on stats, one confirmed point at a time:  ;tdp

    ;tdp                         INFO: the eight stats and the TDPs on hand (spends nothing)
    ;tdp agility                 what the next point costs, from the stat's own command
    ;tdp agility 12              ... and what reaching 12 costs (TDP PROJECT)
    ;tdp train agility           walk to the Agility trainer, TRAIN one point, walk back
    ;tdp train agility 12 strength +2 [stay]
                                 several goals in order: to 12, then two points of Strength;
                                 `stay` stays in the last training room
    ;tdp plan [N]                up to N points (3) where the training plan's `tdp` list says — the stat targets, or the guild's tiers on `auto` — leaving `tdp_reserve` unspent; the ;train task

A stat rises one point per TRAIN typed twice in that stat's training
room (the map tags it: `agility`, `strength`, ...), at the cost the
game quotes first (Elanthipedia: Attributes, Time Development Points,
Train command). Each point also costs a fee of 2 Kronars per TDP;
a character carrying no coins has it added to the provincial debt
(captured 2026-09-12: 28 TDPs and 56 Kronars for Agility 8 → 9), and
the script echoes that line. A stat below its race's starting value
is flagged: DR3 recalculates TDPs assuming every character started at
the racial values, so such a point comes back twice over at the next
recalculation (a DR1 character's rolled stats, #165) — train those
first. `plan` is the ;train task's form (the operator, 2026-09-20: a task
in the plan's order, not only the rest's spending, "then I could
structure the train loop with it"): the character's training plan
names where the TDPs go (`tdp`: stat targets, or `auto` for the
guild's tiers — client/game/tdp.py's GUILD_TIERS) and what to keep
(`tdp_reserve`), and each point is INFO, the next stat, its cost
against the points past the reserve, then one confirmed TRAIN pair
at its trainer; a `{"script": "tdp", "args": ["plan"]}` task runs
it once a cycle wherever the plan puts it. It never trusts the TRAIN wording alone:
it asks the stat's own command (AGILITY, STRENGTH, ...) for the value,
the next point's cost and the TDPs before every point, buys only what
the TDPs cover, and asks again after the pair — a value that did not
rise stops the run with the answers echoed, so an unexpected wording
costs at most one point. It stops on death or a refusal, and walks
back to where it started unless told to stay. Stop with:  ;stop tdp
"""

import re

from client.game import probe
from client.game.tdp import (
    STATS,
    TRAIN_OUTCOMES,
    below_start,
    next_stat,
    parse_goals,
    parse_info,
    parse_project,
    parse_stat_answer,
    plan_goals,
    point_cost,
    stat_name,
)
from client.game.mapdb import MapDB
from client.game.walker import locate, walk

COLLECT_SECONDS = 3  # a command's answer, opening window
# The lines of a TRAIN pair worth showing when it worked: the fee
# (2 Kronars per TDP) and where it went — a coinless character's goes
# on the provincial debt (captured 2026-09-12).
_NOTE = re.compile(r"fee of|debt", re.IGNORECASE)
TAIL_SECONDS = 1.5  # ... and the tail past its roundtime


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def echo_lines(s, text):
    for line in text.splitlines():
        if line.strip():
            s.echo(f"tdp: {line.strip()}")


def show_info(s):
    """INFO's stats and TDPs, one line each; the parsed dict."""
    info = parse_info(ask(s, "info"))
    if not info["stats"]:
        s.echo("tdp: INFO gave no stats — try again in a moment")
        return info
    width = max(len(name) for name in STATS)
    for name in STATS:
        value = info["stats"].get(name)
        s.echo(f"tdp: {name:<{width}} {value if value is not None else '?':>4}")
    s.echo(f"tdp: TDPs {info['tdps'] if info['tdps'] is not None else '?'}")
    under = below_start(info.get("race"), info["stats"])
    if under:
        listed = ", ".join(
            f"{stat} {info['stats'][stat]} (start {start})"
            for stat, start in under.items()
        )
        s.echo(
            f"tdp: below the {info['race']} starting stats: {listed} — DR3 hands "
            "those points back twice over; train them first"
        )
    return info


def quote(s, stat, goal=None):
    """What the next point costs and, with a goal, the whole climb —
    the game's own figures. Returns the stat answer's dict."""
    answer = parse_stat_answer(ask(s, stat.lower()))
    if answer["next_cost"] is None:
        s.echo(f"tdp: {stat.upper()} gave no cost — is that a stat command here?")
        return answer
    s.echo(
        f"tdp: {stat} {answer['value']} → {answer['value'] + 1} costs "
        f"{answer['next_cost']} TDPs; you have {answer['tdps']}"
    )
    if goal is not None and goal > (answer["value"] or 0) + 1:
        project = parse_project(ask(s, f"tdp project {stat.lower()} {goal}"))
        if project is None:
            s.echo("tdp: TDP PROJECT gave no figure")
        else:
            s.echo(f"tdp: {stat} to {goal} costs {project['cost']} TDPs in all")
    return answer


def train_one(s, stat, before):
    """TRAIN twice, then the stat's command: (rose, answer). The two
    TRAIN answers are echoed when the value did not rise."""
    first = ask(s, "train")
    outcome = probe.classify(first, TRAIN_OUTCOMES)
    second = ""
    if outcome != "refused":
        second = ask(s, "train")
    after = parse_stat_answer(ask(s, stat.lower()))
    rose = after["value"] is not None and after["value"] > before
    if rose:
        echo_lines(
            s, "\n".join(line for line in second.splitlines() if _NOTE.search(line))
        )
    else:
        echo_lines(s, first + "\n" + second)
    return rose, after


def train_stat(s, stat, goal, mapdb, walk_fn):
    """Walk to the stat's trainer and buy points up to the goal or the
    TDPs. True when every point up to the goal was bought."""
    rooms = mapdb.rooms_tagged(stat.lower())
    if not rooms:
        s.echo(f"tdp: the map has no room tagged {stat.lower()!r}")
        return False
    if not walk_fn(s, mapdb, set(rooms), describe=f"the {stat} trainer"):
        s.echo(f"tdp: could not reach the {stat} trainer — stopping")
        return False
    answer = quote(s, stat)
    while answer["value"] is not None and answer["value"] < goal:
        if s.dead:
            s.echo("tdp: you are dead — stopping")
            return False
        cost, have = answer["next_cost"], answer["tdps"]
        if cost is None or have is None:
            s.echo(f"tdp: no cost or TDP figure for {stat} — stopping")
            return False
        if cost > have:
            s.echo(f"tdp: the next point costs {cost} and you have {have} — stopping")
            return False
        rose, answer = train_one(s, stat, answer["value"])
        if not rose:
            s.echo(f"tdp: {stat} did not rise — stopping before another point")
            return False
        s.echo(f"tdp: {stat} is now {answer['value']}, TDPs {answer['tdps']}")
    return answer["value"] is not None and answer["value"] >= goal


PLAN_POINTS = 3  # points one `;tdp plan` buys unless told otherwise


def plan_points(s, mapdb, walk_fn, points=PLAN_POINTS):
    """Up to `points` points where the character's training plan says:
    INFO for the stats, the points and the guild, the plan's goals or
    the guild's tiers for the stat, the wiki's cost against the points
    past `tdp_reserve`, then one confirmed point at its trainer; the
    walk back at the end. The points bought."""
    from client.game.training import load_plan

    plan = load_plan(getattr(s.state, "name", None) or "")
    entries = plan.get("tdp") or []
    if not entries:
        s.echo("tdp: the training plan's tdp list is empty — nothing to spend on")
        return 0
    reserve = int(plan.get("tdp_reserve") or 0)
    start = locate(mapdb, s.state)
    bought = 0
    for _ in range(max(points, 0)):
        info = parse_info(ask(s, "info"))
        if info["tdps"] is None or not info["stats"]:
            s.echo("tdp: INFO gave no TDPs — stopping")
            break
        try:
            goals = plan_goals(entries, info["stats"])
        except ValueError as error:
            s.echo(f"tdp: the plan's tdp list — {error}")
            break
        choice = next_stat(info["stats"], goals, info.get("guild"))
        if choice is None:
            s.echo("tdp: every goal of the plan reached")
            break
        stat, value = choice
        cost = point_cost(value)
        if info["tdps"] - reserve < cost:
            s.echo(
                f"tdp: {stat} {value} → {value + 1} costs about {cost} and "
                f"{info['tdps']} on hand keeps {reserve} — stopping"
            )
            break
        if not train_stat(s, stat, value + 1, mapdb, walk_fn):
            break
        bought += 1
    if start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("tdp: could not walk back — you are at the trainer")
    s.echo(f"tdp: {bought} point(s) bought by the plan")
    return bought


def run(s, words, mapdb=None, walk_fn=walk):
    """The verb: show, quote, train, or plan."""
    if not words:
        show_info(s)
        return
    if words[0].lower() == "plan":
        if mapdb is None:
            s.echo("tdp: training needs the map — none loaded")
            return
        points = int(words[1]) if len(words) > 1 and str(words[1]).isdigit() else None
        plan_points(s, mapdb, walk_fn, PLAN_POINTS if points is None else points)
        return
    training = words[0].lower() == "train"
    stay = training and words[-1].lower() == "stay"
    goal_words = words[1 : -1 if stay else None] if training else words
    if training and not goal_words:
        s.echo("usage: ;tdp train <stat> [goal | +n] [<stat> ...] [stay]")
        return
    if not training:
        stat = stat_name(goal_words[0])
        if stat is None:
            s.echo(f"tdp: {goal_words[0]!r} names no stat — one of {', '.join(STATS)}")
            return
        goal = (
            int(goal_words[1])
            if len(goal_words) > 1 and goal_words[1].isdigit()
            else None
        )
        quote(s, stat, goal)
        return
    if mapdb is None:
        s.echo("tdp: training needs the map — none loaded")
        return
    info = show_info(s)
    try:
        goals = parse_goals(goal_words, info["stats"])
    except ValueError as error:
        s.echo(f"tdp: {error}")
        return
    start = locate(mapdb, s.state)
    for stat, goal in goals:
        if not train_stat(s, stat, goal, mapdb, walk_fn):
            break
    else:
        s.echo("tdp: every goal reached")
    if not stay and start is not None and locate(mapdb, s.state) != start:
        if not walk_fn(s, mapdb, {start}, describe="where you started"):
            s.echo("tdp: could not walk back — you are at the trainer")
    show_info(s)


def main(s):
    words = list(s.args)
    if words and words[0].lower() in ("train", "plan"):
        mapdb = MapDB.load()
        run(s, words, mapdb=mapdb)
    else:
        run(s, words)
