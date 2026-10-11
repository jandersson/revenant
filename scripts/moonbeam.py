"""Focus a moonbeam here, and teleport back to it from afar:  ;moonbeam

    ;moonbeam              PERCEIVE MOONS, then Focus Moonbeam here on the moon with the most time left
    ;moonbeam teleport     back to the beam: its moon up with time left, the beam seen by Distant Gaze, then Teleport
    ;moonbeam show         the beam on record and the moons now
    ;moonbeam release      RELEASE MOONBEAM on the beam's moon, and forget it
    ;moonbeam mana=60      the mana for the beam or the teleport (DISCERN's most by default)
    ;stop moonbeam         quit at once

What it does
  - A beam goes on the moon up with the most minutes left: it lasts no longer than its moon.
  - The beam's room and moon are kept for `teleport`, across relaunches.
  - Teleport goes only to a beam whose moon is up with a few minutes to spare and that
    Distant Gaze still shows; then the stun on arrival is waited out.

What stops it: no moon up with time for a beam, a beam's moon that is down or setting,
a beam Distant Gaze does not show, outdoors refused, an answer it does not know.

The model and its wordings are client/game/moonbeam.py's (Elanthipedia: Focus Moonbeam,
Teleport, Distant Gaze; dr-scripts' gate.lic checks the moon the same way).
"""

import time

from client.game import buffs, moonbeam, probe
from client.game.act import ask, said, unknown
from client.game.mapdb import MapDB
from client.game.walker import locate

_NOTES = """
Built for #522 from the hand captures of 2026-10-10 (a circle-200 Moon
Mage: `prepare fm 10`, `cast xibar` on Varlet's Run; `prepare teleport
10` and `cast xibar` ten rooms away). A Teleport to a moon that is down
disintegrates, or past circle 100 sets the mage in the Astral Plane; to
a lapsed beam it is "usually fatal" — so PERCEIVE MOONS and Distant Gaze
both stand before every Teleport, and nothing here guesses. The mana is
DISCERN's most unless named: a longer-lived beam, and a Teleport with
the reach of the island crossings (79-83 mana for 8-9 zones, the wiki).
"""

PREPARE_SECONDS = 30  # a pattern's forming, at most, before CAST
READY = "fully prepared"
SPELLS = {  # PREPARE's word, DISCERN's name
    "beam": ("fm", "focus moonbeam"),
    "gaze": ("dg", "distant gaze"),
    "teleport": ("teleport", "teleport"),
}


def parse_args(words):
    options = {"verb": "focus", "mana": 0}
    for word in words or []:
        key, sep, value = str(word).lower().partition("=")
        if sep and key == "mana" and value.isdigit():
            options["mana"] = int(value)
        elif key in ("teleport", "show", "release"):
            options["verb"] = key
    return options


def character(s):
    return getattr(getattr(s, "state", None), "name", None) or ""


def read_moons(s):
    """PERCEIVE MOONS read: {moon: entry}; {} said when the answer named
    no moon."""
    s.waitrt()
    answer = ask(s, "perceive moons")
    moons = moonbeam.parse_moons(answer)
    if not moons:
        unknown(s, "moonbeam", "PERCEIVE MOONS", answer)
    return moons


def mana_for(s, options, which):
    """The mana named, else DISCERN's most for the spell; 0 (the minimum)
    when DISCERN gives no estimate."""
    if options["mana"]:
        return options["mana"]
    limit = buffs.mana_limit(buffs.discern(s, SPELLS[which][1], buffs.BuffState(), ask))
    return limit[1] if limit else 0


def cast_at(s, which, mana, moon):
    """PREPARE the spell (with `mana`), wait for the pattern, CAST at the
    moon: the cast's answer, or None said when the PREPARE was refused."""
    s.waitrt()
    word = SPELLS[which][0]
    prepared = ask(s, f"prepare {word} {mana}" if mana else f"prepare {word}")
    if buffs.classify(prepared, buffs.PREPARE_OUTCOMES) in ("failed", "blocked"):
        s.echo(
            f"moonbeam: PREPARE {word.upper()} answered {said(prepared)!r} — stopping"
        )
        return None
    if READY not in prepared:
        probe.collect(s, PREPARE_SECONDS, until=READY)
    s.waitrt()
    return ask(s, f"cast {moon}")


