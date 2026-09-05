"""The terminal frontend end to end, headless (#57): a fake session on
an ephemeral port, the Textual app driven by its test pilot, game text
in, rendered lines and a status bar out, a typed command back to the
game. Nothing here ever touches a live game.
"""

import asyncio

import pytest
from test_session import FakeGame, _await, _start_server

from client.tui import RevenantTUI

ROOM = (
    b"<streamWindow id='room' title='Room' subtitle=\" - [Town Green]\"/>"
    b"<pushStream id='room'/><popStream/>"
    b"<style id='roomName'/>[Town Green]<style id=''/>\r\n"
    b"You see a rat.\r\n"
    b"<prompt time='1788577396'>&gt;</prompt>\r\n"
)


def _run(coro):
    return asyncio.run(asyncio.wait_for(coro, 30))


@pytest.fixture
def fake_session():
    game = FakeGame()
    server, port = _start_server(game)
    yield game, server, port
    server.shutdown()


def test_game_text_reaches_the_log_and_typed_commands_reach_the_game(fake_session):
    game, server, port = fake_session
    frontend = RevenantTUI("127.0.0.1", port)
    frontend.rules = []
    app = frontend.build()

    async def scenario():
        from textual.widgets import RichLog, Static

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.5)
            assert _await(lambda: server.clients), "the TUI never attached"
            game.pending.append(ROOM)
            for _ in range(40):
                await pilot.pause(0.1)
                lines = [
                    "".join(segment.text for segment in strip)
                    for strip in app.query_one("#log", RichLog).lines
                ]
                if any("You see a rat." in line for line in lines):
                    break
            else:
                raise AssertionError(f"game text never rendered: {lines}")
            assert any("[Town Green]" in line for line in lines)
            status = str(app.query_one("#status", Static).render())
            assert f"attached to 127.0.0.1:{port}" in status
            await pilot.click("#input")
            await pilot.press(*"look", "enter")
            assert _await(lambda: game.sent), "the command never reached the game"
            assert game.sent[-1] == b"look\n"
            lines = [
                "".join(segment.text for segment in strip)
                for strip in app.query_one("#log", RichLog).lines
            ]
            assert any(line.startswith("> look") for line in lines)

    _run(scenario())
