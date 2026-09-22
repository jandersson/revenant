"""How ;perform trains — these tests are the manual. It PLAYs the
rank's song off-key on the profile's instrument, keeps the song going,
stops it and holds at mind-lock, and stops the song on a typed return
(#208)."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import perform

REPO = pathlib.Path(__file__).parents[2]


def _script():
    spec = importlib.util.spec_from_file_location(
        "perform_script", REPO / "scripts/perform.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


script = _script()

# Captured 2026-09-18 on copper zills.
STARTED = "You fumble slightly as you begin an off-key ruff on your copper zills.\n"
CONTINUES = "You continue playing on your copper zills.\n"
ALREADY = "You're already playing a song!  You'll need to stop that one first.\n"
STOPPED = "You stop playing your song.\n"
RETREATED = "You stop your performance.\n"  # a RETREAT ended it, 2026-09-18


class Fake:
    """A handle whose Performance mindstate follows a script of values,
    one per second of the fake clock; the story is read a second at a
    time through `collect` (the song plays on, or ran out after
    `ends_after` seconds), a command is answered through `ask`, and a
    typed "return" arrives once the clock reaches `stop_at`."""

    def __init__(
        self, mindstates, rank=2, stop_at=None, ends_after=None, hostiles=None
    ):
        self.mindstates = list(mindstates)
        self.stop_at = stop_at
        self.ends_after = ends_after
        self.stopped = False
        self.now = 1000.0
        self.played_at = None
        self.sent, self.echoed = [], []
        self.dead = False
        self.args = []
        self.state = SimpleNamespace(
            name="Lanival",
            experience={
                "Performance": {
                    "rank": rank,
                    "percent": 0,
                    "mindstate": self.mindstates.pop(0),
                }
            }
            if self.mindstates
            else {},
            hostiles=hostiles or {},
        )

    def _tick(self):
        if self.mindstates and self.state.experience:
            self.state.experience["Performance"]["mindstate"] = self.mindstates.pop(0)

    # --- what the script's probe module does, on the fake clock ---
    def ask(self, s, command, *_):
        self.sent.append(command)
        if command.startswith("play "):
            if self.played_at is not None:
                return ALREADY
            self.played_at = self.now
            return STARTED
        if command == "stop play":
            self.played_at = None
            return STOPPED
        return ""

    def collect(self, s, seconds, until=None):
        self.now += seconds
        self._tick()
        if (
            self.played_at is not None
            and self.ends_after is not None
            and self.now - self.played_at >= self.ends_after
        ):
            self.played_at = None
            return "You finish your song.\n"
        return CONTINUES if self.played_at is not None else ""

    # --- the handle ---
    def put(self, command):
        self.sent.append(command)

    def get(self, timeout=None, streams=("",)):
        return None

    def command(self, timeout=None):
        if self.stop_at is not None and not self.stopped and self.now >= self.stop_at:
            self.stopped = True
            return "return"
        return None

    def echo(self, text):
        self.echoed.append(text)

    def waitrt(self):
        pass

    def sleep(self, seconds):
        self.now += seconds
        self._tick()


def run(fake, args=(), instrument="zills"):
    script.clock = lambda: fake.now
    script.probe = SimpleNamespace(ask=fake.ask, collect=fake.collect)
    extra = [f"instrument={instrument}"] if instrument else []
    script.run(fake, script.parse_args(list(args) + extra))
    return "\n".join(fake.echoed)


def plays(fake):
    return [c for c in fake.sent if c.startswith("play ")]


def test_the_song_follows_the_rank_band():
    assert perform.song_for(0) == "scales"
    assert perform.song_for(39) == "scales"
    assert perform.song_for(40) == "arpeggios"
    assert perform.song_for(99) == "march"
    assert perform.song_for(600) == "concerto"
    assert perform.song_for(None) == "scales"


def test_the_play_line_and_the_args():
    assert perform.play_command("scales", "off-key", "zills") == (
        "play scales off-key on my zills"
    )
    assert perform.play_command("ballad", "", "lyre") == "play ballad on my lyre"
    options = perform.parse_args(["instrument=lyre", "song=ballad", "until=30", "once"])
    assert options == {
        "instrument": "lyre",
        "song": "ballad",
        "mood": "off-key",
        "until": 30,
        "once": True,
    }
    assert perform.parse_args(["mood="])["mood"] == ""


def test_a_retreat_ends_the_song_for_the_watch():
    assert any(word in RETREATED.lower() for word in perform.STOPPED)
    assert any(word in STOPPED.lower() for word in perform.STOPPED)


def test_it_plays_once_and_lets_the_song_run_until_mind_lock():
    fake = Fake(mindstates=[5, 10, 20, 30, 34], stop_at=1000 + 60)
    out = run(fake, ["once"])
    assert plays(fake) == ["play scales off-key on my zills"]
    assert "perform: playing scales off-key on the zills (Performance 5/34)" in out
    assert fake.sent[-1] == "stop play"
    assert "Performance at 34/34 — done" in out
    assert fake.now < 1000 + 10  # the lock was noticed within seconds


def test_a_song_that_ran_out_is_started_again():
    fake = Fake(mindstates=[5] * 40 + [34], ends_after=3, stop_at=1000 + 200)
    run(fake, ["once"])
    assert len(plays(fake)) >= 2
    assert fake.sent[-1] == "stop play"


def test_it_holds_at_the_lock_and_resumes_when_drained():
    # Locked from the start; the pool drains to 27 while held; a song,
    # the lock again, then a typed return ends the hold.
    fake = Fake(mindstates=[34] + [27] * 35 + [34] * 200, stop_at=1000 + 120)
    out = run(fake)
    assert "mind-locked" in out
    assert "drained to 27/34 — playing again" in out
    assert plays(fake) == ["play scales off-key on my zills"]
    assert out.endswith("perform: stopping")


def test_a_typed_return_stops_the_song_and_ends():
    fake = Fake(mindstates=[5] * 50, stop_at=1000 + 10)
    out = run(fake)
    assert fake.sent[-1] == "stop play"
    assert "stopping as asked" in out


def test_hostiles_stop_it_before_a_song():
    fake = Fake(mindstates=[5] * 50, hostiles={"1": True})
    out = run(fake)
    assert "hostiles in the room" in out
    assert plays(fake) == []


def test_the_profiles_instrument_is_the_default(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    from client.game import profile

    profile.save_profile(
        "Lanival", profile.load_profile("Lanival") | {"instrument": "lyre"}
    )
    fake = Fake(mindstates=[5, 34], stop_at=1000 + 60)
    run(fake, ["once"], instrument="")
    assert fake.sent[0] == "play scales off-key on my lyre"


class RefusingHere(Fake):
    """The room refuses the first PLAY (captured 2026-09-20 at the bank's
    teller); after the walk home the song starts."""

    REFUSAL = "You decide that now isn't the best time to be playing, and stop.\n"

    def __init__(self, *args, refusals=1, **kwargs):
        super().__init__(*args, **kwargs)
        self.refusals = refusals

    def ask(self, s, command, *_):
        if command.startswith("play ") and self.refusals:
            self.refusals -= 1
            self.sent.append(command)
            return self.REFUSAL
        return super().ask(s, command, *_)


def test_a_room_that_refuses_the_song_sends_it_home_once(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    from client.game import profile

    profile.save_profile("Lanival", profile.load_profile("Lanival") | {"home": "11716"})

    def drive(fake, walker):
        script.clock = lambda: fake.now
        script.probe = SimpleNamespace(ask=fake.ask, collect=fake.collect)
        script.run(fake, script.parse_args(["once", "instrument=zills"]), walker=walker)

    walks = []
    fake = RefusingHere(mindstates=[5, 34])
    drive(fake, lambda s, home: walks.append(home) or True)
    assert walks == ["11716"]
    assert plays(fake) == ["play scales off-key on my zills"] * 2
    assert any("refuses a song here — walking home (11716)" in t for t in fake.echoed)
    # Refused at home too: the run ends with the reason, no third try.
    twice = RefusingHere(mindstates=[5, 34], refusals=2)
    drive(twice, lambda s, home: True)
    assert len(plays(twice)) == 2
    assert any("and at home too — stopping" in t for t in twice.echoed)
    # No home in the profile: said so, one try.
    profile.save_profile("Lanival", profile.load_profile("Lanival") | {"home": ""})
    none = RefusingHere(mindstates=[5, 34])
    drive(none, lambda s, home: True)
    assert len(plays(none)) == 1
    assert any("names no home — stopping" in t for t in none.echoed)


class InCombat(Fake):
    """Captured 2026-09-20 (#243): the game refused the song for a fight
    the parser had not shown yet, right after a ;reexec."""

    def ask(self, s, command, *_):
        if command.startswith("play "):
            self.sent.append(command)
            return "You cannot use the copper zills while in combat!\n"
        return super().ask(s, command)


def test_the_games_own_combat_refusal_ends_the_run():
    fake = InCombat(mindstates=[5, 5])
    out = run(fake, ["once"])
    assert plays(fake) == ["play scales off-key on my zills"]
    assert "perform: in combat — stopping" in out
    assert "nothing known" not in out
    assert "stop play" not in fake.sent  # nothing was playing


def test_no_instrument_anywhere_is_told_so(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    fake = Fake(mindstates=[5])
    out = run(fake, instrument="")
    assert "no instrument" in out
    assert fake.sent == []


def test_a_guild_without_performance_is_told_so():
    fake = Fake(mindstates=[])
    out = run(fake)
    assert "EXP shows no Performance" in out
    assert fake.sent == ["exp performance"]


# Captured 2026-09-20 on the copper zills (#233): the dirt warning at
# PLAY, CLEAN's two demands, the wipe, the clean, and the zills on and
# off the finger.
DIRTY = "Your zills's dirtiness may affect your performance.\n"
MUST_HOLD = "You must be holding the copper zills to clean them.\n"
REMOVED = "You slide a pair of copper zills off your finger.\n"
WET = (
    "Your copper zills are so wet that they are still dripping!  Maybe you "
    "should dry them off before attempting to clean them.\n"
)
WIPED = (
    "Using your rag, you scrub at your copper zills in attempt to wipe the "
    "water from them.  Your rag soaks up the water easily, but remains "
    "noticably damp afterwards.\n[Roundtime: 4 seconds.]\n"
)
CLEANED = (
    "With sure strokes that display your innate talent, you spend a few "
    "moments cleaning your copper zills.  You manage to clean a very large "
    "amount of dirt and grime from them.\n[Roundtime: 5 seconds.]\n"
)
WORN = "You slide a pair of copper zills onto your finger.\n"
GOT_RAG = "You get a cotton rag from inside your canvas sack.\n"
STOWED_RAG = "You put your rag in your canvas sack.\n"


class DirtyZills(Fake):
    """The first PLAY warns of dirt; CLEAN wants the zills in hand, then
    finds them wet, then cleans them — the captured sequence."""

    def __init__(self, *args, rag=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.rag = rag
        # CLEAN wants the zills held, finds them wet, then takes dirt off
        # three times (one pass left them dirty live, 2026-09-20).
        self.cleans = [MUST_HOLD, WET, CLEANED, CLEANED, CLEANED]
        self.warned = False

    def ask(self, s, command, *_):
        if command.startswith("play ") and not self.warned:
            self.warned = True
            return DIRTY + super().ask(s, command)
        answers = {
            "get my rag": GOT_RAG if self.rag else "What were you referring to?\n",
            "remove my zills": REMOVED,
            "wipe my zills with my rag": WIPED,
            "wear my zills": WORN,
            "stow my rag": STOWED_RAG,
        }
        if command in answers:
            self.sent.append(command)
            return answers[command]
        if command == "clean my zills with my rag":
            self.sent.append(command)
            return self.cleans.pop(0)
        return super().ask(s, command)


def _with_cloth(monkeypatch, tmp_path, cloth):
    monkeypatch.setenv("REVENANT_PROFILES", str(tmp_path))
    from client.game import profile

    profile.save_profile(
        "Lanival", profile.load_profile("Lanival") | {"instrument_cloth": cloth}
    )


def test_a_dirty_instrument_is_cleaned_once_with_the_profiles_cloth(
    monkeypatch, tmp_path
):
    # #233: the game warned of the zills' dirt before every song of an
    # evening and the ranks paid for it. The first warning of a run has
    # the cloth fetched, the song stopped, the zills removed (CLEAN wants
    # them held), wiped (they were wet), cleaned, worn again, the cloth
    # stowed, and the song started over.
    _with_cloth(monkeypatch, tmp_path, "rag")
    fake = DirtyZills(mindstates=[5, 34])
    run(fake, ["once"])
    assert fake.sent[:13] == [
        "play scales off-key on my zills",
        "get my rag",
        "stop play",
        "clean my zills with my rag",
        "remove my zills",
        "clean my zills with my rag",
        "wipe my zills with my rag",
        "clean my zills with my rag",
        "clean my zills with my rag",  # dirt came off: again, three passes in all
        "clean my zills with my rag",
        "wear my zills",
        "stow my rag",
        "play scales off-key on my zills",
    ]
    assert any("zills cleaned with the rag (3 pass(es))" in t for t in fake.echoed)
    assert not any("drop" in c for c in fake.sent)


def test_a_dirty_instrument_plays_on_without_a_cloth(monkeypatch, tmp_path):
    # No cloth in the profile: said once, the song plays dirty.
    _with_cloth(monkeypatch, tmp_path, "")
    fake = DirtyZills(mindstates=[5, 34])
    run(fake, ["once"])
    assert plays(fake) == ["play scales off-key on my zills"]
    assert not any(c.startswith(("clean", "get")) for c in fake.sent)
    assert any(
        "names no cloth (instrument_cloth) — playing on" in t for t in fake.echoed
    )
    # A cloth named but not on you: said, the song plays on unstopped.
    _with_cloth(monkeypatch, tmp_path, "rag")
    gone = DirtyZills(mindstates=[5, 34], rag=False)
    run(gone, ["once"])
    assert gone.sent[:3] == [
        "play scales off-key on my zills",
        "get my rag",
        "stop play",
    ]
    assert plays(gone) == ["play scales off-key on my zills"]
    assert any("no rag on you — the zills plays dirty" in t for t in gone.echoed)


def test_hostiles_have_it_get_away_not_just_stop():
    # #285: the song stops and the character leaves the room.
    fake = Fake(mindstates=[5] * 50, hostiles={"1": True})
    fake.state.compass = ["nw"]
    out = run(fake)
    assert "hostiles in the room" in out
    assert "perform: hostiles here — getting away" in out
    assert fake.sent[-3:] == ["retreat", "retreat", "nw"] or "retreat" in fake.sent