def focus(s, options, db):
    moons = read_moons(s)
    moon = moonbeam.best_moon(moons)
    if moon is None:
        sky = ", ".join(moonbeam.says(m, e) for m, e in sorted(moons.items()))
        s.echo(f"moonbeam: no moon up with time for a beam — {sky or 'none read'}")
        return False
    mana = mana_for(s, options, "beam")
    answer = cast_at(s, "beam", mana, moon)
    if answer is None:
        return False
    if moonbeam.FOCUSED not in answer.lower():
        unknown(s, "moonbeam", "CAST (Focus Moonbeam)", answer)
        return False
    title = str(getattr(s.state, "room_title", "") or "")
    moonbeam.record(
        character(s),
        {
            "moon": moon,
            "room": locate(db, s.state),
            "title": title,
            "mana": mana,
            "at": time.time(),
        },
    )
    s.echo(
        f"moonbeam: a {moon.title()} beam here, {title}, with {mana or 'minimum'} "
        f"mana — {moonbeam.says(moon, moons[moon])}; ;moonbeam teleport comes back"
    )
    return True


def teleport(s, options):
    name = character(s)
    beam = moonbeam.load(name)
    if not beam:
        s.echo("moonbeam: no beam on record — ;moonbeam focuses one where you stand")
        return False
    moon = beam["moon"]
    entry = read_moons(s).get(moon)
    left = moonbeam.minutes_left(entry)
    if not entry or not entry.get("up"):
        s.echo(
            f"moonbeam: {moon.title()} is down — its beam went with it, and a "
            "Teleport on a moon that is down is death; not cast"
        )
        moonbeam.clear(name)
        return False
    if left is None or left < moonbeam.TELEPORT_MARGIN:
        s.echo(
            f"moonbeam: {moonbeam.says(moon, entry)} — too close to its setting "
            "to teleport on; not cast"
        )
        return False
    seen = cast_at(s, "gaze", 0, moon)
    if seen is None:
        return False
    if f"{moonbeam.GAZED} {moon.title()} moonbeam" not in seen:
        s.echo(
            f"moonbeam: Distant Gaze does not show the {moon.title()} beam "
            f"({said(seen)!r}) — gone; not teleporting"
        )
        moonbeam.clear(name)
        return False
    mana = mana_for(s, options, "teleport")
    if not mana:
        # Reach is the mana's: a guess too low is a failure nobody has captured.
        s.echo(
            "moonbeam: DISCERN gave Teleport no mana estimate — ;moonbeam teleport "
            "mana=N (the wiki: 5-43 on the mainland by zones, 79-83 island to mainland)"
        )
        return False
    answer = cast_at(s, "teleport", mana, moon)
    if answer is None:
        return False
    if moonbeam.TELEPORTED not in answer:
        unknown(s, "moonbeam", "CAST (Teleport)", answer)
        return False
    buffs.wait_stun(s)  # "You are stunned!" on arrival
    s.waitrt()
    s.echo(
        f"moonbeam: teleported with {mana or 'minimum'} mana — "
        f"{getattr(s.state, 'room_title', '') or beam.get('title')}"
    )
    return True


def show(s):
    beam = moonbeam.load(character(s))
    moons = read_moons(s)
    if beam:
        minutes = int((time.time() - beam.get("at", time.time())) / 60)
        s.echo(
            f"moonbeam: a {beam['moon'].title()} beam at {beam.get('title')} "
            f"(map {beam.get('room')}), {beam.get('mana') or 'minimum'} mana, "
            f"focused {minutes} minutes ago"
        )
    else:
        s.echo("moonbeam: no beam on record")
    for moon in moonbeam.MOONS:
        if moon in moons:
            s.echo(f"moonbeam: {moonbeam.says(moon, moons[moon])}")


def release(s):
    name = character(s)
    beam = moonbeam.load(name)
    if not beam:
        s.echo("moonbeam: no beam on record")
        return
    answer = ask(s, f"release moonbeam {beam['moon']}")
    s.echo(f"moonbeam: RELEASE MOONBEAM answered {said(answer)!r}")
    moonbeam.clear(name)


def run(s, options, db):
    verb = options["verb"]
    if verb == "teleport":
        return teleport(s, options)
    if verb == "show":
        return show(s)
    if verb == "release":
        return release(s)
    return focus(s, options, db)


def main(s):
    run(s, parse_args(s.args), MapDB.load())
