"""An Empath's vela'tohr plant kept up (#473) — these tests are the
manual. ;plant walks to the room, takes the old plant's wounds (TOUCH,
then ;empath self), and casts a new plant: GET the phial, PREPARE EV,
INVOKE the phial, CAST, STOW, STAND, then PERCEIVE for its life. The
cast's answers are Riphik's, captured 2026-10-04 in the Paladins' Guild
Chambers; the creator's TOUCH answers are Elanthipedia's.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import guild, plant
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]

PREPARED = (
    "You feel intense strain as you try to manipulate the mana streams to form this "
    "pattern, and you are not certain that you will have enough mental stamina to "
    "complete it.\nHowever, if you utilize a ritual focus: That will disrupt about "
    "half your current attunement.\nWith meditative movements you prepare your body "
    "for the Embrace of the Vela'Tohr spell."
)
INVOKED = (
    "Kneeling down, you draw the spell pattern's shadow with some of your supply of "
    "phofe attar.\nRoundtime: 20 sec."
)
RITUAL_LINES = [
    "Your phofe attar design erupts, transforming into a pattern of glowing green lines!",
    "The mana-reactive phofe attar burns with carefully arranged power.  Your ritual "
    "directs the energy up into your spell pattern, removing much of the strain of "
    "empowering it off you.",
    "Your glowing green ritual burns away, leaving no sign of its former presence.",
    "You feel fully prepared to cast your spell.",
]
FORMED = (
    "The mental strain of this pattern is considerably eased by your ritual focus.\n"
    "As you gesture an ethereal vela'tohr plant forms and grows before you."
)
PERCEIVED = (
    "You sense that you're currently linked to a Vela'Tohr plant located at "
    "[Paladins' Guild, Chambers].\nThe plant appears to be in good condition.\n"
    "You sense the Embrace of the Vela'Tohr spell upon you, which will last for about "
    "sixty-two roisaen.\nRoundtime: 3 sec."
)
TOOK = (
    "You reach out to touch your vela'tohr plant and it extends a green branch, soft "
    "leaves curling against your flesh with a cool tingle.  You feel an empathic "
    "connection forming between you and your vela'tohr plant.  There is a burst of "
    "pain as your chest erupt in agony and blossom with wounds!  Your vela'tohr plant "
    "looks healthier!"
)
NO_NEED = (
    "You feel a slight warmth that quickly fades, indicating your plant has no need "
    "of healing."
)


def _script():
    spec = importlib.util.spec_from_file_location(
        "plant_script", REPO / "scripts/plant.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.guild = SimpleNamespace(
        character_guild=lambda s: "Empath", is_empath=guild.is_empath
    )
    return module


class Game:
    """The game's answers by command; the ritual's lines queue up after
    the INVOKE for the handle's get()."""

    def __init__(self, s, answers):
        self.s = s
        self.answers = dict(answers)
        self.sent = []

    def __call__(self, s, command, *rest):
        self.sent.append(command)
        if command.startswith("invoke"):
            s.lines.extend(RITUAL_LINES)
        return self.answers.get(command, "")


def handle(room_objs="You also see an armored sentry.", mana=100):
    echoed = []
    lines = []
    started = []
    state = SimpleNamespace(
        name="Lanival",
        room_objs=room_objs,
        vitals={"mana": mana},
        left_hand=None,
        right_hand=None,
        hostiles={},
    )
    return SimpleNamespace(
        state=state,
        dead=False,
        echo=echoed.append,
        echoed=echoed,
        args=[],
        lines=lines,
        started=started,
        get=lambda timeout=None, streams=("",): lines.pop(0) if lines else None,
        command=lambda timeout=None: None,
        waitrt=lambda: None,
        sleep=lambda seconds: None,
        run=lambda name, args=(): started.append((name, list(args))) or True,
        is_running=lambda name: False,
        kill=lambda name: None,
    )


CAST = {
    "get my phial": "You get a deep purple glass phial from inside your backpack.",
    "prepare ev 500": PREPARED,
    "invoke my phial": INVOKED,
    "cast": FORMED,
    "perceive": PERCEIVED,
}


CHAMBERS = MapDB(
    [{"id": 7890, "uid": [1], "title": ["[Paladins' Guild, Chambers]"], "wayto": {}}]
)


def arrive(s, db, goals, describe=None, avoid=(), **_):
    return True


def test_the_plants_life_is_read_off_perceive():
    assert plant.number("sixty-two") == 62
    assert plant.number("ninety") == 90
    assert plant.number("thirty one") == 31
    assert plant.number("several") is None
    assert plant.lasts(PERCEIVED) == 62
    assert plant.lasts("You sense nothing.") is None


