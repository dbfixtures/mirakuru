"""Package of tests for mirakuru.

Tests are written using py.test framework which dictates patterns that should
be followed in test cases.
"""

import sys
from os import path
from subprocess import check_output

TEST_PATH = path.abspath(path.dirname(__file__))

TEST_SERVER_PATH = path.join(TEST_PATH, "server_for_tests.py")
TEST_SOCKET_SERVER_PATH = path.join(TEST_PATH, "unixsocketserver_for_tests.py")
SAMPLE_DAEMON_PATH = path.join(TEST_PATH, "sample_daemon.py")

HTTP_SERVER_CMD = f"{sys.executable} -m http.server"


def ps_aux() -> str:
    """Return output of systems `ps auxww` call."""
    return check_output(("ps", "auxww")).decode()
