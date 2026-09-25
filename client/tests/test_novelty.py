"""The novelty model ;sentinel reads — these tests are the manual. A
bare-named someone addressing you is an address, an NPC with an
article or one of your own characters is not; a word spelled to slip
past a script is a hidden command; a staff notice for this instance is
a broadcast; and the store flags a line once, then the two spam shapes
(#276, after dr-scripts' status-monitor.lic). The cast is synthetic."""

import json

from client.game import novelty
from client.game.novelty import (
    FREQUENCY,
    UNIQUE,
    Novelty,
    address,
    boilerplate,
    broadcast,
    distance,
    hidden_command,
    near,
    newcomers,
    own_names,
    scrub,
    speaker,
)

# Captured shapes, the names replaced by the synthetic cast.
PLAYER_WHISPER = 'Sable whispers to you, "are you there?"'
PLAYER_SAYS = 'Sable says to you, "Hello?"'
PLAYER_THINKS = 'Sable thinks to you, "wake up"'
PLAYER_WAVES = "Sable waves to you."
PLAYER_NODS_AT = "Sable nods with approval at you."
NPC_SAYS = (
    'A fair-skinned priestess says to you, "Are you lost?  Just NOD at me if so."'
)
NPC_WHISPER = '"Remember," he whispers to you, "Knock instead if you\'re looking to go in the VIP room."'
TRAINER = (
    'Uthmor nods with approval, "Your Light shines from within you, Lanival.  '
    'You have earned your next rank!"'
)
TWEET_EVENT = (
    "TWEET:  The war drums are sounding.  Those pesky puppets must be on the "
    "loose in the Memory Garden! #drprime #drplat"
)
TWEET_CALENDAR = (
    "TWEET:  It's Tuesday again, which means Tuesday Tidings are here!  This "
    "week is a berry patch on the new garden in Therenborough!  Check Discord "
    "announcements for more details. #drplat #drfal"
)


def test_a_bare_named_speaker_addressing_you_is_an_address_by_kind():
    assert address(PLAYER_WHISPER, "whispers") == "whisper"
    assert address(PLAYER_WHISPER) == "whisper"
    assert address(PLAYER_SAYS) == "speech"
    assert address(PLAYER_THINKS, "thoughts") == "thought"
    assert address(PLAYER_WAVES) == "gesture"
    assert address(PLAYER_NODS_AT) == "gesture"
    assert speaker(PLAYER_WHISPER) == "Sable"


def test_an_npc_with_an_article_or_a_quoted_whisper_is_no_address():
    assert address(NPC_SAYS) is None
    assert address(NPC_WHISPER) is None
    # A gesture without "to you" / "at you" is the room's business.
    assert address("Sable smiles broadly as he grasps your lesson.") is None


def test_a_shopkeeper_the_room_names_is_no_address():
    # Captured 2026-09-25 after a REFUSE at Mauriga's Botanicals (#310):
    # a bare-named NPC, named by the room's title or its listing.
    nod = (
        'Mauriga nods to you.  "Perhaps another day.  In the meantime, make '
        'sure that you eat a sicle fruit a day!"'
    )
    assert address(nod) == "gesture"  # no room given: read as a player
    assert address(nod, room="[Mauriga's Botanicals, Salesroom]") is None
    listing = "You also see Repairman Catrox, a large sign and a sooty swinging door."
    assert (
        address('Catrox says to you, "Did you want something?"', room=listing) is None
    )
    # A player is listed apart, never in the room's own text.
    assert address(PLAYER_WAVES, room="[Mauriga's Botanicals, Salesroom]") == "gesture"


def test_your_own_characters_and_noise_streams_are_ignored():
    assert address(PLAYER_SAYS, ignore=["sable"]) is None
    assert address(TRAINER, ignore=["Uthmor"]) is None
    assert address(PLAYER_SAYS, stream="combat") is None
    assert address(PLAYER_SAYS, stream="logons") is None


