"""Regenerate client/client/game/boxes_data.py from Elanthipedia's
Locksmithing page: its "Creatures with boxes" table, each creature's
boxes' approximate Locksmithing ranks and cap and the drop rate where
the table gives one (#422).

    uv run python tools/box_tables.py [--refresh]

The page is read through tools/wiki.py's cache (raw wikitext, the table
intact). `;hunt grounds` falls back to these, and to the Critter pages'
Has Boxes (tools/creature_tables.py), on a zone where no box rate is
measured yet. The drop-rate column is mostly blank: 21 of 101 rows on
2026-10-02.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wiki  # noqa: E402

TITLE = "Locksmithing"
SOURCE = "https://elanthipedia.play.net/Locksmithing"
OUT = (
    Path(__file__).resolve().parents[1] / "client" / "client" / "game" / "boxes_data.py"
)
HEADING = "===Creatures with boxes==="

# [[Target|Display]] or [[Target]]
_LINK = re.compile(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
_PAREN = re.compile(r"\s*\([^)]*\)")
_TIER = re.compile(r"\d+(?:st|nd|rd|th) tier", re.IGNORECASE)


def rows_of(text):
    """The table's rows as lists of cells, the header left out."""
    start = text.index(HEADING)
    table = text[start : text.index("|}", start)]
    rows = []
    for chunk in table.split("\n|-")[1:]:
        line = chunk.strip()
        if line.startswith("|") and not line.startswith(("|}", "!")):
            rows.append([cell.strip() for cell in line[1:].split("||")])
    return rows


def names_of(cell):
    """The creature names a cell gives, lowercased: each link as it is
    shown, parentheticals and tiers dropped, a plural made singular when
    the link itself is ("[[Snow Goblin (1)|Snow Goblin]]s, 1st Tier" ->
    "snow goblin")."""
    shown = {
        _PAREN.sub("", display or target).strip().lower()
        for target, display in _LINK.findall(cell)
    }
    text = _LINK.sub(lambda link: link.group(2) or link.group(1), cell)
    names = []
    for part in text.split(","):
        part = " ".join(_PAREN.sub("", part).split()).lower()
        if not part or _TIER.fullmatch(part):
            continue
        if part.endswith("s") and part[:-1] in shown:
            part = part[:-1]
        names.append(part)
    return names


def table(text):
    """{name: (ranks, cap, drop)}, the wiki's words; the first row naming
    a creature keeps its ranks (the table runs easiest first), the first
    drop rate given is kept."""
    found = {}
    for cells in rows_of(text):
        cells += [""] * (5 - len(cells))
        ranks, cap, drop = cells[1], cells[2], cells[4].capitalize()
        for name in names_of(cells[0]):
            old = found.get(name)
            if old is None:
                found[name] = (ranks, cap, drop)
            elif drop and not old[2]:
                found[name] = (old[0], old[1], drop)
    return dict(sorted(found.items()))


def render(locks):
    lines = [
        '"""Creatures whose boxes the wiki lists — generated, do not edit.',
        "",
        f'Source: {SOURCE}, its "Creatures with boxes" table',
        "(tools/box_tables.py regenerates this file). LOCKS maps a",
        "creature's name, lowercased, to (ranks, cap, drop): the approximate",
        "Locksmithing ranks its boxes want and teach to, and the drop rate,",
        '"" where the table leaves it blank — the wiki\'s own words.',
        '"""',
        "",
        "# fmt: off",
        "LOCKS = {",
    ]
    for name, row in locks.items():
        lines.append(f"    {name!r}: {row!r},")
    lines += ["}", "# fmt: on", ""]
    return "\n".join(lines)


def main(argv):
    text = wiki.read(TITLE, refresh="--refresh" in argv)
    locks = table(text)
    OUT.write_text(render(locks), encoding="utf-8")
    rated = sum(1 for row in locks.values() if row[2])
    print(f"{len(locks)} creatures, {rated} with a drop rate -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
