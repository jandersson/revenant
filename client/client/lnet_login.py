"""Where an LNet name's password comes from — the OS keychain, Qt-free.

Lookup order: LNET_PASSWORD for one run, then the keychain (service
"revenant-lnet", one entry per name, the way the game password lives
under "revenant"), then the git-ignored chat/lnet_password.txt that
predates the keychain — a legacy fallback, never the recommended
place. remember() writes the keychain entry after a login the user
asked to keep (#141). Nothing here ever writes a file.
"""

import os

import keyring
import keyring.errors

from client.client_logger import ClientLogger

KEYRING_SERVICE = "revenant-lnet"
log = ClientLogger()


def keychain_password(name):
    """The keychain entry for an LNet name, or None (also None without a
    usable keyring backend — a missing keychain must not stop a chat)."""
    try:
        return keyring.get_password(KEYRING_SERVICE, name)
    except keyring.errors.KeyringError:
        log.log.debug("No usable keyring backend for LNet; treating as unset")
        return None


def lnet_password(name, legacy_file=None):
    """The password to log `name` in with, or None for an unprotected name.

    `legacy_file` is a callable returning the pre-keychain file's
    contents (chat.chat.get_password); it is consulted last.
    """
    if password := os.environ.get("LNET_PASSWORD"):
        return password
    if password := keychain_password(name):
        return password
    if legacy_file is not None:
        return legacy_file() or None
    return None


def remember(name, password):
    """Store the name's password in the keychain; False when no backend
    can hold it (the caller says so, and the password lives for this
    run only)."""
    try:
        keyring.set_password(KEYRING_SERVICE, name, password)
        return True
    except keyring.errors.KeyringError:
        log.log.warning("No usable keyring backend; LNet password not saved")
        return False


def identities(defaults):
    """The LNet names the standalone window may log in as: your own
    characters, from the cached account rosters the picker uses
    (~/.revenant/login.json, never the repo). LNet names are character
    names; a made-up one risks the account, so the window offers these
    and refuses anything else."""
    from client.roster import cached_characters

    names = []
    for _, character in cached_characters(defaults):
        if character and character not in names:
            names.append(character)
    return names


def allowed(name, defaults):
    """The roster spelling of `name` (case-insensitive), or None."""
    wanted = name.strip().lower()
    return next((n for n in identities(defaults) if n.lower() == wanted), None)
