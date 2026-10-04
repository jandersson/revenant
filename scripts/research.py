"""Lock the magic skills by research — a caster's RESEARCH, a Barbarian's MEDITATE RESEARCH:  ;research

    ;research                   every project or skill in turn, the emptiest pool first, until all mind-lock
    ;research stream warding    a caster: those projects only (stream, augmentation, utility, warding, fundamental)
    ;research portion=120       a caster: seconds per RESEARCH portion (30-300, default 300)
    ;research augmentation      a Barbarian: that skill only (augmentation, warding, utility)
    ;research warding=buffalo   a Barbarian: research that ability for the skill
    ;research gap=90            a Barbarian: seconds from one research to the next (60)
    ;research until=30          stop at that mindstate instead of 34
    ;research once              exit when every skill is there instead of holding for the drain
    ;research return            (typed while it runs) end after the portion or research in hand

A caster (any guild but Barbarian, by the latest ;sheet or INFO):
- Casts Gauge Flow when it is down or under 20 minutes left, at one
  step under DISCERN's mana (more mana, a shorter project), a quarter
  less at a time while PREPARE warns of strain (the attunement is short).
- RESEARCH <project> in portions until the breakthrough locks its
  skill: STREAM Attunement, AUGMENTATION, UTILITY, WARDING their own,
  FUNDAMENTAL Arcana and the magic skill at 17/34.
- Finishes a project already in progress first; one at a time.
- A cast, PLAY, STUDY or fight loses a portion; a return typed with
  more than 90 s of it left ends at once, the portion running on.

A Barbarian: MEDITATE RESEARCH <ability> teaches that ability's skill,
about a minute apart (MONKEY Augmentation, TURTLE Warding, PREDICTION
Utility), held at mind-lock until a pool drains (client/game/trainer.py,
the loop every trainer runs).

What stops it: death, hostiles in the room, an answer the tables do
not know (echoed for a capture), Gauge Flow that will not cast.
Stop with:  ;stop research, or ;research return.
"""

from time import monotonic

from client.game import buffs, flight, guild, probe, trainer
from client.game.act import ask, said, unknown
from client.game.probe import classify as classify_answer
from client.game.loop import (
    danger,
    ensure_mindstate,
    exp_entry,
    mindstate,
    pause,
    read_exp,
    wants_stop,
)
from client.game.research import (
    GAUGE_FLOW,
    GAUGE_MINUTES,
    PORTION_SLACK,
    PROJECTS,
    classify,
    gauge_mana,
    next_skill,
    parse_args,
    parse_caster_args,
    portion_end,
    research_command,
    research_status,
    start_outcome,
    wants_caster,
)

_NOTES = """
The Barbarian's mode: MEDITATE RESEARCH <ability> teaches the skill
of that ability whether or not the Barbarian knows it, and Inner Fire
beside it, about a minute apart, with 6-10 s of roundtime and no
ability slot spent (Elanthipedia: Barbarian new player guide,
Meditations; client/game/research.py, docs/barbarian.md, #327). The
defaults are dr-scripts' combat-trainer.lic's. Debilitation cannot be
researched. A tie goes to the skill researched longest ago: at low
ranks a research's dabbling has drained before the next. A skill the
exp window does not move after its research is read with EXP <skill>
(the window pushes a line only when its text changes). A name the game
does not know drops that skill; a non-Barbarian's "trouble
concentrating" ends it.

The caster's mode (#385): Elanthipedia's Magical research and Gauge
Flow pages; the wordings are dr-scripts' researcher.lic and
crossing-training.lic's until the first live run captures them, so
every answer outside the tables is echoed. The portion runs in the
game, not the script: ;stop leaves it running, and only a cast, a
PREPARE, a PLAY, a STUDY, locksmithing or a fight loses it. The
portion wait therefore reads the typed return itself — wants_stop()
runs the interludes, and the almanac's STUDY would lose the portion.
"""

MAX_ROUNDS = 2000  # the fuse under the loop
RETURN_WAIT = 90  # a portion ending within this of a typed return is finished
GAUGE_UNSEEN_MINUTES = 10  # recast after this without a Spells window to read
FIT_TRIES = 4  # PREPAREs a quarter lower each while the attunement is short
clock = monotonic