def test_a_word_spelled_to_slip_past_a_script_is_a_hidden_command():
    assert hidden_command('Sable says, "J_u_M_p"') == "J_u_M_p"
    assert hidden_command("please n-o-d now") == "n-o-d"
    assert hidden_command('Sable says, "jUmP"') == "jUmP"
    assert hidden_command("Just NOD at me if so.") is None  # plain caps
    assert hidden_command("Sable says hello to McDonald.") is None  # a name
    assert hidden_command("the x-y-z axis") is None  # separated, no verb
    assert hidden_command("A striped badger arrives.") is None


def test_a_staff_notice_for_this_instance_is_a_broadcast_the_calendar_is_not():
    assert broadcast(TWEET_EVENT, "ooc")
    assert not broadcast(TWEET_CALENDAR, "ooc")
    assert not broadcast(TWEET_EVENT, "")
    assert not broadcast("TWEET:  Something on the other side. #drplat", "ooc")


def test_the_scrub_makes_a_priced_line_one_line():
    assert scrub("A rat is worth 193 Kronars.") == scrub("A rat is worth 7 kronars.")
    assert scrub("  Two   words ") == "two words"
    assert scrub("42") == ""


def test_boilerplate_is_never_news():
    for line in (
        "Obvious paths: north, south.",
        "Also here: Sable.",
        "You also see a rat.",
        "Roundtime: 3 sec.",
        "...wait 2 seconds.",
        "[hunt: swinging]",
        "",
        "   ",
    ):
        assert boilerplate(line), line
    assert not boilerplate("A rat arrives.")


def test_newcomers_are_the_names_that_were_not_there():
    assert newcomers([], ["Sable"]) == ["Sable"]
    assert newcomers(["Sable"], ["Sable", "Uthmor"]) == ["Uthmor"]
    assert newcomers(["Sable", "Uthmor"], ["Sable"]) == []
    assert newcomers(None, None) == []


def test_own_names_come_from_the_login_file_in_either_shape():
    login = {
        "account": "TESTACCT",
        "character": "Lanival",
        "accounts": {"TESTACCT": ["Lanival", "Sable"], "OTHER": ["Uthmor"]},
    }
    assert own_names(login) == ["Lanival", "Sable", "Uthmor"]
    nested = {"accounts": {"TESTACCT": {"characters": ["Sable"]}}}
    assert own_names(nested) == ["Sable"]
    assert own_names({}) == []
    assert own_names(None) == []


def test_distance_and_nearness():
    assert distance("kitten", "sitting") == 3
    assert distance("", "abc") == 3
    assert near("a rat bites your arm", "a rat bites your leg")
    assert not near("a rat bites your arm", "a rat bites your arm")  # identical
    assert not near("a rat bites your arm", "the sun sets over the harbor")


def test_a_line_is_news_once_then_remembered():
    store = Novelty()
    assert store.observe("A stranger looks at you oddly.", 0.0) == (
        "new",
        "A stranger looks at you oddly.",
    )
    assert store.observe("A stranger looks at you oddly.", 1.0) is None
    # Ten minutes on it is settled as seen, and the file keeps it.
    store.observe("Something else happens.", 700.0)
    assert "a stranger looks at you oddly." in store.seen
    data = json.loads(json.dumps(store.to_json()))
    again = Novelty.from_json(data)
    assert again.observe("A stranger looks at you oddly.", 800.0) is None
    assert again.observe("Something else happens.", 800.0) is None


def test_a_line_naming_a_player_present_is_their_business():
    store = Novelty()
    assert store.observe("Sable swings a sword at a rat.", 0.0, names=["Sable"]) is None
    assert store.observe("Sable swings a sword at a rat.", 0.0)[0] == "new"


def test_the_same_line_past_the_unique_threshold_is_spam():
    store = Novelty()
    verdicts = [
        store.observe("Someone pokes you.", float(i)) for i in range(UNIQUE + 1)
    ]
    assert verdicts[0] == ("new", "Someone pokes you.")
    assert all(verdict is None for verdict in verdicts[1:UNIQUE])
    kind, why = verdicts[UNIQUE]
    assert kind == "spam"
    assert "Someone pokes you." in why
    # The windows reset after the alert: the next repeat starts over.
    assert store.observe("Someone pokes you.", 10.0) is None


