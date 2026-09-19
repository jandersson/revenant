"""How ;soul reads and keeps a Paladin's soul — these tests are the
manual. RUB and EXHALE for the readings; the tithe walks to the
almsbox, checks the purse, PUTs 5 silver of the town's coin; the
prayer walks to the altar, stows the hands, prays and stays knelt for
the completion; the quest reads the orb first and runs the scene on
dr-scripts' lines; the timers survive a restart."""

import importlib.util
import pathlib
import time
from types import SimpleNamespace

from client.game import soul
from client.game.mapdb import MapDB

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "soul_script", REPO / "scripts/soul.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()
script.COLLECT_SECONDS = 0.01
script.TAIL_SECONDS = 0.01
script.FOCUS_SECONDS = 0.01
script.GUARD_SECONDS = 0.01
script.SCENE_SECONDS = 3
script.PRAYER_WAIT = 3
LATER = 0.3  # seconds before an answer's second part arrives

MAP = MapDB(
    [
        {
            "id": 2522,
            "uid": [1],
            "title": ["[Shard, Xibar's Crescent Road]"],
            "wayto": {},
        },
        {
            "id": 13143,
            "uid": [9001],
            "title": ["[Temple of Light, Alcove of Smaragdaus]"],
            "tags": ["tithe"],
            "wayto": {},
        },
        {
            "id": 13430,
            "uid": [9002],
            "title": ["[Tower of Honor, Chapel]"],
            "wayto": {},
        },
        {
            "id": 8228,
            "uid": [9003],
            "title": ["[Tower of Honor, Orb Room]"],
            "wayto": {},
        },
    ]
)

# Captured 2026-09-19 in Shard.
RUB_WHITE = "You rub the orb...\nIt warms slightly and turns a steady white hue!\n"
EXHALE_FLICKER = (
    "You breathe softly on the orb...\nYou catch the faintest flicker of light.\n"
)
TITHED = (
    "You drop 5 silver dokoras into the almsbox and say a soft prayer as the coins clink in.\n"
    "A warm, soothing sensation washes over your soul.\n"
)
WEALTH_RICH = "Wealth:\n  No Kronars.\n  No Lirums.\n  1 gold, 1 silver, 5 bronze, and 5 copper Dokoras (1155 copper Dokoras).\n"
WEALTH_POOR = "Wealth:\n  No Kronars.\n  No Lirums.\n  4 silver, 2 bronze, and 7 copper Dokoras (427 copper Dokoras).\n"
PRAYER_BEGUN = (
    "As you kneel down to pray, you feel your head is not cleared enough to pay "
    "proper respect to Chadatru.\n"
)
PRAYER_DONE = (
    "After clearing your thoughts, you pray deeply toward Chadatru. "
    "A warm, soothing sensation washes over your soul.\n"
)
PRAYER_SOON = (
    "You start to pay respect to Chadatru again when you decide it would be "
    "inappropriate so soon.  You decide to wait awhile longer.\n"
)
FOCUS_REST = (
    "You attempt to focus on the orb, but you feel you need to rest and "
    "contemplate a bit first.\n"
)
# dr-scripts' paladin-quests.lic lines: the scene is uncaptured here.
FOCUS_BEGUN = "You clear your mind of all thoughts...\n"
GIRL = (
    "The girl's breath comes in ragged pants, as she desperately flees from her "
    "pursuers.  Her flight has brought her almost past you, and in a few brief "
    "moments she will be past you and beyond help.\n"
)
GUARDED = "Despite the hopelessness of the situation, you step forward.\n"
GIFT = "Go now, and use my gift wisely.\n"


class Fake:
    """A handle whose answers come from a queue per command prefix; the
    story lines of an answer arrive on get() until they run out. An
    answer given as (now, later) delivers `later` only LATER seconds
    after the command — the scene that plays on after the command's
    own answer."""

    def __init__(self, answers, room_uid=1, objs=""):
        self.answers = {k: list(v) for k, v in answers.items()}
        self.sent = []
        self.echoed = []
        self.walks = []
        self.pending = []
        self.later = None  # (monotonic time, lines)
        self.dead = False
        self.args = []
        self.commands = []
        self.state = SimpleNamespace(
            name="Lanival",
            room_uid=room_uid,
            room_title="",
            room_objs=objs,
            left_hand=None,
            right_hand=None,
            hostiles={},
            indicator={"IconSTANDING": "y"},
        )
        self.status = SimpleNamespace(posture="standing")

    def put(self, command):
        self.sent.append(command)
        self.pending = []
        self.later = None
        for prefix, queue in self.answers.items():
            if command == prefix or command.startswith(prefix + " "):
                answer = queue.pop(0) if queue else ""
                now, later = answer if isinstance(answer, tuple) else (answer, "")
                self.pending = [line + "\n" for line in now.splitlines()]
                if later:
                    self.later = (
                        time.monotonic() + LATER,
                        [line + "\n" for line in later.splitlines()],
                    )
                return

    def get(self, timeout=None, streams=("",)):
        if timeout == 0:
            return None
        if not self.pending and self.later and time.monotonic() >= self.later[0]:
            self.pending, self.later = self.later[1], None
        if not self.pending:
            if timeout:
                time.sleep(min(timeout, 0.02))
            return None
        return self.pending.pop(0)

    def command(self, timeout=None):
        return self.commands.pop(0) if self.commands else None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        pass


