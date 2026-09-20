"""tools/wiki.py caches a wiki page's raw text once and serves it from
the cache after: a fetch fills the cache and the index, the next read
never fetches, --refresh does, a fetch that fails falls back to the
stale copy, and --grep prints the matching lines."""

import importlib.util
import pathlib
import sys
import time

import pytest

REPO = pathlib.Path(__file__).parents[2]


def _tool():
    spec = importlib.util.spec_from_file_location("wiki_tool", REPO / "tools/wiki.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


wiki = _tool()


@pytest.fixture
def cache(monkeypatch, tmp_path):
    monkeypatch.setenv("REVENANT_WIKI_DIR", str(tmp_path))
    return tmp_path


def test_a_page_is_fetched_once_then_read_from_the_cache(cache):
    fetches = []

    def fetcher(title):
        fetches.append(title)
        return f"== {title} ==\nThe soul states from best to worst are:\n"

    assert "soul states" in wiki.read("Soul system", fetcher=fetcher)
    assert wiki.read("Soul system", fetcher=fetcher).startswith("== Soul system ==")
    assert fetches == ["Soul system"]
    assert (cache / "Soul_system.txt").is_file()
    [(title, fetched, size)] = wiki.listing()
    assert title == "Soul system" and size > 0 and time.time() - fetched < 60


def test_refresh_fetches_again_and_a_failed_fetch_keeps_the_stale_copy(cache):
    calls = {"n": 0}

    def fetcher(title):
        calls["n"] += 1
        if calls["n"] >= 3:
            raise OSError("site down")
        return f"copy {calls['n']}\n"

    assert wiki.read("Almsbox", fetcher=fetcher) == "copy 1\n"
    assert wiki.read("Almsbox", refresh=True, fetcher=fetcher) == "copy 2\n"
    assert (
        wiki.read("Almsbox", refresh=True, fetcher=fetcher) == "copy 2\n"
    )  # stale beats nothing
    with pytest.raises(OSError):
        wiki.read("Nowhere", fetcher=fetcher)


def test_the_console_lists_and_greps(cache, capsys, monkeypatch):
    monkeypatch.setattr(
        wiki, "fetch", lambda title: "one\nThe rule of thumb is ranks\nthree\n"
    )
    assert wiki.main(["Cambrinth", "--grep", "RULE"]) == 0
    assert capsys.readouterr().out == "2: The rule of thumb is ranks\n"
    assert wiki.main(["--list"]) == 0
    assert "Cambrinth" in capsys.readouterr().out


def test_a_page_with_a_character_the_console_cannot_write_still_prints(
    cache, monkeypatch
):
    # The Vela'tohr Plant page holds a left-to-right mark (U+200E); a
    # cp1252 console raised UnicodeEncodeError on the print (2026-09-20).
    import io

    monkeypatch.setattr(wiki, "fetch", lambda title: "nectar‎ heals\nsecond\n")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", console)
    assert wiki.main(["Vela'tohr Plant"]) == 0
    console.flush()

    def written(stream):  # the wrapper's own newline translation aside
        return stream.buffer.getvalue().decode("utf-8").replace("\r\n", "\n")

    assert written(console) == "nectar‎ heals\nsecond\n"
    grep = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", grep)
    assert wiki.main(["Vela'tohr Plant", "--grep", "nectar"]) == 0
    grep.flush()
    assert written(grep) == "1: nectar‎ heals\n"


def test_a_redirect_is_followed_to_the_page_it_names(cache):
    # "Vela'tohr Plant" redirects to "Vela'tohr plant"; the two titles
    # share one cache file on Windows, and the stub overwrote the page
    # (2026-09-20). The page's text is what both titles read.
    pages = {
        "Vela'tohr Plant": "#REDIRECT [[Vela'tohr plant]]\n",
        "Vela'tohr plant": "The plant heals.\n",
        "Loop": "#REDIRECT [[Loop]]\n",
    }
    fetches = []

    def fetcher(title):
        fetches.append(title)
        return pages[title]

    assert wiki.read("Vela'tohr Plant", fetcher=fetcher) == "The plant heals.\n"
    assert fetches == ["Vela'tohr Plant", "Vela'tohr plant"]
    assert wiki.read("Vela'tohr plant", fetcher=fetcher) == "The plant heals.\n"
    assert wiki.read("Loop", fetcher=fetcher) == "#REDIRECT [[Loop]]\n"  # never spins


def test_titles_become_safe_file_names_and_raw_urls():
    assert wiki.slug("Brother Durantine's Shop") == "Brother_Durantine's_Shop"
    assert wiki.slug("a/b:c") == "a_b_c"
    assert (
        wiki.page_url("Soul system")
        == "https://elanthipedia.play.net/Soul_system?action=raw"
    )
