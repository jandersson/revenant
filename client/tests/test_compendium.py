"""First Aid from a compendium of anatomy charts — these tests are the
manual. LOOK lists the charts; the hardest one Scholarship reads goes
first; TURN opens its page and STUDY runs until clarity, after which
the chart rests twenty minutes; the compendium is stowed at the end
(client/game/compendium.py, scripts/compendium.py). The answers are
Cecil's, captured 2026-10-04.
"""

import importlib.util
import pathlib
from types import SimpleNamespace

import pytest

from client.game import compendium

REPO = pathlib.Path(__file__).parents[2]

LOOK = (
    "The compendium lies open to the section on Blood Dryad physiology.  A "
    "drawing of a blood dryad with all four limbs extended covers this chart.  "
    "Flipping through the pages, you realize that the compendium contains the "
    "following charts:\n"
    "   Blood Dryad\n"
    "   Blood Nyad\n"
    "   Equine\n"
    "   Glutinous Lipopod\n"
    "   Grass Eel\n"
    "   Silver Leucro\n"
    "   Striped Badger\n"
)
TURNED = "You turn to the section on {} physiology.\n"
BEGIN = (
    "You begin studying the Blood Nyad chart, gradually absorbing the knowledge "
    "contained within.\nRoundtime: 14 seconds.\n"
)
CONTINUE = (
    "You continue studying the Blood Nyad chart, gradually absorbing more of the "
    "knowledge contained within.\nRoundtime: 14 seconds.\n"
)
CLARITY = (
    "In a sudden moment of clarity, the information on the chart suddenly makes "
    "sense to you.\nRoundtime: 14 seconds.\n"
)
FIRST_CLARITY = (
    "With a sudden moment of clarity, the information on the chart suddenly makes "
    "sense to you.\nRoundtime: 10 seconds.\n"
)
RESTING = "Why do you need to study this chart again?\n"
# A chart near the top of the reach (the Boggle at Scholarship 77).
DIFFICULT = (
    "You begin to study the Boggle chart, having a difficult time comprehending "
    "the advanced text.\nRoundtime: 18 seconds.\n"
)
DIFFICULT_ON = (
    "You continue to study the Boggle chart, having a difficult time "
    "comprehending the advanced text.\nRoundtime: 18 seconds.\n"
)
MISSING = "That section does not exist within your compendium.\n"
UNHELD = "You need to be holding your compendium to study it.\n"
GOT = (
    "You get a grey leather compendium embossed with a snakeskin pattern from "
    "inside your backpack.\n"
)
STOWED = "You put your compendium in your backpack.\n"


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(compendium, "_LOCKED", {})
    monkeypatch.setattr(compendium, "_SLOW", set())
    monkeypatch.setattr(compendium, "_EASY", set())


def test_the_look_lists_the_charts():
    assert compendium.charts(LOOK) == [
        "Blood Dryad",
        "Blood Nyad",
        "Equine",
        "Glutinous Lipopod",
        "Grass Eel",
        "Silver Leucro",
        "Striped Badger",
    ]
    assert compendium.charts("You see nothing unusual.") == []


def test_the_hardest_chart_scholarship_reads_goes_first():
    names = compendium.charts(LOOK)
    assert compendium.plan(names, 77) == [
        "Blood Nyad",
        "Glutinous Lipopod",
        "Blood Dryad",
        "Equine",
        "Grass Eel",
        "Striped Badger",
        "Silver Leucro",
    ]
    # Scholarship 25 reads the 25s and the Silver Leucro (20), no more.
    assert compendium.plan(names, 25) == [
        "Grass Eel",
        "Striped Badger",
        "Silver Leucro",
    ]
    # A chart the table does not know comes last, never left out.
    assert compendium.plan(["Mystery Beast", "Equine"], 77) == [
        "Equine",
        "Mystery Beast",
    ]
    # Past rank 100 the reach is the rank over 1.6 (dr-scripts' first-aid).
    assert compendium.reach(160) == 100 and compendium.reach(77) == 77


def test_turn_finds_a_chart_by_its_tables_word():
    assert compendium.index("Glutinous Lipopod") == "glutinous"
    assert compendium.index("Blood Nyad") == "blood nyad"
    assert compendium.index("Mystery Beast") == "mystery beast"