def walk(s, db, goals, describe="", avoid=()):
    s.walks.append(set(goals))
    room = min(goals)
    s.state.room_uid = db.rooms[room]["uid"][0]
    s.state.room_title = db.rooms[room]["title"][0]
    s.state.room_objs = "a soulstone orb" if room == 8228 else ""
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


def test_a_bare_soul_rubs_and_exhales_the_orb_and_says_both():
    fake = Fake(
        {"rub": [RUB_WHITE], "exhale": [EXHALE_FLICKER]}, objs="a soulstone orb"
    )
    script.run(fake, [])
    assert fake.sent == ["rub orb", "exhale orb"]
    assert "soul: steady white hue (5/7), pool: 2/11" in echoes(fake)


def test_without_an_orb_the_reading_asks_your_soulstone_and_reports_nothing_to_read():
    fake = Fake({"rub": ["What were you referring to?\n"], "exhale": [""]})
    script.run(fake, [])
    assert fake.sent == ["rub my soulstone", "exhale my soulstone"]
    assert "nothing to read here" in echoes(fake)


def test_the_tithe_walks_to_the_almsbox_and_puts_the_towns_coin_in(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 1000.0)
    fake = Fake({"wealth": [WEALTH_RICH], "put": [TITHED]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{13143}]
    assert fake.sent == ["wealth", "put 5 silver dokoras in almsbox"]
    assert "soul: tithed 5 silver dokoras" in echoes(fake)
    assert soul.load_timers("Lanival") == {"tithe": 1000.0}


def test_a_short_purse_skips_the_tithe_and_never_withdraws(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    fake = Fake({"wealth": [WEALTH_POOR]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["wealth"]
    assert "427 copper dokoras on you" in echoes(fake)
    assert not any(c.startswith("withdraw") for c in fake.sent)


def test_the_prayer_stays_knelt_for_the_completion_then_stands(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 2000.0)
    fake = Fake({"pray": [(PRAYER_BEGUN, PRAYER_DONE)], "stow": [""], "stand": [""]})
    fake.state.right_hand = {"noun": "handaxe", "exist": "1", "name": "a handaxe"}
    fake.status.posture = "kneeling"
    script.run(fake, ["pray"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{5845, 13430, 13380, 17046} & set(MAP.rooms)]
    assert fake.sent == ["stow my handaxe", "pray chadatru", "stand"]
    assert "soul: prayed to Chadatru" in echoes(fake)
    assert soul.load_timers("Lanival") == {"pray": 2000.0}


def test_a_prayer_too_soon_backs_off(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 3000.0)
    fake = Fake({"pray": [PRAYER_SOON]})
    script.run(fake, ["pray"], mapdb=MAP, walk_fn=walk)
    assert "too soon" in echoes(fake)
    assert soul.load_timers("Lanival") == {"pray_refused": 3000.0}


def test_the_quest_reads_the_orb_first_and_stops_short_of_pristine():
    fake = Fake({"rub": [RUB_WHITE], "exhale": [EXHALE_FLICKER]})
    script.run(fake, ["quest"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{8228}]
    assert fake.sent == ["rub orb", "exhale orb"]
    assert "wants a pristine soul and a full pool" in echoes(fake)


def test_quest_force_focuses_anyway_and_reads_the_rest_refusal():
    fake = Fake({"rub": [RUB_WHITE], "exhale": [EXHALE_FLICKER], "focus": [FOCUS_REST]})
    script.run(fake, ["quest", "force"], mapdb=MAP, walk_fn=walk)
    assert fake.sent[-1] == "focus orb"
    assert "rest and contemplate" in echoes(fake)


def test_the_scene_guards_the_girl_on_her_line_and_ends_on_the_gift():
    pristine = "You rub the orb...\nIt gleams brightly with a pristine luminescence!\n"
    full = "It brightens with a powerful inner light that, somehow, manages to not cast shadows.\n"
    fake = Fake(
        {
            "rub": [pristine],
            "exhale": [full],
            "focus": [(FOCUS_BEGUN, "A deeply rutted dirt road...\n" + GIRL)],
            "guard": [(GUARDED, GIFT)],
        }
    )
    script.run(fake, ["quest"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["rub orb", "exhale orb", "focus orb", "guard girl"]
    assert "the Glyph of Warding is yours" in echoes(fake)


def test_keep_does_the_due_deeds_and_ends_on_return(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    soul.save_timers(
        "Lanival", {"pray": 5000.0}
    )  # the tithe never done, the prayer just
    monkeypatch.setattr(script, "clock", lambda: 5000.0 + 60)
    fake = Fake({"wealth": [WEALTH_RICH], "put": [TITHED]})
    fake.commands = [None, "return"]  # read on the second loop, after the tithe
    script.run(fake, ["keep"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{13143}]
    assert "put 5 silver dokoras in almsbox" in fake.sent
    assert not any(c.startswith("pray") for c in fake.sent)
    assert "next tithe in 240 min" in echoes(fake)
    assert "stopping as asked" in echoes(fake)
    assert soul.load_timers("Lanival")["tithe"] == 5060.0
