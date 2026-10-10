"""Down to the Tasia'zaul's dock in Ratha, the ship to Hara'jaal:  ;harajaal

    ;harajaal          a gold lirum in the purse, then Kretsky at the Uasin Dock: ASK, the password, the ramp
    ;harajaal quest    the first trip: the three first-tier asks before Kretsky (the hedgewizard, Raif, Glath)
    ;stop harajaal     quit at once

What it does
  - Tops the purse up to a gold lirum (1,000 copper) with ;bank when it holds less:
    the guard at the ramp takes it as the bribe.
  - Walks to the upper Uasin Dock (Kretsky's), asks him about Hara'jaal, says the
    password and goes down the ramp to the lower dock.
  - Reads the slate board there and says when the Tasia'zaul is due.
  - quest: first finds each wanderer with ;seek and asks him, his answer echoed.

What stops it: no gold lirum after ;bank, the guard's refusal, a wanderer ;seek
does not find.

Elanthipedia: Hara'jaal access quest, Uasin Dock, Kretsky.
"""

from client.game import money, travel
from client.game.act import ask, said
from client.game.seek import present

_NOTES = """
The Tasia'zaul is the one ship from Ratha to Hara'jaal (Elanthipedia:
Tasia'zaul), boarded from the lower Uasin Dock behind Kretsky
Redthorne and a guard (#515). The wiki's access quest, from the closed
DRSecrets site: on the first tier ASK the Old Drunken Hedgewizard about
rumors, Raif about pirates, Glath about baron and then enclave; then ASK
Kretsky about Hara'jaal, SAY seordbluef, and go up the ramp with a gold
lirum. A character who has made the trip once needs only Kretsky's step.

Captured 2026-10-10 on a circle-200 Moon Mage who had made it before:
the ramp with no coin, before Kretsky — "A guard frowns at you." and
'A guard whispers, "HEH!  Come back when you got hard coin!"'; ASK
KRETSKY ABOUT HARA'JAAL — "Kretsky grins with mischief in his eyes.";
the password — no answer; GO RAMP with a gold lirum — "A guard stops you
with his hand stretched out.  You pass him 1000 lirums and he waves you
down a ramp." onto the lower dock; READ SLATE BOARD — "The Tasia'zaul is
on its way from Hara'jaal.  Expected return time is 15 roisaen past the
Anlas of Anduwen (2 hours 58 minutes)." Back up the ramp is free.

The wanderers' answers are not captured: four ;seek runs over about 80
first-tier rooms met none of them that evening. The quest mode sends
the wiki's asks and echoes what they answer, unread.
"""

KRETSKY_DOCK = 4632  # the upper Uasin Dock; the ramp leads down
BRIBE = 1000  # copper lirums: one gold lirum
PASSWORD = "seordbluef"
WANDERERS = (  # (the ;seek noun, the topics asked in order)
    ("hedgewizard", ("rumors",)),
    ("Raif", ("pirates",)),
    ("Glath", ("baron", "enclave")),
)
SEEK_FROM = 4621  # Cutthroat Alley: a loop of the first tier's streets
SEEK_ROOMS = 30
DOWN = ("waves you down a ramp",)
NO_COIN = ("come back when you got hard coin",)
SLATE = ("Tasia'zaul is",)  # "The Tasia'zaul is on its way from Hara'jaal. ..."


def lirums(s):
    """Copper lirums in the purse, from WEALTH."""
    return money.parse_wealth(ask(s, "wealth"))["carried"].get("Lirums", 0)


def wait_for(s, name):
    while s.is_running(name):
        s.sleep(1)


def gold_lirum(s):
    """A gold lirum on hand, ;bank fetching it when short: True when it is."""
    if lirums(s) >= BRIBE:
        return True
    # keep= is the province's coin, lirums= another province's (#507):
    # one of them is lirums wherever this runs.
    if not s.run("bank", [f"keep={BRIBE}", f"lirums={BRIBE}"]):
        s.echo("harajaal: could not start ;bank — bring a gold lirum by hand")
        return False
    wait_for(s, "bank")
    if lirums(s) >= BRIBE:
        return True
    s.echo(
        f"harajaal: no gold lirum on you after ;bank — the guard wants {BRIBE} lirums"
    )
    return False


def ask_wanderers(s):
    """The first trip's three asks, each wanderer found by ;seek: True
    when every one was found and asked."""
    for noun, topics in WANDERERS:
        if not s.run("seek", [noun, f"rooms={SEEK_ROOMS}", f"from={SEEK_FROM}"]):
            s.echo("harajaal: could not start ;seek")
            return False
        wait_for(s, "seek")
        here = present(
            noun,
            getattr(s.state, "room_objs", "") or "",
            getattr(s.state, "room_players", None) or (),
        )
        if not here:
            s.echo(f"harajaal: no {noun} found on the first tier — try again later")
            return False
        for topic in topics:
            s.echo(
                f"harajaal: {noun} on {topic}: {said(ask(s, f'ask {noun} about {topic}'))}"
            )
    return True


def run(s, options, go):
    """`go(s, room)` walks there (travel.go in the script, a fake in tests)."""
    if options["quest"] and not ask_wanderers(s):
        return "wanderer"
    if not gold_lirum(s):
        return "coin"
    if not go(s, KRETSKY_DOCK):
        return "walk"
    ask(s, "ask kretsky about hara'jaal")
    ask(s, f"say {PASSWORD}")
    answer = ask(s, "go ramp")
    if not any(needle in answer.lower() for needle in DOWN):
        s.echo(f"harajaal: the guard kept you up top: {said(answer, NO_COIN)}")
        return "refused"
    slate = ask(s, "read slate board")
    s.echo(f"harajaal: on the Tasia'zaul's dock — {said(slate, SLATE)}")
    return "down"


def parse_args(args):
    return {"quest": any(str(arg).lower() == "quest" for arg in args)}


def main(s):
    run(
        s,
        parse_args(s.args or []),
        lambda s, room: travel.go(s, room, "Kretsky's dock"),
    )
