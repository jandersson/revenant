"""The parser's state as one JSON-ready dict, for an outside reader (#216).

`snapshot(xml_data, fields=None)` is what the session answers a
revenant-send `--state` request with: the room, the vitals, the exp
window, the hands, the status words (client/game/status.py), the
injuries, the spells, the room's players, creatures and objects, the
rested footer, the possessions — everything the docks draw and the
scripts read as `s.state` and `s.status`, so a driver outside the
session (Claude through the `drive` skill, any tool) reads it here
instead of typing LOOK, EXP or HEALTH at the game to learn it. Every
value is built on the call, from the parser's current fields, and
nothing is sent to the game or echoed to a window. `fields` narrows
the answer to the names given; a name the snapshot does not know is
listed under "unknown" rather than refused.
"""

from client.game.status import Status

FIELDS = (
    "name",
    "dead",
    "room",
    "vitals",
    "status",
    "experience",
    "hands",
    "injuries",
    "spells",
    "room_players",
    "room_creatures",
    "room_objs",
    "hostiles",
    "rested",
    "possessions",
)


def _room(xml_data):
    return {
        "title": getattr(xml_data, "room_title", None),
        "uid": getattr(xml_data, "room_uid", None),
        "compass": list(getattr(xml_data, "compass", None) or []),
    }


def _status(status):
    return {
        "posture": status.posture,
        "badges": status.badges,
        "dead": status.dead,
        "stunned": status.stunned,
        "bleeding": status.bleeding,
        "webbed": status.webbed,
        "hidden": status.hidden,
        "invisible": status.invisible,
        "can_act": status.can_act,
        "roundtime": status.roundtime,
        "casttime": status.casttime,
        "hands_empty": status.hands_empty,
        "summary": status.summary(),
    }


def _hands(xml_data):
    return {
        "left": getattr(xml_data, "left_hand", None),
        "right": getattr(xml_data, "right_hand", None),
    }


def _injuries(xml_data):
    return {
        part: list(hurt)
        for part, hurt in (getattr(xml_data, "injuries", None) or {}).items()
    }


def _spells(xml_data):
    return {
        "prepared": getattr(xml_data, "prepared_spell", None),
        "active": dict(getattr(xml_data, "active_spells", None) or {}),
    }


def snapshot(xml_data, fields=None) -> dict:
    """The state as a dict of plain JSON types; `fields` (an iterable of
    names, or None for all of FIELDS) picks the keys."""
    status = Status(xml_data)
    builders = {
        "name": lambda: getattr(xml_data, "name", None),
        "dead": lambda: status.dead,
        "room": lambda: _room(xml_data),
        "vitals": lambda: dict(getattr(xml_data, "vitals", None) or {}),
        "status": lambda: _status(status),
        "experience": lambda: {
            skill: dict(row)
            for skill, row in (getattr(xml_data, "experience", None) or {}).items()
            if isinstance(row, dict)
        },
        "hands": lambda: _hands(xml_data),
        "injuries": lambda: _injuries(xml_data),
        "spells": lambda: _spells(xml_data),
        "room_players": lambda: list(getattr(xml_data, "room_players", None) or []),
        "room_creatures": lambda: list(getattr(xml_data, "room_creatures", None) or []),
        "room_objs": lambda: getattr(xml_data, "room_objs", "") or "",
        "hostiles": lambda: {
            str(exist): engaged
            for exist, engaged in (getattr(xml_data, "hostiles", None) or {}).items()
        },
        "rested": lambda: getattr(xml_data, "rested", None),
        "possessions": lambda: [
            dict(item) for item in (getattr(xml_data, "possessions", None) or [])
        ],
    }
    wanted = list(FIELDS) if not fields else [str(name).strip() for name in fields]
    answer = {}
    unknown = []
    for name in wanted:
        if not name:
            continue
        if name in builders:
            answer[name] = builders[name]()
        else:
            unknown.append(name)
    if unknown:
        answer["unknown"] = unknown
    return answer
