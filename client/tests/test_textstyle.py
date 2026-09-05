"""How the terminal frontend renders a frame — these tests are the
manual (#57). The style table, the link style, highlight rules over a
base style, and the status line folded from the state frames.
"""

import re

from client.textstyle import STYLES, Status, base_style, render

GLOW = {"pattern": "gleaming|glowing", "color": "#e0c95e", "bold": False}
GLOW["regex"] = re.compile(GLOW["pattern"])
NAME = {"pattern": r"\bLanival\b", "color": "#7fe07f", "bold": True}
NAME["regex"] = re.compile(NAME["pattern"])


def test_plain_text_renders_as_one_unstyled_run():
    assert render("You see nothing.\n", "") == [
        ("You see nothing.\n", False, None, None)
    ]


def test_a_game_style_gives_its_color_and_weight():
    assert render("[Town Green]\n", "roomName") == [
        ("[Town Green]\n", True, "#d8b465", None)
    ]
    assert base_style("alert") == (True, "#e05252", None)
    assert base_style("no such style") == (False, None, None)


def test_a_link_carries_its_command():
    runs = render("INVENTORY HELP", "link:inventory help")
    assert runs == [("INVENTORY HELP", False, "#8fc7e8", "inventory help")]


def test_a_highlight_recolors_its_span_and_keeps_the_rest():
    runs = render("A gleaming sword lies here.", "speech", [GLOW])
    assert runs == [
        ("A ", False, "#8fc7e8", None),
        ("gleaming", False, "#e0c95e", None),
        (" sword lies here.", False, "#8fc7e8", None),
    ]


def test_a_bold_rule_bolds_and_a_link_survives_a_highlight():
    runs = render("Lanival waves.", "link:look Lanival", [NAME])
    assert runs[0] == ("Lanival", True, "#7fe07f", "look Lanival")


def test_the_style_table_matches_the_gui_names():
    assert set(STYLES) == {
        "roomName",
        "bold",
        "speech",
        "whisper",
        "thought",
        "alert",
        "sent",
    }


def test_the_status_line_folds_the_state_frames():
    status = Status()
    assert status.feed("Lanival", "character")
    assert status.feed("21101\t[Barana's Shipyard, Lumber Storage]", "room")
    assert status.feed("health 70 stamina 91 mana 100", "vitals")
    assert status.feed("IconBLEEDING IconSTANDING", "indicators")
    assert not status.feed("You see a rat.\n", "")
    status.connection = "attached"
    assert status.line(roundtime=4) == (
        "Lanival | [Barana's Shipyard, Lumber Storage] | he 70%  st 91%  ma 100% | "
        "standing | bleeding | RT 4 | attached"
    )


def test_dead_replaces_posture_and_badges():
    status = Status()
    status.feed("IconDEAD IconPRONE IconBLEEDING", "indicators")
    assert status.line() == "— | DEAD | connecting"


def test_partial_vitals_accumulate():
    status = Status()
    status.feed("health 100", "vitals")
    status.feed("stamina 80", "vitals")
    assert status.vitals == {"health": 100, "stamina": 80}
