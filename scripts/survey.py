"""Record unmapped rooms into the local map overlay as you walk:  ;survey

Every room you enter that the community map doesn't know (by its nav
uid) is appended to ~/.revenant/mapdb/local.json — titled, uid'd, and
linked from the room you came from with the exact command that got you
there, so ;go2 can walk the route natively after its next map load.
Known rooms gain nothing; the overlay never duplicates. Run it before
wandering event areas or private zones the community map lacks.
Stop with:  ;stop survey
"""

import json

# Local overlay ids live far above community ids and derive from the
# room's uid, so re-surveying the same room is idempotent.
LOCAL_ID_BASE = 10_000_000


def local_id(uid):
    return LOCAL_ID_BASE + uid


def load_overlay(path):
    try:
        with open(path) as stream:
            rooms = json.load(stream)
    except (OSError, ValueError):
        return []
    return rooms if isinstance(rooms, list) else []


def save_overlay(path, rooms):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rooms, indent=1))


def overlay_room(overlay, uid):
    for room in overlay:
        if uid in (room.get("uid") or []):
            return room
    return None


def record_room(overlay, uid, title):
    """Add an unmapped room to the overlay; returns it (existing or new)."""
    room = overlay_room(overlay, uid)
    if room is None:
        room = {"id": local_id(uid), "uid": [uid], "title": [title], "wayto": {}}
        overlay.append(room)
    return room


def record_edge(overlay, db, from_uid, command, to_uid):
    """Link from_uid -> to_uid with the command that walked it.

    A source the overlay owns gains the edge directly. A source only
    the community map knows gets shadow-copied into the overlay first —
    the overlay loads after the community rooms, so the copy (with its
    extra edge) wins. Unknown sources record nothing."""
    if not command:
        return False
    destination = str(local_id(to_uid))
    source = overlay_room(overlay, from_uid)
    if source is None:
        community_id = db.room_by_uid(from_uid)
        if community_id is None:
            return False
        source = dict(db.rooms[community_id])
        source["wayto"] = dict(source.get("wayto") or {})
        overlay.append(source)
    source["wayto"][destination] = command
    return True


def known(db, overlay, uid):
    return db.room_by_uid(uid) is not None or overlay_room(overlay, uid) is not None


def main(s):
    from client.mapdb import MapDB, local_mapdb_path, mapdb_path

    if not mapdb_path().is_file():
        s.echo("map database missing — run ;go2 update first")
        return
    db = MapDB.load()
    path = local_mapdb_path()
    overlay = load_overlay(path)
    s.echo(f"surveying — unmapped rooms will be recorded to {path}")

    last_uid = getattr(s.state, "room_uid", None)
    last_sent = None
    recorded = 0
    while True:
        stream, text = s.get(timeout=None, streams=None)
        if stream == "sent":
            last_sent = text.strip()
            continue
        if stream != "room":
            continue
        uid_text, _, title = text.strip().partition("\t")
        if not uid_text:
            last_uid = None
            continue
        uid = int(uid_text)
        if not known(db, overlay, uid):
            record_room(overlay, uid, title or "[unmapped]")
            linked = last_uid is not None and record_edge(
                overlay, db, last_uid, last_sent, uid
            )
            save_overlay(path, overlay)
            recorded += 1
            how = f" (via {last_sent!r})" if linked else ""
            s.echo(f"recorded unmapped room {title or uid}{how} — {recorded} so far")
        last_uid = uid
