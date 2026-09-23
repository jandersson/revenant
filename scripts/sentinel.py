"""Watch for what an unattended session cannot answer:  ;sentinel  (autostarted)

    ;sentinel                 watch (autostarted; off with the Settings tick or REVENANT_NO_SENTINEL=1)
    ;sentinel ok              (typed while it runs) I am here — the grace ends, the watch goes on
    ;sentinel quiet 30        no alerts for 30 minutes (you are at the keyboard)
    ;sentinel grace 5         a five-minute grace from now on, this run
    ;sentinel status          what it has flagged and where the grace stands
    ;sentinel return          (typed while it runs) stop watching

Every line the game sends goes through client/game/novelty.py (after
dr-scripts' status-monitor.lic — the detection, never its auto-reply).
What rings the bell three times, echoes SENTINEL: in every window and
starts the grace: a player or GM — a bare name, never an NPC with an
article ("A young sacristan says to you, ...") and never one of your
own characters from ~/.revenant/login.json — whispering, speaking,
thinking or gesturing to you; a word spelled to slip past a script
("J_u_M_p", "jUmP"); the same line more than four times in the last
twenty, or six near-duplicates within ninety seconds (status-monitor's
thresholds). What rings once and lands in the Attention dock without a
grace: a staff notice for this instance on the `ooc` stream ("TWEET: ...
#drprime", a calendar notice aside) and a player arriving in the room.
Every other story line never seen before lands in the Attention dock
once and is remembered (`~/.revenant/sentinel/<name>.json`, numerals
and currency words scrubbed, lines naming a player present skipped,
the room's exits and company never news).

The alert also runs settings.json's `alert_command` with the alert as
its last argument — a toast, a mail, a bot; empty runs nothing — and
the grace is `sentinel_grace_minutes` (10): `;sentinel ok` within it and
the watch goes on; unanswered, with `sentinel_logout` on, ;train gets
its return word (the running task finishes and walks home, up to five
minutes), then QUIT — the character is off the board rather than
answered for, the way ;deathwatch keeps a body. No canned reply and no
execution of the commands it finds: those exist to pass a presence
check with nobody home, which is what closes accounts (#276).
Stop with:  ;stop sentinel, or ;sentinel return.
"""

import os
import shlex
import subprocess
import time

from client.game import novelty
from client.game.novelty import (
    ADDRESS_STREAMS,
    address,
    broadcast,
    hidden_command,
    newcomers,
)

POLL = 1.0
SAVE_EVERY = 300.0
ARRIVAL_WINDOW = 1.5  # story lines this soon after a room frame are its description
BELLS = 3
BELL_GAP = 0.25
TRAIN_RETURN_WAIT = 300.0
DEFAULT_GRACE_MINUTES = 10
# Streams a script never learns anything from: the game's windows and
# the engine's synthetic frames.
NOISE_STREAMS = frozenset(
    {
        "combat",
        "percWindow",
        "logons",
        "death",
        "group",
        "exp",
        "inv",
        "atmospherics",
        "assess",
        "shopWindow",
        "compass",
        "vitals",
        "indicators",
        "character",
        "timesync",
        "roundtime",
        "casttime",
        "bell",
        "spells",
        "injuries",
        "shutdown",
        "attached",
        "attention",
        "sent",
        "chatter",
    }
)


def settings_of():
    from client.settings import load_settings

    try:
        return load_settings() or {}
    except Exception:  # noqa: BLE001 — a broken file is no reason to stop watching
        return {}


def own_characters(name):
    """The operator's own characters, this one included."""
    from client.engine.login import load_login_defaults

    names = []
    try:
        names = novelty.own_names(load_login_defaults())
    except Exception:  # noqa: BLE001
        names = []
    if name and name not in names:
        names.append(name)
    return names


