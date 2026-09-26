"""A Barbarian's pieces of the hunt (#328): ANALYZE self-combos for
Expertise, the profile's abilities — berserks, forms, meditations — kept
up, and a roar at the prey for Debilitation. ;hunt calls it beside
client/game/buffs.py, which is a caster's PREPARE and CAST and none of
this (docs/barbarian.md).

ANALYZE <type> starts a self-combo: the game names the attacks to land
("... by landing a jab, a feint and a slice."), the next swings are
those attacks in turn instead of ATTACK, and the finished combo trains
Expertise — a miss moves it on too, and it carries over between kills
(Elanthipedia: Expertise, Barbarian new player guide). FLAME opens at 0
Expertise and gives a little Inner Fire back; ACCURACY wants 50,
DAMAGE 125. The answers are dr-scripts' combat-trainer.lic's
(perform_analyze?): the combo, "cannot repeat" (that combo's cooldown;
FLAME has none), "Analyze what?" and "What are you trying to attack?"
(nothing engaged), "You must be closer", "You fail to find any" (try
again), "You need to hold" (no weapon). combat-trainer never runs one
on a brawling turn — the attacks are weapon attacks — and neither does
this. None captured yet (2026-09-26).

An ability is its verb and name — BERSERK AVALANCHE, FORM BUFFALO,
MEDITATE TENACITY — and ABILITIES is dr-scripts' table of them
(data/base-spells.yaml `barb_abilities`: type, start command, the line
that says it took, the line that says it ended), the game's own
wordings. A running ability is one the Spells window lists (it does
once POWER meditation is known — the guide and lich's DRCA both say
so) or one started this run whose ended line has not come. The
answers are lich-5's DRCA.activate_barb_buff?'s: "You have not been
trained" (the ability is off for the run), "But you are already" (it
runs), "Your inner fire lacks" / "lacking the inner fire" (tried again
after IF_WAIT seconds), "You must be sitting" (a meditation: SIT, again,
STAND), "You must be unengaged" and "You should stand". Meditations go
out only outside the fight: they want the character seated and
unengaged.

A roar (ROAR <name> at <prey>) trains Debilitation — no other Barbarian
way does — and draws on the voice pool, not Inner Fire (Elanthipedia:
Roars). One goes out per ROAR_GAP seconds in the fight while
Debilitation sits below lock; "You have not been trained" turns it off.
No roar wording is captured or published beyond the pool's four
levels, so the first answer of a run is reported for the fixtures.
Qt-free, reloadable.
"""

import re
from time import monotonic

MIND_LOCK = 34
IF_WAIT = 60  # seconds before an ability refused for Inner Fire is tried again
ROAR_GAP = 60  # seconds between roars
COMBO_COOLDOWN = 60  # seconds before a combo on its cooldown is asked again
ANALYZE_MISSES = 3  # answers outside the table before ANALYZE is off for the run
clock = monotonic

