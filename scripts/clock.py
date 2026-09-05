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


def main(s):
    once = bool(s.args) and s.args[0] == "once"
    while True:
        sync_calendar(s)
        sync_moons(s)
        if once:
            return
        s.sleep(INTERVAL)
