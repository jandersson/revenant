"""Credit is per feature: a script that cites Lich or the wiki has a row
in docs/bibliography.md — the manual for that rule, enforced.

A docstring that names Lich, dr-scripts, a .lic file, Genie or
Elanthipedia is a script that drew on someone else's work; the
bibliography must name what and how. Scripts built only from captured
traffic cite nothing and need no row.
"""

import ast
import pathlib
import re

REPO = pathlib.Path(__file__).parents[2]
SCRIPTS = REPO / "scripts"
BIBLIOGRAPHY = REPO / "docs" / "bibliography.md"

CITES_A_SOURCE = re.compile(
    r"\blich\b|dr-scripts|\.lic\b|\bgenie\b|elanthipedia|gswiki", re.IGNORECASE
)


def scripts_citing_sources():
    for path in sorted(SCRIPTS.glob("*.py")):
        doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
        if CITES_A_SOURCE.search(doc):
            yield path.stem


def test_every_script_that_cites_a_source_has_a_bibliography_row():
    text = BIBLIOGRAPHY.read_text(encoding="utf-8")
    missing = [name for name in scripts_citing_sources() if f"`;{name}`" not in text]
    assert not missing, (
        f"scripts citing Lich or the wiki without a docs/bibliography.md row: "
        f"{missing} — add the feature, its source (linked) and how it was used"
    )


def test_the_check_sees_the_scripts_it_should():
    # The rule has teeth only if the scan finds the known citers.
    found = set(scripts_citing_sources())
    assert {"lnet", "tend", "wealth", "athletics", "favors"} <= found


def test_bibliography_links_are_well_formed():
    text = BIBLIOGRAPHY.read_text(encoding="utf-8")
    links = re.findall(r"\]\((https?://[^)]+)\)", text)
    assert links, "the bibliography should link its sources"
    assert all(" " not in link for link in links)