# dr-scripts' data/base-spells.yaml, barb_abilities: name ->
# (type, start command, activated line, ended line), the game's wordings
# as regular expressions (dr-scripts matches them so); ended is None
# where the table has none.
# fmt: off
ABILITIES = {
    'Python': ('form', 'form python', 'imitating the cunning ways of the python', 'finish practicing the Form of the Python'),
    'Piranha': ('form', 'form piranha', 'rapid rhythm of the piranha', 'finish practicing the Form of the Piranha'),
    'Monkey': ('form', 'form monkey', 'you assume the movements of an agile monkey', 'finish practicing the Form of the Monkey'),
    'Bear': ('form', 'form bear', 'you assume the movements of a hungry bear', 'finish practicing the Form of the Bear'),
    'Turtle': ('form', 'form turtle', 'you prepare to deflect incoming magical attacks', 'finish practicing the Form of the Turtle'),
    'Badger': ('form', 'form badger', 'You lower your head slightly and snarl unconsciously as the fierce tenacity of the Badger', 'finish practicing the Form of the Badger'),
    'Swan': ('form', 'form swan', 'you maneuver against the very integrity of mana', 'finish practicing the Form of the Swan'),
    'Wolverine': ('form', 'form wolverine', 'power of the Wolverine swells inside you', 'finish practicing the Form of the Wolverine'),
    'Dragon': ('form', 'form dragon', 'the Form of the Dragon consumes you', 'finish practicing the Form of the Dragon'),
    'Eagle': ('form', 'form eagle', 'Scanning the distance', 'finish practicing the Form of the Eagle'),
    'Panther': ('form', 'form panther', 'you assume the movements of an alert Panther', 'finish practicing the Form of the Panther'),
    'Owl': ('form', 'form owl', 'transfix upon the surrounding shadows', 'finish practicing the Form of the Owl'),
    'Toad': ('form', 'form toad', 'your body slips into the resilient Form of the Toad', 'finish practicing the Form of the Toad'),
    'Buffalo': ('form', 'form buffalo', 'Lurching forward, you reposition your burden and mimic', 'finish practicing the Form of the Buffalo'),
    'Heitak': ('form', 'form heitak', 'Every fiber cries out to leap, to stomp!', 'finish practicing the Form of the Heitak'),
    'Drought': ('berserk', 'berserk drought', 'A supernatural strength and need', 'your foes inhabiting you wanes'),
    'Earthquake': ('berserk', 'berserk earthquake', 'You form the epicenter of a violent rage', 'before your fury crashes to a sudden halt'),
    'Tsunami': ('berserk', 'berserk tsunami', 'hands shake in anticipation of releasing the fury', 'The massive wall of rage within you crashes'),
    'Avalanche': ('berserk', 'berserk avalanche', 'rage of the avalanche replenishes your energy', 'avalanche of rage within you crashes'),
    'Wildfire': ('berserk', 'berserk wildfire', 'and explode in a wild rage of dangerous power', 'wild fire powering your limbs flickers'),
    'Landslide': ('berserk', 'berserk landslide', 'steadying your reaction against reflex based contests', 'your limbs suddenly feel strangely awkward'),
    'Flashflood': ('berserk', 'berserk flashflood', 'your body fills with a flood of resilient rage', 'fury recede as your rage crashes to a sudden halt'),
    'Famine': ('berserk', 'berserk famine', 'you feel yourself growing healthier', 'ravenous hunger of your rage has slaked its thirst'),
    'Volcano': ('berserk', 'berserk volcano', 'momentus eruption of the volcano hardens you against damage', 'undulating wellspring of rage within you crashes to a sudden halt'),
    'Tornado': ('berserk', 'berserk tornado', 'expanding your focus and steadying your shield arm', 'the furious maelstrom empowering your limbs dissipates'),
    'Cyclone': ('berserk', 'berserk cyclone', '^Fury storming forth', 'cyclone of fury drifts away'),
    'Blizzard': ('berserk', 'berserk blizzard', '^Unleashing a blizzard of hate', '^Your blizzard of hate melts away, leaving you deflated'),
    'Hurricane': ('berserk', 'berserk hurricane', '^Fury wells up from within and swirls into a raging hurricane', '^Your rage dissipates, pulling you away from your focused center of fury'),
    'Contemplation': ('meditation', 'meditate contemplation', '^You .* to meditate', 'contemplate enhanced defensive strategies drifts'),
    'Bastion': ('meditation', 'meditate bastion', '^You .* to meditate', 'bastion of strength slips from your mind'),
    'Tenacity': ('meditation', 'meditate tenacity', '^You .* to meditate', 'leaving you vulnerable to physical harm'),
    'Serenity': ('meditation', 'meditate serenity', '^You .* to meditate', 'leaving you vulnerable to magic'),
    'Focus': ('meditation', 'meditate focus', '^You .* to meditate', 'Focus meditation slips away from your mind'),
    'Staunch': ('meditation', 'meditate staunch', '^You .* to meditate', 'heart quickens and blood rushes back'),
    'Unyielding': ('meditation', 'meditate unyielding', '^You .* to meditate', None),
    'Seek': ('meditation', 'meditate seek', '^You .* to meditate', 'enhanced understanding of the natural world vanishes'),
    'Axis': ('meditation', 'meditate axis', '^You .* to meditate', 'The rhythm of the Axis in your core dissolves'),
}
# fmt: on

