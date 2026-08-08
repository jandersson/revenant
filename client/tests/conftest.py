import os
import tempfile


def pytest_configure(config):
    # Keep test logging out of the real ~/.revenant/logs archive.
    os.environ["REVENANT_LOG_DIR"] = tempfile.mkdtemp(prefix="revenant-test-logs-")
