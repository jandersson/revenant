"""Regenerate client/client/game/creatures_data.py from Elanthipedia's
creature pages: every page that uses the Critter template, its level
and the ranks it teaches to (MinCap, MaxCap).

    uv run python tools/creature_tables.py

Pages are read through the wiki's API — the list of pages embedding
Template:Critter, then their wikitext fifty to a request — so the whole
bestiary is a few dozen requests, not one per creature. A creature
teaches a skill fully below MinCap, less and less up to MaxCap, and
nothing past it (Elanthipedia: Experience, the Critter template's
fields); ;hunt says which trained skills a ground has outgrown (#322).
"""

import json
import pathlib
import re
import time
import urllib.parse
import urllib.request

API = "https://elanthipedia.play.net/api.php"
USER_AGENT = "revenant-wiki-cache/1 (a DragonRealms client's research cache)"
OUT = (
    pathlib.Path(__file__).parents[1]
    / "client"
    / "client"
    / "game"
    / "creatures_data.py"
)
BATCH = 50
PAUSE = 1.0  # seconds between requests: the wiki is a community's

_FIELD = re.compile(r"^\|\s*([\w ]+?)\s*=\s*(.*?)\s*$", re.MULTILINE)
_NUMBER = re.compile(r"\d+")
_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
# [[race is::goblin]] -> goblin, [[Page|shown]] -> shown, [[Page]] -> Page
_LINK = re.compile(r"\[\[(?:[^\]|]*::)?(?:[^\]|]*\|)?([^\]]*)\]\]")


def api(params):
    query = urllib.parse.urlencode({**params, "format": "json"})
    request = urllib.request.Request(
        f"{API}?{query}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def critter_titles():
    titles, cont = [], {}
    while True:
        data = api(
            {
                "action": "query",
                "list": "embeddedin",
                "eititle": "Template:Critter",
                "einamespace": 0,
                "eilimit": 500,
                **cont,
            }
        )
        titles += [page["title"] for page in data["query"]["embeddedin"]]
        if "continue" not in data:
            return titles
        cont = data["continue"]
        time.sleep(PAUSE)


def wikitexts(titles):
    for start in range(0, len(titles), BATCH):
        chunk = titles[start : start + BATCH]
        data = api(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": "|".join(chunk),
            }
        )
        for page in data["query"]["pages"].values():
            revisions = page.get("revisions") or []
            if revisions:
                yield page["title"], revisions[0]["slots"]["main"]["*"]
        time.sleep(PAUSE)


def number(text):
    match = _NUMBER.search(text or "")
    return int(match.group()) if match else None


def name_of(title, fields):
    """The creature's name as the game says it, lowercased: the
    template's Critter Name, else the title without its "(1)" or
    "(creature)"."""
    name = _LINK.sub(lambda link: link.group(1), fields.get("critter name") or title)
    name = re.sub(r"<[^>]+>|'{2,}", "", name)
    return " ".join(_PAREN.sub("", name).split()).lower()


def parse(title, text):
    """(name, level, mincap, maxcap) for a Critter page, or None when it
    names no MaxCap."""
    fields = {key.strip().lower(): value for key, value in _FIELD.findall(text)}
    maxcap = number(fields.get("maxcap"))
    if maxcap is None:
        return None
    return (
        name_of(title, fields),
        number(fields.get("level")),
        number(fields.get("mincap")),
        maxcap,
    )


def merge(rows):
    """One entry per name: variants of one creature ("blood wolf (1)",
    "(2)") share a name, and the most generous caps are kept — the
    check says a ground is outgrown only when no variant teaches."""
    table = {}
    for name, level, mincap, maxcap in rows:
        old = table.get(name)
        if old is None or maxcap > old[2]:
            table[name] = (level, mincap, maxcap)
    return dict(sorted(table.items()))


def render(table):
    lines = [
        '"""Creatures and the ranks they teach to — generated, do not edit.',
        "",
        f"Source: Elanthipedia's pages using Template:Critter via {API}",
        "(tools/creature_tables.py regenerates this file). CAPS maps a",
        "creature's name, lowercased, to (level, MinCap, MaxCap): full",
        "learning below MinCap, none past MaxCap; variants of one name keep",
        "the highest MaxCap. level or MinCap is None where the page has none.",
        '"""',
        "",
        "# fmt: off",
        "CAPS = {",
    ]
    for name, (level, mincap, maxcap) in table.items():
        lines.append(f"    {name!r}: ({level!r}, {mincap!r}, {maxcap!r}),")
    lines += ["}", "# fmt: on", ""]
    return "\n".join(lines)


def main():
    titles = critter_titles()
    rows = [row for title, text in wikitexts(titles) if (row := parse(title, text))]
    table = merge(rows)
    OUT.write_text(render(table), encoding="utf-8")
    print(f"{len(titles)} pages, {len(table)} creatures with caps -> {OUT}")


if __name__ == "__main__":
    main()
