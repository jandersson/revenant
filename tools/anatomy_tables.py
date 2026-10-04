"""Regenerate client/client/game/anatomy_data.py from dr-scripts' anatomy
charts: each First Aid chart's name, the word TURN finds its page by,
and the Scholarship it asks.

    uv run python tools/anatomy_tables.py [path/to/base-anatomy-charts.yaml]

The source is dr-scripts' data/base-anatomy-charts.yaml (fetched from
GitHub when no path is given), read line by line: `first_aid_charts`,
then a chart's name, its `index` and its `scholarship`. The output is
committed, never hand-edited (;compendium).
"""

import pathlib
import re
import sys
import urllib.request

SOURCE = (
    "https://raw.githubusercontent.com/elanthia-online/dr-scripts/main/"
    "data/base-anatomy-charts.yaml"
)
OUT = (
    pathlib.Path(__file__).parents[1] / "client" / "client" / "game" / "anatomy_data.py"
)

_NAME = re.compile(r"^  (?P<name>\S.*?):\s*$")
_FIELD = re.compile(r"^    (?P<key>index|scholarship):\s*(?P<value>.+?)\s*$")


def _unquote(value):
    value = value.strip()
    if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse(text):
    """{name: (index, scholarship)} in the file's order."""
    charts, name, fields = {}, None, {}
    for line in text.splitlines():
        if match := _NAME.match(line):
            if name and {"index", "scholarship"} <= fields.keys():
                charts[name] = (fields["index"], int(fields["scholarship"]))
            name, fields = _unquote(match.group("name")), {}
        elif name and (match := _FIELD.match(line)):
            fields[match.group("key")] = _unquote(match.group("value"))
    if name and {"index", "scholarship"} <= fields.keys():
        charts[name] = (fields["index"], int(fields["scholarship"]))
    return charts


def render(charts):
    rows = "\n".join(
        f"    {name!r}: ({index!r}, {need})," for name, (index, need) in charts.items()
    )
    return f'''"""First Aid anatomy charts — generated from dr-scripts'
data/base-anatomy-charts.yaml by tools/anatomy_tables.py, do not edit.

CHARTS maps a chart's name, as LOOK MY COMPENDIUM lists it, to (the
word TURN MY COMPENDIUM TO finds its page by, the Scholarship it asks).
"""

# fmt: off
CHARTS = {{
{rows}
}}
# fmt: on
'''


def main(argv):
    if len(argv) > 1:
        text = pathlib.Path(argv[1]).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(SOURCE, timeout=30) as response:
            text = response.read().decode("utf-8")
    charts = parse(text)
    OUT.write_text(render(charts), encoding="utf-8")
    print(f"{len(charts)} charts -> {OUT}")


if __name__ == "__main__":
    main(sys.argv)
