"""Per-character window-layout persistence (#74), Qt-free.

Side-by-side sessions each get their own window, but one shared
QSettings pair meant the last-closed window dictated every window's
dock layout. These helpers scope the layout keys by character; the
GUI does the actual QSettings reads and writes. The unscoped legacy
keys stay in play as the fallback, so a character without a saved
arrangement inherits the most recently closed layout and diverges
from there.

apply() lands a saved layout on a live window with the window hidden
for the duration: restoring dock state onto a shown window aborted
the whole process inside Qt at the next child setVisible (#124).
"""


def layout_keys(character):
    """The settings keys a window's layout lives under: the character's
    own when one is known, the unscoped legacy pair otherwise."""
    if character:
        return (f"layout/{character}/geometry", f"layout/{character}/windowState")
    return ("geometry", "windowState")


def apply(window, geometry, state):
    """Restore a saved geometry and dock state onto a window, hidden
    while they land; True when there was anything to restore.

    The character's layout arrives after the window is already shown
    (the "character" frame names who is playing). Qt restores dock
    state cleanly on a hidden window — the order its docs assume — but
    on a shown one, a state that reveals docks the startup layout had
    hidden left the window in a state where the next setVisible on a
    child aborted the process (captured 2026-09-04, PyQt 6.11, #124).
    """
    if not geometry and not state:
        return False
    shown = window.isVisible()
    if shown:
        window.hide()
    if geometry:
        window.restoreGeometry(geometry)
    if state:
        window.restoreState(state)
    if shown:
        window.show()
    return True


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
