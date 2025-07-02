CHANGELOG
=========

.. towncrier release notes start

2.6.1 (2025-07-02)
==================

Miscellaneus
------------

- Adjust links after repository transfer
- Adjust workflows for actions-reuse 3.0.0
- Fix rerunfailures configuration
- Run tests against oldest supported dependencies.
- Standardized license field in `pyproject.toml` to use SPDX identifier and avoid deprecation warnings from setuptools.
- Tests: pick free port instead of hardcoding to 3000


2.6.0 (2025-02-07)
==================

Features
--------

- SimpleExecutor now have an envvars property, that returns defined envvars with added os.envvars and mirakuru_uuid envvar.

  This will allow to re-use same envvars for starting process and any additional process runs in inheriting executors. (`#842 <https://github.com/dbfixtures/mirakuru/issues/842>`_)


Miscellaneus
------------

- `#810 <https://github.com/dbfixtures/mirakuru/issues/810>`_, `#841 <https://github.com/dbfixtures/mirakuru/issues/841>`_
- Add pytest-rerunfailures for flaky tests.
- Defer to pytest's tmp_path_factory instead of manual tmpdir setting/detection


2.5.3 (2024-10-11)
==================

Breaking changes
----------------

- Dropped support for Python 3.8 (As it reached EOL)


Features
--------

- Added support for Python 3.13


Miscellaneus
------------

- `#724 <https://github.com/dbfixtures/mirakuru/issues/724>`_, `#726 <https://github.com/dbfixtures/mirakuru/issues/726>`_, `#742 <https://github.com/dbfixtures/mirakuru/issues/742>`_
- * Extended line-lenght to 100 characters
  * updated test_forgotten_stop as on CI on
    Python 3.13 it lost one character out of the marker


2.5.2 (2023-10-17)
==================

Breaking changes
----------------

- Drop support for Python 3.7 (`#667 <https://github.com/dbfixtures/mirakuru/issues/667>`_)


Features
--------

- Support Python 3.12 (`#685 <https://github.com/dbfixtures/mirakuru/issues/685>`_)


Miscellaneus
------------

- `#639 <https://github.com/dbfixtures/mirakuru/issues/639>`_, `#653 <https://github.com/dbfixtures/mirakuru/issues/653>`_, `#655 <https://github.com/dbfixtures/mirakuru/issues/655>`_, `#664 <https://github.com/dbfixtures/mirakuru/issues/664>`_, `#686 <https://github.com/dbfixtures/mirakuru/issues/686>`_


2.5.1 (2023-02-27)
==================

Bugfixes
--------

- Include py.typed to the package published on pypi (`#633 <https://github.com/dbfixtures/mirakuru/issues/633>`_)


2.5.0 (2023-02-17)
==================

Features
--------

- Support Python 3.11 (`#617 <https://github.com/dbfixtures/mirakuru/issues/617>`_)


Miscellaneus
------------

- Reformatted code with black 23 (`#613 <https://github.com/dbfixtures/mirakuru/issues/613>`_)
- Introduce towncrier as changelog management too. (`#615 <https://github.com/dbfixtures/mirakuru/issues/615>`_)
- Moved Development dependency management to pipfile/pipenv (`#616 <https://github.com/dbfixtures/mirakuru/issues/616>`_)
- Move package definition into the pyproject.toml file (`#618 <https://github.com/dbfixtures/mirakuru/issues/618>`_)
- Use shared automerge flow and github app. (`#619 <https://github.com/dbfixtures/mirakuru/issues/619>`_)
- Use tbump to manage versioning (`#628 <https://github.com/dbfixtures/mirakuru/issues/628>`_)


2.4.2
=====

Misc
----

+ Added Python 3.10 to classifiers

2.4.1
=====

Misc
----

- Use strictier mypy checks

2.4.0
=====

Features
--------

- Replace `exp_sig` executor parameter with `expected_returncode`.
  Parameter description already assumed that, however handing it assumed full
  POSIX compatibility on the process side. Now the POSIX is only assumed if no
  `expected_returncode` is passed to the executor, and returncode is simply that,
  a returncode, nothing more

2.3.1
=====

Misc
----

- Moved CI to Github Actions
- Blackified codebase
- Compacted Documentation into readme (was pretty small anyway)

2.3.0
=====

- [enhancement] Ability to set up expected exit code for executor. In Java exit codes 1- 127 have
  special meaning, and the regular exit codes are offset by those of special meaning.

2.2.0
=====

- [enhancement] If process is being closed and the shutdown won't be clean (won't return exit code 0)
  mirakuru will now rise ProcessFinishedWithError exception with exit_code

2.1.2
=====

- [bugfix][macos] Fixed typing issue on macOS

2.1.1
=====

- [bug] Always close connection for HTTPExecutor after_start_check
- [enhancement] Log debug message if execption occured during
  HTTPExecutor start check
- [ehnancement] adjust typing handling in HTTPExecutor

2.1.0
=====

- [feature] Drop support for python 3.5. Rely on typing syntax and fstrings that
  is available since python 3.6 only
- [ehnancement] For output executor on MacOs fallback to `select.select` for OutputExecutor.
  Increases compatibility with MacOS where presence of `select.poll` depends
  on the compiler used.
- [enhancement] Apply shelx.quote on command parts if command is given as a list
  Should result in similar results when running such command with or without shell.

