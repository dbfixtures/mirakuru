"""Package of tests for mirakuru.

Tests are written using py.test framework which dictates patterns that should
be followed in test cases.
"""

import sys
from os import path
from subprocess import check_output

from mirakuru.compat import IS_WINDOWS

TEST_PATH = path.abspath(path.dirname(__file__))

TEST_SERVER_PATH = path.join(TEST_PATH, "server_for_tests.py")
TEST_SOCKET_SERVER_PATH = path.join(TEST_PATH, "unixsocketserver_for_tests.py")
SAMPLE_DAEMON_PATH = path.join(TEST_PATH, "sample_daemon.py")

HTTP_SERVER_CMD = f"{sys.executable} -m http.server"


def list_processes() -> str:
    """Return output of systems `ps aux -w` call."""
    if IS_WINDOWS:
        powershell_command = (
            "Get-CimInstance -Class Win32_Process | Select-Object -ExpandProperty CommandLine"
        )
        return check_output(
            ["powershell.exe", "-Command", powershell_command],
            shell=True,
            text=True,
            errors="ignore",
        )
    return check_output(("ps", "aux", "-w")).decode()
