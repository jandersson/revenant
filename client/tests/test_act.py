"""client.game.act: ask the game and read what it said — the four
helpers every script leans on (#407). ask is probe.ask with one pair
of windows and the game's case kept; missing knows both not-found
wordings; said quotes the game's own line, never a bystander's;
unknown is the one "please report it" echo."""

from types import SimpleNamespace

from client.game import act, probe
from test_probe import FakeHandle


class Echoes:
    def __init__(self):
        self.echoed = []

    def echo(self, text):
        self.echoed.append(text)


# --- ask ---


def test_ask_sends_the_command_and_keeps_the_games_case():
    handle = FakeHandle(["You get a bundling rope from inside your sack.\n"])
    assert act.ask(handle, "get my bundling rope") == (
        "You get a bundling rope from inside your sack."
    )
    assert handle.sent == ["get my bundling rope"]


def test_ask_reads_the_modules_windows_at_call_time(monkeypatch):
    # A script moved onto act has no windows of its own to shorten: a
    # test shortens act's, and the ask must read them when called, not
    # bind them as defaults (the ;soul suite waited two real seconds an
    # ask that way, 2026-09-20).
    seen = []
    monkeypatch.setattr(probe, "ask", lambda s, c, a, b: seen.append((c, a, b)))
    monkeypatch.setattr(act, "ASK_SECONDS", 7)
    monkeypatch.setattr(act, "TAIL_SECONDS", 2)
    act.ask(None, "look")
    act.ask(None, "braid my grass", 4, 3)
    assert seen == [("look", 7, 2), ("braid my grass", 4, 3)]


# --- missing ---


def test_missing_knows_both_not_found_wordings():
    assert act.missing("What were you referring to?")
    assert act.missing("I could not find what you were referring to.")
    assert not act.missing("You get a bundling rope from inside your sack.")


def test_missing_is_case_insensitive_and_false_for_nothing():
    assert act.missing("WHAT WERE YOU REFERRING TO?")
    assert not act.missing("")
    assert not act.missing(None)


def test_missing_takes_a_callers_own_wordings_too():
    # ;repair's ticket and ;skins' bundle must be on you: "You don't
    # have that." and "You aren't wearing that." are the same answer
    # to them.
    assert act.missing("You aren't wearing that.", more=("aren't wearing",))
    assert not act.missing("You aren't wearing that.")


# --- said ---


def test_said_quotes_the_line_holding_the_wording_over_a_bystanders():
    # #359: "Sekhhtha goes west." landed first in the window and stood
    # in for the refusal in the echo.
    answer = "Sekhhtha goes west.\nYou're not experienced enough to go there."
    assert (
        act.said(answer, ("not experienced enough",))
        == "You're not experienced enough to go there."
    )


def test_said_matches_needles_without_regard_to_case():
    answer = "Court Advisor Aaiyaah just arrived.\nThere is no class here to listen to."
    assert act.said(answer, ("NO CLASS",)) == "There is no class here to listen to."


def test_said_is_the_first_line_when_no_needle_matches_or_none_is_given():
    answer = "  You get a bundling rope.  \nYou put it in your sack."
    assert act.said(answer) == "You get a bundling rope."
    assert act.said(answer, ("referring",)) == "You get a bundling rope."


def test_said_skips_blank_lines_and_says_silence_for_nothing():
    assert act.said("\n\n  \nWhat were you referring to?\n") == (
        "What were you referring to?"
    )
    assert act.said("") == act.SILENCE
    assert act.said(None) == act.SILENCE
    assert act.said("  \n ") == "(silence)"


def test_lines_are_the_stripped_non_blank_lines_in_order():
    assert act.lines(" one \n\n two\n") == ["one", "two"]
    assert act.lines(None) == []


# --- unknown ---


def test_unknown_echoes_the_common_report_it_line_and_returns_it():
    s = Echoes()
    line = act.unknown(s, "hunt", "skin", "The rat twitches.\nYou wait.")
    assert line == "The rat twitches."
    assert s.echoed == [
        "hunt: unrecognized skin answer 'The rat twitches.' — please report it"
    ]


def test_unknown_without_a_what_says_unrecognized_answer():
    s = Echoes()
    act.unknown(s, "warrant", "", "")
    assert s.echoed == ["warrant: unrecognized answer '(silence)' — please report it"]


def test_unknown_steps_a_tally_when_one_is_passed():
    s = Echoes()
    tally = SimpleNamespace(unrecognized=2)
    act.unknown(s, "hunt", "bob", "Something new.", tally)
    act.unknown(s, "hunt", "bob", "Something newer.")
    assert tally.unrecognized == 3


def test_missing_knows_the_parsers_refusal_of_a_three_word_name():
    # 2026-10-08: an item is ADJECTIVE NOUN, never three words — `get my
    # massive coal nugget` answered this, and a script read it as a GET
    # that worked (#488).
    assert act.missing("Please rephrase that command.")


def test_noise_only_knows_a_window_that_answers_nothing():
    # #483: these closed a LOOT's and a BOB's windows before their own lines.
    assert act.noise_only(
        "Some nearby vegetation rustles, heralding the arrival of an Endrus serpent."
    )
    assert act.noise_only("You feel fully rested.\n")
    assert act.noise_only(
        "Hssah goes north.\n[You're nimbly balanced and in good position.]"
    )
    assert act.noise_only("")
    assert act.noise_only(
        "< Driving in with exacting precision, you draw a sledgehammer at a wood troll.",
        swings=True,
    )
    assert not act.noise_only(
        "< Driving in with exacting precision, you draw a sledgehammer at a wood troll."
    )
    assert not act.noise_only(
        "You search the Endrus serpent.\nYou find nothing of interest."
    )
    assert not act.noise_only("You feel fully rested.\nYou search the Endrus serpent.")
