"""How ;moonbeam focuses a beam and teleports back to it (#522) — these
tests are the manual. PERCEIVE MOONS says which moon has the most time;
the beam goes on it; Teleport goes only to a beam whose moon is up with
minutes to spare and that Distant Gaze still shows. The wordings are the
hand captures of 2026-10-10 (a circle-200 Moon Mage)."""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game import casting, moonbeam
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "moonbeam_script", REPO / "scripts/moonbeam.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

# PERCEIVE MOONS, captured 2026-10-10 (Xibar up in the east, Yavash down);
# Katamba's western line is the same sentence on the other side.
PERCEIVED = (
    "Xibar is a new moon, high in the eastern sky.\n"
    "You're certain that Xibar is seventy-two degrees above the eastern horizon.\n"
    "Yavash is a full moon and is not visible.  Although you cannot see it, you "
    "can sense it should rise in about 4 anlaen.\n"
    "Katamba is a waxing gibbous moon, low in the western sky.\n"
    "You're certain that Katamba is nine degrees above the western horizon.\n"
    "Roundtime: 9 sec.\n"
)
PREPARED = (
    "That won't affect your current attunement very much.\n"
    "You spread your hands apart then slowly bring them together, fingers "
    "interlocked.\n"
)
FOCUSED = (
    "You gesture.\nA beam of clear silvery-blue light descends from the heavens "
    "as you focus a moonbeam from Xibar into the area.\n"
)
GAZED = (
    "You gesture.\nYou concentrate on your Xibar moonbeam, overlaying an oddly "
    "flat image from its location upon your normal vision...\n"
)
TELEPORTED = (
    "You gesture.\nElanthia seems to fall away from under your feet as the entire "
    "world disappears in a brilliant blue flash.  As your vision slowly returns "
    "you find yourself at...\n[The Crossing, Varlet's Run]\nYou are stunned!\n"
)
DISCERNED = (
    "The spell requires at minimum 5 mana streams and you think you can reinforce "
    "it with 95 more, for a total of 100 streams.\nRoundtime: 8 sec.\n"
)

MAP = MapDB(
    [
        {"id": 8262, "uid": [7], "title": ["[The Crossing, Varlet's Run]"]},
        {"id": 8263, "uid": [8], "title": ["[The Crossing, Hodierna Way]"]},
    ]
)


class Mage:
    """A handle and the game it asks: each command prefix answers from
    its queue; every command sent is kept."""

    def __init__(self, answers, room=7):
        self.answers = {key: list(value) for key, value in answers.items()}
        self.sent, self.echoed = [], []
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            room_uid=room,
            room_title=MAP.rooms[{7: 8262, 8: 8263}[room]]["title"][0],
        )

    def ask(self, s, command, seconds=None, tail=None):
        self.sent.append(command)
        for prefix, queue in self.answers.items():
            if command.startswith(prefix) and queue:
                return queue.pop(0) if len(queue) > 1 else queue[0]
        return ""

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


