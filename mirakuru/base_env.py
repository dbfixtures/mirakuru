# Copyright (C) 2016 by Clearcode <http://clearcode.cc>
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
"""Module contains functions used for finding process descendants."""

import errno
import logging
import re
import subprocess

try:
    import psutil
except ImportError:
    psutil = None


LOG = logging.getLogger(__name__)


PS_XE_PID_MATCH = re.compile(r"^.*?(\d+).+$")
"""_sre.SRE_Pattern matching PIDs in result from `$ ps xe -o pid,cmd`."""


def processes_with_env_psutil(env_name: str, env_value: str) -> set[int]:
    """Find PIDs of processes having environment variable matching given one.

    Internally it uses `psutil` library.

    :param str env_name: name of environment variable to be found
    :param str env_value: environment variable value prefix
    :return: process identifiers (PIDs) of processes that have certain
             environment variable equal certain value
    :rtype: set
    """
    pids = set()

    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=["pid", "environ"])
        except (psutil.NoSuchProcess, IOError):
            # can't do much if psutil is not able to get this process details
            pass
        else:
            penv = pinfo.get("environ")
            if penv and env_value in penv.get(env_name, ""):
                pids.add(pinfo["pid"])

    return pids


def processes_with_env_ps(env_name: str, env_value: str) -> set[int]:
    """Find PIDs of processes having environment variable matching given one.

    It uses `$ ps xe -o pid,cmd` command so it works only on systems
    having such command available (Linux, MacOS). If not available function
    will just LOG error.

    :param str env_name: name of environment variable to be found
    :param str env_value: environment variable value prefix
    :return: process identifiers (PIDs) of processes that have certain
             environment variable equal certain value
    :rtype: set
    """
    pids: set[int] = set()
    ps_xe: list[bytes] = []
    try:
        cmd = "ps", "xe", "-o", "pid,cmd"
        ps_xe = subprocess.check_output(cmd).splitlines()
    except OSError as err:
        if err.errno == errno.ENOENT:
            LOG.error(
                "`$ ps xe -o pid,cmd` command was called but it is not "
                "available on this operating system. Mirakuru will not "
                "be able to list the process tree and find if there are "
                "any leftovers of the Executor."
            )
            return pids
    except subprocess.CalledProcessError:
        LOG.error("`$ ps xe -o pid,cmd` command exited with non-zero code.")

    env = f"{env_name}={env_value}"

    for line in ps_xe:
        sline = str(line)
        if env in sline:
            match = PS_XE_PID_MATCH.match(sline)
            # This always matches: all lines other than the header (not
            # containing our environment variable) have a PID required by the
            # reggex. Still check it for mypy.
            if match:
                pids.add(int(match.group(1)))
    return pids


if psutil:
    processes_with_env = processes_with_env_psutil
else:
    # In case psutil can't be imported (on pypy3) we try to use '$ ps xe'
    processes_with_env = processes_with_env_ps