def mindstates(s, skills):
    """{skill: mindstate or None} in the order given, from the exp window."""
    return {skill: mindstate(s, skill) for skill in skills}


def research(s, ability):
    """One MEDITATE RESEARCH, the roundtime waited out: (outcome, answer)."""
    answer = ask(s, research_command(ability))
    s.waitrt()
    return classify(answer), answer


def run(s, options):
    """The Barbarian's MEDITATE RESEARCH loop."""
    abilities = dict(options["abilities"])
    until = options["until"]
    for skill in abilities:
        if ensure_mindstate(s, skill, ask) is None:
            s.echo(f"research: EXP shows no {skill} yet — its pool counts as empty")
    s.echo(
        "research: "
        + ", ".join(f"{skill} by {ability}" for skill, ability in abilities.items())
        + f", {options['gap']} s apart, until {until}/34"
    )
    last = None
    rounds = 0  # the fuse: steps taken
    researched = {}  # skill: the round it was last researched in
    silent = set()  # skills the exp window did not move after a research

    def step(s):
        """One research round: the emptiest skill, the gap waited, its
        MEDITATE RESEARCH, the exp read. The skill set is the abilities
        still in play (trainer.train reads it afresh), so a dropped
        name leaves the lock gate; the window need not list a skill
        (ensure=False — the pre-loop above said which it lacks)."""
        nonlocal last, rounds
        if rounds >= MAX_ROUNDS:
            return f"{MAX_ROUNDS} rounds"
        rounds += 1
        skill = next_skill(mindstates(s, abilities), until, researched)
        if skill is None:
            return None  # every pool at the target: the loop's gate holds
        if last is not None:
            left = options["gap"] - (clock() - last)
            if left > 0 and not pause(s, left):
                return None  # the loop says why
        last = clock()
        researched[skill] = rounds
        ability = abilities[skill]
        before = exp_entry(s, skill)
        outcome, answer = research(s, ability)
        if outcome == "not a barbarian":
            return (
                f"the game answered {said(answer)!r} — only a Barbarian "
                "researches this way"
            )
        if outcome == "unknown":
            del abilities[skill]
            s.echo(
                f"research: the game knows no ability {ability!r} — {skill} is out of "
                f"the run ({skill.lower()}=<ability> names another)"
            )
            if not abilities:
                return "nothing left to research"
            return None
        if outcome is None:
            s.echo(f"research: {ability} answered {said(answer)!r}")
        if exp_entry(s, skill) == before:
            # The window said nothing of the skill: EXP says it (#327).
            read_exp(s, skill, ask)
            if skill not in silent:
                silent.add(skill)
                s.echo(
                    f"research: the exp window did not move {skill} after its "
                    f"research — reading EXP {skill.upper()} whenever it stays silent"
                )
        return None

    return trainer.train(
        s,
        "research",
        lambda: list(abilities),
        step,
        until=until,
        once=options["once"],
        again="researching again",
        ensure=False,
    )


# --- a caster's magical research (#385) ---


def gauge_minutes(s):
    """Gauge Flow's minutes left by the Spells window — None when it is
    not up, a large number for "Indefinite", and False for a parser
    without the window."""
    active = getattr(s.state, "active_spells", None)
    if not isinstance(active, dict):
        return False
    for name, minutes in active.items():
        if str(name).strip().lower() == GAUGE_FLOW.lower():
            return 9999 if minutes is None else minutes
    return None


def report(s):
    """The report buffs.cast_once makes of a cast or target answer nothing
    recognized: the common report-it echo, naming Gauge Flow."""

    def answered(what, answer):
        unknown(s, "research", f"Gauge Flow's {what}", answer)

    return answered


