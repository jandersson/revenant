"""Which cached characters still need a ;sheet snapshot — Qt-free, no IO.

The roster sweep (tools/roster_sweep.py) walks the characters that have
no snapshot yet; this module decides who those are, given the cached
login defaults and the names already in xp.db. Pure functions, so the
selection is testable without a game, a database, or a window (#111).

`guild` only reaches xp.db's character table through `;sheet`, so a
character with no snapshot is invisible to `;circle` and to beholder's
Circle-gates view. "Pending" here means exactly that: cached in a
roster, absent from the history.
"""


def cached_characters(defaults):
    """[(account, character)] for every character in the cached rosters,
    in a stable order: account by name, then the roster's own order.

    Falls back to the legacy flat cache (a single account/character
    pair) written before per-account rosters existed.
    """
    accounts = defaults.get("accounts")
    if isinstance(accounts, dict) and accounts:
        pairs = []
        for key, entry in sorted(accounts.items()):
            account = entry.get("account") or key
            for name in entry.get("characters") or []:
                pairs.append((account, name))
        return pairs
    account = defaults.get("account") or ""
    character = defaults.get("character") or ""
    return [(account, character)] if character else []


def pending_characters(defaults, snapshotted):
    """[(account, character)] for the cached characters with no snapshot.

    `snapshotted` is any iterable of character names; matching is
    case-insensitive, since the game's own capitalisation is what lands
    in xp.db while a roster may hold anything.
    """
    have = {str(name).lower() for name in snapshotted}
    return [
        (account, character)
        for account, character in cached_characters(defaults)
        if character.lower() not in have
    ]


def snapshot_summary(defaults, snapshotted):
    """(total, done, pending) counts for the cached roster — the line
    the sweep prints before it starts."""
    pairs = cached_characters(defaults)
    pending = pending_characters(defaults, snapshotted)
    return len(pairs), len(pairs) - len(pending), len(pending)
