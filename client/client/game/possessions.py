"""Possessions by the game's exist ids (#184).

INV LIST wraps every item in a command link that carries its id —
`<d cmd='remove #53174575'>a lumpy bundle</d>` for a worn item,
`<d cmd='get #50886622 in #53174575'>a rat tail</d>` for a container's
content (captured 2026-09-13) — and the game accepts `#<id>` as a
noun, so a script can act on exactly this handaxe rather than on "my
handaxe" and whatever the game matches first. The parser
(client/engine/xml_data.py) collects the links as the listing streams,
whoever asked for it; `build()` turns them into items, `find()` looks
one up by noun, and `rows()` gives `;sheet` its inventory rows with
the ids beside the names. Only INV LIST (4-5 s of roundtime, on
demand) and the hand tags carry ids in our stream — story lines and
room objects do not — so the model is exact as of the last listing,
not live between them.
"""

import re

from client.game.inventory import _depth

# "remove #53174575", "get #50886622 in #53174575", "get #50886688".
# A state the listing appends to a container's name: "a plain steel
# coffer (closed)" (2026-09-26) — not part of the noun.
_STATE_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")


def noun_of(name):
    """The item's noun: the name's last word, a trailing "(closed)" or
    "(open)" dropped (#323: both of Cecil's boxes read as "(closed)", and
    ;boxes never found the coffer in the backpack)."""
    words = _STATE_SUFFIX.sub("", str(name or "")).split()
    return words[-1] if words else ""


_COMMAND = re.compile(
    r"^\s*(?P<verb>[a-z]+)\s+#(?P<exist>\d+)(?:\s+in\s+#(?P<container>\d+))?",
    re.IGNORECASE,
)


def parse_command(cmd):
    """(verb, exist, container exist or None) from a link's cmd, or
    None for a link that names no item ("inventory help")."""
    match = _COMMAND.match(cmd or "")
    if not match:
        return None
    return match.group("verb").lower(), match.group("exist"), match.group("container")


def build(links):
    """Items from the listing's links, in the listing's order:
    `links` are (indent, cmd, name) — the whitespace and dash before
    the link on its line, the link's cmd, its text. Each item:
    {"exist", "name", "noun", "verb", "container_exist", "worn",
    "depth"}; links that name no item are skipped."""
    items = []
    for indent, cmd, name in links:
        parsed = parse_command(cmd)
        name = " ".join(str(name or "").split())
        if parsed is None or not name:
            continue
        verb, exist, container = parsed
        items.append(
            {
                "exist": exist,
                "name": name,
                "noun": noun_of(name),
                "verb": verb,
                "container_exist": container,
                "worn": verb == "remove",
                # the dash after the spaces is not indentation, as in the text
                "depth": _depth(
                    len(str(indent or "")) - len(str(indent or "").lstrip(" "))
                ),
            }
        )
    return items


def find(items, noun):
    """The items whose noun is `noun` or whose name carries the word,
    in the listing's order; [] for none."""
    wanted = str(noun or "").strip().lower()
    if not wanted:
        return []
    return [
        item
        for item in items or []
        if item["noun"].lower() == wanted or wanted in item["name"].lower().split()
    ]


def rows(items):
    """`;sheet`'s inventory rows from the items — one row per item
    (ids tell twins apart, so nothing collapses), each naming its
    container by name and both by id."""
    names = {item["exist"]: item["name"] for item in items}
    return [
        {
            "container": names.get(item["container_exist"]),
            "item": item["name"],
            "quantity": 1,
            "depth": item["depth"],
            "exist": item["exist"],
            "container_exist": item["container_exist"],
        }
        for item in items
    ]
