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

"""Mirakuru main module."""

import logging

from mirakuru.base import Executor, SimpleExecutor
from mirakuru.exceptions import (
    AlreadyRunning,
    ExecutorError,
    ProcessExitedWithError,
    TimeoutExpired,
)
from mirakuru.http import HTTPExecutor
from mirakuru.output import OutputExecutor
from mirakuru.pid import PidExecutor
from mirakuru.tcp import TCPExecutor

__version__ = "2.6.1"

__all__ = (
    "Executor",
    "SimpleExecutor",
    "OutputExecutor",
    "TCPExecutor",
    "HTTPExecutor",
    "PidExecutor",
    "ExecutorError",
    "TimeoutExpired",
    "AlreadyRunning",
    "ProcessExitedWithError",
)


# Set default logging handler to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())