2.0.1
=====

- [repackage] - mark python 3.5 as required. Should disallow installing on python 2

2.0.0
=====

- [feature] Add UnixSocketExecutor for executors that communicate with Unix Sockets
- [feature] Mirakuru is now fully type hinted
- [feature] Drop support for python 2
- [feature] Allow for configuring process outputs to pipe to
- [feature] OutputExecutor can now check for banner in stderr
- [feature] HTTPEecutor now can check status on different method.
  Along with properly configured payload and headers.
- [feature] Ability to set custom env vars for orchestrated process
- [feature] Ability to set custom cwd path for orchestrated process
- [enhancement] psutil is no longer required on cygwin

1.1.0
=====

- [enhancement] Executor's timeout to be set for both executor's start and stop
- [enhancement] It's no longer possible to hang indefinitely on the start
  or stop. Timeout is set to 3600 seconds by default, with values possible
  between `0` and `sys.maxsize` with the latter still bit longer
  than `2924712086` centuries.

1.0.0
=====

- [enhancement] Do not fail if processes child throw EPERM error
  during clean up phase
- [enhancement] Run subprocesses in shell by default on Windows
- [ehnancement] Do not pass preexec_fn on windows

0.9.0
=====

- [enhancement] Fallback to kill through SIGTERM on Windows,
  since SIGKILL is not available
- [enhancement] detect cases where during stop process already exited,
  and simply clean up afterwards

0.8.3
=====

- [enhancement] when killing the process ignore OsError with errno `no such process` as the process have already died.
- [enhancement] small context manager code cleanup


0.8.2
=====

- [bugfix] atexit cleanup_subprocesses() function now reimports needed functions


0.8.1
=====

- [bugfix] Handle IOErrors from psutil (#112)
- [bugfix] Pass global vars to atexit cleanup_subprocesses function (#111)


0.8.0
=====

- [feature] Kill all running mirakuru subprocesses on python exit.
- [enhancement] Prefer psutil library (>=4.0.0) over calling 'ps xe' command to find leaked subprocesses.


0.7.0
=====

- [feature] HTTPExecutor enriched with the 'status' argument.
  It allows to define which HTTP status code(s) signify that a HTTP server is running.
- [feature] Changed executor methods to return itself to allow method chaining.
- [feature] Context Manager to return Executor instance, allows creating Executor instance on the fly.
- [style] Migrated `%` string formating to `format()`.
- [style] Explicitly numbered replacement fields in string.
- [docs] Added documentation for timeouts.

0.6.1
=====

- [refactoring] Moved source to src directory.
- [fix, feature] Python 3.5 fixes.
- [fix] Docstring changes for updated pep257.

0.6.0
=====

- [fix] Modify MANIFEST to prune tests folder.
- [feature] HTTPExecutor will now set the default 80 if not present in a URL.
- [feature] Detect subprocesses exiting erroneously while polling the checks and error early.
- [fix] Make test_forgotten_stop pass by preventing the shell from optimizing forking out.

0.5.0
=====

- [style] Corrected code to conform with W503, D210 and E402 linters errors as reported by pylama `6.3.1`.
- [feature] Introduced a hack that kills all subprocesses of executor process.
  It requires 'ps xe -ww' command being available in OS otherwise logs error.
- [refactoring] Classes name convention change.
  Executor class got renamed into SimpleExecutor and StartCheckExecutor class got renamed into Executor.

0.4.0
=====

- [feature] Ability to set up custom signal for stopping and killing processes managed by executors.
- [feature] Replaced explicit parameters with keywords for kwargs handled by basic Executor init method.
- [feature] Executor now accepts both list and string as a command.
- [fix] Even it's not recommended to import all but `from mirakuru import *` didn't worked. Now it's fixed.
- [tests] increased tests coverage.
  Even test cover 100% of code it doesn't mean they cover 100% of use cases!
- [code quality] Increased Pylint code evaluation.

0.3.0
=====

- [feature] Introduced PidExecutor that waits for specified file to be created.
- [feature] Provided PyPy compatibility.
- [fix] Closing all resources explicitly.

0.2.0
=====

- [fix] Kill all children processes of Executor started with shell=True.
- [feature] Executors are now context managers - to start executors for given context.
- [feature] Executor.stopped - context manager for stopping executors for given context.
- [feature] HTTPExecutor and TCPExecutor before .start() check whether port
  is already used by other processes and raise AlreadyRunning if detects it.
- [refactoring] Moved python version conditional imports into compat.py module.


0.1.4
=====

- [fix] Fixed an issue where setting shell to True would execute only part of the command.

0.1.3
=====

- [fix] Fixed an issue where OutputExecutor would hang, if started process stopped producing output.

0.1.2
=====

- [fix] Removed leftover sleep from TCPExecutor._wait_for_connection.

0.1.1
=====

- [fix] Fixed `MANIFEST.in`.
- Updated packaging options.

0.1.0
=====

- Exposed process attribute on Executor.
- Exposed port and host on TCPExecutor.
- Exposed URL on HTTPExecutor.
- Simplified package structure.
- Simplified executors operating API.
- Updated documentation.
- Added docblocks for every function.
- Applied license headers.
- Stripped orchestrators.
- Forked off from `summon_process`.
