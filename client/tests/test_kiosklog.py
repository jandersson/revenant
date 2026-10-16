"""The kiosk dataset read out of a game log (#574): each sale goes to its
kiosk's owner, each STUDY becomes a reading, each TAP a resale with the
Finesse it sold under; a rerun adds nothing. The wordings were captured
at Grisgonda's on 2026-10-16 (#567); names are the synthetic cast's."""

import sqlite3

from client.game import kiosklog

ROOM = (
    "<streamWindow id='room' title='Room' subtitle=\" - [Grisgonda's, Appraisal "
    "Room]\" location='center' target='drop' ifClosed='' resident='true'/>"
)
TWO_KIOSKS = (
    "<component id='room objs'>You also see a euhedral crystalline kiosk, a "
    "heptagonally symmetrical crystalline kiosk and a Dwarven appraiser.</component>"
)
DOUBLED = (
    "<component id='room objs'>You also see a euhedral crystalline kiosk, a "
    "heptagonally symmetrical crystalline kiosk, a euhedral crystalline kiosk and a "
    "Dwarven appraiser.</component>"
)


def prompt(epoch):
    return f'<prompt time="{epoch}">&gt;</prompt>'


def sale(look, seller, kind):
    return (
        f"A {look} ripples like water, and the surface spirals open, revealing an "
        f"empty interior chamber.  {seller} places her {kind} in the crystalline "
        "kiosk, which chimes and closes seamlessly.  After a brief moment, the kiosk "
        "pulses with soft light and a tidy pile of coins rises from its surface, "
        "which she quickly pockets."
    )


REFRESH = (
    "Uthmor gestures at a euhedral crystalline kiosk, which responds by briefly "
    "undulating with green-orange hues."
)
STUDY = [
    "As you examine your kiosk, a silvery-voiced message ringing of glass and order "
    "echoes in your mind.",
    "You note that your kiosk is currently configured to dispense tied bundles.",
    "During this kiosk's trading session, it has purchased the following:",
    "  No Kronars in pouches.",
    "  1 gold, 7 silver, and 8 copper Kronars in bundles.",
    "  The markup is set to 55%.",
    "Finally, your kiosk's current reserves are:",
    "  It holds 97 platinum, 8 gold, 2 silver, 6 bronze, and 6 copper Kronars in "
    "reserve for purchases.",
    "  19 platinum, 9 gold, 1 silver, 6 bronze, and 4 copper Kronars in pouches.",
    "  23 platinum, 3 gold, 2 silver, 7 bronze, and 8 copper Kronars in bundles.",
    "Flowing like water, the kiosk returns to its normal form.",
    "Roundtime: 5 sec.",
]
OTHERS_STUDY = [
    "As you are not the owner of a euhedral crystalline kiosk, it rearranges "
    "slightly and displays the following information:",
    "  The markup is set to 55%.",
    "  Per guild privilege, the kiosk also indicates that its owner is Uthmor.",
    "Roundtime: 5 sec.",
]
TAP = (
    "A heptagonally symmetrical crystalline kiosk ripples like water, and the surface "
    "spirals open, revealing a crystalline bundle dusted in frost, which you remove.  "
    "After a moment, the kiosk chimes and closes seamlessly."
)
RESALE = [
    '<pushStream id="percWindow"/>Finesse  (30 roisaen)',
    "<component id='exp Trading'></component>",
    prompt(1100),
    TAP,
    prompt(1160),
    '<pushStream id="percWindow"/>Finesse  (29 roisaen)',  # once a minute
    "The tanner Falken looks the tight bundle over carefully, then whispers, "
    '"I can give 347570 Kronars for it."',
    "<component id='exp Trading'><d cmd='skill Trading'> Trading</d>:  767 40%  "
    "[19/34]</component>",
    "<right exist='1' noun='bundle'>crystalline bundle</right>"
    "You ask the tanner Falken to buy a crystalline tight bundle.",
    prompt(1170),
    "The tanner Falken ponders over the bundle for a while, then hands you 347570 "
    "Kronars.",
    "<component id='exp Trading'><d cmd='skill Trading'> Trading</d>:  767 41%  "
    "[18/34]</component>",
]


def scan(lines, mana=None):
    return kiosklog.scan(lines, "Lanival", lambda epoch: mana)


def rows(events, table):
    return [row for name, row in events if name == table]


