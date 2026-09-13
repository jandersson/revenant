"""How ;favors earns a favor — these tests are the manual.

Walk to the Stone Grotto, pray an orb loose (default Truffenyi, any
neutral aspect by argument), GO ARCH, wait out the hand-solved puzzles,
walk to the temple creche, rub the orb full, offer it, verify with
FAVOR. The wordings the classifier trusts most are quoted on
Elanthipedia (docs/favors.md); the rest are assumptions until an
attended run captures them (#82).
"""

import importlib.util
import pathlib
from types import SimpleNamespace

REPO = pathlib.Path(__file__).parents[2]


def _favors():
    spec = importlib.util.spec_from_file_location(
        "favors_script", REPO / "scripts/favors.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


favors = _favors()

LEARNING = {"Athletics": {"rank": 30, "percent": 10.0, "mindstate": 5}}


class FakeHandle:
    """The script surface: canned (stream, line) answers per command.

    command(timeout=0) always answers None — the script's entry drain
    must not eat the canned user lines meant for the puzzle phase."""

    def __init__(self, responses=None, experience=None, indicator=None):
        self.responses = {c: list(seqs) for c, seqs in (responses or {}).items()}
        self.pending = []
        self.sent = []
        self.echoed = []
        self.commands = []
        self.args = []
        self.state = SimpleNamespace(
            experience=dict(LEARNING) if experience is None else experience,
            indicator=indicator or {},
            room_uid=None,
            room_title=None,
            compass=[],
        )

    def put(self, command):
        self.sent.append(command)
        seqs = self.responses.get(command, [])
        self.pending = list(seqs.pop(0)) if seqs else []

    def get(self, timeout=None, streams=("",)):
        while self.pending:
            stream, text = self.pending.pop(0)
            if streams is None:
                return stream, text
            if stream in streams:
                return text
        return None

    def command(self, timeout=None):
        if timeout == 0:
            return None
        return self.commands.pop(0) if self.commands else None

    def echo(self, text):
        self.echoed.append(text)

    def sleep(self, seconds):
        pass

    def waitrt(self):
        pass


class DrainingHandle(FakeHandle):
    """Every rub empties the experience pool — the drained-mid-fill case."""

    def put(self, command):
        super().put(command)
        if command == "rub my orb":
            self.state.experience = {}


class FakeMap:
    """path() always answers "already there" — walking is stubbed."""

    def path(self, start, goals):
        return []


def _quick(monkeypatch):
    monkeypatch.setattr(favors, "COLLECT_SECONDS", 0.01)
    monkeypatch.setattr(favors, "RESULT_SECONDS", 0.01)
    monkeypatch.setattr(favors, "OFFER_SECONDS", 0.01)


def test_default_immortal_is_truffenyi():
    assert favors.resolve_immortal([]) == "Truffenyi"


def test_any_neutral_aspect_by_argument_lenient_on_case_and_apostrophes():
    assert favors.resolve_immortal(["meraud"]) == "Meraud"
    assert favors.resolve_immortal(["HAVROTH"]) == "Hav'roth"
    assert favors.resolve_immortal(["urrem'tier"]) == "Urrem'tier"


def test_light_and_dark_aspects_are_refused():
    # Kuniyo is Everild's light aspect, Asketi is Hodierna's dark —
    # the general altar ritual names neutral aspects only (docs/favors.md).
    assert favors.resolve_immortal(["Kuniyo"]) is None
    assert favors.resolve_immortal(["Asketi"]) is None


def test_unknown_immortal_refused_with_the_thirteen_listed():
    handle = FakeHandle()
    handle.args = ["Kuniyo"]
    favors.main(handle, db=FakeMap(), walk=lambda *a, **k: True)
    assert handle.sent == []
    assert any("Truffenyi" in echo and "Meraud" in echo for echo in handle.echoed)


def test_refuses_to_run_dead():
    handle = FakeHandle(indicator={"IconDEAD": "y"})
    favors.main(handle, db=FakeMap(), walk=lambda *a, **k: True)
    assert handle.sent == []
    assert any("dead" in echo for echo in handle.echoed)


def test_refuses_with_nothing_learning():
    handle = FakeHandle(experience={})
    favors.main(handle, db=FakeMap(), walk=lambda *a, **k: True)
    assert handle.sent == []
    assert any("train something first" in echo for echo in handle.echoed)


def test_classify_rub_outcomes():
    # "properly prepared" is Elanthipedia-quoted; the rest assumptions.
    assert (
        favors.classify(
            "You sense that your sacrifice is properly prepared.",
            favors.RUB_OUTCOMES,
        )
        == "full"
    )
    assert (
        favors.classify(
            "The orb glows a pale violet, wavering slightly.", favors.RUB_OUTCOMES
        )
        == "progress"
    )
    assert (
        favors.classify("What were you referring to?", favors.RUB_OUTCOMES) == "no_orb"
    )
    assert favors.classify("Wholly novel wording.", favors.RUB_OUTCOMES) is None


def test_classify_offer_outcomes():
    # The light show is Elanthipedia-quoted (docs/favors.md).
    assert (
        favors.classify(
            "Then, an instant later, the multicolored lights gather around you "
            "and mix together, forming a white mass of brightness.",
            favors.OFFER_OUTCOMES,
        )
        == "granted"
    )


def test_the_grotto_ritual_is_the_wiki_sequence(monkeypatch):
    _quick(monkeypatch)
    handle = FakeHandle(
        {"get orb on altar": [[("", "You get a small glass orb from the altar.")]]}
    )
    outcome = favors.ritual(handle, "Meraud")
    assert handle.sent == [
        "kneel",
        "pray",
        "pray",
        "pray",
        "say Meraud",
        "stand",
        "get orb on altar",
    ]
    assert outcome == "ok"


def test_full_run_earns_a_favor(monkeypatch):
    _quick(monkeypatch)
    monkeypatch.setattr(favors, "locate", lambda db, state: favors.GROTTO)
    handle = FakeHandle(
        {
            "get orb on altar": [
                [("", "You get a violet-tinged glass orb from the altar.")]
            ],
            "go arch": [[("compass", "east west")]],
            "rub my orb": [
                [("", "The orb glows a pale violet, wavering slightly.")],
                [("", "You sense that your sacrifice is properly prepared.")],
            ],
            "put my orb on altar": [
                [("", "The multicolored lights gather around you and mix together.")]
            ],
            "favor": [[("", "You currently have 1 favor, from Truffenyi.")]],
        }
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert "say Truffenyi" in handle.sent
    assert handle.sent.index("stand") < handle.sent.index("get orb on altar")
    assert any("back on the map" in echo for echo in handle.echoed)
    assert any("favor earned" in echo for echo in handle.echoed)
    assert any("1 favor, from Truffenyi" in echo for echo in handle.echoed)


PLANT_ROOM = (
    "[Siergelde, Labyrinth]\n"
    "You are standing in a square room of smooth, stone walls.  A table sits "
    "against one wall, directly opposite an ancient window.  The air is stifling "
    "due to the lack of circulation, and a plant upon the table looks as though "
    "it is slowly choking to death in the heat.\n"
    "Obvious paths: none.\n"
)


def test_the_choking_plant_room_is_solved_by_opening_the_window(monkeypatch):
    # Captured 2026-09-13: three OPEN WINDOWs, then GO WINDOW teleports
    # back to the grotto, where the run resumes on its own.
    _quick(monkeypatch)
    handle = FakeHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
            "look": [[("", line) for line in PLANT_ROOM.splitlines()]],
            "open window": [
                [
                    (
                        "",
                        "Judging the thickness of the paint which has sealed the "
                        "window shut, you shimmy the frame of the glass to loosen it.",
                    )
                ],
                [
                    (
                        "",
                        "Shaking the frame of the glass once more, you manage to "
                        "loosen it even further.",
                    )
                ],
                [
                    (
                        "",
                        "With a mighty growl, you grasp the lower edge of the glass "
                        "frame and hoist it upward.  At first it only creaks, but soon "
                        "it slides open with jerking movements.",
                    )
                ],
                [("", "That is already open.")],
            ],
            "go window": [
                [
                    (
                        "",
                        "You hoist yourself off the floor and manage to swing "
                        "yourself through the open window.",
                    ),
                    (
                        "",
                        "You feel giddy all over and you grin widely as everything "
                        "about you disappears and you suddenly find yourself "
                        "transported to...",
                    ),
                ]
            ],
            "rub my orb": [
                [("", "You sense that your sacrifice is properly prepared.")],
            ],
            "put my orb on altar": [
                [("", "The multicolored lights gather around you and mix together.")]
            ],
            "favor": [[("", "You currently have 1 favor, from Truffenyi.")]],
        }
    )
    monkeypatch.setattr(
        favors,
        "locate",
        lambda db, state: favors.GROTTO if "go window" in handle.sent else None,
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    puzzle = handle.sent[handle.sent.index("go arch") + 1 :]
    assert puzzle[:5] == [
        "look",
        "open window",
        "open window",
        "open window",
        "go window",
    ]
    assert any("the choking plant" in echo for echo in handle.echoed)
    assert any("back on the map" in echo for echo in handle.echoed)
    assert any("favor earned" in echo for echo in handle.echoed)


VASE_ROOM = (
    "[Siergelde, Labyrinth]\n"
    "A peaceful grotto bathed in an ethereal light is swathed in hedges of "
    "oleander and nutflower.  The path upon which you stand winds around a "
    "simple white altar hewn of shimmering marble, and disappears in a copse of "
    "juniper trees.    You also see a vase on top of the altar.\n"
    "Obvious exits: none.\n"
)


def test_the_vase_room_is_filled_with_a_free_hand_and_left_by_the_path(monkeypatch):
    # Captured 2026-09-13, the second favor: GET NUTFLOWER arranges the
    # blossoms itself, GO PATH teleports back; the orb and the handaxe
    # had both hands, so the handaxe is stowed first.
    _quick(monkeypatch)
    handle = FakeHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
            "look": [[("", line) for line in VASE_ROOM.splitlines()]],
            "stow my handaxe": [[("", "You put your handaxe in your canvas sack.")]],
            "get nutflower": [
                [
                    (
                        "",
                        "You carefully pick some of the nutflower blossoms and "
                        "arrange them neatly in the vase.",
                    )
                ],
                [("", "You have already filled the vase to overflowing.")],
            ],
            "go path": [
                [
                    (
                        "",
                        "Having filled the vase with flowers, you stride along the "
                        "branching path toward the copse of juniper trees.",
                    ),
                    (
                        "",
                        "You feel giddy all over and you grin widely as everything "
                        "about you disappears and you suddenly find yourself "
                        "transported to...",
                    ),
                ]
            ],
            "rub my orb": [
                [("", "You sense that your sacrifice is properly prepared.")],
            ],
            "put my orb on altar": [
                [("", "The multicolored lights gather around you and mix together.")]
            ],
            "favor": [[("", "You currently have 2 favors with the gods.")]],
        }
    )
    handle.state.right_hand = {"noun": "handaxe", "exist": "2", "name": "handaxe"}
    original_put = handle.put

    def put(command):  # the altar's orb fills the other hand
        original_put(command)
        if command == "get orb on altar":
            handle.state.left_hand = {"noun": "orb", "exist": "1", "name": "orb"}

    handle.put = put
    monkeypatch.setattr(
        favors,
        "locate",
        lambda db, state: favors.GROTTO if "go path" in handle.sent else None,
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    puzzle = handle.sent[handle.sent.index("go arch") + 1 :]
    assert puzzle[:4] == ["look", "stow my handaxe", "get nutflower", "go path"]
    assert any("the empty vase" in echo for echo in handle.echoed)
    assert any("favor earned" in echo for echo in handle.echoed)


FONT_ROOM = (
    "[Siergelde, Labyrinth]\n"
    "Two fiery braziers stand astride a steep stone stairway which leads to a "
    "massive iron door above the main chamber in which you stand.  The soft light "
    "which undulates upon the walls reveals this place to be a room of worship, "
    "though its deity remains a mystery.    You also see a granite altar with "
    "several candles and a water jug on it, and a granite font.\n"
    "Obvious exits: none.\n"
)


def test_the_font_room_is_filled_from_the_jug_and_left_by_stair_and_door(
    monkeypatch,
):
    # Captured 2026-09-13, the third favor.
    _quick(monkeypatch)
    handle = FakeHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
            "look": [[("", line) for line in FONT_ROOM.splitlines()]],
            "get jug": [[("", "You reverently take the jug from the altar.")]],
            "pour jug in font": [
                [
                    (
                        "",
                        "You carefully carry the earthen jug to the font and pour "
                        "the water out.  The soft scent of lilac rises from the filled "
                        "basin, refreshing and invigorating your senses.",
                    )
                ]
            ],
            "go stair": [
                [
                    (
                        "",
                        "You reach the top of the stairway, and notice that the door "
                        "has swung open of its own accord!",
                    )
                ]
            ],
            "go door": [
                [
                    (
                        "",
                        "You step gleefully through the door, happy to have done "
                        "some little service to whichever deity resides within the "
                        "chamber.",
                    ),
                    (
                        "",
                        "You feel giddy all over and you grin widely as everything "
                        "about you disappears and you suddenly find yourself "
                        "transported to...",
                    ),
                ]
            ],
            "rub my orb": [
                [("", "You sense that your sacrifice is properly prepared.")],
            ],
            "put my orb on altar": [
                [("", "The multicolored lights gather around you and mix together.")]
            ],
            "favor": [[("", "You currently have 3 favors with the gods.")]],
        }
    )
    monkeypatch.setattr(
        favors,
        "locate",
        lambda db, state: favors.GROTTO if "go door" in handle.sent else None,
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    puzzle = handle.sent[handle.sent.index("go arch") + 1 :]
    assert puzzle[:5] == ["look", "get jug", "pour jug in font", "go stair", "go door"]
    assert any("the empty font" in echo for echo in handle.echoed)
    assert any("favor earned" in echo for echo in handle.echoed)


def test_an_unknown_puzzle_room_is_left_to_the_human(monkeypatch):
    _quick(monkeypatch)
    handle = FakeHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
            "look": [
                [
                    ("", "[Siergelde, Labyrinth]"),
                    ("", "Three levers jut from the wall."),
                ]
            ],
            "rub my orb": [
                [("", "You sense that your sacrifice is properly prepared.")],
            ],
            "put my orb on altar": [
                [("", "The multicolored lights gather around you and mix together.")]
            ],
            "favor": [[("", "You currently have 1 favor, from Truffenyi.")]],
        }
    )
    handle.commands = ["done"]
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert any(
        "a puzzle room I do not know — [Siergelde, Labyrinth]" in e
        for e in handle.echoed
    )
    assert any("solve this room by hand" in echo for echo in handle.echoed)
    assert "open window" not in handle.sent
    assert "rub my orb" in handle.sent  # ;favors done resumed the run


