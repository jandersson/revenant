"""How the ;chat commands behave — these tests are the manual.

Each test states one user expectation: the line typed in a front end on
the left, what leaves revenant (or renders in Thoughts) on the right.
The LNet server itself is never simulated — only our side is under test.
The grammar is a 1:1 port of lich's lnet.lic.
"""

import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(REPO))  # chat/ lives at the repo root, not in client/

from chat.chat import LnetMessage, Server  # noqa: E402


def _lnet_script():
    spec = importlib.util.spec_from_file_location(
        "lnet_script", REPO / "scripts" / "lnet.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lnet = _lnet_script()


# --- the grammar: what each typed command means -------------------------


def test_chat_alone_sends_to_your_default_channel():
    assert lnet.parse("chat hey folks") == ("default", "hey folks")


def test_chat_on_names_a_channel():
    assert lnet.parse("chat on General hey folks") == (
        "channel",
        "General",
        "hey folks",
    )


def test_chat_colon_is_the_short_channel_form():
    assert lnet.parse("chat :General hey folks") == ("channel", "General", "hey folks")


def test_chat_to_sends_a_private_message():
    assert lnet.parse("chat to Somefriend psst") == ("private", "Somefriend", "psst")


def test_chat_double_colon_is_the_short_private_form():
    assert lnet.parse("chat ::Somefriend psst") == ("private", "Somefriend", "psst")


def test_chat_dot_prefix_says_a_message_starting_with_to_or_on():
    # ";chat .to the victor go the spoils" says "to the victor go the spoils"
    assert lnet.parse("chat .to the victor go the spoils") == (
        "default",
        "to the victor go the spoils",
    )


def test_reply_answers_the_last_private_message():
    assert lnet.parse("reply hello yourself") == ("reply", "hello yourself")


def test_who_asks_who_is_connected():
    assert lnet.parse("who") == ("who", None)


def test_who_with_a_name_asks_about_that_person():
    assert lnet.parse("who Somefriend") == ("who", "Somefriend")


def test_stats_asks_for_server_statistics():
    assert lnet.parse("stats") == ("stats",)


def test_channels_lists_the_top_channels():
    assert lnet.parse("channels") == ("channels", False)


def test_channels_all_lists_every_channel():
    assert lnet.parse("channels all") == ("channels", True)


def test_tune_and_untune_manage_channel_subscriptions():
    assert lnet.parse("tune Deceased") == ("tune", "Deceased")
    assert lnet.parse("untune Deceased") == ("untune", "Deceased")


def test_anything_else_is_unrecognized():
    assert lnet.parse("dance wildly") == ("unknown", "dance wildly")


# --- the wire: what actually leaves revenant ----------------------------


class WireTap:
    """Stands in for the SSL connection; records what would be sent."""

    def __init__(self):
        self.sent = []

    def send(self, data):
        self.sent.append(data)


def _tapped_server():
    server = Server()
    server.connection = WireTap()
    return server


def test_a_default_channel_message_names_no_channel():
    # The server applies your default channel when the attribute is absent.
    server = _tapped_server()
    server.send_message("hey folks")
    assert server.connection.sent == [b'<message type="channel">hey folks</message>\n']


def test_a_channel_message_names_the_channel():
    server = _tapped_server()
    server.send_message("hey folks", channel="General")
    assert server.connection.sent == [
        b'<message type="channel" channel="General">hey folks</message>\n'
    ]


def test_a_private_message_names_the_recipient():
    server = _tapped_server()
    server.send_message("psst", to="Somefriend")
    assert server.connection.sent == [
        b'<message type="private" to="Somefriend">psst</message>\n'
    ]


def test_who_is_a_connected_query():
    server = _tapped_server()
    server.send_query("connected")
    assert server.connection.sent == [b'<query type="connected" />\n']


def test_channels_asks_for_the_top_15_by_default():
    server = _tapped_server()
    server.send_query("channels", num="15")
    assert server.connection.sent == [b'<query type="channels" num="15" />\n']


def test_tune_and_untune_are_their_own_elements():
    server = _tapped_server()
    server.tune("Deceased")
    server.tune("Deceased", off=True)
    assert server.connection.sent == [
        b'<tune channel="Deceased" />\n',
        b'<untune channel="Deceased" />\n',
    ]


# --- the display: how chat renders in the Thoughts window ---------------


def _message(**fields):
    defaults = dict(
        contents=None, channel=None, to=None, message_type=None, sender=None
    )
    return LnetMessage(**{**defaults, **fields})


def test_channel_chat_renders_with_channel_and_sender():
    message = _message(
        message_type="channel", channel="General", sender="Somefriend", contents="hi"
    )
    assert str(message) == '[General]-Somefriend: "hi"'


def test_an_incoming_tell_renders_as_private():
    message = _message(message_type="private", sender="Somefriend", contents="psst")
    assert str(message) == '[Private]-Somefriend: "psst"'


def test_your_own_reflected_tell_renders_as_private_to():
    message = _message(message_type="private", to="Somefriend", contents="psst")
    assert str(message) == '[PrivateTo]-Somefriend: "psst"'


def test_server_notices_render_bare():
    message = _message(message_type="server", contents="Welcome to LNet")
    assert str(message) == '[server]: "Welcome to LNet"'


# --- replying before anyone has sent you a tell -------------------------


class FakeHandle:
    def __init__(self):
        self.echoed = []

    def echo(self, text):
        self.echoed.append(text)


def test_reply_with_no_tell_yet_explains_itself():
    handle = FakeHandle()
    result = lnet.obey(handle, _tapped_server(), "reply hello?", last_priv=None)
    assert handle.echoed == ["No private message to reply to."]
    assert result is None


def test_unrecognized_commands_point_at_the_manual():
    handle = FakeHandle()
    lnet.obey(handle, _tapped_server(), "dance wildly", last_priv=None)
    assert handle.echoed == ["unrecognized: 'dance wildly' — see ;help lnet"]


def test_the_servers_reflection_of_your_own_tell_renders_as_private_to():
    # Captured 2026-09-04 (#145): a `;chat to Atanamir test` came back as
    # `[server]: "test"`. lnet.lic's dispatch names the shape — the server
    # reflects your own private as type "privateto" with the recipient in
    # `to` and no `from` — so it renders like the tell it echoes.
    message = _message(message_type="privateto", to="Somefriend", contents="test")
    assert str(message) == '[PrivateTo]-Somefriend: "test"'


def test_a_privateto_element_off_the_wire_parses_to_that_shape():
    server = Server()
    server._reset_parser()
    server.connection = type(
        "Chunks",
        (),
        {
            "recv": lambda self, n: (
                b'<message type="privateto" to="Somefriend">test</message>\n'
            )
        },
    )()
    (message,) = server.receive_messages()
    assert (message.message_type, message.to, message.sender) == (
        "privateto",
        "Somefriend",
        None,
    )
    assert str(message) == '[PrivateTo]-Somefriend: "test"'
