"""How ;tend reads wounds and applies bandages — these tests are the manual.

HEALTH-line shapes and tend responses follow lich's healing data (DRCH);
bleed rates per https://elanthipedia.play.net/Damage#Bleeding_Levels.
Only our side is under test — the game is never simulated beyond its
documented answer lines.
"""

import importlib.util
import pathlib

REPO = pathlib.Path(__file__).parents[2]


def _tend():
    spec = importlib.util.spec_from_file_location(
        "tend_script", REPO / "scripts/tend.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tend = _tend()

HEALTH = [
    "Your body feels beat up.",
    "You have some tiny scratches to the head, cuts and bruises about the chest.",
    "Bleeding",
    "      Area       Rate",
    "-----------------------",
    "      l. leg     light",
    "      chest      moderate",
    "      r. arm     clotted",
    "      neck       slight(tended)",
    "inside chest     bad",
]


def test_health_lines_become_bleeder_rows():
    bleeders = tend.parse_health(HEALTH)
    assert [(b["area"], b["rate"]) for b in bleeders] == [
        ("left leg", "light"),
        ("chest", "moderate"),
        ("right arm", "clotted"),
        ("neck", "slight(tended)"),
        ("chest", "bad"),
    ]


def test_sides_are_spelled_out_for_the_tend_command():
    assert tend.expand_area("l. leg") == "left leg"
    assert tend.expand_area("r. arm") == "right arm"


def test_triage_tends_the_worst_external_bleeder_first():
    queue = tend.triage(tend.parse_health(HEALTH))
    assert [b["area"] for b in queue] == ["chest", "left leg"]  # moderate > light


def test_clotted_and_tended_wounds_are_left_alone():
    queue = tend.triage(tend.parse_health(HEALTH))
    assert all(b["rate"] in ("light", "moderate") for b in queue)


def test_internal_bleeders_are_magics_job():
    # "inside chest  bad" needs hundreds of First Aid ranks — never queued.
    assert all(not b["inside"] for b in tend.triage(tend.parse_health(HEALTH)))
    assert any(b["inside"] for b in tend.parse_health(HEALTH))


def test_a_clean_bill_of_health_has_no_bleeders():
    assert tend.parse_health(["You have no significant injuries."]) == []


class FakeHandle:
    """The script surface ;tend uses: canned waitfor answers per tend."""

    def __init__(self, answers, dead=False):
        self.answers = list(answers)
        self.dead = dead
        self.puts = []
        self.echoes = []
        self.args = []

    def put(self, command):
        self.puts.append(command)

    def waitfor(self, *patterns, timeout=None, streams=("",)):
        return self.answers.pop(0) if self.answers else None

    def waitrt(self):
        pass

    def echo(self, text):
        self.echoes.append(text)


def test_tend_reports_success_on_the_working_answer():
    handle = FakeHandle(["You work carefully at tending your wound."])
    assert tend.tend(handle, "left leg") is True
    assert handle.puts == ["tend my left leg"]


def test_a_fumble_is_a_failure_not_a_retry_loop():
    handle = FakeHandle(["You fumble around with the bandages."])
    assert tend.tend(handle, "chest") is False
    assert handle.puts == ["tend my chest"]  # exactly one attempt


def test_a_dislodged_object_is_tended_again_once():
    # The bolt pops free into a hand; the wound underneath still bleeds.
    handle = FakeHandle(
        [
            "You carefully remove a crossbow bolt from your leg.",
            "You work carefully at tending your wound.",
        ]
    )
    assert tend.tend(handle, "left leg") is True
    assert handle.puts == ["tend my left leg", "tend my left leg"]


def test_a_ghost_gets_no_bandages():
    handle = FakeHandle([], dead=True)
    handle.args = ["once"]
    tend.main(handle)
    assert handle.puts == []
    assert any("dead" in echo for echo in handle.echoes)