def fit_mana(s, mana):
    """The most mana up to `mana` the caster's attunement holds (#474):
    a PREPARE the game warns of strain at ("You feel intense strain ...",
    Elanthipedia's Prepare command: insufficient attunement) is released
    and tried a quarter lower. DISCERN's figure is the spell's range, not
    the pool: Riphik (Attunement 482) strained at 90 and 98, read "most of
    your current attunement" at 75, and the cast at 75 left 7% mana
    (2026-10-04). A release costs no mana."""
    for _ in range(FIT_TRIES):
        if mana <= 0:
            return 0
        answer = ask(s, f"prepare {GAUGE_FLOW} {mana}")
        ask(s, "release spell")
        if classify_answer(answer, buffs.PREPARE_OUTCOMES) != "strain":
            return mana
        lower = mana * 3 // 4
        s.echo(f"research: Gauge Flow at {mana} mana strains — trying {lower}")
        mana = lower
    return mana


def ensure_gauge(s, gauge):
    """Gauge Flow up for a portion: cast when the Spells window lacks it
    or shows under GAUGE_MINUTES left (without the window, once per
    GAUGE_UNSEEN_MINUTES). The mana is DISCERN's, asked once per run;
    a cast that fails there is tried at the minimum. False when the
    spell will not cast."""
    minutes = gauge_minutes(s)
    if minutes is False:
        cast_at = gauge.get("cast_at")
        if cast_at is not None and clock() - cast_at < GAUGE_UNSEEN_MINUTES * 60:
            return True
    elif minutes is not None and minutes >= GAUGE_MINUTES:
        return True
    if gauge.get("mana") is None:
        answer = ask(s, "discern gauge flow")
        s.waitrt()
        gauge["mana"] = fit_mana(
            s, gauge_mana(buffs.mana_limit(answer or ""), buffs.MANA_STEP)
        )
    why = "not up" if not minutes else f"{minutes} min left"
    for attempt in range(2):
        mana = gauge["mana"]
        outcome = buffs.cast_once(
            s, GAUGE_FLOW, mana, buffs.BuffState(), ask, report(s)
        )
        if outcome in ("ok", "strained"):
            gauge["cast_at"] = clock()
            s.echo(f"research: Gauge Flow cast at {mana or 'the minimum'} mana ({why})")
            return True
        if outcome == "collapsed" and mana and attempt == 0:
            s.echo(
                f"research: Gauge Flow failed at {mana} mana — the minimum from here"
            )
            gauge["mana"] = 0
            continue
        break
    s.echo(
        f"research: Gauge Flow did not cast ({outcome}) — research needs it; stopping"
    )
    return False


def await_portion(s, ends_at):
    """Wait for the portion due to end at `ends_at` (clock()): (end,
    line, returned). `end` is "breakthrough", "portion" or "lost"
    (research.portion_end) with its line; "danger"; "returned" for a
    return typed with more than RETURN_WAIT left, the portion running
    on in the game; None once PORTION_SLACK has passed the end with no
    end line. A return typed with less left is `returned` and the
    portion finished. The return is read here, not through
    wants_stop(): that runs the interludes, and a STUDY loses the
    portion."""
    partial, returned = "", False
    while clock() < ends_at + PORTION_SLACK:
        if danger(s):
            return "danger", "", returned
        while (typed := s.command(timeout=0)) is not None:
            if "return" in typed.lower():
                if ends_at - clock() > RETURN_WAIT:
                    return "returned", "", True
                returned = True
        piece = s.get(timeout=1, streams=probe.STORY_STREAMS)
        if piece is None:
            continue
        partial += piece
        if not partial.endswith("\n"):
            continue
        line, partial = partial.rstrip("\r\n"), ""
        end = portion_end(line)
        if end:
            return end, line, returned
    return None, "", returned


def pick_project(s, projects, until, researched):
    """The project whose skill has the emptiest pool below `until`."""
    skill = next_skill(
        mindstates(s, [PROJECTS[p] for p in projects]), until, researched
    )
    return next((p for p in projects if PROJECTS[p] == skill), None)