@pytest.fixture(autouse=True)
def _wired(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    monkeypatch.setattr(script, "probe", SimpleNamespace(collect=lambda *a, **k: ""))
    monkeypatch.setattr(
        script, "locate", lambda db, state: {7: 8262, 8: 8263}[state.room_uid]
    )
    monkeypatch.setattr(casting, "wait_stun", lambda s: None)


def run(mage, *words):
    script.ask = mage.ask
    buffs_ask = mage.ask  # DISCERN goes through the same game
    script.casting = SimpleNamespace(
        CastState=casting.CastState,
        PREPARE_OUTCOMES=casting.PREPARE_OUTCOMES,
        classify=casting.classify,
        mana_limit=casting.mana_limit,
        wait_stun=lambda s: None,
        discern=lambda s, spell, state, ask: buffs_ask(s, f"discern {spell}"),
    )
    script.run(mage, script.parse_args(list(words)), MAP)
    return "\n".join(mage.echoed)


def test_perceive_moons_reads_each_moon_and_its_time_left():
    moons = moonbeam.parse_moons(PERCEIVED)
    assert moons["xibar"] == {"up": True, "degrees": 72, "side": "east"}
    assert moons["yavash"] == {"up": False, "degrees": None, "side": None}
    assert moons["katamba"] == {"up": True, "degrees": 9, "side": "west"}
    # East: 108 degrees still to go; west: the 9 above the horizon.
    assert moonbeam.minutes_left(moons["xibar"]) == 106
    assert moonbeam.minutes_left(moons["katamba"]) == 9
    assert moonbeam.minutes_left(moons["yavash"]) == 0
    assert moonbeam.best_moon(moons) == "xibar"
    assert moonbeam.number("seventy-two") == 72
    assert moonbeam.number("nine") == 9
    assert moonbeam.number("lots") is None


def test_a_moon_about_to_set_is_no_place_for_a_beam():
    moons = moonbeam.parse_moons(
        "You're certain that Xibar is five degrees above the western horizon.\n"
    )
    assert moonbeam.best_moon(moons) is None  # five minutes: under FOCUS_MARGIN


def test_the_beam_goes_on_the_moon_with_the_most_time_and_is_recorded():
    mage = Mage(
        {
            "perceive moons": [PERCEIVED],
            "discern focus moonbeam": [DISCERNED],
            "prepare fm": [PREPARED],
            "cast": [FOCUSED],
        }
    )
    out = run(mage)
    assert mage.sent == [
        "perceive moons",
        "discern focus moonbeam",
        "prepare fm 100",
        "cast xibar",
    ]
    beam = moonbeam.load("Lanival")
    assert (beam["moon"], beam["room"], beam["mana"]) == ("xibar", 8262, 100)
    assert beam["ends"] > beam["at"]  # the moon's setting, for the walker
    assert moonbeam.usable(beam, beam["at"])
    assert "a Xibar beam here, [The Crossing, Varlet's Run], with 100 mana" in out


def test_no_moon_up_with_time_is_said_and_nothing_cast():
    mage = Mage(
        {
            "perceive moons": [
                "Xibar is a new moon and is not visible.\n"
                "Yavash is a full moon and is not visible.\n"
            ]
        }
    )
    out = run(mage)
    assert mage.sent == ["perceive moons"]
    assert "no moon up with time for a beam — Xibar down, Yavash down" in out


def test_teleport_checks_the_moon_and_the_beam_then_goes():
    moonbeam.record(
        "Lanival", {"moon": "xibar", "room": 8262, "title": "[Varlet's Run]"}
    )
    mage = Mage(
        {
            "perceive moons": [PERCEIVED],
            "prepare dg": [PREPARED],
            "prepare teleport": [PREPARED],
            "discern teleport": [DISCERNED],
            "cast": [GAZED, TELEPORTED],
        },
        room=8,
    )
    out = run(mage, "teleport")
    assert mage.sent == [
        "perceive moons",
        "prepare dg",
        "cast xibar",  # Distant Gaze: the beam is still there
        "discern teleport",
        "prepare teleport 100",
        "cast xibar",
    ]
    assert "teleported with 100 mana" in out


def test_no_teleport_on_a_moon_that_is_down():
    moonbeam.record("Lanival", {"moon": "yavash", "room": 8262})
    mage = Mage({"perceive moons": [PERCEIVED]})
    out = run(mage, "teleport")
    assert mage.sent == ["perceive moons"]
    assert "Yavash is down" in out and "not cast" in out
    assert moonbeam.load("Lanival") is None  # the beam went with its moon


def test_no_teleport_to_a_beam_distant_gaze_does_not_show():
    moonbeam.record("Lanival", {"moon": "xibar", "room": 8262})
    mage = Mage(
        {
            "perceive moons": [PERCEIVED],
            "prepare dg": [PREPARED],
            "cast": ["You gesture.\nYou have no moonbeam focused on Xibar.\n"],
        }
    )
    out = run(mage, "teleport")
    assert not any(command.startswith("prepare teleport") for command in mage.sent)
    assert "does not show the Xibar beam" in out


def test_no_teleport_without_a_mana_estimate_or_a_named_mana():
    moonbeam.record("Lanival", {"moon": "xibar", "room": 8262})
    mage = Mage(
        {
            "perceive moons": [PERCEIVED],
            "prepare dg": [PREPARED],
            "cast": [GAZED],
            "discern teleport": ["You have no idea how to cast that spell.\n"],
        }
    )
    out = run(mage, "teleport")
    assert not any(command.startswith("prepare teleport") for command in mage.sent)
    assert "mana=N" in out
    mage = Mage(
        {
            "perceive moons": [PERCEIVED],
            "prepare": [PREPARED],
            "cast": [GAZED, TELEPORTED],
        }
    )
    run(mage, "teleport", "mana=40")
    assert "prepare teleport 40" in mage.sent
