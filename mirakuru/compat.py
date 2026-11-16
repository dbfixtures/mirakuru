# Copyright (C) 2014 by Clearcode <http://clearcode.cc>
# and associates (see AUTHORS).

# This file is part of mirakuru.

# mirakuru is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# mirakuru is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with mirakuru.  If not, see <http://www.gnu.org/licenses/>.
"""Mirakuru compatibility module."""

import shlex
import signal
import sys

# Windows does not have SIGKILL, fall back to SIGTERM.
SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    # Own library handles, so the argument types set here stay local.
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    _shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    _shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    _kernel32.LocalFree.restype = wintypes.HLOCAL

    def _split_windows_command_line(command: str) -> list[str]:
        """Split a command line with the Windows `CommandLineToArgvW` function."""
        # Given an empty command line, CommandLineToArgvW returns the path of
        # the current program instead of no arguments.
        if not command.strip():
            return []
        argument_count = ctypes.c_int()
        arguments = _shell32.CommandLineToArgvW(command, ctypes.byref(argument_count))
        if not arguments:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return [arguments[index] for index in range(argument_count.value)]
        finally:
            _kernel32.LocalFree(arguments)


def split_command_line(command: str) -> list[str]:
    """Split a command line into the arguments the started program reads.

    POSIX shell rules apply, except on Windows, where programs split their
    own command line by the rules `CommandLineToArgvW` implements.
    """
    if sys.platform == "win32":
        return _split_windows_command_line(command)
    else:
        return shlex.split(command)


__all__ = ("SIGKILL", "split_command_line")
