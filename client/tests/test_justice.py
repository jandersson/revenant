"""RECALL WARRANT read back — these tests are the manual. The clean
answer captured on 2026-09-22, a wanted answer by its shape, and
silence said rather than taken for clean."""

import importlib.util
import pathlib
from types import SimpleNamespace

from client.game import justice

CLEAN = (
    "Taking a moment to think, you are certain you do not have any outstanding "
    "warrants.\n"
)
REPO = pathlib.Path(__file__).parents[2]


def test_the_clean_answer_reads_clean_and_a_warrant_reads_wanted():
    assert justice.parse_warrants(CLEAN) is False
    assert (
        justice.parse_warrants("You recall a warrant for your arrest in Zoluren.")
        is True
    )
    assert justice.parse_warrants("") is None
    assert justice.parse_warrants("Recall what?") is None
    assert justice.describe(False) == "no outstanding warrants"
    assert justice.describe(True).startswith("WANTED")
    assert "did not say" in justice.describe(None)


def test_the_script_asks_once_and_says_what_it_read():
    spec = importlib.util.spec_from_file_location(
        "warrant_script", REPO / "scripts/warrant.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    sent, echoed = [], []
    fake = SimpleNamespace(echo=echoed.append, state=SimpleNamespace(name="Lanival"))
    script.probe = SimpleNamespace(ask=lambda s, c, *_: sent.append(c) or CLEAN)
    script.main(fake)
    assert sent == ["recall warrant"]
    assert echoed == ["warrant: no outstanding warrants"]
    script.probe = SimpleNamespace(ask=lambda s, c, *_: "Recall what?\n")
    echoed.clear()
    script.main(fake)
    assert "unrecognized answer 'Recall what?'" in echoed[0]
    assert echoed[-1].startswith("warrant: the game did not say")
