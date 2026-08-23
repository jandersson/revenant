"""Per-character window-layout persistence (#74), Qt-free.

Side-by-side sessions each get their own window, but one shared
QSettings pair meant the last-closed window dictated every window's
dock layout. These helpers scope the layout keys by character; the
GUI does the actual QSettings reads and writes. The unscoped legacy
keys stay in play as the fallback, so a character without a saved
arrangement inherits the most recently closed layout and diverges
from there.
"""


def layout_keys(character):
    """The settings keys a window's layout lives under: the character's
    own when one is known, the unscoped legacy pair otherwise."""
    if character:
        return (f"layout/{character}/geometry", f"layout/{character}/windowState")
    return ("geometry", "windowState")


def save_pairs(character, geometry, state):
    """Everything closeEvent should write: the character's own keys
    plus the legacy pair, which doubles as the newest-layout fallback
    for characters that have never saved an arrangement."""
    pairs = {"geometry": geometry, "windowState": state}
    if character:
        geometry_key, state_key = layout_keys(character)
        pairs[geometry_key] = geometry
        pairs[state_key] = state
    return pairs
