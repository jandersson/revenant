"""The climbs table: one row per attempt with its context, read back
oldest first; the refusal wordings classified the walker's way."""

import json
import sqlite3

from client.game import climblog

FOOTING = (
    "Your oak-hafted handaxe and plate vambraces make the climb more difficult.\n"
    "You pick your way up the tree, but reach a point where your footing is "
    "questionable.  Reluctantly, you climb back down.\n"
)
VERTIGO = "You make your way up the tree.  Struck by vertigo, you cling to the tree, then slowly climb back down.\n"


def test_refusal_kinds_from_the_captured_wordings():
    assert climblog.refusal_kind(FOOTING) == "footing"
    assert climblog.refusal_kind(VERTIGO) == "vertigo"
    assert climblog.refusal_kind("You must be standing to do that.\n") == "posture"
    assert climblog.refusal_kind("You lose your grip and climb back down.\n") == "other"
    assert climblog.refusal_kind("You climb the tree.\n") is None


def test_the_hindering_line_is_kept_verbatim():
    assert climblog.hindering_line(FOOTING).startswith("Your oak-hafted handaxe")
    assert climblog.hindering_line(VERTIGO) == ""


def test_rows_round_trip_with_extras_as_json():
    db = sqlite3.connect(":memory:")
    climblog.ensure_schema(db)
    climblog.record(
        db,
        character_name="Lanival",
        experiment="tree-1",
        phase="after",
        attempt=1,
        room=6153,
        obstacle="felled tree",
        outcome="footing",
        wording=FOOTING,
        hindering=climblog.hindering_line(FOOTING),
        athletics_rank=7,
        athletics_mindstate=3,
        agility=8,
        strength=10,
        tdps=347,
        encumbrance="Burdened",
        health=100,
        appraise="You are fairly certain you could climb it.",
        stats={"Agility": 8, "Reflex": 8},
    )
    climblog.record(
        db,
        character_name="Sable",
        experiment="other",
        phase="after",
        attempt=1,
        obstacle="wall",
        outcome="up",
    )
    (mine,) = climblog.rows(db, experiment="tree-1")
    assert mine["character_name"] == "Lanival" and mine["outcome"] == "footing"
    assert mine["encumbrance"] == "Burdened" and mine["agility"] == 8
    assert json.loads(mine["extra"]) == {"stats": {"Agility": 8, "Reflex": 8}}
    assert [r["experiment"] for r in climblog.rows(db)] == ["tree-1", "other"]
    assert [r["obstacle"] for r in climblog.rows(db, character="Sable")] == ["wall"]


def test_summary_lines_read_like_a_lab_notebook():
    db = sqlite3.connect(":memory:")
    climblog.ensure_schema(db)
    climblog.record(
        db,
        logged_at="2026-09-11T21:22:24+00:00",
        character_name="Lanival",
        experiment="tree-1",
        phase="after",
        attempt=2,
        obstacle="felled tree",
        outcome="vertigo",
        wording=VERTIGO,
        hindering="Your plate vambraces makes the climb more difficult.",
        athletics_rank=7,
        agility=9,
        strength=10,
        encumbrance="None",
        health=98,
    )
    (line,) = climblog.summarize(climblog.rows(db))
    assert line == (
        "21:22:24 after#2 vertigo: Ath 7 Agi 9 Str 10 enc None hp 98 "
        "[Your plate vambraces makes the climb more difficult.]"
    )
