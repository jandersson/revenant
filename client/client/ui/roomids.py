"""The map room id after each room name — the decision, toolkit-free.

Lich's roomnumbers script appends the map id to the room title so a
`;go2 1234` target can be read straight off the story; the Map dock
already resolves that id from the "room" stream. What is left is
timing: the game's room-name line and the engine's "room" frame come
in either order (the <nav> uid can land a line before the title), so
this tracker pairs a shown title with a resolved room whichever
arrives first, and answers with the id to append exactly once per
room-name line. The window keeps a cursor at the end of that line and
inserts what the tracker hands back (settings: show_room_ids).
"""


def room_id_suffix(room_id) -> str:
    """What follows the title: the map id in parentheses, dim."""
    return f" ({room_id})"


class RoomIdTracker:
    def __init__(self):
        self._pending_title = None  # a shown title not annotated yet
        self._room = None  # (map id, title) of the last resolved frame

    def title_shown(self, title):
        """A room-name line was appended. The id to append now when the
        matching frame already resolved, else None (the frame's turn)."""
        title = (title or "").strip()
        if not title:
            return None
        self._pending_title = title
        if self._room is not None and self._room[1] == title:
            self._pending_title = None
            return self._room[0]
        return None

    def room_resolved(self, room_id, title):
        """A "room" frame resolved on the map (room_id None: off the
        map). The id to append to the shown title when it matches and
        still waits, else None."""
        title = (title or "").strip()
        self._room = (room_id, title) if room_id is not None else None
        if room_id is None or self._pending_title != title:
            return None
        self._pending_title = None
        return room_id