def test_a_sale_goes_to_the_owner_named_before_or_after_it():
    events = scan(
        [
            ROOM,
            TWO_KIOSKS,
            prompt(1000),
            REFRESH,
            sale("euhedral crystalline kiosk", "Sable", "pouch"),
            prompt(1010),
            sale("heptagonally symmetrical crystalline kiosk", "Sable", "bundle"),
            prompt(1020),
            TAP,  # names the heptagonal kiosk ours, after its sale
        ]
    )
    sales = rows(events, "kiosk_sales")
    assert [(r["kiosk"], r["owner"], r["kind"]) for r in sales] == [
        ("euhedral crystalline kiosk", "Uthmor", "pouch"),
        ("heptagonally symmetrical crystalline kiosk", "Lanival", "bundle"),
    ]
    assert sales[0]["room"] == "Grisgonda's, Appraisal Room"
    assert sales[0]["seen_at"].startswith("1970-01-01T00:16:40")


def test_two_kiosks_with_one_look_leave_the_owner_unknown():
    events = scan(
        [
            DOUBLED,
            prompt(1000),
            REFRESH,
            sale("euhedral crystalline kiosk", "Sable", "pouch"),
        ]
    )
    assert rows(events, "kiosk_sales")[0]["owner"] is None


def test_a_kiosk_cast_after_a_sale_is_not_its_owner():
    cast = (
        "<spell>None</spell>Your tessera grows cold, flickering in a complex "
        "undulating pattern, and with the sound of shattering glass and a hiss of "
        "displaced air, a euhedral crystalline kiosk unfolds from nothingness."
    )
    events = scan(
        [
            prompt(1000),
            sale("euhedral crystalline kiosk", "Sable", "pouch"),
            prompt(1010),
            cast,
            sale("euhedral crystalline kiosk", "Sable", "bundle"),
        ]
    )
    assert [r["owner"] for r in rows(events, "kiosk_sales")] == [None, "Lanival"]


def test_the_owners_study_and_another_traders_become_readings():
    events = scan(
        [prompt(1000), *STUDY, prompt(1010), *OTHERS_STUDY, prompt(1020), TAP]
    )
    mine, theirs = rows(events, "kiosk_readings")
    assert mine["kiosk"] == "heptagonally symmetrical crystalline kiosk"  # the TAP's
    assert (mine["mine"], mine["markup"], mine["reserve"]) == (1, 55, 978266)
    assert (mine["pouch"], mine["bundle"]) == (199164, 233278)
    assert (theirs["owner"], theirs["mine"], theirs["markup"]) == ("Uthmor", 0, 55)
    assert theirs["reserve"] is None


def test_a_resale_keeps_the_stored_value_the_pay_and_the_finesse_it_sold_under():
    events = scan([prompt(1000), *STUDY, *RESALE], mana=72)
    (resale,) = rows(events, "kiosk_resales")
    assert resale["kind"] == "bundle"
    assert resale["stored"] == 233278
    assert (resale["buyer"], resale["offered"], resale["paid"]) == (
        "tanner Falken",
        347570,
        347570,
    )
    assert (resale["finesse"], resale["finesse_mana"]) == (1, 72)
    # The lesson lands with the quote, before the sale: its peak is kept.
    assert (resale["trading_before"], resale["trading_after"]) == (0, 19)


def test_a_resale_without_finesse_in_the_spells_window_says_so():
    lines = [line for line in RESALE if "percWindow" not in line]
    (resale,) = rows(scan([prompt(1000), *STUDY, *lines], mana=72), "kiosk_resales")
    assert (resale["finesse"], resale["finesse_mana"]) == (0, None)


def test_one_sale_seen_by_two_characters_is_kept_once_with_the_owner_either_knew(
    tmp_path,
):
    path = tmp_path / "history.db"
    look = "euhedral crystalline kiosk"
    blind = kiosklog.scan([prompt(1000), sale(look, "Sable", "pouch")], "Uthmor")
    knowing = scan([prompt(1002), REFRESH, sale(look, "Sable", "pouch")])
    assert kiosklog.record(blind, path)["kiosk_sales"] == 1
    assert kiosklog.record(knowing, path)["kiosk_sales"] == 0
    assert kiosklog.record(knowing, path) == {
        "kiosk_sales": 0,
        "kiosk_readings": 0,
        "kiosk_resales": 0,
    }
    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "SELECT observer, owner FROM kiosk_sales"
        ).fetchall() == [("Uthmor", "Uthmor")]
    finally:
        connection.close()