def test_near_duplicate_lines_within_the_span_are_spam():
    # The first line has nothing to rhyme with, so the threshold is met
    # one line later.
    store = Novelty()
    verdicts = []
    for i in range(FREQUENCY + 1):
        verdicts.append(
            store.observe(f"A stranger pokes you in the {'arm' * (i + 1)}.", float(i))
        )
    assert verdicts[0] == ("new", "A stranger pokes you in the arm.")
    assert verdicts[-1][0] == "spam"
    assert "near-duplicate" in verdicts[-1][1]


def test_your_own_doings_and_paragraphs_are_news_once_but_never_spam():
    # 2026-09-23, the first evening: ;perform's "You continue playing on
    # your copper zills." rang the bells every few minutes, and a walk's
    # room descriptions rhymed past the near-duplicate threshold.
    from client.game.novelty import spam_material

    assert not spam_material("You continue playing on your copper zills.")
    assert not spam_material("Your armor hinders your attempt.")
    assert not spam_material("A " + "long room paragraph " * 12 + "ends here.")
    assert spam_material("Someone pokes you.")
    store = Novelty()
    verdicts = [
        store.observe("You continue playing on your copper zills.", float(i))
        for i in range(UNIQUE * 3)
    ]
    assert verdicts[0][0] == "new"
    assert all(verdict is None for verdict in verdicts[1:])
    walk = [
        store.observe(f"You go {way}.", float(i))
        for i, way in enumerate(["north", "south", "east", "west", "up", "down", "out"])
    ]
    assert all(verdict is None or verdict[0] == "new" for verdict in walk)


def test_inventory_lines_and_the_exp_tables_husks_are_boilerplate():
    # The first evening's dock: the sheet's INV LIST items with their
    # leading dash, and the exp table once its numbers are scrubbed.
    for line in (
        "-some dried nemoih",
        "-an ordinary lockpick",
        ", , and ( ).",
        "favors :",
    ):
        assert boilerplate(line), line
    assert not boilerplate("Heavy Thrown: 3 12% clear (0/34)")  # words remain
    assert not boilerplate("A stranger arrives.")


def test_an_answer_to_the_characters_own_command_is_news_once_but_never_spam():
    # "Crush what?" fifteen times in four minutes, "Somebody has already
    # located and identified the current trap" twelve: the scripts'
    # own repeated commands, answered.
    store = Novelty()
    verdicts = [
        store.observe("Crush what?", float(i), answer=True) for i in range(UNIQUE * 3)
    ]
    assert verdicts[0] == ("new", "Crush what?")
    assert all(verdict is None for verdict in verdicts[1:])


def test_the_same_spam_line_rings_at_most_once_an_hour():
    from client.game.novelty import SPAM_REPEAT

    store = Novelty()
    first = [
        store.observe("A stranger pokes you.", float(i)) for i in range(UNIQUE + 1)
    ]
    assert first[-1][0] == "spam"
    again = [
        store.observe("A stranger pokes you.", 100.0 + i) for i in range(UNIQUE + 1)
    ]
    assert all(verdict is None for verdict in again)
    # An hour on the line has long settled into the seen-store, which
    # never judges a line again: silent for good, not once an hour.
    later = [
        store.observe("A stranger pokes you.", SPAM_REPEAT + 200.0 + i)
        for i in range(UNIQUE + 1)
    ]
    assert all(verdict is None for verdict in later)
    assert "a stranger pokes you." in store.seen


def test_near_duplicates_spread_past_the_span_are_not_spam():
    store = Novelty()
    verdicts = []
    for i in range(FREQUENCY + 1):
        verdicts.append(
            store.observe(f"A stranger pokes you in the {'arm' * (i + 1)}.", i * 100.0)
        )
    assert all(verdict is None or verdict[0] == "new" for verdict in verdicts)


def test_the_store_file_round_trips_and_a_bad_file_yields_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("REVENANT_SENTINEL_DIR", str(tmp_path))
    store = Novelty()
    store.observe("A rat arrives.", 0.0)
    novelty.save("Lanival", store)
    assert not store.dirty
    loaded = novelty.load("Lanival")
    assert loaded.observe("A rat arrives.", 0.0) is None
    (tmp_path / "Sable.json").write_text("{not json")
    assert novelty.load("Sable").seen == set()
    assert novelty.load("Nobody").seen == set()
    assert not list(tmp_path.glob("*.tmp"))
