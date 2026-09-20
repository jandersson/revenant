"""Regenerate client/client/game/herbs_data.py from Elanthipedia's Healing herbs page.

    uv run python tools/herb_tables.py [healing_herbs.html]

Fetches https://elanthipedia.play.net/Healing_herbs (or reads a saved
copy) and writes two tables: HERBS, one row per herb with what it
heals (the wiki's body part, internal/external location and wounds/
scars type, kept verbatim) plus the foraging columns; and SHOPS, the
herb products each named store stocks. client/game/herbs.py maps the
wiki's vocabulary onto the HEALTH wound areas. Run it when the wiki
changes; the output is committed so the client needs no network.
"""

import html
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://elanthipedia.play.net/Healing_herbs"
OUT = (
    Path(__file__).resolve().parents[1] / "client" / "client" / "game" / "herbs_data.py"
)

HERB_COLUMNS = (
    "Item",
    "Ranks",
    "Season",
    "Time",
    "Special Conditions",
    "Terrain",
    "Body Part Healed",
    "Location",
    "Type",
)


def cells_of(row):
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
    return [
        html.unescape(re.sub(r"<[^>]+>", "", cell)).strip().replace("\n", " ")
        for cell in cells
    ]


def tables_of(page):
    return [
        [cells_of(row) for row in re.findall(r"<tr.*?</tr>", table, re.S)]
        for table in re.findall(r"<table.*?</table>", page, re.S)
    ]


def herb_rows(page):
    """(name, ranks, season, time, conditions, terrain, part, location,
    kind) per herb, the wiki's words, lowercased where they are keys."""
    for table in tables_of(page):
        if table and table[0][: len(HERB_COLUMNS)] == list(HERB_COLUMNS):
            for cells in table[1:]:
                if len(cells) < len(HERB_COLUMNS) or not cells[0]:
                    continue
                name, ranks, season, time, conditions, terrain, part, location, kind = (
                    cells[: len(HERB_COLUMNS)]
                )
                yield (
                    name.lower(),
                    int(ranks) if ranks.isdigit() else None,
                    season.lower(),
                    time.lower(),
                    conditions,
                    terrain,
                    part.lower(),
                    location.lower(),
                    kind.lower(),
                )
            return
    raise SystemExit("no herb table found — did the page change?")


_DOUBLED_TOWN = re.compile(r"(\s\([^()]+\))\1$")


def store_name(text):
    """A store as the table names it, with a town given twice collapsed:
    the page writes "Alchemy Society (Crossing) (Crossing)" where the
    shop's own title already carries the town (#199)."""
    return _DOUBLED_TOWN.sub(r"\1", text.strip())


def shop_rows(page):
    """(product, stores) per herb product the shop table lists."""
    for table in tables_of(page):
        if table and table[0][:2] == ["Herb", "Store locations"]:
            for cells in table[1:]:
                if len(cells) < 2 or not cells[0]:
                    continue
                stores = [
                    store_name(store)
                    for store in re.split(r",\s*(?=[^,]*\()", cells[1])
                    if store.strip()
                ]
                yield cells[0].lower(), tuple(stores)
            return
    raise SystemExit("no shop table found — did the page change?")


def render(herbs, shops):
    lines = [
        '"""Healing herbs and where shops stock them — generated, do not edit.',
        "",
        f"Source: {URL} (tools/herb_tables.py regenerates this file).",
        "HERBS rows are (name, foraging ranks, season, time, conditions,",
        "terrain, body part healed, location, kind) in the wiki's own words:",
        "part is one of its body parts (all, limb, torso, skinnerve, ...),",
        "location is internal, external or internal/external, kind is wounds",
        "or scars; an item that heals nothing by itself carries blanks.",
        "SHOPS rows are (product, stores) from the availability table.",
        '"""',
        "",
        "# fmt: off",
        "HERBS = (",
    ]
    for row in herbs:
        lines.append(f"    {row!r},")
    lines += [")", "", "SHOPS = ("]
    for row in shops:
        lines.append(f"    {row!r},")
    lines += [")", "# fmt: on", ""]
    return "\n".join(lines)


def main(argv):
    if len(argv) > 1:
        page = Path(argv[1]).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(URL) as response:
            page = response.read().decode("utf-8")
    herbs = list(herb_rows(page))
    shops = list(shop_rows(page))
    OUT.write_text(render(herbs, shops), encoding="utf-8")
    print(f"wrote {len(herbs)} herbs and {len(shops)} shop rows to {OUT}")


if __name__ == "__main__":
    main(sys.argv)
