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
