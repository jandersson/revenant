"""How the chat window turns typed lines into LNet actions — the manual.

The grammar itself (parse) is the ;lnet script's, tested with it in
client/tests/test_lnet_chat.py; these pin the window's input rule and
the dispatcher both share.
"""

from chat.commands import input_to_command, obey, parse


class FakeServer:
    def __init__(self):
        self.sent = []

    def send_message(self, contents, channel=None, to=None):
        self.sent.append(("message", contents, channel, to))

    def send_query(self, query_type, **attributes):
        self.sent.append(("query", query_type, attributes))

    def tune(self, channel, off=False):
        self.sent.append(("tune", channel, off))


def test_plain_text_is_a_message_to_the_default_channel():
    assert input_to_command("hello everyone") == "chat hello everyone"


def test_a_command_word_needs_no_semicolon_in_the_window():
    assert input_to_command("who") == "who"
    assert input_to_command("chat to Somefriend psst") == "chat to Somefriend psst"


def test_a_semicolon_prefix_is_accepted_and_dropped():
    assert input_to_command(";who Somefriend") == "who Somefriend"
    assert input_to_command("; channels all") == "channels all"


def test_an_explicit_unknown_command_reaches_obey_to_be_refused():
    assert input_to_command(";dance") == "dance"
    echoes = []
    obey(echoes.append, FakeServer(), "dance", None)
    assert echoes and "unrecognized" in echoes[0]


def test_whitespace_is_nothing():
    assert input_to_command("   ") is None


def test_obey_sends_messages_and_queries_and_tunes():
    server = FakeServer()
    obey(print, server, "chat hey", None)
    obey(print, server, "chat on General hey", None)
    obey(print, server, "chat to Somefriend psst", None)
    obey(print, server, "who", None)
    obey(print, server, "channels", None)
    obey(print, server, "untune Deceased", None)
    assert server.sent == [
        ("message", "hey", None, None),
        ("message", "hey", "General", None),
        ("message", "psst", None, "Somefriend"),
        ("query", "connected", {}),
        ("query", "channels", {"num": "15"}),
        ("tune", "Deceased", True),
    ]


def test_reply_goes_to_the_last_private_sender_or_complains():
    server = FakeServer()
    echoes = []
    assert obey(echoes.append, server, "reply hi", None) is None
    assert echoes == ["No private message to reply to."]
    assert obey(echoes.append, server, "reply hi", "Somefriend") == "Somefriend"
    assert server.sent == [("message", "hi", None, "Somefriend")]


def test_parse_is_the_same_grammar_the_script_uses():
    assert parse("chat ::Somefriend psst") == ("private", "Somefriend", "psst")
    assert parse("stats") == ("stats",)
