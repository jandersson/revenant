"""Playing an instrument — the model behind ;perform (#208).

Performance trains by playing: PLAY (song) {mood} ON {instrument}
starts a song that then runs on its own, and the best gain is a song
"played with only the slightest hint of difficulty" (Elanthipedia:
Performance skill, Play command). The Play command page gives the
song per rank band, SONGS below, and says off-key or halting moods
make any song easier, so the default is the band's song off-key.
Captured 2026-09-18 on a rank-2 Paladin with a pair of copper zills
worn, on the Faldesu ferry: `play scales off-key on my zills` — "You
fumble slightly as you begin an off-key ruff on your copper zills.";
then, unprompted, "You continue playing on your copper zills." and
"You continue to fumble through a few uncertain rhythms on your
copper zills, but it doesn't sound like what you intended." while
Performance rose 2 00% learning → thoughtful within a minute and
reached rank 3 on the second start; a second PLAY while playing:
"You're already playing a song!  You'll need to stop that one
first."; STOP PLAY: "You stop playing your song." A song survives
GO DOCK and a walk of a hundred rooms (it was still going after 95
seconds), but the walker's RETREAT burst ended it: "You stop your
performance." Whether a song ends on its own, and its wording, is
uncaptured (ENDED is a guess), as is a PLAY without the instrument.
An instrument gathers dirt as it plays and the game says so at PLAY;
CLEAN with a cloth takes it off (Elanthipedia: Clean command; the
wordings below, #233). Model: docs/training.md.
"""

# (first rank of the band, song) — Elanthipedia: Play command.
SONGS = (
    (0, "scales"),
    (40, "arpeggios"),
    (50, "ditty"),
    (59, "ballad"),
    (70, "waltz"),
    (80, "march"),
    (100, "lament"),
    (125, "hymn"),
    (180, "polka"),
    (220, "reel"),
    (250, "serenade"),
    (300, "psalm"),
    (350, "tango"),
    (450, "bolero"),
    (475, "nocturne"),
    (525, "requiem"),
    (550, "concerto"),
)
MOOD = "off-key"  # the easiest style, for the band's song at its floor
STARTED = ("as you begin", "you begin")
CONTINUES = ("you continue",)
ALREADY = ("already playing a song",)
STOPPED = ("you stop playing", "you stop your performance")
# Uncaptured: the wording of a song that ran out on its own.
ENDED = ("you finish", "finish playing", "finish your song", "song ends")
# Uncaptured: a PLAY with the instrument not on you.
NO_INSTRUMENT = ("what were you referring", "could not find", "don't have")
# Captured 2026-09-20 at the Provincial Bank's teller: a room where the
# game refuses a song — "You decide that now isn't the best time to be
# playing, and stop." The song is for another room, not another try.
NOT_HERE = ("isn't the best time to be playing",)

# Instrument care (#233; Elanthipedia: Clean command — "CLEAN
# (stringed/percussion instrument) WITH (cloth)"), captured 2026-09-20
# on the copper zills. The game says at PLAY when dirt weighs on the
# song: "Your zills's dirtiness may affect your performance." CLEAN
# wants the instrument in hand — "You must be holding the copper zills
# to clean them." (REMOVE: "You slide a pair of copper zills off your
# finger.") — and dry: "Your copper zills are so wet that they are
# still dripping!  Maybe you should dry them off before attempting to
# clean them.", which WIPE <instrument> WITH <cloth> answers, "Using
# your rag, you scrub at your copper zills in attempt to wipe the water
# from them.  Your rag soaks up the water easily, but remains noticably
# damp afterwards." (4 s). The clean itself: "With sure strokes that
# display your innate talent, you spend a few moments cleaning your
# copper zills.  You manage to clean a very large amount of dirt and
# grime from them." (5 s); WEAR puts it back, "You slide a pair of
# copper zills onto your finger." A GET of a cloth not on you is
# assumed to answer the usual "What were you referring to?".
DIRTY = ("dirtiness may affect",)
MUST_HOLD = ("must be holding",)
WET = ("still dripping",)
WIPED = ("wipe the water",)
CLEANED = ("moments cleaning", "dirt and grime")
NO_CLOTH = ("what were you referring", "could not find")


def song_for(rank):
    """The song of the rank's band: scales at 0-39, ..., a concerto from
    550; scales for an unknown rank."""
    song = SONGS[0][1]
    for floor, name in SONGS:
        if rank is not None and rank >= floor:
            song = name
    return song


def play_command(song, mood, instrument):
    """The PLAY line: `play scales off-key on my zills`; no mood gives
    the game's default style."""
    mood = f" {mood}" if mood else ""
    return f"play {song}{mood} on my {instrument}"


def parse_args(args):
    """{"instrument", "song", "mood", "until", "once"} from ;perform's
    arguments; "" for the instrument means the profile's, "" for the
    song means the rank's band."""
    options = {"instrument": "", "song": "", "mood": MOOD, "until": 34, "once": False}
    for arg in args:
        key, sep, value = str(arg).lower().partition("=")
        if sep and key in ("instrument", "song", "mood"):
            options[key] = value
        elif sep and key == "until" and value.isdigit():
            options["until"] = int(value)
        elif key == "once":
            options["once"] = True
    return options
