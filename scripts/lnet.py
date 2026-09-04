"""LNet chat in the Thoughts window, 1:1 with lich's lnet:  ;lnet

Start with ;lnet (or just use a command — it starts on demand), then:

  ;chat <message>                   send to your default channel
  ;chat on <channel> <message>      send to a channel   (;chat :<channel> too)
  ;chat to <name> <message>         private message     (;chat ::<name> too)
  ;reply <message>                  answer the last private message
  ;who [name]                       who is connected
  ;stats                            server statistics
  ;channels [all]                   list channels (top 15, or all)
  ;tune <channel>  /  ;untune <channel>

Incoming chat renders in Thoughts the way lich did: [Channel]-Name: "msg",
[Private]-Name for tells, your own reflected sends as [PrivateTo]-Name.
Identity is your character (override LNET_NAME); the password comes from
the OS keychain (service "revenant-lnet", set by the standalone chat
window's remember checkbox, or `keyring set revenant-lnet <Name>`),
LNET_PASSWORD for one run, or the legacy git-ignored
chat/lnet_password.txt. Stop: ;stop lnet

The same grammar and dispatcher (chat/commands.py) drive the standalone
window, `revenant-chat`, which needs no game session at all (#141).
"""

import os
import sys
from pathlib import Path

# chat/ lives at the repo root, not in client/: reachable from a session
# started at the root, made so for one started elsewhere.
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from chat.commands import obey as _obey  # noqa: E402
from chat.commands import parse  # noqa: E402,F401 -- the grammar, tested here

RECV_TIMEOUT = 0.25  # also the user-command poll cadence


def main(s):
    from chat.chat import LoginRejected, Server, default_log_dir, get_password
    from client.lnet_login import lnet_password

    name = (
        os.environ.get("LNET_NAME")
        or (s.state.name if s.state else None)  # parsed from the game login
        or os.environ.get("REVENANT_CHARACTER")  # cold parser after ;reexec
    )
    if not name:
        s.echo("can't tell who you are — set LNET_NAME or REVENANT_CHARACTER")
        return
    lnet = Server(log_dir=default_log_dir())
    lnet.set_login_info(name, password=lnet_password(name, legacy_file=get_password))
    last_priv = None
    try:
        lnet.connect()
        lnet.login()
        # A timeout keeps the loop polling for user commands and ;stop.
        lnet.connection.settimeout(RECV_TIMEOUT)
        s.echo(f"logging in as {name} ...")
        while True:
            while (line := s.command(timeout=0)) is not None:
                last_priv = obey(s, lnet, line, last_priv)
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
                    s.echo(f"connected as {name} — chat appears in Thoughts")
                    continue
                if message.message_type == "private" and message.sender:
                    last_priv = message.sender
                s.emit(str(message), "thoughts")
    except LoginRejected as rejection:
        # Rejections arrive asynchronously, after login() has returned.
        s.echo(f"LNet login rejected: {rejection}")
        s.echo(
            "store this name's LNet password in the keychain (revenant-chat "
            "asks and remembers it, or: keyring set revenant-lnet <Name>); "
            "reset it at https://lnet.lichproject.org"
        )
    except (ConnectionError, OSError) as error:
        s.echo(f"LNet connection lost: {error}")
    finally:
        lnet.connection.close()


def obey(s, lnet, line, last_priv):
    """Execute one user command (chat/commands.py's dispatcher, echoing
    through the script handle); returns the (possibly updated) last_priv."""
    return _obey(s.echo, lnet, line, last_priv)
