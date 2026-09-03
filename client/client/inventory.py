"""Read INV FULL's nested item list into flat, searchable rows.

`;sheet` snapshots this into xp.db so "which character has that thing?"
is a query rather than 31 logins (#117). Qt-free and IO-free: the
parser is the whole module, and tests exercise it against captured
traffic.

The game answers INV FULL with an indented tree::

    You take a moment and rummage about your person, taking stock ...
    You have:
      an ornate scabbard
         -a short sword
         -a broadsword
      a curved lunch pail labeled "Victuals"
         -a goblet of rich bloodwyne
         -a goblet of rich bloodwyne
    [Use INVENTORY HELP for more options.]

Top-level items are indented two spaces; every level below adds three
more and a leading "-". Depth is derived from the indentation rather
than the dashes, so a deeper tree than the three levels we have
captured still parses.

Rows come back flat, each naming its immediate container, because that
is what answers the question the table exists for. Identical items in
the same container collapse into one row with a quantity — one
captured character carried six identical goblets, and another
thirty-nine identical crystal shards.
"""

import re

HEADER = "You have:"
# The game closes the list with its own footer; the roundtime line that
# follows is not part of the inventory.
FOOTER = "[Use INVENTORY HELP for more options.]"

TOP_INDENT = 2  # "  a target shield"
STEP = 3  # each level below adds three spaces and a "-"

_ITEM = re.compile(r"^(\s*)-?(.*\S)\s*$")


def _depth(indent):
    """Nesting level from an item line's leading whitespace."""
    if indent <= TOP_INDENT:
        return 0
    return (indent - TOP_INDENT + STEP - 1) // STEP


def parse_inventory(text):
    """[{"container", "item", "quantity", "depth"}] from INV FULL output.

    `container` is None for what the character wears or holds directly.
    Returns [] when the answer holds no inventory list at all — a
    refusal or an unanswered command must store nothing rather than an
    empty inventory, which would read as "owns nothing".
    """
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == HEADER)
    except StopIteration:
        return []

    counts = {}
    order = []
    stack = []  # the container name at each depth
    for line in lines[start + 1 :]:
        if FOOTER in line:
            break
        if not line.strip():
            continue
        match = _ITEM.match(line)
        if not match:
            continue
        indent, item = len(match.group(1)), match.group(2)
        depth = _depth(indent)
        del stack[depth:]
        container = stack[depth - 1] if depth and len(stack) >= depth else None
        stack.append(item)
        key = (container, item, depth)
        if key not in counts:
            order.append(key)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"container": container, "item": item, "quantity": counts[key], "depth": depth}
        for key in order
        for container, item, depth in (key,)
    ]


def flatten(rows):
    """ "container > item" strings, the shape a roster-wide search reads."""
    return [
        f"{row['container']} > {row['item']}" if row["container"] else row["item"]
        for row in rows
    ]
