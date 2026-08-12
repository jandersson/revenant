import os
import tempfile


def pytest_configure(config):
    # Keep test logging out of the real ~/.revenant/logs archive.
    os.environ["REVENANT_LOG_DIR"] = tempfile.mkdtemp(prefix="revenant-test-logs-")
    # Keep tests away from the real saved login names in ~/.revenant.
    os.environ["REVENANT_LOGIN_DEFAULTS"] = os.path.join(
        tempfile.mkdtemp(prefix="revenant-test-config-"), "login.json"
    )
