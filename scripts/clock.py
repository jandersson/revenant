"""Sync the Elanthian clock against the game:  ;clock

The ntpdate of Elanthia: sends TIME, compares the answer to the
computed calendar (client/eltime.py), and stores the correction in
~/.revenant/settings.json (eltime_offset_seconds) for the GUI's clocks
dock; then OBSERVE MOONS to anchor the three moons' phases the same
way (eltime_moons). Echoes the date and the drift. ;clock resyncs
every six hours; ;clock once syncs a single time and exits.

Moon observation needs the sky — indoors it is skipped with a note —
and costs a few seconds of roundtime.
"""

import time

from client import eltime, settings

INTERVAL = 6 * 3600  # seconds between syncs
COLLECT_SECONDS = 4  # how long to gather each command's response


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
    captured_at = time.time()
    s.put("time")
    parsed = eltime.parse_time_output(collect(s, COLLECT_SECONDS))
    if parsed is None:
        s.echo("clock: no TIME answer parsed — is the game answering?")
        return
    previous = settings.setting("eltime_offset_seconds") or 0
    offset = round(eltime.calibrate(parsed, captured_at))
    settings.save_settings({"eltime_offset_seconds": offset})
    et = eltime.elanthian_now(captured_at, offset)
    _, date_line = eltime.describe(et)
    s.echo(
        f"clock: {date_line}, {et.anlas_name} — "
        f"offset {offset:+d}s ({offset - previous:+d}s since last sync)"
    )


def sync_moons(s):
    captured_at = time.time()
    s.put("observe moons")
    text = collect(s, COLLECT_SECONDS)
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
