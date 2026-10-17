"""Trader shop prices from drservice.info's Plaza:  uv run python tools/plaza.py [--grep WORD] [--city NAME] [--under N] [--refresh]

    uv run python tools/plaza.py --grep pouch              every shop item whose name holds the word
    uv run python tools/plaza.py --city shard --under 10   Shard's items under 10 Kronar platinum
    uv run python tools/plaza.py --grep tessera --refresh  download again even when cached

The Plaza Shop Browser (https://drservice.info/Plaza/) scans every
player shop: each item, its shop, city, price and Kronar value. Its
table loads in the browser, so the source is the Excel export
(`Export.asmx/Latest`), kept under ~/.revenant/plaza for a day and
read with the standard library. One line per item, cheapest first:
item | shop | city | price | last scanned. A price is in the city's
own coin, with its Kronar value beside it where they differ; --under
compares Kronar platinum, so the cities compare. The filters combine.
REVENANT_PLAZA_DIR moves the cache.
"""

import argparse
import datetime
import io
import os
import re
import sys
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

URL = "https://drservice.info/Plaza/Export.asmx/Latest"
REFRESH_HOURS = 24
USER_AGENT = "revenant-plaza-cache/1 (a DragonRealms client's price lookup)"
X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXCEL_EPOCH = datetime.datetime(1899, 12, 30)


def cache_dir() -> Path:
    return Path(os.environ.get("REVENANT_PLAZA_DIR", "~/.revenant/plaza")).expanduser()


def fetch(timeout: float = 60) -> bytes:
    request = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _text(element) -> str:
    return "".join(t.text or "" for t in element.iter(X + "t"))


def parse(data: bytes) -> list:
    """The export's rows as dicts keyed by its header (Tap, Shop Name,
    City, Price, KValue, ScanDate, ...). Raises on anything not an
    export: a zip without the sheet, XML that does not parse."""
    with zipfile.ZipFile(io.BytesIO(data)) as book:
        shared = ET.fromstring(book.read("xl/sharedStrings.xml"))
        sheet = ET.fromstring(book.read("xl/worksheets/sheet.xml"))
    strings = [_text(si) for si in shared.iter(X + "si")]
    table = []
    for row in sheet.iter(X + "row"):
        cells = {}
        for cell in row.iter(X + "c"):
            column = re.match(r"[A-Z]+", cell.get("r", "")).group()
            value = cell.find(X + "v")
            if value is None:
                cells[column] = ""
            elif cell.get("t") == "s":
                cells[column] = strings[int(value.text)]
            else:
                cells[column] = value.text or ""
        table.append(cells)
    if not table:
        return []
    header = table[0]
    return [
        {header[c]: v for c, v in cells.items() if c in header} for cells in table[1:]
    ]


def read(refresh: bool = False, fetcher=None) -> list:
    """The export's rows, from the cache when it is under a day old,
    downloaded (and cached) otherwise. A failed download falls back to
    the stale copy; with none, it raises."""
    path = cache_dir() / "latest.xlsx"
    fresh = path.is_file() and time.time() - path.stat().st_mtime < REFRESH_HOURS * 3600
    if fresh and not refresh:
        return parse(path.read_bytes())
    try:
        data = (fetcher or fetch)()
        rows = parse(data)  # an error page is never cached
    except Exception:
        if path.is_file():
            return parse(path.read_bytes())  # stale beats nothing
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    partial.write_bytes(data)
    partial.replace(path)
    return rows


def _number(text) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def plat(copper: float) -> str:
    return f"{copper / 10000:,.4f}".rstrip("0").rstrip(".")


def scanned(serial) -> str:
    """An Excel date serial (days since 1899-12-30) as YYYY-MM-DD."""
    days = _number(serial)
    return (
        (EXCEL_EPOCH + datetime.timedelta(days=days)).date().isoformat()
        if days
        else "?"
    )


def select(rows, grep=None, city=None, under=None) -> list:
    """The rows that match every filter given, cheapest in Kronars first."""
    chosen = [
        row
        for row in rows
        if (not grep or grep.lower() in row.get("Tap", "").lower())
        and (not city or city.lower() in row.get("City", "").lower())
        and (under is None or _number(row.get("KValue")) < under * 10000)
    ]
    return sorted(chosen, key=lambda row: _number(row.get("KValue")))


def line(row) -> str:
    price, kronars = _number(row.get("Price")), _number(row.get("KValue"))
    cost = f"{plat(price)} plat"
    if price != kronars:
        cost += f" ({plat(kronars)} Kronar plat)"
    shop = row.get("Shop Name", "").strip('"')
    return " | ".join(
        (
            row.get("Tap", ""),
            shop,
            row.get("City", ""),
            cost,
            scanned(row.get("ScanDate")),
        )
    )


def utf8_console(stream) -> None:
    """Item names hold what they hold; a cp1252 console would crash the
    print, so the stream is switched to UTF-8 where it can be."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError):
        pass


def main(argv=None) -> int:
    utf8_console(sys.stdout)
    utf8_console(sys.stderr)
    parser = argparse.ArgumentParser(
        prog="tools/plaza.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--grep", metavar="WORD", help="items whose name holds WORD")
    parser.add_argument("--city", metavar="NAME", help="Crossing, Riverhaven, Shard")
    parser.add_argument(
        "--under", metavar="N", type=float, help="under N Kronar platinum"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="download again even when cached"
    )
    args = parser.parse_args(argv)
    try:
        rows = read(refresh=args.refresh)
    except Exception as error:
        print(f"plaza: could not download the export: {error}", file=sys.stderr)
        return 1
    chosen = select(rows, grep=args.grep, city=args.city, under=args.under)
    for row in chosen:
        print(line(row))
    if not chosen:
        print("plaza: no item matches", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
