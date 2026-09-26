"""Render the README's LLM-driven screenshot: the game window offscreen,
fed a synthetic session in which Claude drives a character through
revenant-send — every line it sends echoed as ">> [claude] ...", the
scripts it starts answering in the window.

    uv run python tools/claude_screenshot.py [out.png]   (docs/claude-driven.png)

Nothing is live: the window is built around a stub engine and never
shown on screen (WA_DontShowOnScreen — the native platform, so the
OS's own dark theme and fonts render as in play; the offscreen
platform has neither), every file it touches is under a temp
directory (as the GUI suite's conftest does), and the text is the synthetic cast's
(Lanival), shaped on lines captured from ;hunt boxes and ;boxes on
2026-09-26 — no character, account or other player of the operator's
appears. Re-run it when the window's look changes.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = Path(tempfile.mkdtemp(prefix="revenant-shot-"))
for name, file in {
    "REVENANT_LOG_DIR": "logs",
    "REVENANT_SETTINGS": "settings.json",
    "REVENANT_HIGHLIGHTS": "highlights.json",
    "REVENANT_MAPDB": "mapdb.json",
    "REVENANT_MAPDB_LOCAL": "local.json",
    "REVENANT_LOGIN_DEFAULTS": "login.json",
    "REVENANT_SESSIONS": "sessions.json",
    "REVENANT_PROFILES": "profiles",
    "REVENANT_TRAINING": "training",
    "REVENANT_QSETTINGS": "layout.ini",
}.items():
    os.environ[name] = str(TEMP / file)

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDockWidget  # noqa: E402

# (text, stream, style): stream "" is the story, "script" the scripts'
# echoes, "sent" the session's echo of a line sent from outside.
TRANSCRIPT = [
    ("[Farmland, Grain Fields]", "", "roomName"),
    (
        "Tall stalks of grain sway above a trampled patch where something has "
        "been rooting through the dirt.",
        "",
        "",
    ),
    ("Obvious paths: north, east, south, west.", "", ""),
    (">> [claude] ;hunt boxes", "", "sent"),
    ("[hunt] hunt: the boxes style — until boxes", "script", ""),
    ("[hunt] hunt: broadsword for Large Edged (8/34) — to 30", "script", ""),
    (
        "You slice a stout broadsword at a scavenger goblin.  A scavenger goblin "
        "fails to evade.  The broadsword lands a solid hit to the goblin's chest!",
        "",
        "",
    ),
    ("The scavenger goblin slowly tips over and falls down.", "", "bold"),
    ("[hunt] hunt: goblin down (4)", "script", ""),
    ("You search the scavenger goblin.", "", ""),
    ("The goblin was carrying a poorly made iron box!", "", ""),
    ("You pick up a poorly made iron box.", "", ""),
    ("You put your box in your canvas sack.", "", ""),
    ("[hunt] hunt: loot so far — 6 coin pile(s), 2 box(es)", "script", ""),
    (">> [claude] ;hunt return", "", "sent"),
    ("[hunt] hunt: returning on request — 9 kill(s), 9 skin(s)", "script", ""),
    # The walk home: the goblins' farmland, the Crossing's northeast
    # gate, the trail up to the guild (the route of 2026-09-26).
    ("[hunt] walking 38 steps to '11716'", "script", ""),
    ("[Farmland, Open Area]", "", "roomName"),
    ("[The Crossing, Northeast Customs]", "", "roomName"),
    ("[Holy Warrior's Promenade]", "", "roomName"),
    ("[Paladins' Guild, Library]", "", "roomName"),
    ("[hunt] hunt: home at [Paladins' Guild, Library]", "script", ""),
    (">> [claude] ;boxes", "", "sent"),
    ("[boxes] boxes: 2 box(es) in the sack — Locksmithing 0/34", "script", ""),
    (
        "[boxes] boxes: off and stowed: knuckles, gauntlets, shield — worn back "
        "at the end",
        "script",
        "",
    ),
    ("[boxes] boxes: the box's trap is down (careful, read 7/17)", "script", ""),
    ("[boxes] boxes: the box is unlocked (plain, read 6/17)", "script", ""),
    ("[boxes] boxes: the box opened — 3 item(s) out (1 box(es) so far)", "script", ""),
    (
        "[boxes] boxes: the crate opened — 4 item(s) out (2 box(es) so far)",
        "script",
        "",
    ),
    (
        "[boxes] boxes: every box tried — 2 opened, 0 kept for a better locksmith",
        "script",
        "",
    ),
    (">> [claude] wealth", "", "sent"),
    ("Wealth:", "", ""),
    ("  11 silver, 4 bronze, and 7 copper Kronars (1147 copper Kronars).", "", ""),
]


# The exp window as the engine writes it (core.py): a clear, then one
# line per learning skill.
EXPERIENCE = [
    ("Large Edged", 5, 42, "thinking"),
    ("Small Blunt", 19, 26, "mind lock"),
    ("Locksmithing", 14, 35, "considering"),
    ("Holy Magic", 90, 27, "very engaged"),
    ("Augmentation", 86, 12, "learning"),
    ("Evasion", 61, 8, "focused"),
    ("Skinning", 23, 51, "perusing"),
]
SPELLS = [("Heroic Strength", 18), ("Aspirant's Aegis", 5), ("Courage", 6)]
# Docks with nothing to show in a synthetic session, hidden for the shot.
HIDDEN_DOCKS = (
    "Thoughts",
    "Arrivals",
    "Deaths",
    "Group",
    "Attention",
    "Map",
    "Injuries",
    "Compass",
)


class StubEngine:
    """What ClientGUI needs of an engine; read() ends the reader thread."""

    description = "synthetic session"

    def __init__(self):
        self.connection = None

    def connect(self):
        pass

    def read(self, output_callback):
        raise EOFError


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "docs" / "claude-driven.png"
    app = QApplication.instance() or QApplication(["revenant-shot"])
    from client.gui.client_gui import ClientGUI

    window = ClientGUI(StubEngine(), character="Lanival")
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.resize(1440, 640)
    window.show()
    now = int(time.time())
    window.dispatch_game_text("health 100 mana 84 stamina 97 spirit 100", "vitals", "")
    window.dispatch_game_text("n e s w", "compass", "")
    window.dispatch_game_text("IconSTANDING", "indicators", "")
    window.dispatch_game_text(f"{now + 4}\t{now}", "roundtime", "")
    window.dispatch_game_text("", "exp", "clear")
    for skill, rank, percent, rate in EXPERIENCE:
        line = f"{skill:<18} {rank:>5} {percent:>3}%  {rate}\n"
        window.dispatch_game_text(line, "exp", "")
    # One frame carries the whole running set, a line per spell.
    frame = "\n".join(f"{name}\t{minutes}" for name, minutes in SPELLS)
    window.dispatch_game_text(frame, "spells", "")
    for text, stream, style in TRANSCRIPT:
        window.dispatch_game_text(text + "\n", stream, style)
    for dock in window.findChildren(QDockWidget):
        if dock.windowTitle() in HIDDEN_DOCKS:
            dock.hide()
    thread = window._reader_thread
    if thread is not None:
        thread.join(timeout=5)  # the stub's EOF: its "Disconnected" first
    for _ in range(20):
        app.processEvents()
        time.sleep(0.05)
    window.status_bar.showMessage("Connected (attached to 127.0.0.1:4242)")
    # The window restores its default geometry once shown: size it last.
    window.showNormal()
    window.resize(1440, 760)
    for _ in range(10):
        app.processEvents()
        time.sleep(0.05)
    window.grab().save(str(out))
    print(f"wrote {out}")
    window._detaching = True
    window.close()
    window.deleteLater()
    app.processEvents()


if __name__ == "__main__":
    main(sys.argv)
