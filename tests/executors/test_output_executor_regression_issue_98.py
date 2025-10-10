# mypy: no-strict-optional
"""Regression test for mirakuru issue #98.

The problem: OutputExecutor hangs when there is too much output
produced before the expected banner appears.

This test intentionally generates a large amount of stdout noise before
printing the banner. On a correct implementation, OutputExecutor should
handle the stream and detect the banner within the timeout, starting the
process successfully. Due to the bug, this currently times out/hangs,
so we mark the test as xfail until the bug is fixed.

See: https://github.com/dbfixtures/mirakuru/issues/98
"""

import subprocess

from mirakuru import OutputExecutor, TimeoutExpired


def test_output_executor_handles_large_output_before_banner() -> None:
    """OutputExecutor should not hang even with large pre-banner output.

    The command prints many large lines to stdout, then finally prints the
    banner and sleeps, keeping the process alive. If OutputExecutor properly
    drains stdout, it should detect the banner and start within the timeout.
    """
    # Generate ~4-5 MB of output quickly, then print the banner and sleep.
    # Use only POSIX shell + bash built-ins to keep environment-simple.
    long_line = "x" * 80
    # The brace expansion {1..60000} relies on bash; we explicitly use bash -c.
    command = (
        "bash -c '"
        f"for i in {{1..60000}}; do echo {long_line!s}; done; "
        "echo BANNER_READY; sleep 100'"
    )

    # Use a reasonably generous timeout to allow draining and detection.
    executor = OutputExecutor(
        command,
        banner="BANNER_READY",
        timeout=15,
        stdin=None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        with executor:
            assert executor.running() is True
    except TimeoutExpired:
        assert False, f"OutputExecutor should not hang. {executor.output()}"
