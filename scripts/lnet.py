"""Mirror LNet chat into the Thoughts window:  ;lnet

Logs into lnet.lichproject.org (name from LNET_NAME, password from
LNET_PASSWORD or the git-ignored chat/lnet_password.txt) and emits every
chat message to the "thoughts" stream — out-of-game LNet chatter lands in
the same dock as in-game gweth thoughts, lich-style.

Read-only: nothing typed in a front end is ever sent to LNet
(sending is issue #29). Stop with:  ;stop lnet
"""

import os

RECV_TIMEOUT = 1.0  # seconds between stop-checks while the socket is quiet


def format_message(message) -> str:
    tag = message.to or message.message_type or "lnet"
    sender = message.sender or "?"
    return f"[LNet {tag}] {sender}: {message.contents}"


def main(s):
    from chat.chat import LoginRejected, Server, get_password

    name = os.environ.get("LNET_NAME", "Wabbajack")
    lnet = Server()
    lnet.set_login_info(name, password=get_password())
    try:
        lnet.connect()
        lnet.login()
    except LoginRejected as rejection:
        s.echo(f"LNet login rejected: {rejection}")
        s.echo("set LNET_PASSWORD (or chat/lnet_password.txt) and retry")
        return
    # A timeout makes the receive loop wake regularly so ;stop can land.
    lnet.connection.settimeout(RECV_TIMEOUT)
    s.echo(f"connected as {name} — LNet chat appears in the Thoughts window")
    try:
        while True:
            try:
                messages = lnet.receive_messages()
            except TimeoutError:
                s.sleep(0)  # raises ScriptStopped once ;stop is called
                continue
            for message in messages:
                if isinstance(message, bytes):
                    continue  # unrecognized protocol element
                if message.message_type == "greeting":
                    continue
                s.emit(format_message(message), "thoughts")
    except (ConnectionError, OSError) as error:
        s.echo(f"LNet connection lost: {error}")
    finally:
        lnet.connection.close()
