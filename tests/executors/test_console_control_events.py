# mypy: no-strict-optional
"""Tests that stop processes with Windows console control events."""

import signal
import sys
import time
from pathlib import Path

import pytest

from mirakuru import SimpleExecutor
from mirakuru.base import STATUS_CONTROL_C_EXIT

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Console control events exist on Windows only."
)


def wait_until_ready(ready_path: Path) -> None:
    """Wait for the started process to create the file, for up to 10 seconds."""
    deadline = time.time() + 10
    while not ready_path.exists():
        assert time.time() < deadline, "The process did not start."
        time.sleep(0.1)


@pytest.mark.skipif(
    sys.implementation.name == "pypy",
    reason="PyPy doesn't exit on a console control event it has no handler for.",
)
def test_stop__ctrl_break_event(tmp_path: Path) -> None:
    """Check that a process ended by a console control event stops without an error."""
    # Given
    ready_path = tmp_path / "ready"
    executor = SimpleExecutor(
        [
            sys.executable,
            "-c",
            f"import pathlib, time; pathlib.Path({str(ready_path)!r}).touch(); time.sleep(300)",
        ],
        timeout=10,
        stop_signal=signal.CTRL_BREAK_EVENT,  # type: ignore[attr-defined,unused-ignore]
    ).start()
    # An event that arrives while the process is still loading ends it with
    # STATUS_DLL_INIT_FAILED instead.
    wait_until_ready(ready_path)
    process = executor.process

    # When
    executor.stop()

    # Then
    assert executor.running() is False
    assert process.returncode == STATUS_CONTROL_C_EXIT


def test_stop__ctrl_break_event_lets_process_tree_shut_down(tmp_path: Path) -> None:
    """Check that the process and its descendants handle the event and exit on their own."""
    # Given
    ready_path = tmp_path / "ready"
    stopped_path = tmp_path / "stopped"
    child_code = (
        "import pathlib, signal, sys, time\n"
        "def stop(*_):\n"
        f"    pathlib.Path({str(stopped_path)!r}).touch()\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGBREAK, stop)\n"
        f"pathlib.Path({str(ready_path)!r}).touch()\n"
        "while True:\n"
        "    time.sleep(0.1)\n"
    )
    root_code = (
        "import signal, subprocess, sys, time\n"
        "def stop(*_):\n"
        "    child.wait()\n"
        "    sys.exit(0)\n"
        "signal.signal(signal.SIGBREAK, stop)\n"
        f"child = subprocess.Popen([sys.executable, '-c', {child_code!r}])\n"
        "while True:\n"
        "    time.sleep(0.1)\n"
    )
    executor = SimpleExecutor(
        [sys.executable, "-c", root_code],
        stop_signal=signal.CTRL_BREAK_EVENT,  # type: ignore[attr-defined,unused-ignore]
    ).start()
    wait_until_ready(ready_path)

    # When
    executor.stop()

    # Then
    assert stopped_path.exists()