def _creche_answers():
    return {
        "rub my orb": [[("", "You sense that your sacrifice is properly prepared.")]],
        "put my orb on altar": [
            [("", "The multicolored lights gather around you and mix together.")]
        ],
        "favor": [[("", "You currently have 4 favors with the gods.")]],
    }


def test_an_orb_already_in_hand_skips_the_prayer(monkeypatch):
    # 2026-09-13, the operator: a run with an orb in hand must not pray
    # for another (beyond two, fed experience is wasted).
    _quick(monkeypatch)
    monkeypatch.setattr(favors, "locate", lambda db, state: favors.GROTTO)
    handle = FakeHandle(_creche_answers())
    handle.state.left_hand = {"noun": "orb", "exist": "1", "name": "Truffenyi orb"}
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert "kneel" not in handle.sent and "get my orb" not in handle.sent
    assert any("already in your possession" in echo for echo in handle.echoed)
    assert handle.sent[0] == "rub my orb"
    assert any("favor earned" in echo for echo in handle.echoed)


def test_a_stowed_orb_is_fetched_and_the_prayer_skipped(monkeypatch):
    _quick(monkeypatch)
    monkeypatch.setattr(favors, "locate", lambda db, state: favors.GROTTO)
    handle = FakeHandle(
        _creche_answers()
        | {"get my orb": [[("", "You get a Truffenyi orb from your canvas sack.")]]}
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert handle.sent[:2] == ["get my orb", "rub my orb"]
    assert "kneel" not in handle.sent


def test_no_orb_anywhere_means_the_usual_prayer(monkeypatch):
    _quick(monkeypatch)
    monkeypatch.setattr(favors, "locate", lambda db, state: favors.GROTTO)
    handle = FakeHandle(
        _creche_answers()
        | {
            "get my orb": [[("", "What were you referring to?")]],
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
        }
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert handle.sent[0] == "get my orb"
    assert "kneel" in handle.sent and "get orb on altar" in handle.sent


def test_an_orb_in_hand_off_the_map_solves_the_puzzles_first(monkeypatch):
    _quick(monkeypatch)
    handle = FakeHandle(
        _creche_answers()
        | {
            "look": [[("", line) for line in PLANT_ROOM.splitlines()]],
            "open window": [[("", "...soon it slides open with jerking movements.")]],
            "go window": [[("", "You feel giddy all over ... transported to...")]],
        }
    )
    handle.state.right_hand = {"noun": "orb", "exist": "1", "name": "Truffenyi orb"}
    monkeypatch.setattr(
        favors,
        "locate",
        lambda db, state: favors.GROTTO if "go window" in handle.sent else None,
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert handle.sent[:4] == ["look", "open window", "go window", "rub my orb"]
    assert "kneel" not in handle.sent


def test_no_orb_from_the_altar_stops_before_the_arch(monkeypatch):
    _quick(monkeypatch)
    handle = FakeHandle({"get orb on altar": [[("", "What were you referring to?")]]})
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert "go arch" not in handle.sent
    assert any("no orb appeared" in echo for echo in handle.echoed)


def test_go_arch_going_nowhere_stops_for_capture(monkeypatch):
    _quick(monkeypatch)
    handle = FakeHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("", "What were you referring to?")]],
        }
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert "rub my orb" not in handle.sent
    assert any("went nowhere" in echo for echo in handle.echoed)


