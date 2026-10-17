"""tools/plaza.py reads drservice.info's Plaza export (an .xlsx of
every player shop's items) and answers price questions: the export is
parsed by its header, downloaded once a day and kept, a failed or bad
download falls back to the stale copy, and --grep, --city and --under
print one line per item, cheapest in Kronars first."""

import importlib.util
import io
import os
import pathlib
import time
import zipfile

import pytest

REPO = pathlib.Path(__file__).parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("plaza_tool", REPO / "tools/plaza.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


plaza = _tool()

NS = 'xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
HEADER = ["Tap", "Price", "Plats", "KValue", "Shop Name", "Owner", "City", "ScanDate"]
ITEMS = [
    # Tap, Price, Plats, KValue, Shop Name, Owner, City, ScanDate (2026-10-16)
    [
        "grey suede gem pouch",
        50000,
        5,
        50000,
        '"Lanival\'s Sundries"',
        "Lanival",
        "Crossing",
        46311.81,
    ],
    [
        "black leather gem pouch",
        80000,
        8,
        100000,
        "Sable's Satchels",
        "Sable",
        "Riverhaven",
        46311.5,
    ],
    [
        "steel lockpick ring",
        300000,
        30,
        300000,
        "Uthmor's Locks",
        "Uthmor",
        "Shard",
        46300.25,
    ],
]


def export(rows=ITEMS) -> bytes:
    """An export in the site's shape: shared strings, x: prefixes,
    numbers as t="n", the scan date a bare serial, an empty string
    cell as `<x:c t="s" />`."""
    strings, cells_xml = [], []
    for number, row in enumerate([HEADER, *rows], 1):
        cells = []
        for column, value in zip("ABCDEFGHIJ", row):
            ref = f"{column}{number}"
            if value == "":
                cells.append(f'<x:c r="{ref}" s="0" t="s" />')
            elif isinstance(value, str):
                strings.append(value)
                cells.append(
                    f'<x:c r="{ref}" t="s"><x:v>{len(strings) - 1}</x:v></x:c>'
                )
            else:
                kind = "" if column == "H" else ' t="n"'
                cells.append(f'<x:c r="{ref}"{kind}><x:v>{value}</x:v></x:c>')
        cells_xml.append(f'<x:row r="{number}">{"".join(cells)}</x:row>')
    shared = "".join(
        f"<x:si><x:t>{s.replace('&', '&amp;')}</x:t></x:si>" for s in strings
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("xl/sharedStrings.xml", f"<x:sst {NS}>{shared}</x:sst>")
        book.writestr(
            "xl/worksheets/sheet.xml",
            f"<x:worksheet {NS}><x:sheetData>{''.join(cells_xml)}</x:sheetData></x:worksheet>",
        )
    return buffer.getvalue()


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_PLAZA_DIR", str(tmp_path))
    return tmp_path


def test_the_export_is_read_by_its_header():
    [pouch, *_] = plaza.parse(export())
    assert pouch["Tap"] == "grey suede gem pouch"
    assert pouch["City"] == "Crossing"
    assert float(pouch["KValue"]) == 50000


def test_an_empty_cell_reads_as_empty_text():
    [row] = plaza.parse(
        export([["plain tin ring", 100, 1, 100, "", "Sable", "Shard", 46311.0]])
    )
    assert row["Shop Name"] == ""


def test_the_export_is_downloaded_once_a_day_then_read_from_the_cache(cache):
    downloads = []

    def fetcher():
        downloads.append(1)
        return export()

    assert len(plaza.read(fetcher=fetcher)) == 3
    assert len(plaza.read(fetcher=fetcher)) == 3
    assert downloads == [1]
    day_old = time.time() - 25 * 3600
    os.utime(cache / "latest.xlsx", (day_old, day_old))
    plaza.read(fetcher=fetcher)
    assert downloads == [1, 1]
    plaza.read(refresh=True, fetcher=fetcher)
    assert downloads == [1, 1, 1]


def test_a_failed_or_bad_download_keeps_the_stale_copy(cache):
    plaza.read(fetcher=export)

    def down():
        raise OSError("site down")

    assert len(plaza.read(refresh=True, fetcher=down)) == 3
    assert len(plaza.read(refresh=True, fetcher=lambda: b"<html>error</html>")) == 3
    assert (
        plaza.parse((cache / "latest.xlsx").read_bytes())[0]["Tap"]
        == "grey suede gem pouch"
    )


def test_a_bad_download_with_no_cache_raises_and_caches_nothing(cache):
    with pytest.raises(zipfile.BadZipFile):
        plaza.read(fetcher=lambda: b"<html>error</html>")
    assert not (cache / "latest.xlsx").exists()


def test_the_filters_combine_and_the_cheapest_in_kronars_comes_first():
    rows = plaza.parse(export())
    pouches = plaza.select(rows, grep="POUCH")
    assert [row["Tap"] for row in pouches] == [
        "grey suede gem pouch",
        "black leather gem pouch",
    ]
    assert [row["Tap"] for row in plaza.select(rows, city="river")] == [
        "black leather gem pouch"
    ]
    # --under is Kronar platinum: 8 Lirum plat is 10 Kronar plat, not under 10
    assert [row["Tap"] for row in plaza.select(rows, under=10)] == [
        "grey suede gem pouch"
    ]
    assert plaza.select(rows, grep="pouch", city="shard") == []


def test_a_line_names_the_item_shop_city_price_and_scan_date():
    crossing, riverhaven, shard = plaza.parse(export())
    assert plaza.line(crossing) == (
        "grey suede gem pouch | Lanival's Sundries | Crossing | 5 plat | 2026-10-16"
    )
    assert plaza.line(riverhaven) == (
        "black leather gem pouch | Sable's Satchels | Riverhaven"
        " | 8 plat (10 Kronar plat) | 2026-10-16"
    )
    assert plaza.line(shard).endswith("| 30 plat | 2026-10-05")


def test_grep_prints_the_matching_items(cache, capsys):
    plaza.read(fetcher=export)
    assert plaza.main(["--grep", "lockpick"]) == 0
    assert capsys.readouterr().out == (
        "steel lockpick ring | Uthmor's Locks | Shard | 30 plat | 2026-10-05\n"
    )
    assert plaza.main(["--grep", "anvil"]) == 0
    assert "no item matches" in capsys.readouterr().err
