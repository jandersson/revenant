"""How the input line's Up/Down history behaves — the manual (#76)."""

from client.command_history import CommandHistory


def test_up_recalls_the_last_command():
    history = CommandHistory()
    history.record("look")
    history.record("climb rise")
    assert history.previous("") == "climb rise"
    assert history.previous("climb rise") == "look"
    assert history.previous("look") is None  # oldest: stay put


def test_down_walks_forward_and_restores_the_draft():
    history = CommandHistory()
    history.record("look")
    history.record("climb rise")
    assert history.previous("half-typed dr") == "climb rise"
    assert history.previous("climb rise") == "look"
    assert history.next() == "climb rise"
    assert history.next() == "half-typed dr"  # past the newest: the draft
    assert history.next() is None  # not browsing anymore


def test_sending_leaves_browse_mode_and_dedupes_repeats():
    history = CommandHistory()
    history.record("look")
    history.previous("")
    history.record("look")  # a repeat: no duplicate entry
    assert history.entries == ["look"]
    # Recording ended the browse: Up starts from the newest again.
    assert history.previous("") == "look"


def test_blank_commands_are_never_recorded():
    history = CommandHistory()
    history.record("   ")
    assert history.entries == []
    assert history.previous("") is None


def test_the_history_is_capped():
    history = CommandHistory(limit=3)
    for number in range(6):
        history.record(f"command {number}")
    assert history.entries == ["command 3", "command 4", "command 5"]
