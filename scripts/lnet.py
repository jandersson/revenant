"""LNet chat in the Thoughts window, 1:1 with lich's lnet:  ;lnet

Start with ;lnet (or just use a command — it starts on demand), then:

  ;chat <message>                   send to your default channel
  ;chat on <channel> <message>      send to a channel   (;chat :<channel> too)
  ;chat to <name> <message>         private message     (;chat ::<name> too)
  ;reply <message>                  answer the last private message
    (the first private from anyone shows this hint; a name you have heard
    from this session may be typed without the server's DR: prefix or case)
  ;who [name]                       who is connected
  ;stats                            server statistics
  ;channels [all]                   list channels (top 15, or all)
  ;tune <channel>  /  ;untune <channel>

Incoming chat renders in Thoughts the way lich did: [Channel]-Name: "msg",
[Private]-Name for tells, your own reflected sends as [PrivateTo]-Name.
Identity is your character (override LNET_NAME); the password comes from
the OS keychain (service "revenant-lnet", set by File → LNet
Password… in the game window, the standalone chat window's remember
checkbox, or `keyring set revenant-lnet <Name>`),
LNET_PASSWORD for one run, or the legacy git-ignored
chat/lnet_password.txt. A connection the server closes is logged in
again after 30 s, then 1, 2, 4 and 5 minutes; a rejected login ends it.
Stop: ;stop lnet

The same grammar and dispatcher (chat/commands.py) drive the standalone
window, `revenant-chat`, which needs no game session at all (#141).
"""

import os
import socket
import sys
from pathlib import Path

# chat/ lives at the repo root, not in client/: reachable from a session
# started at the root, made so for one started elsewhere.
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from chat.commands import obey as _obey  # noqa: E402
from chat.commands import parse  # noqa: E402,F401 -- the grammar, tested here
from chat.commands import remember_sender, reply_hint  # noqa: E402

RECV_TIMEOUT = 0.25  # also the user-command poll cadence
# The server closes the connection now and then — Mondays at 13:29 UTC
# on 2026-09-21 and 09-28, a ping due and never sent — and the script
# used to end there (#371). It logs in again after these waits, the
# last repeating; a login that got through starts them over.
RECONNECT_WAITS = (30, 60, 120, 240, 300)


def say(s, text):
    """A status line — no password stored, logging in, connected, the
    login rejected — in the main window and, as the chat window
    would print it, in Thoughts, where the chat lands and the eye is
    (the operator, 2026-09-22: an autostarted ;lnet's rejection went
    unseen in the story)."""
    s.echo(text)
    s.emit(f"* {text}", "thoughts")


def make_server():
    """A fresh LNet connection object, its traffic logged (tests swap it)."""
    from chat.chat import Server, default_log_dir

    return Server(log_dir=default_log_dir())


def main(s):
    from chat.chat import get_password
    from client.engine.lnet_login import lnet_password

    name = (
        os.environ.get("LNET_NAME")
        or (s.state.name if s.state else None)  # parsed from the game login
        or os.environ.get("REVENANT_CHARACTER")  # cold parser after ;reexec
    )
    if not name:
        s.echo("can't tell who you are — set LNET_NAME or REVENANT_CHARACTER")
        return
    password = lnet_password(name, legacy_file=get_password)
    if password is None:
        # A protected name answers "password required" to this; an
        # unprotected one logs in. Said up front so the fix is known
        # before the rejection (#290).
        say(
            s,
            f"no LNet password stored for {name} — File → LNet Password… in the "
            "window stores one; trying without",
        )
    chat = {
        "last_priv": None,
        "known": {},  # senders heard this session, for ;chat to <name> (#147)
        "hinted": set(),  # senders whose first private carried the reply hint
    }
    failures = 0
    while True:
        outcome, connected = serve(s, name, password, chat)
        if outcome == "rejected":
            return
        if connected:
            failures = 0
        wait = RECONNECT_WAITS[min(failures, len(RECONNECT_WAITS) - 1)]
        failures += 1
        say(s, f"logging in to LNet again in {wait} s (;stop lnet to stay off)")
        wait_out(s, wait)


def serve(s, name, password, chat):
    """One connection: log in, relay until it ends. ("rejected" | "lost",
    whether the server's welcome came)."""
    from chat.chat import LoginRejected

    lnet = make_server()
    lnet.set_login_info(name, password=password)
    connected = False
    try:
        lnet.connect()
        lnet.login()
        # A timeout keeps the loop polling for user commands and ;stop.
        lnet.connection.settimeout(RECV_TIMEOUT)
        say(s, f"logging in to LNet as {name} ...")
        while True:
            while (line := s.command(timeout=0)) is not None:
                chat["last_priv"] = obey(
                    s, lnet, line, chat["last_priv"], chat["known"]
                )
            try:
                messages = lnet.receive_messages()
            except TimeoutError:
                s.sleep(0)  # raises ScriptStopped once ;stop is called
                continue
            for message in messages:
                if isinstance(message, bytes):
                    continue  # unrecognized protocol element
                if message.message_type == "greeting":
                    # The server's welcome doubles as login confirmation.
                    connected = True
                    say(s, f"connected to LNet as {name}")
                    continue
                if message.sender and message.message_type in ("private", "channel"):
                    remember_sender(chat["known"], message.sender)
                s.emit(str(message), "thoughts")
                if message.message_type == "private" and message.sender:
                    chat["last_priv"] = message.sender
                    if message.sender not in chat["hinted"]:
                        chat["hinted"].add(message.sender)
                        s.emit(reply_hint(message.sender), "thoughts")
    except LoginRejected as rejection:
        # Rejections arrive asynchronously, after login() has returned.
        say(s, f"LNet login rejected for {name}: {rejection}")
        say(
            s,
            "store the password with File → LNet Password… in the window (or "
            "revenant-chat, or keyring set revenant-lnet <Name>); reset it at "
            "https://lnet.lichproject.org",
        )
        return "rejected", connected
    except (ConnectionError, OSError) as error:
        say(s, f"LNet connection lost: {error}")
        return "lost", connected
    finally:
        close(lnet)


def close(lnet):
    """Shut the socket down, then close it (a bare close does not wake a
    blocked recv on Linux)."""
    connection = getattr(lnet, "connection", None)
    if connection is None:
        return
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    connection.close()


def wait_out(s, seconds):
    """The pause before logging in again: typed chat commands are told
    LNet is down; ;stop ends it (the sleep raises)."""
    for _ in range(int(seconds)):
        while (line := s.command(timeout=0)) is not None:
            s.echo(
                f"not connected to LNet — logging in again shortly ({line!r} not sent)"
            )
        s.sleep(1)


def obey(s, lnet, line, last_priv, known=None):
    """Execute one user command (chat/commands.py's dispatcher, echoing
    through the script handle); returns the (possibly updated) last_priv."""
    return _obey(s.echo, lnet, line, last_priv, known)
