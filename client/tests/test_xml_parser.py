import pytest
from xml.etree.ElementTree import ParseError, XMLParser
from client.engine.xml_data import XMLData
import pathlib


@pytest.fixture
def xml_data():
    return XMLData()


@pytest.fixture
def login_strings():
    """About 5 minutes worth of strings in a list from first logging in to the game"""
    sample_file = pathlib.Path(__file__).parents[0] / "login-sample.log"
    with open(sample_file) as infile:
        raw_strings = infile.readlines()
    return raw_strings


def _feed(xml_data, login_strings):
    """Feed captured lines into a fresh XMLParser, matching core.py's
    root-wrapping so multiple top-level self-closing tags on one line
    (e.g. a burst of <indicator/>s) are all processed."""
    for string in login_strings:
        try:
            XMLParser(target=xml_data).feed(f"<r>{string}</r>")
        except ParseError:
            continue


def test_player_id(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.player_id == "440984"


def test_instance(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.game == "DR"


def test_name(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.name == "Lanival"


def test_server_time(xml_data, login_strings):
    _feed(xml_data, login_strings)
    # Last <prompt time=.../> in the captured session. Was 1626783177
    # before the root-wrap fix, because lines containing multiple prompts
    # silently dropped all but the first.
    assert xml_data.server_time == 1626783184


def test_compass_directions(xml_data):
    XMLParser(target=xml_data).feed(
        '<r><compass><dir value="n"/><dir value="sw"/><dir value="up"/></compass></r>'
    )
    assert xml_data.compass == ["n", "sw", "up"]


def test_compass_replaced_on_next_room(xml_data):
    XMLParser(target=xml_data).feed('<r><compass><dir value="n"/></compass></r>')
    XMLParser(target=xml_data).feed('<r><compass><dir value="e"/></compass></r>')
    assert xml_data.compass == ["e"]


def test_compass_inside_component_is_decoration(xml_data):
    # The room-exits component embeds an empty <compass> alongside the
    # real top-level one; it must neither clobber the exits nor raise
    # compass_updated (captured live 2026-08-13).
    XMLParser(target=xml_data).feed('<r><compass><dir value="n"/></compass></r>')
    xml_data.compass_updated = False
    XMLParser(target=xml_data).feed(
        "<r><component id='room exits'>Obvious paths: "
        "<d>southwest</d>.<compass></compass></component></r>"
    )
    assert xml_data.compass == ["n"]
    assert xml_data.compass_updated is False


# --- the exp window: how skill learning becomes state -------------------


def test_exp_component_parses_rank_percent_and_mindstate(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Athletics'>      Athletics:  346 13% "
        "deliberative</component></r>"
    )
    assert xml_data.experience["Athletics"] == {
        "rank": 346,
        "percent": 13,
        "mindstate": 11,  # deliberative is 11/34
        "rate": "deliberative",
    }
    assert xml_data.exp_updated


def test_exp_component_brief_mode_carries_the_mindstate_number(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Attunement'>Attunement:  520 42% [17/34]</component></r>"
    )
    assert xml_data.experience["Attunement"]["mindstate"] == 17
    assert xml_data.experience["Attunement"]["rate"] == "scrutinizing"


def test_empty_exp_component_clears_the_skill(xml_data):
    # Captured live: the game sends an empty component when a skill
    # leaves the learning queue.
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Shield Usage'>Shield Usage: 100 5% clear</component></r>"
    )
    XMLParser(target=xml_data).feed(
        "<r><component id='exp Shield Usage'></component></r>"
    )
    assert "Shield Usage" not in xml_data.experience


def test_exp_window_extras_are_not_skills(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><component id='exp tdp'>    TDPs:  721</component></r>"
    )
    assert xml_data.experience == {}


def test_nav_tag_carries_the_room_uid(xml_data):
    # Sent on every movement — the exact position fix for ;go2.
    XMLParser(target=xml_data).feed("<r>You stroll east.<nav rm='10081'/></r>")
    assert xml_data.room_uid == 10081


def test_room_title_from_stream_window(xml_data):
    XMLParser(target=xml_data).feed(
        "<r><streamWindow id='room' title='Room' "
        'subtitle=" - [The Crossing, Herald Street]"/></r>'
    )
    assert xml_data.room_title == "[The Crossing, Herald Street]"


def test_room_title_from_room_name_style(xml_data):
    XMLParser(target=xml_data).feed(
        '<r><style id="roomName"/>[Ilithi, Sana\'ati Dyaus] <style id=""/></r>'
    )
    assert xml_data.room_title == "[Ilithi, Sana'ati Dyaus]"


def test_roundtime_and_casttime(xml_data):
    XMLParser(target=xml_data).feed('<r><roundTime value="1723456789"/></r>')
    XMLParser(target=xml_data).feed('<r><castTime value="1723456792"/></r>')
    assert xml_data.roundtime == 1723456789
    assert xml_data.casttime == 1723456792


# Captured 2026-08-22: the game updates its minivitals dialog one bar
# at a time (skin + progressBar per change).
MINIVITALS_HEALTH = (
    "<dialogData id='minivitals'><skin id='healthSkin' name='healthBar'"
    " controls='health' left='0%' top='0%' width='25%' height='100%'/>"
    "<progressBar id='health' value='100' text='health 100%' left='0%'"
    " customText='t' top='0%' width='25%' height='100%'/></dialogData>"
)
MINIVITALS_CONCENTRATION = (
    "<dialogData id='minivitals'><progressBar id='concentration' value='98'"
    " text='concentration 98%' left='75%' customText='t' top='0%'"
    " width='25%' height='100%'/></dialogData>"
)
# The injuries dialog reuses progressBar with its own ids (captured).
INJURIES_BAR = (
    "<dialogData id='injuries'><skin id='healthSkin' name='healthBar2'"
    " controls='health2' align='n' top='160' width='140' left='0' height='15'/>"
    "<progressBar id='health2' value='55' text='HEALTH 55%' customText='t'"
    " align='n' top='160' width='140' left='0' height='15'/></dialogData>"
)


# Captured 2026-08-22 (#72): three cougars arrive — the room-objs
# enumeration, then a crtrStatus per creature, closed by a prompt.
CRTR_ARRIVE = (
    "<component id='room objs'>You also see <pushBold/>a cougar<popBold/>,"
    " a rise in the cliff, <pushBold/>a cougar<popBold/> and"
    " <pushBold/>a cougar<popBold/>.</component>"
    '<crtrStatus exist="78646435" hostile="1" disengaged="1"/>'
    '<crtrStatus exist="78646436" hostile="1" disengaged="1"/>'
    '<crtrStatus exist="78646437" hostile="1" disengaged="1"/>'
    '<prompt time="1787407791">&gt;</prompt>'
)
# ... and later one wanders off: the fresh enumeration replaces the set.
CRTR_FEWER = (
    "<component id='room objs'>You also see a rise in the cliff and"
    " <pushBold/>a cougar<popBold/>.</component>"
    '<crtrStatus exist="78646436" hostile="1" disengaged="1"/>'
    '<prompt time="1787407825">&gt;</prompt>'
)


def test_hostiles_track_the_rooms_creatures(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{CRTR_ARRIVE}</r>")
    assert xml_data.hostiles == {
        "78646435": False,  # disengaged='1': present, not yet engaged
        "78646436": False,
        "78646437": False,
    }
    XMLParser(target=xml_data).feed(f"<r>{CRTR_FEWER}</r>")
    assert xml_data.hostiles == {"78646436": False}


def test_hostiles_swap_only_at_the_closing_prompt(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{CRTR_ARRIVE}</r>")
    # A fresh enumeration without its prompt yet: readers still see
    # the previous complete set, never a half-built one.
    XMLParser(target=xml_data).feed(
        '<r><crtrStatus exist="78646436" hostile="1" disengaged="0"/></r>'
    )
    assert len(xml_data.hostiles) == 3
    XMLParser(target=xml_data).feed('<r><prompt time="1787407826">&gt;</prompt></r>')
    assert xml_data.hostiles == {"78646436": True}


# Captured 2026-08-22 (#85): the cave bear was announced exactly once;
# later room objs pulses carried NO crtrStatus tags behind them.
CRTR_BEAR = (
    "<component id='room objs'>You also see <pushBold/>a cave bear<popBold/>"
    " and a rusty ladder.</component>"
    '<crtrStatus exist="79912449" hostile="1" disengaged="1"/>'
    '<prompt time="1787426830">&gt;</prompt>'
)


def test_prose_only_room_objs_pulses_never_wipe_hostiles(xml_data):
    # The wipe that let ;athletics climb into an engaged cave bear
    # (#85): an empty room objs pulse, then a prose-only re-listing,
    # neither carrying crtrStatus — the bear must survive both.
    XMLParser(target=xml_data).feed(f"<r>{CRTR_BEAR}</r>")
    assert xml_data.hostiles == {"79912449": False}
    XMLParser(target=xml_data).feed(
        "<r><component id='room objs'></component>"
        '<prompt time="1787426835">&gt;</prompt></r>'
    )
    XMLParser(target=xml_data).feed(
        "<r><component id='room objs'>You also see <pushBold/>a cave bear"
        "<popBold/> and a rusty ladder.</component>"
        '<prompt time="1787426840">&gt;</prompt></r>'
    )
    assert xml_data.hostiles == {"79912449": False}


def test_a_harmless_reannouncement_drops_the_creature(xml_data):
    # A crtrStatus burst IS the enumeration: a creature re-announced
    # non-hostile (a kill) drops out at the swap.
    XMLParser(target=xml_data).feed(f"<r>{CRTR_BEAR}</r>")
    XMLParser(target=xml_data).feed(
        '<r><crtrStatus exist="79912449" hostile="0" disengaged="1"/>'
        '<prompt time="1787426900">&gt;</prompt></r>'
    )
    assert xml_data.hostiles == {}


def test_non_hostile_creatures_never_count(xml_data):
    XMLParser(target=xml_data).feed(
        '<r><crtrStatus exist="78245133" hostile="0" disengaged="1"/>'
        '<prompt time="1787407585">&gt;</prompt></r>'
    )
    assert xml_data.hostiles == {}


def test_a_room_change_clears_hostiles(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{CRTR_ARRIVE}</r>")
    XMLParser(target=xml_data).feed("<r><nav rm='414008'/></r>")
    assert xml_data.hostiles == {}


def test_minivitals_bars_accumulate_into_vitals(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{MINIVITALS_HEALTH}</r>")
    assert xml_data.vitals == {"health": 100}
    assert xml_data.vitals_updated
    XMLParser(target=xml_data).feed(f"<r>{MINIVITALS_CONCENTRATION}</r>")
    assert xml_data.vitals == {"health": 100, "concentration": 98}


def test_injuries_progress_bars_never_pollute_vitals(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{INJURIES_BAR}</r>")
    assert xml_data.vitals == {}
    assert not xml_data.vitals_updated


def test_route_plain_text_goes_to_main(xml_data):
    assert xml_data.route("You see a stunted forest troll.") == [
        ("", "You see a stunted forest troll.", "")
    ]


def test_route_single_line_stream(xml_data):
    line = '<pushStream id="thoughts"/>You sense: hello there<popStream/>'
    assert xml_data.route(line) == [("thoughts", "You sense: hello there", "")]


def test_route_mixed_line_splits_streams(xml_data):
    line = (
        'Before.<pushStream id="logons"/> * Bob joined the realms. <popStream/>After.'
    )
    assert xml_data.route(line) == [
        ("", "Before.", ""),
        ("logons", " * Bob joined the realms. ", ""),
        ("", "After.", ""),
    ]


def test_route_buffers_multiline_stream(xml_data):
    assert (
        xml_data.route('<pushStream id="percWindow"/>Clear Vision  (29 roisaen)') == []
    )
    assert xml_data.route("<popStream/>") == [
        ("percWindow", "Clear Vision  (29 roisaen)", "")
    ]


def test_route_discards_duplicate_streams(xml_data):
    line = '<pushStream id="talk"/>You say, "hi"<popStream/>'
    assert xml_data.route(line) == []


def test_route_unescapes_entities(xml_data):
    line = "A troll&apos;s club whooshes."
    assert xml_data.route(line) == [("", "A troll's club whooshes.", "")]


# --- styling: how the game's markers become styled segments -------------


def test_bold_text_is_a_styled_run_within_the_line(xml_data):
    line = "You gesture. <pushBold/>A troll's club<popBold/> whooshes."
    assert xml_data.route(line) == [
        ("", "You gesture. ", ""),
        ("", "A troll's club", "bold"),
        ("", " whooshes.", ""),
    ]


def test_speech_preset_styles_the_say_prefix(xml_data):
    # Captured live: the game wraps only "You say" in the speech preset.
    line = "<preset id='speech'>You say</preset>, \"Hello world.\""
    assert xml_data.route(line) == [
        ("", "You say", "speech"),
        ("", ', "Hello world."', ""),
    ]


def test_room_name_style_spans_until_reset(xml_data):
    assert xml_data.route('<style id="roomName" />[Northwall Trail, Grassland]') == [
        ("", "[Northwall Trail, Grassland]", "roomName")
    ]
    # The empty style id on the next line closes the span.
    assert xml_data.route('<style id=""/>Obvious paths: east.') == [
        ("", "Obvious paths: east.", "")
    ]


def test_bold_persists_across_lines_until_popped(xml_data):
    assert xml_data.route("<pushBold/>*** IMPORTANT ***") == [
        ("", "*** IMPORTANT ***", "bold")
    ]
    assert xml_data.route("still shouting") == [("", "still shouting", "bold")]
    assert xml_data.route("<popBold/>calm again") == [("", "calm again", "")]


def test_clear_stream_is_a_control_segment(xml_data):
    # The spell-list pulse: wipe the window, then the fresh list arrives.
    assert xml_data.route('<clearStream id="percWindow"/>') == [
        ("percWindow", "", "clear")
    ]


def test_indicator(xml_data, login_strings):
    _feed(xml_data, login_strings)
    # IconPOISONED / IconDISEASED are not present in login-sample.log, so
    # they are not asserted here (the original test expected them, which
    # is why it was marked skip).
    assert xml_data.indicator["IconSTANDING"] == "y"
    assert xml_data.indicator["IconPRONE"] == "n"
    assert xml_data.indicator["IconKNEELING"] == "n"
    assert xml_data.indicator["IconSITTING"] == "n"
    assert xml_data.indicator["IconSTUNNED"] == "n"
    assert xml_data.indicator["IconHIDDEN"] == "n"
    assert xml_data.indicator["IconINVISIBLE"] == "n"
    assert xml_data.indicator["IconDEAD"] == "n"
    assert xml_data.indicator["IconWEBBED"] == "n"
    assert xml_data.indicator["IconJOINED"] == "n"
    assert xml_data.indicator["IconBLEEDING"] == "n"


def test_idle_warning_gets_the_alert_style():
    # Captured 2026-08-20 (issue #42): the idle check arrives with no
    # markup at all between two prompts; official frontends supply the
    # emphasis, so the parser stamps our own "alert" style on it.
    xml_data = XMLData()
    assert xml_data.route("YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.") == [
        ("", "YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.", "alert")
    ]
    # Ordinary unstyled text stays plain.
    assert xml_data.route("You feel fully rested.") == [
        ("", "You feel fully rested.", "")
    ]


def test_command_links_get_link_styles():
    xml_data = XMLData()
    segments = xml_data.route("Obvious paths: <d>north</d>, <d>east</d>.")
    assert segments == [
        ("", "Obvious paths: ", ""),
        ("", "north", "link:north"),
        ("", ", ", ""),
        ("", "east", "link:east"),
        ("", ".", ""),
    ]


def test_command_links_prefer_the_cmd_attribute():
    xml_data = XMLData()
    segments = xml_data.route("You see <d cmd='go wooden gate'>a gate</d> here.")
    assert ("", "a gate", "link:go wooden gate") in segments


def test_the_bell_around_the_idle_warning_is_stripped_and_sounded():
    # Captured 2026-09-04 (#131): the warning arrives wrapped in BEL
    # (0x07) at each end — the official frontend's cue to beep. A font
    # has no glyph for it, so the boxes must never reach a widget; the
    # bell itself becomes a synthetic segment the GUI sounds.
    xml_data = XMLData()
    line = "\x07YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.\x07"
    assert xml_data.route(line) == [
        ("bell", "", ""),
        ("", "YOU HAVE BEEN IDLE TOO LONG. PLEASE RESPOND.", "alert"),
    ]


def test_other_control_characters_are_stripped_without_a_bell():
    xml_data = XMLData()
    assert xml_data.route("You feel\x08 fully rested.") == [
        ("", "You feel fully rested.", "")
    ]
    assert xml_data.route("<pushBold/>Whee\x1b!<popBold/>") == [("", "Whee!", "bold")]


def test_a_line_without_a_bell_emits_no_bell_segment():
    xml_data = XMLData()
    assert all(stream != "bell" for stream, _, _ in xml_data.route("Quiet."))


# Captured 2026-09-05 (#149): the kill. The corpse's tag keeps
# hostile="1" and adds dead="1"; ;hunt counted it as an opponent and
# swung at it five times ("The ship's rat is already quite dead.").
CRTR_DEAD = (
    "<component id='room objs'>You also see <pushBold/>a ship's rat<popBold/>"
    " which appears dead.</component>"
    '<crtrStatus exist="15816359" hostile="1" disengaged="1" dead="1" sleeping="1"/>'
    '<prompt time="1788578245">&gt;</prompt>'
)


def test_a_dead_creature_is_no_hostile(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{CRTR_ARRIVE}</r>")
    XMLParser(target=xml_data).feed(f"<r>{CRTR_DEAD}</r>")
    assert xml_data.hostiles == {}


# -- hands: <left> and <right>, one tag per hand as it changes ---------------


def _feed_one(xml_data, line):
    XMLParser(target=xml_data).feed(f"<r>{line}</r>")


def test_hands_from_the_login_pair(xml_data):
    # Captured 2026-09-11: the pair the game sends at login, a handaxe
    # in the left hand and a piece of armor carried in the right.
    _feed_one(
        xml_data,
        '<left exist="45793296" noun="handaxe">oak-hafted handaxe</left>'
        '<right exist="45793297" noun="vambraces">plate vambraces</right>',
    )
    assert xml_data.left_hand == {
        "noun": "handaxe",
        "exist": "45793296",
        "name": "oak-hafted handaxe",
    }
    assert xml_data.right_hand == {
        "noun": "vambraces",
        "exist": "45793297",
        "name": "plate vambraces",
    }
    assert xml_data.hands_updated


def test_a_hand_empties_on_its_own_tag(xml_data):
    # The tags come one at a time as each hand changes (the stow that
    # emptied the left hand, captured 2026-09-11); the other hand keeps
    # its state. "Empty" is the game's word for nothing held.
    _feed_one(
        xml_data,
        '<left exist="45793296" noun="handaxe">oak-hafted handaxe</left>'
        '<right exist="45793297" noun="vambraces">plate vambraces</right>',
    )
    xml_data.hands_updated = False
    _feed_one(xml_data, "<left>Empty</left>")
    assert xml_data.left_hand is None
    assert xml_data.right_hand["noun"] == "vambraces"
    assert xml_data.hands_updated
    xml_data.hands_updated = False
    _feed_one(xml_data, "<left>Empty</left>")  # no change: no update flag
    assert not xml_data.hands_updated


def test_hands_start_empty_in_the_login_sample(xml_data, login_strings):
    _feed(xml_data, login_strings)
    assert xml_data.left_hand is None and xml_data.right_hand is None


def test_hand_tags_never_reach_the_story(xml_data):
    # route() strips the element; the text is state, not a story line.
    segments = xml_data.route(
        '<left exist="1" noun="handaxe">oak-hafted handaxe</left><right>Empty</right>'
    )
    assert "handaxe" not in "".join(text for _, text, _ in segments)


# -- the injuries panel: one <image> per body part -----------------------


WOUNDED_PANEL = (
    '<dialogData id="injuries"><image id="head" name="Injury1" height="0" width="0"/>'
    '<image id="neck" name="Injury1" height="0" width="0"/>'
    '<image id="rightArm" name="Injury1" height="0" width="0"/>'
    '<image id="rightHand" name="rightHand" height="0" width="0"/>'
    '<image id="chest" name="Injury1" height="0" width="0"/>'
    '<image id="nsys" name="nsys" height="0" width="0"/></dialogData>'
)
CLEAN_PANEL = (
    '<dialogData id="injuries"><image id="head" name="head" height="0" width="0"/>'
    '<image id="neck" name="neck" height="0" width="0"/>'
    '<image id="rightArm" name="rightArm" height="0" width="0"/>'
    '<image id="chest" name="chest" height="0" width="0"/></dialogData>'
)


def test_the_injuries_panel_names_the_hurt_parts(xml_data):
    # Captured 2026-09-11 after the felled-tree falls: name == part id
    # is clean, Injury<N> is a fresh wound.
    _feed_one(xml_data, WOUNDED_PANEL)
    assert xml_data.injuries == {
        "head": ("wound", 1),
        "neck": ("wound", 1),
        "rightArm": ("wound", 1),
        "chest": ("wound", 1),
    }
    assert xml_data.injuries_updated


def test_a_clean_panel_clears_the_parts_it_lists(xml_data):
    _feed_one(xml_data, WOUNDED_PANEL)
    xml_data.injuries_updated = False
    _feed_one(xml_data, CLEAN_PANEL)  # the Empath's touch, same pulse
    assert xml_data.injuries == {}
    assert xml_data.injuries_updated
    xml_data.injuries_updated = False
    _feed_one(xml_data, CLEAN_PANEL)
    assert not xml_data.injuries_updated  # no change, no flag


def test_scars_and_levels_follow_the_pattern(xml_data):
    _feed_one(
        xml_data,
        '<dialogData id="injuries"><image id="back" name="Scar2" height="0" width="0"/>'
        '<image id="leftLeg" name="Injury3" height="0" width="0"/></dialogData>',
    )
    assert xml_data.injuries == {"back": ("scar", 2), "leftLeg": ("wound", 3)}


def test_the_panels_skins_and_bar_do_not_become_parts(xml_data):
    _feed_one(
        xml_data,
        '<dialogData id="injuries"><skin id="injuredSkin" name="InjuriesPanel"/>'
        '<skin id="healthSkin" name="healthBar2" controls="health2"/>'
        '<progressBar id="health2" value="100" text="HEALTH 100%"/></dialogData>',
    )
    assert xml_data.injuries == {}
    assert xml_data.vitals == {}  # health2 stays out of the vitals too


# -- spells: the prepared one and the Spells window's timers ----------------
# Captured 2026-09-12: Heroic Strength prepared and cast by a circle-1
# Paladin; the window is wiped and rewritten on every pulse, and a
# roisan is a real minute (client/game/eltime.py).


def test_the_prepared_spell_comes_from_the_spell_tag(xml_data):
    _feed_one(xml_data, "<spell>Heroic Strength</spell>")
    assert xml_data.prepared_spell == "Heroic Strength"
    _feed_one(xml_data, "<spell>None</spell>You gesture.")
    assert xml_data.prepared_spell is None


def test_active_spells_come_from_the_spells_window(xml_data):
    _feed_one(xml_data, '<clearStream id="percWindow"/>')
    _feed_one(xml_data, '<pushStream id="percWindow"/>Heroic Strength  (10 roisaen)\n')
    _feed_one(xml_data, "<popStream/><castTime value='1789234651'/>")
    assert xml_data.active_spells == {"Heroic Strength": 10}
    _feed_one(xml_data, '<clearStream id="percWindow"/>')
    _feed_one(
        xml_data,
        '<pushStream id="percWindow"/>Heroic Strength  (9 roisaen)\n'
        "Manifest Force  (Indefinite)\n",
    )
    _feed_one(xml_data, "<popStream/>")
    assert xml_data.active_spells == {"Heroic Strength": 9, "Manifest Force": None}


def test_the_windows_lines_arrive_one_per_feed_and_stay_apart(xml_data):
    # The engine splits the chunk on newlines and feeds each line on
    # its own, newline gone: two spells once glued into one (#175).
    _feed_one(xml_data, '<pushStream id="percWindow"/>Heroic Strength  (9 roisaen)')
    _feed_one(xml_data, "Manifest Force  (Indefinite)")
    _feed_one(xml_data, "<popStream/>")
    assert xml_data.active_spells == {"Heroic Strength": 9, "Manifest Force": None}
    assert xml_data.spells_updated


def test_a_wipe_alone_means_no_spell_is_running(xml_data):
    _feed_one(xml_data, '<pushStream id="percWindow"/>Heroic Strength  (1 roisan)\n')
    _feed_one(xml_data, "<popStream/>")
    assert xml_data.active_spells == {"Heroic Strength": 1}
    _feed_one(xml_data, '<clearStream id="percWindow"/>')
    assert xml_data.active_spells == {}


def test_prompts_are_counted(xml_data):
    # Handle.waitrt waits for the count to move past the one seen at a
    # send before trusting the roundtime (2026-09-12).
    assert xml_data.prompt_count == 0
    _feed_one(xml_data, '<prompt time="1789239200">&gt;</prompt>')
    _feed_one(
        xml_data,
        '<roundTime value="1789239202"/><prompt time="1789239200">&gt;</prompt>',
    )
    assert xml_data.prompt_count == 2
    assert xml_data.roundtime == 1789239202


# -- the room's players: <component id='room players'> (#178) ------------------


def test_room_players_are_read_from_also_here(xml_data):
    # Captured 2026-09-12: titles before the name, " who is ..." after.
    _feed_one(
        xml_data,
        "<component id='room players'>Also here: Sky Knight Kaldean who is "
        "darkened by an unnatural shadow, Sand Flower Cyranth, Cecil and "
        "Penello.</component>",
    )
    assert xml_data.room_players == ["Kaldean", "Cyranth", "Cecil", "Penello"]
    assert xml_data.players_updated
    xml_data.players_updated = False
    _feed_one(xml_data, "<component id='room players'>Also here: Rhatler.</component>")
    assert xml_data.room_players == ["Rhatler"]
    _feed_one(
        xml_data,
        "<component id='room players'>Also here: Ghost Hunter Tedriel who is "
        "emanating a bright holy aura.</component>",
    )
    assert xml_data.room_players == ["Tedriel"]
    _feed_one(xml_data, "<component id='room players'></component>")
    assert xml_data.room_players == []


# -- possessions: INV LIST's links carry the exist ids (#184) ------------------

INV_LIST_LINES = (
    "You have:",
    "  <d cmd='remove #53174575'>a lumpy bundle</d>",
    "     -<d cmd='get #50886622 in #53174575'>a rat tail</d>",
    "     -<d cmd='get #50886623 in #53174575'>a rat tail</d>",
    "  <d cmd='remove #50886620'>a large canvas sack</d>",
    "     -<d cmd='get #50886688 in #50886620'>an oak-hafted handaxe</d>",
    "[Use <d cmd='inventory help'>INVENTORY HELP</d> for more options.]",
)


def test_inv_lists_links_become_possessions_at_the_footer(xml_data):
    # Captured 2026-09-13: worn items are "remove #id" links, contents
    # "get #id in #container"; the engine feeds one line per root.
    for line in INV_LIST_LINES[:-1]:
        _feed_one(xml_data, line)
        assert xml_data.possessions == [] and not xml_data.possessions_updated
    _feed_one(xml_data, INV_LIST_LINES[-1])
    assert xml_data.possessions_updated
    assert [
        (item["exist"], item["name"], item["container_exist"], item["depth"])
        for item in xml_data.possessions
    ] == [
        ("53174575", "a lumpy bundle", None, 0),
        ("50886622", "a rat tail", "53174575", 1),
        ("50886623", "a rat tail", "53174575", 1),
        ("50886620", "a large canvas sack", None, 0),
        ("50886688", "an oak-hafted handaxe", "50886620", 1),
    ]
    assert xml_data.possessions[0]["worn"] and not xml_data.possessions[1]["worn"]
    # An ordinary line with a link outside a listing is not an item.
    xml_data.possessions_updated = False
    _feed_one(xml_data, "Obvious paths: <d>north</d>.")
    assert not xml_data.possessions_updated


def test_a_listing_without_its_footer_closes_at_the_prompt(xml_data):
    for line in INV_LIST_LINES[:3]:
        _feed_one(xml_data, line)
    _feed_one(xml_data, '<prompt time="1789234651">&gt;</prompt>')
    assert [item["exist"] for item in xml_data.possessions] == ["53174575", "50886622"]
    assert xml_data.possessions_updated


# -- rested experience: the exp window's footer (#176) ------------------------


def test_the_rested_footer_is_kept_from_the_exp_window(xml_data):
    # Captured 2026-09-12: the footer comes as its own exp component on
    # every pulse, and the parser dropped it until #176.
    assert xml_data.rested is None
    _feed_one(
        xml_data,
        "<component id='exp rexp'>Rested EXP Stored: 5:44 hours  Usable This "
        "Cycle: 5:30 hours  Cycle Refreshes: 1:17 hour</component>",
    )
    assert xml_data.rested == {"stored": 344, "usable": 330, "refresh": 77}
    assert xml_data.rested_updated
    xml_data.rested_updated = False
    _feed_one(
        xml_data,
        "<component id='exp rexp'>Rested EXP Stored: 5:44 hours  Usable This "
        "Cycle: 5:30 hours  Cycle Refreshes: 1:17 hour</component>",
    )
    assert not xml_data.rested_updated  # the same footer again is no change
    _feed_one(
        xml_data,
        "<component id='exp rexp'>Rested EXP Stored: 5:02 hours  Usable This "
        "Cycle: 5:58 hours  Cycle Refreshes: 23:27 hours</component>",
    )
    assert xml_data.rested == {"stored": 302, "usable": 358, "refresh": 1407}
    assert xml_data.rested_updated
    # The footer is not a skill: the exp window keeps only skills.
    assert "rexp" not in xml_data.experience


# -- the room's creatures: the bolded names of <component id='room objs'> (#178)


def test_room_creatures_are_the_bolded_names_of_the_room_listing(xml_data):
    # Captured 2026-09-12: NPCs and creatures are bolded, scenery is not;
    # a repeated creature is listed once per head.
    _feed_one(
        xml_data,
        "<component id='room objs'>You also see <pushBold/>a town guard<popBold/>, "
        "<pushBold/>Forest Warden Hengwild<popBold/>, a large parchment and a big "
        "orange sign with a picture of a smiling Dwarf.</component>",
    )
    assert xml_data.room_creatures == ["a town guard", "Forest Warden Hengwild"]
    assert xml_data.creatures_updated
    xml_data.creatures_updated = False
    _feed_one(
        xml_data,
        "<component id='room objs'>You also see <pushBold/>a musk hog<popBold/> and "
        "<pushBold/>a musk hog<popBold/>.</component>",
    )
    assert xml_data.room_creatures == ["a musk hog", "a musk hog"]
    assert xml_data.creatures_updated
    xml_data.creatures_updated = False
    _feed_one(
        xml_data,
        "<component id='room objs'>You also see a rusty ladder.</component>",
    )
    assert xml_data.room_creatures == []
    assert xml_data.creatures_updated


def test_a_room_change_clears_the_creatures_until_the_new_listing(xml_data):
    XMLParser(target=xml_data).feed(f"<r>{CRTR_ARRIVE}</r>")
    assert xml_data.room_creatures == ["a cougar", "a cougar", "a cougar"]
    _feed_one(xml_data, "<nav rm='1234'/>")
    assert xml_data.room_creatures == []
    XMLParser(target=xml_data).feed(f"<r>{CRTR_FEWER}</r>")
    assert xml_data.room_creatures == ["a cougar"]