def test_the_answers_are_classified():
    classify = __import__("client.game.probe", fromlist=["classify"]).classify
    assert classify(BEGIN, compendium.STUDY_OUTCOMES) == "studying"
    assert classify(CONTINUE, compendium.STUDY_OUTCOMES) == "studying"
    assert classify(CLARITY, compendium.STUDY_OUTCOMES) == "clarity"
    assert classify(FIRST_CLARITY, compendium.STUDY_OUTCOMES) == "clarity"
    assert classify(RESTING, compendium.STUDY_OUTCOMES) == "locked"
    # Slow, not refused: the Boggle reached clarity at the 39th study.
    assert classify(DIFFICULT, compendium.STUDY_OUTCOMES) == "studying"
    assert classify(DIFFICULT_ON, compendium.STUDY_OUTCOMES) == "studying"
    assert classify(UNHELD, compendium.STUDY_OUTCOMES) == "unheld"
    assert classify(TURNED.format("Equine"), compendium.TURN_OUTCOMES) == "turned"
    assert classify(MISSING, compendium.TURN_OUTCOMES) == "missing"


def test_a_chart_rests_twenty_minutes_after_clarity():
    compendium.lock("Equine", 1000)
    assert compendium.locked("Equine", 1000 + 19 * 60)
    assert not compendium.locked("Equine", 1000 + 20 * 60)
    assert compendium.next_unlock(["Equine"], 1000 + 5 * 60) == (15 * 60, "Equine")
    assert compendium.next_unlock(["Equine", "Kelpie"], 1000) is None  # one is open


