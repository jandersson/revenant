"""Regenerate client/client/wounds_data.py from Elanthipedia's Damage page.

    uv run python tools/wound_tables.py [damage.html]

Fetches https://elanthipedia.play.net/Damage (or reads a saved copy)
and writes the wound wording tables the HEALTH parser matches against:
one row per (area, severity, kind, phrase), placeholders kept as the
wiki writes them ("[right/left]", "[hand/arm/leg/tail]"). Run it when
the wiki changes; the output is committed so the client needs no
network. The generic "(touch)" rows carry no body area and are left
out — HEALTH never shows them.
"""

import html
import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://elanthipedia.play.net/Damage"
OUT = Path(__file__).resolve().parents[1] / "client" / "client" / "wounds_data.py"

# The page's wound tables, in order of its sections.
AREAS = ("head", "eye", "neck", "chest", "abdomen", "back", "limb", "skin")
KINDS = ("external", "scar", "internal", "internal_scar")
LEVELS = {
    "insignificant": 1,
    "negligible": 2,
    "minor": 3,
    "harmful": 4,
    "damaging": 5,
    "severe": 6,
    "devastating": 7,
    "useless": 8,
}


def cells_of(row):
    cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
    return [
        html.unescape(re.sub(r"<[^>]+>", "", cell)).strip().replace("\n", " ")
        for cell in cells
    ]


def rows_of(page):
    tables = re.findall(r"<table.*?</table>", page, re.S)
    wound_tables = [
        table for table in tables if "Fresh External" in table or "Fresh Skin" in table
    ]
    assert len(wound_tables) == len(AREAS), len(wound_tables)
    for area, table in zip(AREAS, wound_tables):
        for row in re.findall(r"<tr.*?</tr>", table, re.S)[1:]:
            cells = cells_of(row)
            severity = cells[0].lower()
            if "(touch)" in severity:
                continue  # generic wording without a body area
            level = LEVELS[severity.split()[0]]
            for kind, phrase in zip(KINDS, cells[1:5]):
                phrase = phrase.strip()
                if phrase and phrase != "-":
                    yield area, level, kind, phrase


def main(argv):
    if len(argv) > 1:
        page = Path(argv[1]).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(URL) as response:
            page = response.read().decode("utf-8")
    rows = list(rows_of(page))
    lines = [
        '"""Wound wordings by body area, severity and kind — generated, do not edit.',
        "",
        f"Source: {URL} (tools/wound_tables.py regenerates this file).",
        "Rows are (area, level, kind, phrase); levels 1-8 are insignificant,",
        "negligible, minor, harmful, damaging, severe, devastating, useless;",
        "kinds are external, scar, internal, internal_scar. Placeholders",
        '"[right/left]" / "[left/right]" and "[hand/arm/leg/tail]" are the',
        "wiki's; client/wounds.py expands them.",
        '"""',
        "",
        "# fmt: off",
        "ROWS = (",
    ]
    for area, level, kind, phrase in rows:
        lines.append(
            f"    ({json.dumps(area)}, {level}, {json.dumps(kind)}, {json.dumps(phrase)}),"
        )
    lines.append(")")
    lines.append("# fmt: on")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main(sys.argv)
