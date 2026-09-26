"""Regenerate client/client/game/hunting_data.py from dr-scripts' hunting
zones: every zone's rooms, province, creatures with their rank ranges,
and each town's zones weakest first.

    uv run python tools/hunting_tables.py [path/to/base-hunting.yaml]

The source is dr-scripts' data/base-hunting.yaml (fetched from GitHub
when no path is given). It is read line by line, not as YAML: the rank
ranges live in the comments above each zone —
"# https://elanthipedia.play.net/Rat   0-30" — which a YAML load drops.
`hunting_zones` gives ZONES (the province from the section banners,
ZOLUREN ... FORFEDHDAR), `hunting_areas_by_town` gives TOWNS;
`escort_zones` (zones reached through a scripted escort) are left out.
The output is committed, never hand-edited (#340).
"""

import pathlib
import re
import sys
import urllib.parse
import urllib.request

SOURCE = (
    "https://raw.githubusercontent.com/elanthia-online/dr-scripts/main/"
    "data/base-hunting.yaml"
)
OUT = (
    pathlib.Path(__file__).parents[1] / "client" / "client" / "game" / "hunting_data.py"
)

_BANNER = re.compile(r"^#{5,}\s+([A-Z][A-Z' ]+?)\s+#{5,}\s*$")
_SECTION = re.compile(r"^([a-z_]+):\s*$")
_ZONE = re.compile(r"^  ([a-z0-9_'\-]+):\s*(?:#.*)?$")
_ROOM = re.compile(r"^\s*-\s*(\d+)")
_TOWN = re.compile(r"^  ([A-Za-z_' ]+):\s*$")
_TOWN_ZONE = re.compile(r"^\s{4}-\s*([a-z0-9_'\-]+)")
_CREATURE = re.compile(
    r"^\s*#\s*https?://elanthipedia\.play\.net/(?P<page>\S+)\s+"
    r"(?P<low>\d+|\?)\s*-\s*(?P<high>\d+|\?)"
)
_COMMENT = re.compile(r"^\s*#\s?(.*?)\s*$")


def creature_name(page):
    """An Elanthipedia page name as a creature: "Wood_Troll_(1)" ->
    "Wood Troll", "Kra%27hei_hatchling" -> "Kra'hei hatchling"."""
    name = urllib.parse.unquote(page).replace("_", " ")
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()


def rank(text):
    return None if text == "?" else int(text)


def parse(text):
    """(zones, towns): zones {name: (province, rooms, creatures, notes)},
    creatures [(name, low, high)]; towns {town: [zone, ...]}."""
    zones, towns = {}, {}
    section = province = zone = town = None
    creatures, notes = [], []
    for line in text.splitlines():
        if match := _BANNER.match(line):
            province = match.group(1).strip().title()
            continue
        if match := _SECTION.match(line):
            section, zone, town = match.group(1), None, None
            creatures, notes = [], []
            continue
        if section == "hunting_zones":
            if match := _CREATURE.match(line):
                page = match.group("page")
                creatures.append(
                    (
                        creature_name(page),
                        rank(match.group("low")),
                        rank(match.group("high")),
                    )
                )
                continue
            if line.strip().startswith("#"):
                comment = _COMMENT.match(line).group(1)
                # A commented-out room ("# - 13126") is no note.
                if (
                    comment
                    and not comment.startswith("#")
                    and not re.match(r"^-\s*\d+", comment)
                ):
                    notes.append(comment)
                continue
            if match := _ZONE.match(line):
                zone = match.group(1)
                zones[zone] = (province, [], list(creatures), list(notes))
                creatures, notes = [], []
                continue
            if zone and (match := _ROOM.match(line)):
                zones[zone][1].append(int(match.group(1)))
        elif section == "hunting_areas_by_town":
            if match := _TOWN.match(line):
                town = match.group(1).replace("_", " ").strip()
                towns[town] = []
                continue
            if town and (match := _TOWN_ZONE.match(line)):
                towns[town].append(match.group(1))
    return zones, towns


def render(zones, towns):
    lines = [
        '"""Hunting zones — generated from dr-scripts\' data/base-hunting.yaml',
        "by tools/hunting_tables.py, do not edit.",
        "",
        "ZONES maps a zone to (province, rooms, creatures, notes): the map",
        "room ids to hunt, [(creature, low rank, high rank)] from the",
        "Elanthipedia-linked comment above the zone (None where it reads",
        '"?"), and the comment\'s other lines. TOWNS maps a town to its',
        "zones, weakest first, as dr-scripts lists them (#340).",
        '"""',
        "",
        "# fmt: off",
        "ZONES = {",
    ]
    for name, (province, rooms, creatures, notes) in zones.items():
        lines.append(
            f"    {name!r}: ({province!r}, {tuple(rooms)!r}, {tuple(creatures)!r}, {tuple(notes)!r}),"
        )
    lines.append("}")
    lines.append("TOWNS = {")
    for town, names in towns.items():
        lines.append(f"    {town!r}: {tuple(names)!r},")
    lines.append("}")
    lines.append("# fmt: on")
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) > 1:
        text = pathlib.Path(argv[1]).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(SOURCE, timeout=30) as response:
            text = response.read().decode("utf-8")
    zones, towns = parse(text)
    OUT.write_text(render(zones, towns), encoding="utf-8")
    print(f"{len(zones)} zones, {len(towns)} towns -> {OUT}")


if __name__ == "__main__":
    main()