# The ANALYZE answers, first match wins (combat-trainer's patterns).
_COMBO = re.compile(r"by landing (?:an? )?(?P<list>.+?)\.?\s*$", re.MULTILINE)
ANALYZE_OUTCOMES = (
    ("cooldown", ("cannot repeat",)),
    ("no foe", ("analyze what", "what are you trying to attack")),
    ("closer", ("you must be closer",)),
    ("again", ("you fail to find any",)),
    ("no weapon", ("you need to hold",)),
)
ABILITY_OUTCOMES = (
    ("untrained", ("you have not been trained",)),
    ("running", ("but you are already",)),
    ("no fire", ("your inner fire lacks", "lacking the inner fire")),
    ("sit", ("you must be sitting",)),
    ("unengage", ("you must be unengaged",)),
    ("stand", ("you should stand",)),
)
ROAR_UNTRAINED = ("you have not been trained", "you don't know", "what roar")


class BarbState:
    """What the Barbarian pieces remember through one hunt."""

    def __init__(self):
        self.combo = []  # the attacks the running self-combo still wants
        self.combos = 0  # self-combos ANALYZE started
        self.analyze_misses = 0
        self.analyze_off = False
        self.analyze_cooldown_until = 0.0
        self.started = {}  # ability -> clock() it was started this run
        self.off = set()  # abilities the game says are not trained
        self.retry_at = {}  # ability -> clock() it may be tried again
        self.last_roar = None
        self.roar_off = False
        self.roars = 0
        self.roar_reported = False


def _classify(text, outcomes):
    lowered = (text or "").lower()
    for outcome, phrases in outcomes:
        if any(phrase in lowered for phrase in phrases):
            return outcome
    return None


def _took(pattern, answer):
    """True when the answer holds the ability's activated line — a
    regular expression in dr-scripts' table (the meditations' is
    "^You .* to meditate")."""
    return re.search(pattern, answer or "", re.IGNORECASE | re.MULTILINE) is not None


def combo_attacks(text):
    """The attacks an ANALYZE answer names, in order, as verbs: "... by
    landing a jab, a feint and a slice." -> ["jab", "feint", "slice"].
    [] when the answer names no combo."""
    match = _COMBO.search(text or "")
    if not match:
        return []
    items = re.split(r",\s*(?:and\s+)?|\s+and\s+", match.group("list"))
    verbs = []
    for item in items:
        words = re.findall(r"[a-z'\-]+", item.lower())
        words = [word for word in words if word not in ("a", "an", "the")]
        if words:
            verbs.append(words[-1])
    return verbs


def _mindstate(state, skill):
    for name, entry in (getattr(state, "experience", None) or {}).items():
        if str(name).lower() == skill.lower() and isinstance(entry, dict):
            return entry.get("mindstate")
    return None


def _locked(state, skill):
    value = _mindstate(state, skill)
    return value is not None and value >= MIND_LOCK


def analyze_type(profile):
    """The profile's self-combo ("flame"), lower-case; "" is off."""
    return str(profile.get("analyze") or "").strip().lower()


def next_combo_attack(s, profile, barb, ask, prefix, report):
    """The attack to swing instead of ATTACK, or None for a plain ATTACK.
    With the profile's `analyze` set, Expertise below lock and no combo
    running, ANALYZE <type> goes out first and its attacks queue up."""
    kind = analyze_type(profile)
    if not kind or barb.analyze_off:
        barb.combo = []
        return None
    if not barb.combo:
        if _locked(s.state, "Expertise") or clock() < barb.analyze_cooldown_until:
            return None
        answer = ask(s, f"analyze {kind}")
        s.waitrt()
        attacks = combo_attacks(answer)
        if attacks:
            barb.combo = attacks
            barb.combos += 1
            barb.analyze_misses = 0
        else:
            outcome = _classify(answer, ANALYZE_OUTCOMES)
            if outcome == "cooldown":
                barb.analyze_cooldown_until = clock() + COMBO_COOLDOWN
            elif outcome == "no weapon":
                barb.analyze_off = True
                s.echo(
                    f"{prefix}: ANALYZE {kind.upper()} wants a weapon in hand — off for this run"
                )
            elif outcome is None:
                barb.analyze_misses += 1
                report(f"analyze {kind}", answer)
                if barb.analyze_misses >= ANALYZE_MISSES:
                    barb.analyze_off = True
                    s.echo(
                        f"{prefix}: ANALYZE {kind.upper()} answered nothing known "
                        f"{ANALYZE_MISSES} times — off for this run"
                    )
            return None
    return barb.combo.pop(0)