def test_a_cast_is_due_with_no_record_another_session_or_near_its_end(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    assert plant.due("Lanival", "7890", 111, now=1000.0)
    plant.record("Lanival", "7890", 62, 111, now=1000.0)
    assert not plant.due("Lanival", "7890", 111, now=1000.0 + 51 * 60)
    assert plant.due("Lanival", "7890", 111, now=1000.0 + 52 * 60)  # ten to go
    assert plant.due("Lanival", "7890", 222, now=1001.0)  # a logout ended it
    assert plant.due("Lanival", "1900", 111, now=1001.0)


def test_plant_walks_there_casts_and_records_the_plants_life(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle()
    game = Game(s, CAST)
    script.ask = game
    result = script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive)
    assert result == "cast"
    assert game.sent == [
        "get my phial",
        "prepare ev 500",
        "invoke my phial",
        "cast",
        "stow my phial",
        "stand",
        "perceive",
    ]
    mark = plant.load("Lanival")
    assert (mark["room"], mark["minutes"]) == ("7890", 62)
    assert "plant: a vela'tohr plant stands at 7890 for about 62 min" in s.echoed


def test_the_old_plants_wounds_are_taken_and_healed_first(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle(room_objs="You also see an ethereal vela'tohr plant.")
    game = Game(s, CAST | {"touch plant": TOOK})
    script.ask = game
    assert (
        script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive) == "cast"
    )
    assert game.sent[0] == "touch plant"
    assert s.started == [("empath", ["self"])]
    clean = handle(room_objs="You also see an ethereal vela'tohr plant.")
    script.ask = Game(clean, CAST | {"touch plant": NO_NEED})
    script.run(clean, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive)
    assert clean.started == []


def test_plant_tend_takes_the_wounds_and_heals_without_a_cast(tmp_path, monkeypatch):
    # #491, 2026-10-08: Cecil's seven wounds went into the plant and only
    # Riphik's TOUCH, sent by hand, took them back out.
    import os

    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    plant.record("Lanival", "7890", 62, os.getpid(), now=1000.0)
    script = _script()
    s = handle(room_objs="You also see an ethereal vela'tohr plant.")
    game = Game(s, CAST | {"touch plant": TOOK})
    script.ask = game
    options = script.parse_args(["tend", "7890"])
    assert options["tend"] and options["room"] == "7890"
    assert script.run(s, options, db=CHAMBERS, walk=arrive) == "tended"
    assert game.sent == ["touch plant"]  # no GET, PREPARE, INVOKE or CAST
    assert s.started == [("empath", ["self"])]
    mark = plant.load("Lanival")
    assert mark["room"] == "7890" and mark["tended"] > 1000.0
    clean = handle(room_objs="You also see an ethereal vela'tohr plant.")
    script.ask = Game(clean, CAST | {"touch plant": NO_NEED})
    assert script.run(clean, script.parse_args(["tend"]), db=CHAMBERS) == "clean"
    assert clean.started == []
    assert "plant: the plant has no need of healing" in clean.echoed
    bare = handle()
    script.ask = Game(bare, {})
    assert script.run(bare, script.parse_args(["tend"]), db=CHAMBERS) == "no plant"


def test_an_empty_phial_ends_the_run_and_marks_the_record(tmp_path, monkeypatch):
    # #496 (Riphik, 2026-10-09 03:54): five recasts 15 minutes apart failed
    # on the same INVOKE answer before anyone was told.
    import os

    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    plant.record("Lanival", "7890", 63, os.getpid(), now=1000.0)
    script = _script()
    s = handle()
    empty = (
        "You notice that your phial does not have enough phofe attar left to focus "
        "a ritual.\n"
    )
    game = Game(s, CAST | {"invoke my phial": empty})
    script.ask = game
    assert script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive) == (
        "no focus"
    )
    assert "cast" not in game.sent and "release spell" in game.sent
    assert game.sent[-2:] == ["stow my phial", "stand"]
    assert any("the phial is empty — a new phial of phofe attar" in t for t in s.echoed)
    assert plant.no_focus("Lanival")
    # A cast with a new phial rewrites the record and clears the mark.
    plant.record("Lanival", "7890", 63, os.getpid(), now=2000.0)
    assert not plant.no_focus("Lanival")


