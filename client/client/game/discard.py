"""What a script may DROP: an allowlist, and the one way to drop.

Nothing the client sends drops an item unless the item is on the list:
a dropped item is a lost item (the operator's rule, 2026-09-12). The
built-in list is the foraged junk a training loop makes and discards
on purpose — ;mechlore's grass and the grass rope it braids — and
nothing else; settings.json's `droppable` (a list of item names as
typed after DROP MY) extends it for a character's own junk. Every
script drops through drop() below, which refuses anything else with
an echo and sends nothing; a hand is freed with STOW, a load lightened
by stowing or banking coins, never by dropping.

Names are matched whole, so "grass rope" is droppable and "rope" is
not — the bundling rope ;hunt's skins ride on is "bundling rope".
"""

from client.settings import setting

DEFAULT_DROPPABLE = ("grass", "grass rope")


def droppable_items() -> frozenset:
    """The built-in list plus settings.json's `droppable`, lowercased."""
    extra = setting("droppable") or []
    if isinstance(extra, str):
        extra = extra.split(",")
    names = [str(name).strip().lower() for name in extra if str(name).strip()]
    return frozenset(name.lower() for name in DEFAULT_DROPPABLE) | frozenset(names)


def droppable(item) -> bool:
    return str(item or "").strip().lower() in droppable_items()


def drop(s, item, ask):
    """DROP MY <item> through the script's ask(), when the item is on
    the list; otherwise an echo saying so, nothing sent, and None."""
    if not droppable(item):
        s.echo(
            f"drop refused: {item!r} is not on the droppable list — stow it "
            "instead, or add it to settings.json's `droppable`"
        )
        return None
    return ask(s, f"drop my {item}")