def ability(name):
    """(name as the table spells it, its row) for a profile's ability
    name ("avalanche", "Berserk Avalanche"), or (name, None)."""
    words = str(name).strip().split()
    if words and words[0].lower() in ("berserk", "form", "meditate", "meditation"):
        words = words[1:]
    key = " ".join(words).title()
    return key, ABILITIES.get(key)


def running(s, barb, name):
    """True while the ability runs: the Spells window lists it, or it was
    started this run and its ended line has not come since."""
    for spell in getattr(s.state, "active_spells", None) or {}:
        if name.lower() in str(spell).lower():
            return True
    if name not in barb.started:
        return False
    flagged = getattr(s, "flagged", None)
    if callable(flagged) and flagged(f"barb-{name}"):
        del barb.started[name]
        return False
    return True


def keep_abilities(s, profile, barb, ask, prefix, report, fight=False):
    """Start each of the profile's `abilities` that is not running.
    Outside the fight every kind; in it berserks and forms only (a
    meditation wants a seated, unengaged Barbarian). Returns the names
    started."""
    started = []
    for wanted in profile.get("abilities") or []:
        name, row = ability(wanted)
        if row is None:
            if name not in barb.off:
                barb.off.add(name)
                s.echo(
                    f"{prefix}: no Barbarian ability {wanted!r} in the table — skipped"
                )
            continue
        kind, command, took, ended = row
        if name in barb.off or clock() < barb.retry_at.get(name, 0):
            continue
        if fight and kind == "meditation":
            continue
        if running(s, barb, name):
            continue
        answer = ask(s, command)
        outcome = None if _took(took, answer) else _classify(answer, ABILITY_OUTCOMES)
        if outcome == "sit":
            ask(s, "sit")
            answer = ask(s, command)
            ask(s, "stand")
            outcome = (
                None if _took(took, answer) else _classify(answer, ABILITY_OUTCOMES)
            )
        s.waitrt()
        if _took(took, answer) or outcome == "running":
            barb.started[name] = clock()
            flag = getattr(s, "flag", None)
            if callable(flag) and ended:
                flag(f"barb-{name}", ended)
            started.append(name)
        elif outcome == "untrained":
            barb.off.add(name)
            s.echo(f"{prefix}: {name} is not trained — off for this run (ABILITY LIST)")
        elif outcome == "no fire":
            barb.retry_at[name] = clock() + IF_WAIT
        elif outcome in ("unengage", "stand", "sit"):
            barb.retry_at[name] = clock() + IF_WAIT
        else:
            report(command, answer)
            barb.retry_at[name] = clock() + IF_WAIT
    return started


def roar_due(s, profile, barb):
    """True when the profile roars, Debilitation is below lock and
    ROAR_GAP seconds have passed since the last roar."""
    if not str(profile.get("roar") or "").strip() or barb.roar_off:
        return False
    if _locked(s.state, "Debilitation"):
        return False
    return barb.last_roar is None or clock() - barb.last_roar >= ROAR_GAP


def roar(s, profile, barb, ask, prefix, report, target=""):
    """ROAR <name> [at <target>] once, when due; True when one went out."""
    if not roar_due(s, profile, barb):
        return False
    name = str(profile["roar"]).strip().lower()
    command = f"roar {name}" + (f" at {target}" if target else "")
    answer = ask(s, command)
    s.waitrt()
    barb.last_roar = clock()
    if any(word in answer.lower() for word in ROAR_UNTRAINED):
        barb.roar_off = True
        s.echo(
            f"{prefix}: ROAR {name.upper()} is not trained — roaring off for this run"
        )
        return True
    barb.roars += 1
    if not barb.roar_reported:
        barb.roar_reported = True
        report(command, answer)  # uncaptured: the first answer, for the fixtures
    return True