def test_a_tend_is_due_twenty_minutes_after_the_cast_or_the_last_tend(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    assert not plant.tend_due("Lanival", "7890", 1, now=5000.0)  # no plant recorded
    plant.record("Lanival", "7890", 62, 1, now=1000.0)
    assert not plant.tend_due("Lanival", "7890", 1, now=1000.0 + 19 * 60)
    assert plant.tend_due("Lanival", "7890", 1, now=1000.0 + 20 * 60)
    assert not plant.tend_due("Lanival", "7890", 2, now=1000.0 + 20 * 60)  # a logout
    assert not plant.tend_due("Lanival", "1234", 1, now=1000.0 + 20 * 60)  # elsewhere
    plant.note_tend("Lanival", now=1000.0 + 20 * 60)
    assert not plant.tend_due("Lanival", "7890", 1, now=1000.0 + 39 * 60)
    assert plant.tend_due("Lanival", "7890", 1, now=1000.0 + 40 * 60)
    assert plant.load("Lanival")["minutes"] == 62  # the cast's record kept


def test_an_unrelated_line_first_does_not_lose_the_prepare(tmp_path, monkeypatch):
    # 2026-10-05 00:05: "You feel fully rested." closed PREPARE's window,
    # the spell's lines came after it, and the cast was given up held.
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle()
    s.state.prepared_spell = "Embrace of the Vela'Tohr"  # held from that run

    class Late(Game):
        def __call__(self, s, command, *rest):
            if command == "prepare ev 500":
                self.sent.append(command)
                s.lines.extend(PREPARED.splitlines())
                return "You feel fully rested."
            return super().__call__(s, command, *rest)

    game = Late(s, CAST)
    script.ask = game
    assert (
        script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive) == "cast"
    )
    assert game.sent[:3] == ["get my phial", "release spell", "prepare ev 500"]


def test_the_cast_waits_for_fully_prepared_after_the_rituals_lines():
    # 2026-10-05 00:11: CAST after "...burns away" but before "fully
    # prepared" — "Your spell badly backfires."
    script = _script()
    s = handle()
    s.lines.extend(RITUAL_LINES[:3])
    assert script.ritual_done(s, INVOKED) is False
    s.lines.extend(RITUAL_LINES)
    assert script.ritual_done(s, INVOKED) is True
    assert s.lines == []


def test_a_song_left_playing_is_stopped_before_the_prepare(tmp_path, monkeypatch):
    # 2026-10-05 00:10: "You should stop playing before you do that."
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle()
    answers = ["You should stop playing before you do that.", PREPARED]

    class Song(Game):
        def __call__(self, s, command, *rest):
            if command == "prepare ev 500":
                self.sent.append(command)
                return answers.pop(0)
            return super().__call__(s, command, *rest)

    game = Song(s, CAST)
    script.ask = game
    assert (
        script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive) == "cast"
    )
    assert game.sent[:4] == [
        "get my phial",
        "prepare ev 500",
        "stop play",
        "prepare ev 500",
    ]


def test_a_research_portion_running_is_confirmed_away(tmp_path, monkeypatch):
    # 2026-10-05 14:12: the recast came due while a research portion ran.
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle()
    answers = [
        "Are you sure you want to do that?  You'll interrupt your research!",
        PREPARED,
    ]

    class Research(Game):
        def __call__(self, s, command, *rest):
            if command == "prepare ev 500":
                self.sent.append(command)
                return answers.pop(0)
            return super().__call__(s, command, *rest)

    game = Research(s, CAST)
    script.ask = game
    assert (
        script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive) == "cast"
    )
    assert game.sent[:3] == ["get my phial", "prepare ev 500", "prepare ev 500"]


def test_low_mana_waits_and_records_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle(mana=40)
    game = Game(s, CAST)
    script.ask = game
    assert script.run(s, script.parse_args([]), db=CHAMBERS, walk=arrive) == "failed"
    assert game.sent == []
    assert "plant: mana 40% — the cast waits for 50%" in s.echoed
    assert plant.load("Lanival") is None


def test_a_lost_ritual_releases_the_spell_and_stows_the_focus(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_TRAINING", str(tmp_path))
    script = _script()
    s = handle()
    lost = "Your concentration slips for a moment, and your spell is lost."
    game = Game(s, CAST | {"invoke my phial": INVOKED + "\n" + lost})
    script.ask = game
    assert (
        script.run(s, script.parse_args(["7890"]), db=CHAMBERS, walk=arrive) == "failed"
    )
    assert game.sent[-3:] == ["release spell", "stow my phial", "stand"]
    assert "cast" not in game.sent


def test_any_guild_but_empath_is_told_so():
    script = _script()
    script.guild = SimpleNamespace(
        character_guild=lambda s: "Paladin", is_empath=guild.is_empath
    )
    s = handle()
    assert script.run(s, script.parse_args(["7890"])) == "not an empath"
    assert s.echoed == ["plant: Embrace of the Vela'Tohr is an Empath's spell"]
