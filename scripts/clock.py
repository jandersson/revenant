"""Sync the Elanthian clock against the game:  ;clock

The ntpdate of Elanthia: sends TIME, compares the answer to the
computed calendar (client/eltime.py), and stores the correction in
~/.revenant/settings.json (eltime_offset_seconds) for the GUI's clocks
dock — unless TIME's day-phase word ("and it is dusk") contradicts the
computed hour, in which case the offset is refused and reported, since a
parse that drifts the clock is worse than none; then OBSERVE MOONS to
anchor the three moons' phases the same
way (eltime_moons). Echoes the date and the drift. ;clock resyncs
every six hours; ;clock once syncs a single time and exits.

;clock watch sends nothing at all: it listens for the lines the game
prints AT a boundary — "The sun rises ...", "The sun sinks below the
horizon ...", "Katamba slowly rises above the horizon." — and uses
them. A sun line is a calibration point to the minute: the offset is
corrected when the computed clock is more than 90 seconds out, and
confirmed otherwise. A moon rise or set pins that moon's orbit
(eltime_moon_rises), so ;clock moons can say "Xibar: down, rises in
40m" and the clocks dock can mark each moon up or down. Model and
captures: docs/eltime.md.

Moon observation needs the sky — indoors it is skipped with a note —
and costs a few seconds of roundtime. Calibration binds to the
server's own clock (every prompt states it), so a drifting local
clock cannot skew the calendar.
"""

import time

from client import eltime, settings

INTERVAL = 6 * 3600  # seconds between syncs
COLLECT_SECONDS = 4  # how long to gather each command's response


def game_now(s):
    """The server's clock when the state knows it — every prompt
    states it, so after an answer it stamps that answer — falling back
    to the local clock (#102). Calibrating against it makes the stored
    offset a pure server-epoch mapping, immune to local drift."""
    server_time = getattr(getattr(s, "state", None), "server_time", None)
    return server_time or time.time()


def collect(s, seconds):
    """Main-stream text for a window after a command — TIME and OBSERVE
    answer in multi-line blocks with no end marker."""
    pieces = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        line = s.get(timeout=0.5)
        if line is not None:
            pieces.append(line)
    return "\n".join(pieces)


def sync_calendar(s):
    s.put("time")
    parsed = eltime.parse_time_output(collect(s, COLLECT_SECONDS))
    # After the collect, the prompt that came with the answer has
    # stamped state.server_time — the instant the answer describes.
    captured_at = game_now(s)
    if parsed is None:
        s.echo("clock: no TIME answer parsed — is the game answering?")
        return
    previous = settings.setting("eltime_offset_seconds") or 0
    offset = round(eltime.calibrate(parsed, captured_at))
    et = eltime.elanthian_now(captured_at, offset)
    # TIME also says which part of the day it is; a computed hour that
    # contradicts it means the parse went wrong (#101 drifted the clock
    # two game hours), so the offset is refused, not stored (#103).
    hour = et.hour + et.minute / 60
    if eltime.phase_agrees(parsed.get("phase"), hour) is False:
        s.echo(
            f"clock: TIME says it is {parsed['phase']} but the computed hour "
            f"is {et.hour:02d}:{et.minute:02d} — offset {offset:+d}s NOT stored; "
            "the TIME parse is suspect, please report this answer"
        )
        return
    settings.save_settings({"eltime_offset_seconds": offset})
    _, date_line = eltime.describe(et)
    s.echo(
        f"clock: {date_line}, {et.anlas_name} — "
        f"offset {offset:+d}s ({offset - previous:+d}s since last sync)"
    )


def sync_moons(s):
    s.put("observe moons")
    text = collect(s, COLLECT_SECONDS)
    captured_at = game_now(s)
    if "hard to do while inside" in text:
        s.echo("clock: moons skipped — can't see the sky from indoors")
        return
    phases = eltime.parse_observe_output(text)
    if not phases:
        s.echo("clock: no moons visible to sync")
        return
    anchors = dict(settings.setting("eltime_moons") or {})
    anchors.update(eltime.calibrate_moons(phases, captured_at))
    settings.save_settings({"eltime_moons": anchors})
    s.echo(
        "clock: moons synced — "
        + ", ".join(f"{moon} {eltime.PHASES[index]}" for moon, index in phases.items())
    )


DRIFT_TOLERANCE = 90  # real seconds; the sun lines repeat to within ~2 min


def hear_boundary(s, line, now=None):
    """One main-stream line, acted on when it is a boundary: a sun line
    corrects or confirms the offset, a moon line re-anchors that orbit.
    Returns what was echoed, or None for an ordinary line."""
    now = game_now(s) if now is None else now
    if boundary := eltime.sun_boundary(line):
        name, hour = boundary
        offset = settings.setting("eltime_offset_seconds") or 0
        drift = eltime.drift_seconds(eltime.fractional_hour(now, offset), hour)
        if abs(drift) > DRIFT_TOLERANCE:
            settings.save_settings({"eltime_offset_seconds": offset - drift})
            note = f"clock: {name} says the clock ran {drift:+d}s — offset now {offset - drift:+d}s"
        else:
            note = f"clock: {name} confirms the calibration ({drift:+d}s)"
        s.echo(note)
        return note
    if event := eltime.moon_event(line):
        moon, kind = event
        rise = now if kind == "rise" else eltime.rise_from_set(moon, now)
        anchors = dict(settings.setting("eltime_moon_rises") or {})
        anchors[moon] = round(rise)
        settings.save_settings({"eltime_moon_rises": anchors})
        note = f"clock: {moon.capitalize()} {kind} pinned — {eltime.describe_moon_position(moon, now, rise)}"
        s.echo(note)
        return note
    return None


def watch(s):
    s.echo("clock: watching for sun and moon boundaries — ;stop clock to end")
    while True:
        line = s.get(timeout=5)
        if line is not None:
            hear_boundary(s, line)


def report_moons(s):
    anchors = dict(settings.setting("eltime_moon_rises") or {})
    now = game_now(s)
    for moon in eltime.MOON_NAMES:
        s.echo(
            f"clock: {moon.capitalize()}: "
            f"{eltime.describe_moon_position(moon, now, anchors.get(moon))}"
        )


def main(s):
    if s.args and s.args[0] == "watch":
        watch(s)
        return
    if s.args and s.args[0] == "moons":
        report_moons(s)
        return
    once = bool(s.args) and s.args[0] == "once"
    while True:
        sync_calendar(s)
        sync_moons(s)
        if once:
            return
        s.sleep(INTERVAL)
