"""A terminal frontend attached to a running session:  revenant-tui

    revenant-tui [character] [--attach HOST:PORT]

Plays the game from a terminal the way the GUI does from a window: it
attaches to the session (the launcher's registry finds the character's
port, or --attach names one), renders every stream into one scrolling
log with the game's styles and your highlight rules, and sends what
you type. Docked streams (thoughts, spells, arrivals, deaths, the exp
dashboard) appear inline with a [stream] prefix. The status bar shows
the character, the room, the vitals, posture and badges, and the
roundtime counting down. Up/Down browse the command history. Ctrl+Q
detaches - the session and the character stay in the game, exactly
like File -> Detach; type quit to log out.

Built on Textual; the rendering rules live in the toolkit-free
client/textstyle.py with their tests. It never logs in by itself: with
no session running it says so and points at `revenant` (#57).
"""

import argparse
import sys
from threading import Thread
from time import time

from client import reader
from client.client_logger import ClientLogger
from client.command_history import CommandHistory
from client.highlights import load_rules
from client.sendcmd import resolve_port
from client.session import DEFAULT_HOST, AttachedEngine
from client.streamroute import clears_window, window_title
from client.textstyle import Status, render


def _to_app(app, fn, *args):
    """Run fn on the app's thread; nothing when the app has already
    exited (the reader thread outlives a detach by a moment)."""
    try:
        app.call_from_thread(fn, *args)
    except RuntimeError:
        pass


def _rich_style(bold, color, link):
    parts = []
    if bold:
        parts.append("bold")
    if color:
        parts.append(color)
    if link:
        parts.append("underline")
    return " ".join(parts)


class RevenantTUI(ClientLogger):
    """The Textual app, built lazily so importing this module never
    needs the toolkit (tests import the rendering rules only)."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.engine = AttachedEngine(host, port)
        self.status = Status()
        self.history = CommandHistory()
        self.rules = load_rules()
        self.rt_end = 0.0
        self.partial = {}

    def build(self):
        from rich.text import Text
        from textual.app import App
        from textual.widgets import Input, RichLog, Static

        outer = self

        class TUI(App):
            BINDINGS = [("ctrl+q", "quit", "Detach")]
            CSS = """
            RichLog { height: 1fr; }
            #status { height: 1; background: $panel; color: $text; }
            Input { dock: bottom; }
            """

            def compose(self):
                yield RichLog(id="log", wrap=True, markup=False, highlight=False)
                yield Static("connecting ...", id="status")
                yield Input(placeholder="type a command; Ctrl+Q detaches", id="input")

            def on_mount(self):
                self.query_one("#input", Input).focus()
                self.set_interval(1.0, self.tick)
                outer.start_reader(self)

            def on_unmount(self):
                outer.detach()  # ends the reader thread; the session lives on

            def on_input_submitted(self, event):
                text = event.value
                event.input.value = ""
                outer.history.record(text)
                outer.send(text)
                self.append(f"> {text}\n", "", "sent")

            def on_key(self, event):
                if event.key not in ("up", "down"):
                    return
                box = self.query_one("#input", Input)
                shown = (
                    outer.history.previous(box.value)
                    if event.key == "up"
                    else outer.history.next()
                )
                if shown is not None:
                    box.value = shown
                    box.cursor_position = len(shown)
                event.prevent_default()

            def append(self, text, stream, style):
                if style == "clear":
                    if clears_window(stream):
                        self.query_one("#log", RichLog).clear()
                    return
                if outer.status.feed(text, stream):
                    self.refresh_status()
                    return
                if stream in ("roundtime", "casttime"):
                    outer.note_roundtime(text)
                    self.refresh_status()
                    return
                if stream == "bell":
                    self.bell()
                    return
                if stream in ("compass", "timesync"):
                    return
                title = window_title(stream)
                prefix = f"[{title.lower()}] " if title else ""
                line = Text()
                if prefix and stream not in outer.partial:
                    line.append(prefix, "dim")
                for piece, bold, color, link in render(text, style, outer.rules):
                    line.append(piece, _rich_style(bold, color, link))
                # A line arrives as several segments, only the last with
                # the newline; RichLog writes whole lines, so glue them.
                held = outer.partial.pop(stream, None)
                if held is not None:
                    held.append_text(line)
                    line = held
                if text.endswith("\n"):
                    line.rstrip()
                    self.query_one("#log", RichLog).write(line)
                else:
                    outer.partial[stream] = line

            def tick(self):
                if outer.rt_end:
                    self.refresh_status()

            def refresh_status(self):
                remaining = max(0, round(outer.rt_end - time())) if outer.rt_end else 0
                self.query_one("#status", Static).update(outer.status.line(remaining))

            def note_status(self, message):
                outer.status.connection = message
                self.refresh_status()

        return TUI()

    def note_roundtime(self, text):
        try:
            end, server_now = (int(part) for part in text.split("\t"))
        except ValueError:
            return
        self.rt_end = time() + max(0, end - server_now)

    def send(self, text):
        connection = self.engine.connection
        if connection is None:
            return
        try:
            connection.write((text + "\n").encode("ASCII", "replace"))
        except OSError:
            self.status.connection = "connection lost — reattaching"

    def start_reader(self, app):
        self.engine.connect()
        self.status.connection = f"attached to {self.host}:{self.port}"
        app.refresh_status()

        def output_loop():
            reader.pump(
                lambda: self.engine.read(
                    output_callback=lambda text, stream, style: _to_app(
                        app, app.append, text, stream, style
                    )
                ),
                lambda message: _to_app(app, app.note_status, message),
                self.log,
            )

        Thread(target=output_loop, daemon=True).start()

    def detach(self):
        """Close our end of the session connection: the reader thread
        sees EOF and stops; the session and the character carry on."""
        connection = self.engine.connection
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

    def run(self):
        self.build().run()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="revenant-tui", description=__doc__)
    parser.add_argument("character", nargs="?", help="whose session to attach to")
    parser.add_argument("--attach", metavar="HOST:PORT", help="a session address")
    args = parser.parse_args(argv)
    host, port = DEFAULT_HOST, None
    if args.attach:
        host, _, port_text = args.attach.rpartition(":")
        host = host or DEFAULT_HOST
        port = int(port_text)
    else:
        port, why = resolve_port(args.character, host=host)
        if port is None:
            print(f"revenant-tui: {why}; start one with: revenant", file=sys.stderr)
            return 1
    RevenantTUI(host, port).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
