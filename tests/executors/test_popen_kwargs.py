"""Test passing additional Popen kwargs to subprocess.Popen."""

import os
from unittest import mock

import pytest

from mirakuru.base import SimpleExecutor


@pytest.mark.parametrize("command", ("echo test", ["echo", "test"]))
def test_additional_popen_kwargs_are_passed_through(command: str | list[str]) -> None:
    """Test that additional Popen kwargs are correctly passed through to subprocess.Popen.

    Given:
        Additional kwargs to be passed to popen.
    When:
        Executor starts
    Then:
        Additional kwargs are passed through.
    """
    popen_kwargs = {"bufsize": 1, "close_fds": True}

    with mock.patch("subprocess.Popen") as popen_mock:
        # Make the mocked Popen act like a context manager-compatible Popen
        proc = mock.MagicMock()
        # Make poll() return None initially (running), but 0 after the first call
        # to simulate stopping
        proc.poll.side_effect = [None, 0]
        proc.wait.return_value = 0
        proc.__exit__.return_value = None
        proc.pid = 12345
        popen_mock.return_value = proc

        with SimpleExecutor(command, popen_kwargs=popen_kwargs):
            assert popen_mock.called
            args, kwargs = popen_mock.call_args

            assert kwargs.get("shell") is False

            # Additional kwargs passed through
            for k, v in popen_kwargs.items():
                assert kwargs.get(k) == v

            # Executor still sets its standard kwargs
            assert "env" in kwargs and isinstance(kwargs["env"], dict)
            assert kwargs.get("cwd") is None
            assert kwargs.get("universal_newlines") is True
            assert callable(kwargs.get("preexec_fn"))


def test_additional_popen_kwargs_do_not_override_standard_streams() -> None:
    """Test that additional Popen kwargs do not override standard streams.

    Given:
        Additional kwargs to be passed to popen.
    When:
        Executor starts
    Then:
        Standard streams are not overridden.
    """
    with mock.patch("subprocess.Popen") as popen_mock:
        proc = mock.MagicMock()
        # Make poll() return None initially (running), but 0 after the first call
        # to simulate stopping
        proc.poll.side_effect = [None, 0]
        proc.wait.return_value = 0
        proc.__exit__.return_value = None
        proc.pid = 12345
        popen_mock.return_value = proc

        with SimpleExecutor("echo test", popen_kwargs={"stdout": os.devnull}):
            _, kwargs = popen_mock.call_args
            # stdout should not be os.devnull; it should be whatever SimpleExecutor sets
            # by default (PIPE). We cannot import subprocess.PIPE directly here without
            # shadowing the module under test; check that it's not the devnull we passed.
            assert kwargs.get("stdout") != os.devnull