def test_abort_mid_puzzles_stops_the_run(monkeypatch):
    _quick(monkeypatch)
    handle = FakeHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
        }
    )
    handle.commands = ["abort"]
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert "rub my orb" not in handle.sent
    assert any("aborted" in echo for echo in handle.echoed)


def test_drained_pool_stops_with_guidance(monkeypatch):
    _quick(monkeypatch)
    monkeypatch.setattr(favors, "locate", lambda db, state: favors.GROTTO)
    handle = DrainingHandle(
        {
            "get orb on altar": [[("", "You get a glass orb from the altar.")]],
            "go arch": [[("compass", "none")]],
            "rub my orb": [[("", "The orb glows faintly.")]],
        }
    )
    favors.main(handle, db=FakeMap(), walk=lambda s, db, goals, describe: True)
    assert "put my orb on altar" not in handle.sent
    assert any("pool drained" in echo for echo in handle.echoed)


def test_unrecognized_rub_wordings_are_echoed_for_capture(monkeypatch):
    _quick(monkeypatch)
    handle = DrainingHandle({"rub my orb": [[("", "A wholly novel orb wording.")]]})
    assert favors.fill(handle) == "drained"
    assert any(
        "unrecognized (rub): A wholly novel orb wording." in echo
        for echo in handle.echoed
    )
