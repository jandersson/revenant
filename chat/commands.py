"""The LNet chat command grammar and its dispatcher, shared by the
session's ;lnet script and the standalone chat window (#141).

parse() turns one typed line into an action tuple, a 1:1 port of
lnet.lic's user-input loop; obey() carries the action out against a
chat.Server. input_to_command() is the window's convenience: a line
with no leading ";" is a message to your default channel, so plain
typing chats and ";who" still asks who is on.
"""

import re

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

# What a window user may type after ";" (or bare, in a ;lnet session).
COMMAND_WORDS = (
    "chat",
    "reply",
    "who",
    "stats",
    "channels",
    "channel",
    "tune",
    "untune",
)


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


def input_to_command(text):
    """What a line typed in the chat window means, or None for nothing.

    ";who" and "who" are the who command; anything that is not a command
    word is a message to your default channel — a chat window's input
    line is for chatting. A line of whitespace is nothing.
    """
    text = text.strip()
    if not text:
        return None
    body = text[1:].strip() if text.startswith(";") else text
    first = body.split(None, 1)[0].lower() if body else ""
    if first in COMMAND_WORDS:
        return body
    if text.startswith(";"):
        return body  # explicit but unknown: obey() will say so
    return f"chat {text}"


def obey(echo, lnet, line, last_priv):
    """Execute one user command against `lnet` (a chat.Server); echo(text)
    reports to the user. Returns the (possibly updated) last_priv."""
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
            echo("No private message to reply to.")
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
        echo(f"unrecognized: {line!r} — see ;help lnet")
    return last_priv
