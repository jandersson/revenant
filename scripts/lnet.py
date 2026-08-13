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

(;who, ;stats, and ;channels replies aren't rendered yet — issue #30.)

Incoming chat renders in Thoughts the way lich did: [Channel]-Name: "msg",
[Private]-Name for tells, your own reflected sends as [PrivateTo]-Name.
Identity is your character (override LNET_NAME); the password comes from
LNET_PASSWORD or the git-ignored chat/lnet_password.txt. Stop: ;stop lnet
"""

import os
import re

RECV_TIMEOUT = 0.25  # also the user-command poll cadence

# The chat grammar, ported 1:1 from lnet.lic's user-input loop.
_PRIVATE = re.compile(r"^chat\s+\:\:(.+?) (.*)", re.I)
_PRIVATE_TO = re.compile(r"^chat\s+to\s+(.+?) (.*)", re.I)
_CHANNEL = re.compile(r"^chat\s+\:([^\:].*?) (.*)", re.I)
_CHANNEL_ON = re.compile(r"^chat\s+on\s+(.+?) (.*)", re.I)
_DEFAULT = re.compile(r"^chat\s+(?!\:\:|to |on )(.*)", re.I)
_REPLY = re.compile(r"^reply\s+(.+)", re.I)
_WHO = re.compile(r"^who(?:\s+([A-Za-z\:]+))?$", re.I)
_CHANNELS = re.compile(r"^channels?\s*(full|all)?$", re.I)
_TUNE = re.compile(r"^(tune|untune)\s+([A-Za-z]+)$", re.I)


def parse(line):
    """One user line -> an action tuple, exactly as lnet.lic dispatches it.

    ("private", name, msg) | ("channel", chan, msg) | ("default", msg) |
    ("reply", msg) | ("who", name|None) | ("stats",) | ("channels", bool_all)
    | ("tune"/"untune", chan) | ("unknown", line)
    """
    if match := (_PRIVATE.match(line) or _PRIVATE_TO.match(line)):
        return ("private", match.group(1), match.group(2))
    if match := (_CHANNEL.match(line) or _CHANNEL_ON.match(line)):
        return ("channel", match.group(1), match.group(2))
    if match := _DEFAULT.match(line):
        # lich unescapes a leading ".to "/".on " so those words are sayable
        return ("default", re.sub(r"^\.(to|on) ", r"\1 ", match.group(1), flags=re.I))
    if match := _REPLY.match(line):
        return ("reply", match.group(1))
    if match := _WHO.match(line):
        return ("who", match.group(1))
    if line.strip().lower() == "stats":
        return ("stats",)
    if match := _CHANNELS.match(line):
        return ("channels", bool(match.group(1)))
    if match := _TUNE.match(line):
        return (match.group(1).lower(), match.group(2))
    return ("unknown", line)


def main(s):
    from chat.chat import LoginRejected, Server, get_password

    name = (
        os.environ.get("LNET_NAME")
        or (s.state.name if s.state else None)  # parsed from the game login
        or os.environ.get("REVENANT_CHARACTER")  # cold parser after ;reexec
    )
    if not name:
        s.echo("can't tell who you are — set LNET_NAME or REVENANT_CHARACTER")
        return
    lnet = Server()
    lnet.set_login_info(name, password=get_password())
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
            "put this name's LNet password in chat/lnet_password.txt (or "
            "LNET_PASSWORD); reset it at https://lnet.lichproject.org"
        )
    except (ConnectionError, OSError) as error:
        s.echo(f"LNet connection lost: {error}")
    finally:
        lnet.connection.close()


def obey(s, lnet, line, last_priv):
    """Execute one user command; returns the (possibly updated) last_priv."""
    action = parse(line)
    if action[0] == "private":
        lnet.send_message(action[2], to=action[1])
    elif action[0] == "channel":
        lnet.send_message(action[2], channel=action[1])
    elif action[0] == "default":
        lnet.send_message(action[1])
    elif action[0] == "reply":
        if last_priv:
            lnet.send_message(action[1], to=last_priv)
        else:
            s.echo("No private message to reply to.")
    elif action[0] == "who":
        if action[1]:
            lnet.send_query("connected", name=action[1])
        else:
            lnet.send_query("connected")
    elif action[0] == "stats":
        lnet.send_query("server stats")
    elif action[0] == "channels":
        if action[1]:
            lnet.send_query("channels")
        else:
            lnet.send_query("channels", num="15")
    elif action[0] in ("tune", "untune"):
        lnet.tune(action[1], off=action[0] == "untune")
    else:
        s.echo(f"unrecognized: {line!r} — see ;help lnet")
    return last_priv
