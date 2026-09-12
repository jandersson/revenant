"""Read your burden, what the wiki's formula says it means, and pin it:  ;enc

    ;enc                    INFO + ENCUMBRANCE: the level, the weight band it implies for your
                            Strength and Stamina, and the points that would lighten it (logged)
    ;enc log <note>         log a reading with a note ("stowed the greaves")
    ;enc ballast [step=50]  the experiment: at a teller, withdraw coins in steps of that many
                            stones until the burden rises, so the load's true weight is pinned;
                            every step logged, the coins deposited back
    ;enc show               the logged readings

The game shows a burden level, not a weight. Elanthipedia's rule
(Encumbrance): at level L (1 None ... 12 squashed) a character carries
up to 10 x ceil(0.4 x (L + 5) x (Strength + Stamina)) stones, so the
level is a band of weights and every point of either stat widens the
bands. ;enc reads INFO and ENCUMBRANCE and says which band you are in
and how many points would drop you a level — a range, because the
load's place in the band is unknown. `ballast` pins it: coins weigh
0.2 stones each, so withdrawing a known weight until the level rises
brackets the load to one step, and the points needed become exact.
The coins are copper, so the count drawn is the count carried, and
they go back with DEPOSIT step by step; a teller's refusal stops the
run with what was already drawn deposited. The formula is the wiki's
and held its first test (docs/encumbrance.md). Stop with:  ;stop enc
"""

from client.game import probe
from client.game.encumbrance import (
    LEVELS,
    band,
    coins_for,
    level_index,
    open_history,
    parse_level,
    points_to_lighten,
    record,
    rows,
    summarize,
)
from client.game.history import database_path
from client.game.mapdb import MapDB
from client.game.tdp import parse_info
from client.game.walker import walk

COLLECT_SECONDS = 3
TAIL_SECONDS = 1.5
STEP_STONES = 50  # a ballast step: 250 coins
MAX_BALLAST = 600  # stones; 3000 coins is the most a run will draw
WITHDRAW_REFUSALS = (
    "do not seem to have an account",
    "not have enough",
    "cannot",
    "can't",
)


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS)


def reading(s):
    """(strength, stamina, level) from INFO and ENCUMBRANCE."""
    info = parse_info(ask(s, "info"))
    level = parse_level(ask(s, "encumbrance"))
    return info["stats"].get("Strength"), info["stats"].get("Stamina"), level


def explain(s, strength, stamina, level):
    """The band and the points, as lines."""
    if level is None or strength is None or stamina is None:
        s.echo("enc: no reading — INFO or ENCUMBRANCE went unanswered")
        return
    s.echo(f"enc: {level} at Strength {strength} + Stamina {stamina}")
    over, up_to = band(level, strength, stamina)
    s.echo(
        f"enc: by the wiki's formula the load weighs over {over} and up to {up_to} stones"
    )
    points = points_to_lighten(level, strength, stamina)
    if points is None:
        return
    index = level_index(level)
    lighter = LEVELS[index - 2]
    fewest, most = points
    span = f"{fewest}" if fewest == most else f"{fewest} to {most}"
    s.echo(
        f"enc: {span} point(s) of Strength or Stamina would make it {lighter} — "
        "the exact count needs the weight; ;enc ballast pins it. Or shed load: "
        "a piece of armor in hand or in a sack counts in full, worn it counts a "
        "fraction (docs/encumbrance.md)"
    )


def character(s):
    return getattr(s.state, "name", None) or "unknown"


def ballast(s, step, mapdb=None, walk_fn=walk):
    """Withdraw coins step by step until the burden rises, logging each
    step; deposit everything drawn. The load is pinned to one step."""
    strength, stamina, level = reading(s)
    if level is None:
        s.echo("enc: no reading — stopping")
        return
    if mapdb is not None:
        tellers = mapdb.rooms_tagged("bank")
        if tellers and not walk_fn(s, mapdb, set(tellers), describe="the bank teller"):
            s.echo("enc: could not reach a teller — stopping")
            return
    db = open_history(database_path())
    record(db, character(s), strength, stamina, level, 0, "ballast start")
    start = level_index(level)
    drawn, ballast_stones, risen = [], 0, None
    try:
        while ballast_stones < MAX_BALLAST:
            # copper coins: the count drawn is the count carried, and a
            # coin of any metal weighs the same
            count = coins_for(step)
            answer = ask(s, f"withdraw {count} copper")
            if any(needle in answer.lower() for needle in WITHDRAW_REFUSALS):
                s.echo(f"enc: the teller refused — {answer.strip().splitlines()[0]}")
                return
            drawn.append(count)
            ballast_stones += step
            level = parse_level(ask(s, "encumbrance"))
            record(
                db,
                character(s),
                strength,
                stamina,
                level or "?",
                ballast_stones,
                "ballast",
            )
            s.echo(f"enc: +{ballast_stones} stones of coins → {level}")
            if level and level_index(level) > start:
                risen = ballast_stones
                break
        if risen is None:
            s.echo(
                f"enc: {MAX_BALLAST} stones of coins and no change — the band is wider than that"
            )
            return
        up_to = band(LEVELS[start - 1], strength, stamina)[1]
        low, high = up_to - risen, up_to - risen + step
        s.echo(
            f"enc: the load weighs over {low} and up to {high} stones "
            f"(the {LEVELS[start - 1]} band ends at {up_to})"
        )
        for weight in (low + 1, high):
            points = points_to_lighten(LEVELS[start - 1], strength, stamina, weight)
            if points is None:  # starting at None: nothing lighter to reach
                break
            s.echo(
                f"enc: at {weight} stones, {points[0]} point(s) of Strength or Stamina "
                f"would make it {LEVELS[start - 2]}"
            )
        record(
            db,
            character(s),
            strength,
            stamina,
            LEVELS[start - 1],
            0,
            f"pinned {low}-{high} stones",
        )
    finally:
        for count in reversed(drawn):
            ask(s, f"deposit {count} copper")
        if drawn:
            s.echo(f"enc: deposited the {ballast_stones} stones of coins back")
        db.close()


def main(s):
    words = [str(a) for a in (s.args or [])]
    verb = words[0].lower() if words else ""
    if verb == "show":
        db = open_history(database_path())
        entries = rows(db, character=character(s))
        db.close()
        for line in summarize(entries) or ["enc: nothing logged yet"]:
            s.echo(line if line.startswith("enc:") else f"enc: {line}")
        return
    if verb == "ballast":
        step = STEP_STONES
        for word in words[1:]:
            key, sep, value = word.partition("=")
            if sep and key == "step" and value.isdigit():
                step = int(value)
        ballast(s, step, mapdb=MapDB.load())
        return
    note = " ".join(words[1:]) if verb == "log" else ""
    strength, stamina, level = reading(s)
    explain(s, strength, stamina, level)
    if level is not None:
        db = open_history(database_path())
        record(db, character(s), strength, stamina, level, 0, note or "reading")
        db.close()
