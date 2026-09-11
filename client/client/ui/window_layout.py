"""Per-character window-layout persistence (#74), Qt-free.

Side-by-side sessions each get their own window, but one shared
QSettings pair meant the last-closed window dictated every window's
dock layout. These helpers scope the layout keys by character; the
GUI does the actual QSettings reads and writes. The unscoped legacy
keys stay in play as the fallback, so a character without a saved
arrangement inherits the most recently closed layout and diverges
from there.

startup_layout() picks what to restore before the window is first
shown: the character's own layout when the character is already known
(the session registry names it for an attach, the login for direct
mode), the legacy pair otherwise. Restoring before the first show is
the only order Qt has proved safe with every saved state; apply() —
hide, restore, show — is the fallback for a character learned only
from the "character" frame, and one saved state still aborted inside
Qt on that path (#124, #140).
"""


def layout_keys(character):
    """The settings keys a window's layout lives under: the character's
    own when one is known, the unscoped legacy pair otherwise."""
    if character:
        return (f"layout/{character}/geometry", f"layout/{character}/windowState")
    return ("geometry", "windowState")


def startup_layout(get, character):
    """(geometry, state, scoped) to restore before the first show.

    `get(key)` reads a settings value. The character's own pair wins
    when either half is saved (scoped=True); a character without a
    layout inherits the legacy pair (#74) and scoped is False, so the
    caller still applies the character's layout if one is saved later."""
    if character:
        geometry_key, state_key = layout_keys(character)
        geometry, state = get(geometry_key), get(state_key)
        if geometry or state:
            return geometry, state, True
    return get("geometry"), get("windowState"), False


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