class Watch:
    def __init__(self, s, settings, store, own):
        self.s = s
        self.settings = settings
        self.store = store
        self.own = own
        self.buffers = {}  # stream -> the piece of a line still coming
        self.arrived_at = 0.0
        self.players = list(getattr(s.state, "room_players", None) or [])
        self.quiet_until = 0.0
        self.grace_until = None
        self.grace_reason = ""
        self.grace_minutes = float(
            settings.get("sentinel_grace_minutes") or DEFAULT_GRACE_MINUTES
        )
        self.alerts = 0
        self.flagged = 0
        self.saved_at = time.time()
        self.command_failed = False

    # -- output ---------------------------------------------------------

    def say(self, text):
        self.s.echo(f"SENTINEL: {text}")

    def note(self, text):
        self.s.emit(f"{text}\n", "attention")
        self.flagged += 1

    def ring(self, times):
        for i in range(times):
            self.s.emit("", "bell")
            if i + 1 < times:
                self.s.sleep(BELL_GAP)

    def hand_off(self, text):
        """settings.json's alert_command with the alert as its last
        argument, fire-and-forget; a failure is said once."""
        command = str(self.settings.get("alert_command") or "").strip()
        if not command or self.command_failed:
            return
        try:
            words = shlex.split(command, posix=os.name != "nt")
            subprocess.Popen(
                words + [text],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, ValueError) as error:
            self.command_failed = True
            self.say(f"alert_command failed ({error}) — not tried again this run")

    def alert(self, kind, text, now):
        """The escalating alert: bells, the echo, the hand-off, the
        grace — unless the watch is quiet."""
        self.alerts += 1
        line = f"{kind}: {text}"
        self.note(f"! {line}")
        if now < self.quiet_until:
            return
        self.ring(BELLS)
        if self.grace_until is None:
            self.grace_until = now + self.grace_minutes * 60
            self.grace_reason = line
            self.say(
                f"{line} — type ;sentinel ok within {self.grace_minutes:g} min "
                f"or the session ends"
            )
        else:
            self.say(line)
        self.hand_off(line)

    # -- the lines ------------------------------------------------------

    def lines_from(self, stream, text):
        """Whole lines out of the stream's pieces: a piece ending in a
        newline completes one, the rest waits for the next piece."""
        pending = self.buffers.get(stream, "") + text
        lines = pending.split("\n")
        self.buffers[stream] = lines.pop()
        return [line.rstrip("\r") for line in lines]

    def handle(self, stream, line, now):
        if stream == "room":
            self.arrived_at = now
            return
        if stream in NOISE_STREAMS:
            return
        if stream == "ooc":
            if broadcast(line, stream):
                self.note(f"broadcast: {line.strip()}")
                self.ring(1)
            return
        kind = address(line, stream, ignore=self.own)
        if kind:
            self.alert(kind, line.strip(), now)
            return
        if stream in ADDRESS_STREAMS:
            word = hidden_command(line)
            if word:
                self.alert("hidden command", f"{word!r} in {line.strip()!r}", now)
                return
        if stream != "":
            return
        if now - self.arrived_at < ARRIVAL_WINDOW:
            return
        verdict = self.store.observe(line, now, names=self.players)
        if verdict is None:
            return
        what, detail = verdict
        if what == "new":
            self.note(detail)
        else:
            self.alert("spam", detail, now)

    def watch_players(self, now):
        current = list(getattr(self.s.state, "room_players", None) or [])
        arrived = [
            name for name in newcomers(self.players, current) if name not in self.own
        ]
        self.players = current
        if arrived and now >= self.quiet_until:
            self.note(f"arrived: {', '.join(arrived)}")
            self.ring(1)

    # -- the grace and its end ------------------------------------------

    def check_grace(self, now):
        if self.grace_until is None or now < self.grace_until:
            return False
        self.grace_until = None
        if not self.settings.get("sentinel_logout", True):
            self.say(
                f"no answer to {self.grace_reason!r} — staying (sentinel_logout off)"
            )
            return False
        self.end_session()
        return True

    def end_session(self):
        s = self.s
        self.say(f"no answer to {self.grace_reason!r} — ending the session")
        if s.is_running("train"):
            self.say("telling ;train to return — the task finishes and walks home")
            s.tell("train", "return")
            deadline = time.time() + TRAIN_RETURN_WAIT
            while s.is_running("train") and time.time() < deadline:
                s.sleep(2)
            if s.is_running("train"):
                self.say("the training loop is still going — stopping it")
                s.kill("train")
        self.say("QUIT — log back in when you are there")
        s.put("quit")

    # -- commands -------------------------------------------------------

    def command(self, line, now):
        """A typed ;sentinel <word>: True when the watch should end."""
        words = str(line or "").split()
        head = words[0].lower() if words else ""
        if head == "return":
            return True
        if head == "ok":
            if self.grace_until is None:
                self.say("noted — no grace was running")
            else:
                self.say("noted — the grace is off, watching on")
            self.grace_until = None
            return False
        if head == "quiet":
            minutes = 30.0
            if len(words) > 1:
                try:
                    minutes = max(0.0, float(words[1]))
                except ValueError:
                    pass
            self.quiet_until = now + minutes * 60
            self.grace_until = None
            self.say(f"quiet for {minutes:g} min — the dock still fills, no bells")
            return False
        if head == "grace":
            if len(words) > 1:
                try:
                    self.grace_minutes = max(0.5, float(words[1]))
                except ValueError:
                    pass
            self.say(f"the grace is {self.grace_minutes:g} min")
            return False
        if head == "status":
            self.status(now)
            return False
        self.say("words: ok, quiet [minutes], grace <minutes>, status, return")
        return False

    def status(self, now):
        parts = [
            f"{self.flagged} line(s) flagged, {self.alerts} alert(s), "
            f"{len(self.store.seen) + len(self.store.fresh)} line(s) remembered"
        ]
        if self.grace_until is not None:
            left = max(0, int(self.grace_until - now))
            parts.append(
                f"grace running: {left // 60}:{left % 60:02d} left ({self.grace_reason})"
            )
        if now < self.quiet_until:
            parts.append(f"quiet for {int((self.quiet_until - now) // 60)} more min")
        if self.own:
            parts.append(f"ignoring {', '.join(self.own)}")
        self.say("; ".join(parts))

    # -- the loop -------------------------------------------------------

    def save(self, force=False):
        if not self.store.dirty:
            return
        now = time.time()
        if not force and now - self.saved_at < SAVE_EVERY:
            return
        try:
            novelty.save(getattr(self.s.state, "name", None), self.store)
        except OSError as error:
            self.say(f"could not save the seen lines: {error}")
        self.saved_at = now

    def loop(self):
        s = self.s
        while True:
            now = time.time()
            typed = s.command(timeout=0)
            while typed is not None:
                if self.command(typed, now):
                    return
                typed = s.command(timeout=0)
            item = s.get(timeout=POLL, streams=None)
            while item is not None:
                stream, text = item
                for line in self.lines_from(stream, text):
                    self.handle(stream, line, now)
                item = s.get(timeout=0, streams=None)
            self.watch_players(now)
            if self.check_grace(now):
                return
            self.save()


def main(s):
    name = getattr(s.state, "name", None)
    settings = settings_of()
    store = novelty.load(name)
    watch = Watch(s, settings, store, own_characters(name))
    watch.say(
        f"watching — {len(store.seen)} line(s) remembered, grace "
        f"{watch.grace_minutes:g} min, ;sentinel ok answers an alert"
    )
    try:
        watch.loop()
    finally:
        watch.save(force=True)
