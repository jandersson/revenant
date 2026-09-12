"""The character's state in words — a readable face over the parser's
raw fields, for scripts and for ;status.

The parser (client/engine/xml_data.py) keeps what the game pushes:
indicator flags by their icon id, vitals by name, the hands, the room,
the injuries, the exp window, the roundtime clock. A script that wants
"is he stunned" should not spell IconSTUNNED and "y". This is the
`status(state)` view — Lich's idiom, where dr-scripts read
`stunned?`, `hidden?`, `checkprone` and friends off XMLData instead
of the tags — with the posture as one word, the badges as booleans,
the hands as nouns, the timers as seconds left, and a one-line
summary. Every value is derived on access: nothing is cached, so a
view taken once stays current. Model: docs/protocol.md.
"""

POSTURES = (
    ("IconSTANDING", "standing"),
    ("IconKNEELING", "kneeling"),
    ("IconSITTING", "sitting"),
    ("IconPRONE", "prone"),
)
BADGES = (
    ("IconDEAD", "dead"),
    ("IconSTUNNED", "stunned"),
    ("IconBLEEDING", "bleeding"),
    ("IconWEBBED", "webbed"),
    ("IconHIDDEN", "hidden"),
    ("IconINVISIBLE", "invisible"),
    ("IconJOINED", "joined"),
)
VITALS = ("health", "mana", "stamina", "spirit", "concentration")


class Status:
    """A live view of a parser state; construct with status(state)."""

    def __init__(self, state):
        self._state = state

    # -- flags ------------------------------------------------------------

    def _on(self, icon):
        indicators = getattr(self._state, "indicator", None) or {}
        return indicators.get(icon) == "y"

    @property
    def dead(self):
        return self._on("IconDEAD")

    @property
    def stunned(self):
        return self._on("IconSTUNNED")

    @property
    def bleeding(self):
        return self._on("IconBLEEDING")

    @property
    def webbed(self):
        return self._on("IconWEBBED")

    @property
    def hidden(self):
        return self._on("IconHIDDEN")

    @property
    def invisible(self):
        return self._on("IconINVISIBLE")

    @property
    def joined(self):
        return self._on("IconJOINED")

    @property
    def posture(self):
        """ "standing", "kneeling", "sitting", "prone", or None before the
        game has said."""
        for icon, word in POSTURES:
            if self._on(icon):
                return word
        return None

    @property
    def standing(self):
        return self.posture == "standing"

    @property
    def prone(self):
        return self.posture == "prone"

    @property
    def badges(self):
        """The states that are on, in the strip's order: ["stunned",
        "bleeding"]; "dead" first when it is."""
        return [word for icon, word in BADGES if self._on(icon)]

    @property
    def can_act(self):
        """Alive, unstunned, unwebbed: the game will take a command."""
        return not (self.dead or self.stunned or self.webbed)

    # -- body -------------------------------------------------------------

    @property
    def vitals(self):
        """{"health": 100, ...} for the vitals the game has shown."""
        return dict(getattr(self._state, "vitals", None) or {})

    @property
    def health(self):
        return self.vitals.get("health")

    @property
    def injuries(self):
        """{part: (kind, level)} from the injuries panel; {} when clean."""
        return dict(getattr(self._state, "injuries", None) or {})

    @property
    def left_hand(self):
        """The noun in the left hand, or None when empty."""
        held = getattr(self._state, "left_hand", None)
        return held.get("noun") if held else None

    @property
    def right_hand(self):
        held = getattr(self._state, "right_hand", None)
        return held.get("noun") if held else None

    @property
    def hands_empty(self):
        return self.left_hand is None and self.right_hand is None

    # -- place and time ---------------------------------------------------

    @property
    def room(self):
        """The room title as the game names it, or None."""
        return getattr(self._state, "room_title", None)

    @property
    def room_uid(self):
        return getattr(self._state, "room_uid", None)

    @property
    def hostiles(self):
        """{name: count} of the creatures the room shows."""
        return dict(getattr(self._state, "hostiles", None) or {})

    @property
    def roundtime(self):
        """Seconds of roundtime left, by the game's own clock (0 when
        none, or before the clock has been heard)."""
        return self._left(getattr(self._state, "roundtime", 0))

    @property
    def casttime(self):
        return self._left(getattr(self._state, "casttime", 0))

    def _left(self, until):
        now = getattr(self._state, "server_time", None)
        if not until or now is None:
            return 0
        return max(0, int(until) - int(now))

    @property
    def mindstates(self):
        """{skill: mindstate 0-34} for every skill the exp window shows."""
        experience = getattr(self._state, "experience", None) or {}
        return {
            skill: entry.get("mindstate")
            for skill, entry in experience.items()
            if isinstance(entry, dict)
        }

    def mindstate(self, skill):
        return self.mindstates.get(skill)

    # -- summary ------------------------------------------------------------

    def summary(self):
        """One line: room, posture and badges, vitals, hands, roundtime."""
        parts = []
        if self.room:
            parts.append(self.room)
        if self.dead:
            parts.append("DEAD")
        else:
            words = ([self.posture] if self.posture else []) + [
                badge for badge in self.badges if badge != "dead"
            ]
            if words:
                parts.append(" ".join(words))
        vitals = self.vitals
        shown = [f"{name[:2]} {vitals[name]}%" for name in VITALS if name in vitals]
        if shown:
            parts.append("  ".join(shown))
        hands = f"L {self.left_hand or '-'} R {self.right_hand or '-'}"
        parts.append(hands)
        if self.hostiles:
            parts.append("hostiles: " + ", ".join(sorted(self.hostiles)))
        if self.roundtime:
            parts.append(f"RT {self.roundtime}")
        if self.casttime:
            parts.append(f"CT {self.casttime}")
        return " | ".join(parts) if parts else "(no state yet)"


def status(state):
    """The readable view of a parser state (a script's s.state)."""
    return Status(state)
