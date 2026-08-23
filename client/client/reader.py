"""The frontend's reader loop: pump frames until the connection ends.

A crash inside the loop must surface, never die silently: the reader
runs on a worker thread, and the default threading excepthook is a
stderr print nobody sees — the window would stay up, claim Connected,
and simply never show game text again (#96). Qt-free on purpose: the
GUI hands in its engine read and status signal, and the headless test
suite exercises the loop.
"""

from time import sleep


def pump(read, emit_status, log, delay=0.01):
    """Call read() forever, pacing by `delay`, until the connection
    ends. EOF is the clean end (the session dropped us — reconnect
    guidance); any other exception is logged in full and announced the
    same way, so a half-dead window never claims Connected."""
    while True:
        try:
            read()
        except EOFError:
            emit_status("Disconnected — File → Reconnect")
            return
        except Exception:
            log.exception("reader thread crashed")
            emit_status(
                "Connection handler crashed — File → Reconnect "
                "(details in the debug log under ~/.revenant/logs/)"
            )
            return
        sleep(delay)
