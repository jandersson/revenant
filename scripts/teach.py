"""Teach a skill to another character and keep the class open:  ;teach

    ;teach scholarship to cecil    TEACH the skill to that student, offer it again whenever they come back
    ;teach scholarship open        TEACH ... OPEN — a class anyone may LISTEN to
    ;teach return                  (typed while it runs) STOP TEACHING and end

A class is TEACH <skill> TO <student> on the teacher's side — "You
begin to lecture Cecil on the proper use of the Scholarship skill." —
and LISTEN TO <teacher> on the student's (`;listen`); both learn until
one of them moves, and the teacher then sees "All of your students
have left, so you stop teaching." (captured 2026-09-22 in the
Paladins' Guild Chambers). An offer no one takes up expires within
minutes — "You stop trying to teach Parry Ability to Cecil." — and a
student joining reads "Cecil begins to listen to you teach the Parry
Ability skill." This script offers the class and stands there: an
expired offer is made again at once, and when the students leave it
waits a moment and offers again, so a student whose `;train` rest
walked away rejoins on return, and it
ends on `return` (STOP TEACHING), on death or hostiles (the shared
escape), or when TEACH says the skill cannot be taught. The teacher's
Teaching skill trains by it; a `;train` task for the teacher is
`{"skills": ["Teaching"], "script": "teach", "args": ["scholarship",
"to", "cecil"], "return_word": "return"}`. Elanthipedia: Teach
command. Stop with:  ;stop teach (the class stays up — STOP TEACHING
yourself), or ;teach return.
"""

from client.game import flight, probe
from client.game.loop import danger, pause, wants_stop
from client.game.probe import classify
from client.game.teaching import (
    OFFER_EXPIRED,
    STUDENT_JOINED,
    STUDENTS_LEFT,
    TEACH_OUTCOMES,
    parse_teach_args,
    teach_command,
)

COLLECT_SECONDS = 2
TAIL_SECONDS = 1
POLL = 5  # seconds between looks at the flags
REOFFER_AFTER = 20  # seconds after the students left before the next offer
MAX_REOFFERS = 200  # the fuse under an evening of rests


def ask(s, command):
    return probe.ask(s, command, COLLECT_SECONDS, TAIL_SECONDS).lower()


def offer(s, options):
    """TEACH once; "teaching" when the class is up (or was already),
    else the failure named."""
    answer = ask(s, teach_command(options["skill"], options["student"]))
    outcome = classify(answer, TEACH_OUTCOMES)
    if outcome in ("teaching", "already"):
        return "teaching"
    first = (answer.strip().splitlines() or ["(silence)"])[0]
    if outcome is None:
        s.echo(f"teach: TEACH answered {first!r} — please report it")
        return "unknown"
    s.echo(f"teach: {first}")
    return outcome


def run(s, options):
    if not options["skill"]:
        s.echo(
            "teach: which skill? ;teach <skill> to <student>, or ;teach <skill> open"
        )
        return
    if offer(s, options) != "teaching":
        s.echo("teach: no class — stopping")
        return
    who = options["student"] or "anyone"
    s.echo(f"teach: teaching {options['skill']} to {who}")
    s.flag("students left", *STUDENTS_LEFT)
    s.flag("offer expired", *OFFER_EXPIRED)
    s.flag("student joined", *STUDENT_JOINED)
    offers = 1
    try:
        while True:
            if not pause(s, POLL):
                why = danger(s)
                if why:
                    ask(s, "stop teaching")
                    s.echo(f"teach: {why} — stopping")
                    if "hostiles" in why:
                        flight.react(s, "teach")
                    return
                if wants_stop(s):
                    break
                break
            if s.flagged("student joined"):
                s.echo("teach: a student joined the class")
            expired = s.flagged("offer expired")
            if s.flagged("students left") or expired:
                why = "the offer expired untaken" if expired else "the students left"
                wait = 0 if expired else REOFFER_AFTER
                s.echo(
                    f"teach: {why} — offering again" + (f" in {wait} s" if wait else "")
                )
                if wait and not pause(s, wait):
                    break
                if offer(s, options) != "teaching":
                    s.echo("teach: the class could not be offered again — stopping")
                    return
                offers += 1
                if offers > MAX_REOFFERS:
                    s.echo("teach: offered enough for one evening — stopping")
                    return
    finally:
        s.unflag("students left")
        s.unflag("offer expired")
        s.unflag("student joined")
    ask(s, "stop teaching")
    s.echo(f"teach: stopping as asked ({offers} offer(s))")


def main(s):
    run(s, parse_teach_args(s.args or []))
