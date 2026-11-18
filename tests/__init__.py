"""Package of tests for mirakuru.

Tests are written using py.test framework which dictates patterns that should
be followed in test cases.
"""

import sys
from os import path

import psutil
import pytest

WINDOWS = sys.platform == "win32"

TEST_PATH = path.abspath(path.dirname(__file__))

TEST_SERVER_PATH = path.join(TEST_PATH, "server_for_tests.py")
TEST_SOCKET_SERVER_PATH = path.join(TEST_PATH, "unixsocketserver_for_tests.py")
SAMPLE_DAEMON_PATH = path.join(TEST_PATH, "sample_daemon.py")

HTTP_SERVER_CMD = f"{sys.executable} -m http.server"

SLEEP_300 = [sys.executable, "-c", "import time; time.sleep(300)"]
"""Command that sleeps for 300 seconds, as a list of arguments."""
SLEEP_300_LINE = f'"{sys.executable}" -c "import time; time.sleep(300)"'
"""Command that sleeps for 300 seconds, as one line both POSIX and Windows split alike."""


def skip_on_windows(issue: int) -> pytest.MarkDecorator:
    """Skip a test on Windows until the issue that ports it is done."""
    return pytest.mark.skipif(
        WINDOWS,
        reason=f"Not run on Windows yet, see https://github.com/dbfixtures/mirakuru/issues/{issue}.",
    )


needs_posix_daemon = pytest.mark.skipif(
    WINDOWS, reason="The sample daemon uses python-daemon, which runs on POSIX only."
)


def signalled_exit_code(sig: int) -> int:
    """Return the exit code of a process that the executor ended with the signal."""
    return sig if WINDOWS else -sig


def running_command_lines() -> str:
    """Return the command lines of all running processes, one per line."""
    return "\n".join(
        " ".join(process.info["cmdline"] or ()) for process in psutil.process_iter(["cmdline"])
    )