def _script():
    spec = importlib.util.spec_from_file_location(
        "compendium_script", REPO / "scripts/compendium.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Game:
    """The compendium in Cecil's backpack, two charts in it."""

    def __init__(self, s, studies):
        self.s = s
        self.sent = []
        self.studies = {name: list(answers) for name, answers in studies.items()}
        self.page = None

    def __call__(self, s, command):
        self.sent.append(command)
        state = s.state
        if command == "get my compendium":
            state.right_hand = {
                "noun": "compendium",
                "exist": "9",
                "name": "compendium",
            }
            return GOT
        if command == "stow my compendium":
            state.right_hand = None
            return STOWED
        if command == "look my compendium":
            head = LOOK.split("\n   ")[0]
            return head + "\n" + "".join(f"   {name}\n" for name in self.studies)
        if command.startswith("turn my compendium to "):
            word = command.removeprefix("turn my compendium to ")
            for name in self.studies:
                if compendium.index(name) == word:
                    self.page = name
                    return TURNED.format(name)
            return MISSING
        if command == "study my compendium":
            return self.studies[self.page].pop(0)
        return ""


def handle(mindstate=10):
    echoed = []
    state = SimpleNamespace(
        name="Lanival",
        left_hand=None,
        right_hand=None,
        hostiles={},
        experience={
            "First Aid": {"rank": 37, "percent": 0, "mindstate": mindstate},
            "Scholarship": {"rank": 77, "percent": 0, "mindstate": 1},
        },
    )
    return SimpleNamespace(
        name="compendium",
        args=[],
        state=state,
        dead=False,
        echo=echoed.append,
        echoed=echoed,
        sleep=lambda seconds: None,
        waitrt=lambda: None,
        command=lambda timeout=None: None,
    )


def test_each_chart_is_studied_to_clarity_hardest_first_then_the_book_stowed():
    script = _script()
    s = handle()
    game = Game(
        s,
        {
            "Blood Nyad": [BEGIN, CONTINUE, CLARITY],
            "Silver Leucro": [RESTING],  # studied within the last twenty minutes
        },
    )
    script.ask = game
    script.clock = lambda: 5000.0
    why = script.run(s, {"until": 34, "once": True}, {})
    assert game.sent == [
        "get my compendium",
        "look my compendium",
        "turn my compendium to blood nyad",
        "study my compendium",
        "study my compendium",
        "study my compendium",
        "turn my compendium to silver leucro",
        "study my compendium",
        "stow my compendium",
    ]
    assert why.startswith("every chart is resting")
    assert any("Blood Nyad at clarity" in text for text in s.echoed)
    assert "1 chart(s) to clarity in 3 studies" in s.echoed[-1]
    assert s.state.right_hand is None  # stowed at the end


def test_a_chart_studied_with_difficulty_is_studied_on_to_clarity():
    # 2026-10-04: the Boggle, Cougar and Kelpie were skipped as "past your
    # Scholarship" on their first "difficult time" answer; the Boggle
    # then reached clarity at the 39th study by hand.
    script = _script()
    s = handle()
    game = Game(
        s,
        {
            "Blood Nyad": [DIFFICULT, DIFFICULT_ON, CONTINUE, DIFFICULT_ON, CLARITY],
            "Silver Leucro": [RESTING],
        },
    )
    script.ask = game
    script.clock = lambda: 5000.0
    script.run(s, {"until": 34, "once": True}, {})
    assert game.sent.count("study my compendium") == 6  # five on the Nyad, one rest
    assert any("Blood Nyad at clarity" in text for text in s.echoed)
    assert not any("past your Scholarship" in text for text in s.echoed)


def test_a_chart_resting_from_an_earlier_run_is_not_studied_again():
    script = _script()
    compendium.lock("Blood Nyad", 4900.0)  # ten minutes' rest still to go
    s = handle()
    game = Game(s, {"Blood Nyad": [], "Silver Leucro": [FIRST_CLARITY]})
    script.ask = game
    script.clock = lambda: 5000.0
    script.run(s, {"until": 34, "once": True}, {})
    assert "turn my compendium to blood nyad" not in game.sent
    assert "turn my compendium to silver leucro" in game.sent


def test_with_both_hands_full_nothing_is_stowed_to_make_room():
    script = _script()
    s = handle()
    s.state.left_hand = {"noun": "scimitar", "exist": "1", "name": "steel scimitar"}
    s.state.right_hand = {"noun": "shield", "exist": "2", "name": "target shield"}
    game = Game(s, {})
    script.ask = game
    why = script.run(s, {"until": 34, "once": True}, {})
    assert why == "no compendium in hand"
    assert game.sent == []
    assert any("both hands are full" in text for text in s.echoed)


def test_until_and_once_parse():
    script = _script()
    assert script.parse_args(["until=30", "once"]) == {"until": 30, "once": True}
    assert script.parse_args([]) == {"until": 34, "once": False}


# --- at your level first, the slow ones for Scholarship ---


def test_a_charts_level_is_the_wikis_rank():
    assert compendium.level("Blood Nyad") == 70  # dr-scripts' 35
    assert compendium.level("Boggle") == 90
    assert compendium.level("Human") == 100
    assert compendium.level("Snow Goblin") == 120  # the scales meet past the races
    assert compendium.level("Mystery Beast") is None


def test_at_level_charts_go_first_while_first_aid_has_room():
    names = ["Boggle", "Blood Nyad", "Equine"]
    # Scholarship 77: the Boggle (90) is slow, the Nyad (70) and Equine (60) at level.
    assert compendium.choose(names, 0, 77, True, True) == "Blood Nyad"
    # First Aid locked, Scholarship not: the slow chart, every study pays.
    assert compendium.choose(names, 0, 77, False, True) == "Boggle"
    # The at-level ones resting: the slow one fills the time.
    compendium.lock("Blood Nyad", 0)
    compendium.lock("Equine", 0)
    assert compendium.choose(names, 60, 77, True, True) == "Boggle"
    compendium.lock("Boggle", 0)
    assert compendium.choose(names, 60, 77, True, True) is None
    # Neither skill with room: nothing to study.
    assert compendium.choose(["Equine"], 2000, 77, False, False) is None


def test_a_slow_chart_fills_the_time_after_the_at_level_ones():
    script = _script()
    s = handle()
    game = Game(
        s,
        {
            "Boggle": [DIFFICULT, CONTINUE, DIFFICULT_ON, CLARITY],
            "Blood Nyad": [BEGIN, CLARITY],
        },
    )
    script.ask = game
    script.clock = lambda: 5000.0
    script.run(s, {"until": 34, "once": True}, {})
    turns = [command for command in game.sent if command.startswith("turn")]
    assert turns == ["turn my compendium to blood nyad", "turn my compendium to boggle"]
    assert any("Boggle at clarity" in text for text in s.echoed)
    assert any("slow, for the time between: Boggle" in text for text in s.echoed)


def test_a_chart_that_proves_slow_gives_way_to_an_at_level_one():
    # The Glutinous Lipopod looks at level (70 under 77) and goes first,
    # the harder of the two; its first answer is "difficult time", so it
    # is set aside while Equine is open, and finished once Equine rests.
    script = _script()
    s = handle()
    game = Game(
        s,
        {
            "Glutinous Lipopod": [DIFFICULT, CONTINUE, CLARITY],
            "Equine": [BEGIN, CLARITY],
        },
    )
    script.ask = game
    script.clock = lambda: 5000.0
    script.run(s, {"until": 34, "once": True}, {})
    turns = [command for command in game.sent if command.startswith("turn")]
    assert turns == [
        "turn my compendium to glutinous",
        "turn my compendium to equine",
        "turn my compendium to glutinous",
    ]
    assert any("Glutinous Lipopod is slow" in text for text in s.echoed)
    assert any("Glutinous Lipopod at clarity" in text for text in s.echoed)
    assert "Glutinous Lipopod" in compendium._SLOW
    assert "Equine" in compendium._EASY
