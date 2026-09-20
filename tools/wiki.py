"""Elanthipedia pages cached locally:  uv run python tools/wiki.py <Page title> [--refresh] [--grep WORD]

    uv run python tools/wiki.py "Soul system"            print the page's raw wikitext, fetching it once
    uv run python tools/wiki.py "Cambrinth" --grep rank  only the lines holding the word (case-insensitive)
    uv run python tools/wiki.py "Almsbox" --refresh      fetch again even when cached
    uv run python tools/wiki.py --list                   the cached pages and when each was fetched

Research on a game mechanic starts at Elanthipedia (CLAUDE.md), and a
page read once is read again the next evening: the soul system, a
quest walkthrough, a shop's stock. This keeps each page's raw
wikitext (`?action=raw`, the tables intact — a summarizing fetch
garbles them, .claude/learnings.md) under ~/.revenant/wiki/<title>.txt
with the fetch time beside it, so the second look costs nothing and
survives the site being slow or down; a redirect page is followed to
the page it names, and the console is written as UTF-8 whatever the
page holds. The cache is the operator's
machine's, never the repo's; a page older than REFRESH_DAYS is fetched
again on the next read. REVENANT_WIKI_DIR moves the directory.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://elanthipedia.play.net/"
REFRESH_DAYS = 30
USER_AGENT = "revenant-wiki-cache/1 (a DragonRealms client's research cache)"


def cache_dir() -> Path:
    return Path(os.environ.get("REVENANT_WIKI_DIR", "~/.revenant/wiki")).expanduser()


def slug(title: str) -> str:
    """A file name for a page title: spaces to underscores, the rest
    kept where the filesystem allows it."""
    cleaned = re.sub(r"[^\w' .()-]+", "_", title.strip().replace(" ", "_"))
    return cleaned or "untitled"


def page_url(title: str) -> str:
    return BASE + urllib.parse.quote(title.strip().replace(" ", "_")) + "?action=raw"


def index_path() -> Path:
    return cache_dir() / "index.json"


def load_index() -> dict:
    try:
        return json.loads(index_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_index(index: dict) -> None:
    index_path().parent.mkdir(parents=True, exist_ok=True)
    index_path().write_text(
        json.dumps(index, indent=1, sort_keys=True), encoding="utf-8"
    )


def fetch(title: str, timeout: float = 30) -> str:
    request = urllib.request.Request(
        page_url(title), headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


_REDIRECT = re.compile(r"^\s*#REDIRECT\s*\[\[([^\]|]+)", re.IGNORECASE)


def follow_redirect(title: str, text: str, fetcher, hops: int = 3) -> str:
    """The page a redirect points at, fetched in the redirect's place —
    "Vela'tohr Plant" is `#REDIRECT [[Vela'tohr plant]]`, and on a
    case-insensitive filesystem the two titles share one cache file,
    so the redirect stub overwrote the page it named (2026-09-20). Up
    to `hops` redirects; the text as it came otherwise."""
    for _ in range(hops):
        match = _REDIRECT.match(text or "")
        if not match:
            break
        target = match.group(1).strip()
        if target == title.strip():
            break  # a page pointing at itself never spins (a case-only hop is real)
        title, text = target, fetcher(target)
    return text


def read(title: str, refresh: bool = False, fetcher=None) -> str:
    """The page's raw wikitext, from the cache when it holds a fresh
    copy, fetched (and cached) otherwise — a redirect page followed to
    the page it names. Raises URLError/HTTPError when the page cannot
    be fetched and no cached copy exists."""
    path = cache_dir() / f"{slug(title)}.txt"
    index = load_index()
    entry = index.get(title)
    fresh = (
        path.is_file()
        and entry is not None
        and time.time() - entry.get("fetched", 0) < REFRESH_DAYS * 86400
    )
    if fresh and not refresh:
        return path.read_text(encoding="utf-8")
    try:
        text = follow_redirect(title, (fetcher or fetch)(title), fetcher or fetch)
    except Exception:
        if path.is_file():
            return path.read_text(encoding="utf-8")  # stale beats nothing
        raise
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    index[title] = {"fetched": time.time(), "file": path.name, "bytes": len(text)}
    save_index(index)
    return text


def listing() -> list:
    """[(title, fetched time, bytes)] of every cached page, by title."""
    return sorted(
        (title, entry.get("fetched", 0), entry.get("bytes", 0))
        for title, entry in load_index().items()
    )


def utf8_console(stream) -> None:
    """A Windows console writes cp1252, and a wiki page holds what it
    holds: the Vela'tohr Plant page's left-to-right mark crashed the
    print with UnicodeEncodeError (2026-09-20). The stream is switched
    to UTF-8 with replacement where it can be; a stream that cannot be
    reconfigured (a test's capture) is left alone."""
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
    parser = argparse.ArgumentParser(prog="tools/wiki.py", description=__doc__)
    parser.add_argument("title", nargs="?", help="the page title, as the wiki shows it")
    parser.add_argument(
        "--refresh", action="store_true", help="fetch again even when cached"
    )
    parser.add_argument("--grep", metavar="WORD", help="only the lines holding WORD")
    parser.add_argument("--list", action="store_true", help="the cached pages")
    args = parser.parse_args(argv)
    if args.list:
        for title, fetched, size in listing():
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(fetched))
            print(f"{when}  {size:>7}  {title}")
        return 0
    if not args.title:
        parser.error("a page title, or --list")
    try:
        text = read(args.title, refresh=args.refresh)
    except Exception as error:
        print(f"wiki: could not fetch {args.title!r}: {error}", file=sys.stderr)
        return 1
    if args.grep:
        needle = args.grep.lower()
        for number, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                print(f"{number}: {line}")
        return 0
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