def run_caster(s, options):
    """The caster's magical research loop."""
    projects = list(options["projects"])
    until, portion = options["until"], options["portion"]
    for project in projects:
        skill = PROJECTS[project]
        if ensure_mindstate(s, skill, ask) is None:
            s.echo(f"research: EXP shows no {skill} yet — its pool counts as empty")
    status = ask(s, "research status")
    current, percent = research_status(status)
    if current == "other":
        s.echo(
            f"research: RESEARCH STATUS shows a project this script does not run "
            f"({said(status)!r}) — finish it or RESEARCH CANCEL it; stopping"
        )
        return
    s.echo(
        "research: "
        + ", ".join(f"{p.upper()} for {PROJECTS[p]}" for p in projects)
        + f", {portion} s portions, until {until}/34"
    )
    if current:
        s.echo(
            f"research: finishing the {current.upper()} project in progress"
            + (f" ({percent}%)" if percent is not None else "")
        )
    gauge = {}
    researched = {}  # skill: the round its project last had a portion
    returned = False  # typed during a portion that was then finished
    for round_number in range(MAX_ROUNDS):
        reason = danger(s)
        if reason:
            s.echo(f"research: {reason} — stopping")
            if "hostiles" in reason:
                flight.react(s, "research")
            return
        if returned or wants_stop(s):
            s.echo("research: stopping as asked")
            return
        if current is None:
            current = pick_project(s, projects, until, researched)
            if current is None:
                skills = [PROJECTS[p] for p in projects]
                if options["once"]:
                    s.echo(f"research: {', '.join(skills)} at {until}/34 — done")
                    return
                if not trainer.hold_at_lock(
                    s, "research", skills, until, again="researching again"
                ):
                    s.echo("research: stopping")
                    return
                continue
            skill = PROJECTS[current]
            s.echo(
                f"research: {current.upper()} for {skill} "
                f"({mindstate(s, skill) or 0}/34)"
            )
        skill = PROJECTS[current]
        if (mindstate(s, skill) or 0) >= until:
            # A project in progress whose skill is full: its breakthrough
            # would teach nothing now, so the pool drains first.
            if options["once"]:
                s.echo(f"research: {skill} at {until}/34 — done")
                return
            if not trainer.hold_at_lock(
                s, "research", [skill], until, again="researching again"
            ):
                s.echo("research: stopping")
                return
            continue
        if not ensure_gauge(s, gauge):
            return
        before = exp_entry(s, skill)
        answer = ask(s, f"research {current} {portion}")
        s.waitrt()
        outcome = start_outcome(answer)
        if outcome == "unknown":
            s.echo(
                f"research: RESEARCH {current.upper()} answered "
                f"{said(answer)!r} — out of the run"
            )
            if current in projects:
                projects.remove(current)
            current = None
            if not projects:
                s.echo("research: nothing left to research — stopping")
                return
            continue
        if outcome in ("blocked", None):
            s.echo(
                f"research: RESEARCH {current.upper()} answered "
                f"{said(answer)!r} — stopping"
            )
            return
        researched[skill] = round_number
        ends_at = clock() + portion
        end, line, returned = await_portion(s, ends_at)
        if end == "danger":
            continue  # the loop's top says why and gets away
        if end == "returned":
            s.echo(
                f"research: ending — the portion runs on in the game for about "
                f"{max(0, round(ends_at - clock()))} s more "
                f"(a cast, PLAY, STUDY or fight loses it)"
            )
            return
        if end == "breakthrough":
            if exp_entry(s, skill) == before:
                read_exp(s, skill, ask)
            s.echo(
                f"research: breakthrough — {current.upper()} done, "
                f"{skill} {mindstate(s, skill) or 0}/34"
            )
            current = None
        elif end == "portion":
            s.echo(f"research: {current.upper()} portion done — more to learn")
        elif end == "lost":
            s.echo(f"research: the portion was lost ({line!r}) — starting it again")
        else:
            # No end line the table knows: RESEARCH STATUS says where
            # the project stands, and the answer is kept for a capture.
            status = ask(s, "research status")
            current, _ = research_status(status)
            s.echo(
                f"research: no end line within {portion + PORTION_SLACK} s — "
                f"RESEARCH STATUS: {said(status)!r}"
            )
            if current == "other":
                s.echo("research: another project is in progress — stopping")
                return
    s.echo(f"research: {MAX_ROUNDS} rounds — stopping")


def main(s):
    args = list(s.args or [])
    if wants_caster(args) or guild.character_guild(s) not in (None, "Barbarian"):
        run_caster(s, parse_caster_args(args))
    else:
        run(s, parse_args(args))
