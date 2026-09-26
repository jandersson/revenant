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
script.BADGE_SECONDS_ANSWER = 0.01
# The waits end on their `until` line, and the fake's second answer
# comes LATER (0.3 s) after the first, so a second is a ceiling only the
# negative cases reach; at 3 s it was the suite's wall (2026-09-20).
script.SCENE_SECONDS = 1.0
script.PRAYER_WAIT = 1.0
LATER = 0.3  # seconds before an answer's second part arrives

MAP = MapDB(
    [
        {
            "id": 2522,
            "uid": [1],
            "title": ["[Shard, Xibar's Crescent Road]"],
            "wayto": {"13143": "east", "13430": "north", "8228": "up"},
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
# The scene, captured 2026-09-19 05:40 (the first accepted FOCUS).
FOCUS_BEGUN = (
    "You clear your mind of all thoughts and focus only on the task ahead.  "
    "Vision fades as darkness slowly overcomes you.\n"
    "You suddenly find yourself in another place...\n"
)
GIRL = (
    "The girl's breath comes in ragged pants, as she desperately flees from her "
    "pursuers.  Her flight has brought her almost past you, and in a few brief "
    "moments she will be past you and beyond help.\n"
)
GUARDED = (
    "Despite the hopelessness of the situation, you move to guard the fleeing "
    "girl, raising your battered old sword in defiance.\n"
)
GIFT = "'Go now, and use my gift to preserve those who have fallen with honor.'\n"


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
    s.state.room_objs = {
        8228: "a soulstone orb",
        815: "You also see a paladin guard and a steel tithe box.",
    }.get(room, "")
    return True


def echoes(fake):
    return "\n".join(fake.echoed)


def test_a_bare_soul_rubs_and_exhales_the_orb_and_says_both(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    fake = Fake(
        {"rub": [RUB_WHITE], "exhale": [EXHALE_FLICKER]}, objs="a soulstone orb"
    )
    script.run(fake, [])
    assert fake.sent == ["rub orb", "exhale orb"]
    assert "soul: steady white hue (5/7), pool: 2/11" in echoes(fake)


def test_without_an_orb_the_reading_asks_your_soulstone_and_reports_nothing_to_read(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    fake = Fake({"rub": ["What were you referring to?\n"], "exhale": [""]})
    script.run(fake, [])  # no map: the soulstone in the pocket is the only try
    assert fake.sent == ["rub my soulstone", "exhale my soulstone"]
    assert "nothing to read here" in echoes(fake)


# The arches' lines: the Crossing guild 2026-09-20, Shard's tower 2026-09-19.
ARCH_PRISTINE = (
    "You step through a shining soulstone archway....\n"
    "The archway gleams with a pristine luminescence in welcome!\n"
)
ARCH_WHITE = (
    "You step through a gleaming soulstone archway....\n"
    "The archway emits a warm, steady white hue!\n"
)


def test_without_an_orb_the_reading_walks_through_the_nearest_arch_and_keeps_the_state(
    monkeypatch, tmp_path
):
    # #231: the Crossing guild has no orb; the soulstone arch answers the
    # state in the RUB's words, the pool has no reading there.
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 1000.0)
    fake = Fake({"go": [ARCH_PRISTINE]})
    script.run(fake, [], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{2522}]  # Xibar's Crescent Road: `go tower` is the arch
    assert fake.sent == ["go tower"]
    assert "(7/7) (the arch; the pool wants an orb" in echoes(fake)
    assert soul.load_timers("Lanival") == {"read": 1000.0, "state": 7}
    # An arch that answers nothing the table knows is a refusal: backoff.
    silent = Fake({"go": ["You can't go there.\n"]})
    script.run(silent, [], mapdb=MAP, walk_fn=walk)
    assert "nothing the table knows" in echoes(silent)
    assert soul.load_timers("Lanival")["read_refused"] == 1000.0


def test_keep_reads_the_state_first_and_skips_every_deed_while_pristine(
    monkeypatch, tmp_path
):
    # The operator, 2026-09-20: a pristine soul wants no deeds.
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 5000.0)
    soul.save_timers("Lanival", {})  # no reading, every deed due
    fake = Fake({"go": [ARCH_PRISTINE]})
    fake.commands = [None, "return"]
    script.run(fake, ["keep"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["go tower"]  # no badge, no tithe, no prayer
    assert "soul: pristine — no deeds needed" in echoes(fake)
    assert soul.load_timers("Lanival") == {"read": 5000.0, "state": 7}
    # Below pristine the deeds run as before (the tithe here).
    monkeypatch.setattr(script, "clock", lambda: 9000.0)
    soul.save_timers("Lanival", {"badge": 9000.0, "pray": 9000.0})
    fake = Fake({"go": [ARCH_WHITE], "wealth": [WEALTH_RICH], "put": [TITHED]})
    fake.commands = [None, "return"]
    script.run(fake, ["keep"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["go tower", "wealth", "put 5 silver dokoras in almsbox"]
    assert soul.load_timers("Lanival")["state"] == 5


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


def test_the_crossing_guilds_tithe_box_takes_kronars_in_box(monkeypatch, tmp_path):
    # Herald Street outside the Paladins' Guild (map 815), read 2026-09-20:
    # "a steel tithe box" whose inscription says PUT ... KRONARS IN BOX.
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 1000.0)
    crossing = MapDB(
        [
            {
                "id": 815,
                "uid": [10078],
                "title": ["[The Crossing, Herald Street]"],
                "wayto": {"814": "south"},
            },
            {"id": 814, "uid": [10079], "title": ["[The Crossing, Herald Street]"]},
        ]
    )
    rich = "Wealth:\n  1 gold, 1 silver, 5 bronze, and 5 copper Kronars (1155 copper Kronars).\n  No Lirums.\n  No Dokoras.\n"
    tithed = TITHED.replace("dokoras", "kronars").replace("almsbox", "box")
    fake = Fake(
        {"wealth": [rich], "put": [tithed]},
        room_uid=10078,
        objs="You also see a paladin guard and a steel tithe box.",
    )
    script.run(fake, ["tithe"], mapdb=crossing, walk_fn=walk)
    assert fake.walks == [{815}]
    assert fake.sent == ["wealth", "put 5 silver kronars in box"]
    assert "soul: tithed 5 silver kronars" in echoes(fake)


def test_a_short_purse_skips_the_tithe_and_never_withdraws(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    fake = Fake({"wealth": [WEALTH_POOR]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["wealth"]
    assert "427 copper dokoras on you" in echoes(fake)
    assert not any(c.startswith("withdraw") for c in fake.sent)
    # The short purse counts as a refusal: keep backs off instead of
    # asking WEALTH every second (2026-09-19).
    assert "tithe_refused" in soul.load_timers("Lanival")


# #304: WEALTH with a debt to the province, in the shape captured
# 2026-09-21 (#266), the almsbox's coin owed.
WEALTH_OWING = (
    "Debt:\n  You owe 1 silver, 6 bronze and 8 copper Dokoras to the Principality "
    "of Ilithi. (168 copper Dokoras)\n\n" + WEALTH_RICH
)
TITHE_DEBT_LINE = (
    "That's very altruistic, but you should really pay off your debt before "
    "making any donations.\n"
)


def test_a_debt_to_the_province_skips_the_tithe_and_says_debt_pays_it(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 1000.0)
    fake = Fake({"wealth": [WEALTH_OWING]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["wealth"]  # no PUT the box would refuse
    assert "you owe the province 168 copper dokoras" in echoes(fake)
    assert ";debt pays it" in echoes(fake)
    timers = soul.load_timers("Lanival")
    assert timers["tithe_debt"] == "dokoras"
    assert timers["tithe_refused"] == 1000.0


def test_a_standing_debt_costs_no_walk_to_the_almsbox(monkeypatch, tmp_path):
    # 2026-09-24: every rest walked 38 steps to the box to be refused.
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    soul.save_timers("Lanival", {"tithe_debt": "dokoras"})
    fake = Fake({"wealth": [WEALTH_OWING]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == []
    assert fake.sent == ["wealth"]
    assert "you owe" not in echoes(fake)  # said once, when first found


def test_a_paid_debt_clears_the_mark_and_the_tithe_goes_ahead(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 1000.0)
    soul.save_timers("Lanival", {"tithe_debt": "dokoras"})
    fake = Fake({"wealth": ["Debt:\n  No debt.\n\n" + WEALTH_RICH], "put": [TITHED]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert fake.walks == [{13143}]
    assert fake.sent == ["wealth", "put 5 silver dokoras in almsbox"]
    assert soul.load_timers("Lanival") == {"tithe": 1000.0}


def test_the_almsbox_naming_a_debt_reads_as_debt_not_unknown(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    fake = Fake({"wealth": [WEALTH_RICH], "put": [TITHE_DEBT_LINE]})
    script.run(fake, ["tithe"], mapdb=MAP, walk_fn=walk)
    assert "unknown answer" not in echoes(fake)
    assert ";debt pays it" in echoes(fake)
    assert soul.load_timers("Lanival")["tithe_debt"] == "dokoras"


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
    # The tithe never done; the prayer and the badge just; the soul read
    # steady white a minute ago (below pristine: the deeds run).
    soul.save_timers(
        "Lanival", soul.mark_state({"pray": 5000.0, "badge": 5000.0}, 5, 5000.0)
    )
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


# --- the pilgrim's badge (captured 2026-09-20 with four sites on it) ------
BADGE_DONE = (
    "As you feel your connection to them grow, you sense the eyes of the gods upon you.\n"
    "Roundtime: 10 sec.\n"
    "A warm, soothing sensation washes over your soul.\n"
    "You feel a strengthening of your faith and bolstering of your soul.\n"
)
BADGE_EMPTY = (
    "You think really hard about your badge.  It doesn't do anything though.\n"
)


def test_the_badge_deed_removes_prays_and_wears(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 7000.0)
    fake = Fake(
        {
            "remove": ["You remove a pilgrim's badge.\n"],
            "pray": [BADGE_DONE],
            "wear": [""],
        }
    )
    script.run(fake, ["badge"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["remove my badge", "pray badge", "wear my badge"]
    assert "soul: prayed on the badge" in echoes(fake)
    assert soul.load_timers("Lanival") == {"badge": 7000.0}


def test_a_badge_in_the_sack_is_fetched_and_an_empty_one_said(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 7000.0)
    fake = Fake(
        {
            "remove": ["What were you referring to?\n"],  # in the sack, not worn
            "get": ["You get a pilgrim's badge.\n"],
            "pray": [BADGE_EMPTY],
            "wear": [""],
        }
    )
    script.run(fake, ["badge"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == [
        "remove my badge",
        "get my badge",
        "pray badge",
        "wear my badge",
    ]
    assert "PUSH an attuned altar WITH BADGE first" in echoes(fake)


def test_no_badge_turns_the_deed_off_for_the_run(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    none = Fake(
        {
            "remove": ["What were you referring to?\n"],
            "get": ["What were you referring to?\n"],
        }
    )
    script.run(none, ["badge"], mapdb=MAP, walk_fn=walk)
    assert none.sent == ["remove my badge", "get my badge"]
    assert "no pilgrim's badge on you" in echoes(none)


def test_a_badge_prayer_within_its_timer_is_said_and_backed_off(monkeypatch, tmp_path):
    # Captured 2026-09-20, nine minutes after a boost: the contemplation
    # without the soul line.
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 9000.0)
    soon = (
        "You think upon the Immortals, and the holy places built in their honor by "
        "mortals who have heard them speak, or seen the power of their beings.\n"
        "As you feel your connection to them grow, you sense the eyes of the gods upon you.\n"
    )
    fake = Fake(
        {"remove": ["You remove a pilgrim's badge.\n"], "pray": [soon], "wear": [""]}
    )
    script.run(fake, ["badge"], mapdb=MAP, walk_fn=walk)
    assert "timer has not cleared" in echoes(fake)
    assert soul.load_timers("Lanival") == {"badge_refused": 9000.0}


def test_keep_prays_on_the_badge_when_its_timer_allows(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    soul.save_timers(  # only the badge due, the soul read below pristine
        "Lanival", soul.mark_state({"tithe": 5000.0, "pray": 5000.0}, 5, 5000.0)
    )
    monkeypatch.setattr(script, "clock", lambda: 5000.0 + 60)
    fake = Fake(
        {
            "remove": ["You remove a pilgrim's badge.\n"],
            "pray": [BADGE_DONE],
            "wear": [""],
        }
    )
    fake.commands = [None, "return"]
    script.run(fake, ["keep"], mapdb=MAP, walk_fn=walk)
    assert fake.sent == ["remove my badge", "pray badge", "wear my badge"]
    assert "badge in 31 min" in echoes(fake)
    assert soul.load_timers("Lanival")["badge"] == 5060.0


def test_a_deed_room_across_the_world_is_skipped_not_walked_to(monkeypatch, tmp_path):
    # A keep in the Crossing must not set off for Shard's almsbox
    # (2026-09-20): farther than MAX_STEPS is skipped and backed off,
    # and so is an almsbox the map cannot reach at all.
    monkeypatch.setenv("REVENANT_SOUL_DIR", str(tmp_path))
    monkeypatch.setattr(script, "clock", lambda: 8000.0)
    monkeypatch.setattr(script, "MAX_STEPS", 0)
    far = MapDB(
        [
            {"id": 1, "uid": [1], "title": ["[A]"], "wayto": {"13143": "north"}},
            {
                "id": 13143,
                "uid": [9001],
                "title": ["[Temple of Light, Alcove of Smaragdaus]"],
                "tags": ["tithe"],
            },
        ]
    )
    fake = Fake({"wealth": [WEALTH_RICH]}, room_uid=1)
    script.run(fake, ["tithe"], mapdb=far, walk_fn=walk)
    assert fake.walks == [] and fake.sent == []
    assert "1 rooms away" in echoes(fake) and "skipping it" in echoes(fake)
    assert "tithe_refused" in soul.load_timers("Lanival")
    cut = MapDB(
        [
            {"id": 1, "uid": [1], "title": ["[A]"]},
            {"id": 13143, "uid": [9001], "title": ["[Alcove]"], "tags": ["tithe"]},
        ]
    )
    lost = Fake({"wealth": [WEALTH_RICH]}, room_uid=1)
    script.run(lost, ["tithe"], mapdb=cut, walk_fn=walk)
    assert "unreachable" in echoes(lost) and lost.walks == []
