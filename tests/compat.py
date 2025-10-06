"""Tests compat module."""

import signal

# Windows does not have SIGQUIT, fall back to SIGTERM.
SIGQUIT = getattr(signal, "SIGQUIT", signal.SIGTERM)
