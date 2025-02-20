.. image:: https://raw.githubusercontent.com/dbfixtures/mirakuru/master/logo.png
    :height: 100px

mirakuru
========

Mirakuru is a process orchestration tool designed for functional and integration tests.

Maybe you want to be able to start a database before you start your program
or maybe you just need to set additional services up for your tests.
This is where you should consider using **mirakuru** to add superpowers to your program or tests.


.. image:: https://img.shields.io/pypi/v/mirakuru.svg
    :target: https://pypi.python.org/pypi/mirakuru/
    :alt: Latest PyPI version

.. image:: https://img.shields.io/pypi/wheel/mirakuru.svg
    :target: https://pypi.python.org/pypi/mirakuru/
    :alt: Wheel Status

.. image:: https://img.shields.io/pypi/pyversions/mirakuru.svg
    :target: https://pypi.python.org/pypi/mirakuru/
    :alt: Supported Python Versions

.. image:: https://img.shields.io/pypi/l/mirakuru.svg
    :target: https://pypi.python.org/pypi/mirakuru/
    :alt: License


Usage
-----

In a project that relies on multiple processes there might be a need to guard code
with tests that verify interprocess communication. So one needs to set up all of
required databases, auxiliary and application services to verify their cooperation.
Synchronising (or orchestrating) test procedure with tested processes might be a hell.

If so, then **mirakuru** is what you need.

``Mirakuru`` starts your process and waits for the clear indication that it's running.
Library provides seven executors to fit different cases:

* **SimpleExecutor** - starts a process and does not wait for anything.
  It is useful to stop or kill a process and its subprocesses.
  Base class for all the rest of executors.
* **Executor** - base class for executors verifying if a process has started.
* **OutputExecutor** - waits for a specified output to be printed by a process.
* **TCPExecutor** - waits for the ability to connect through TCP with a process.
* **UnixSocketExecutor** - waits for the ability to connect through Unix socket
  with a process
* **HTTPExecutor** - waits for a successful HEAD request (and TCP before).
* **PidExecutor** - waits for a specified .pid file to exist.

SimpleExecutor
++++++++++++++

The simplest executor implementation.
It simply starts the process passed to constructor, and reports it as running.

.. code-block:: python

    from mirakuru import SimpleExecutor

    process = SimpleExecutor('my_special_process')
    process.start()

    # Here you can do your stuff, e.g. communicate with the started process

    process.stop()

OutputExecutor
++++++++++++++

OutputExecutor is the executor that starts the process,
but does not report it as started, unless it receives specified marker/banner in
process output.

.. code-block:: python

    from mirakuru import OutputExecutor

    process = OutputExecutor('my_special_process', banner='processed!')
    process.start()

    # Here you can do your stuff, e.g. communicate with the started process

    process.stop()

What happens during start here, is that the executor constantly checks output
produced by started process, and looks for the banner part occurring within the
output.
Once the output is identified, as in example `processed!` is found in output.
It is considered as started, and executor releases your script from wait to work.


TCPExecutor
+++++++++++

Is the executor that should be used to start
processes that are using TCP connection. This executor tries to connect with
the process on given host:port to see if it started accepting connections. Once it
does, it reports the process as started and a code returns to normal execution.

.. code-block:: python

    from mirakuru import TCPExecutor

    process = TCPExecutor('my_special_process', host='localhost', port=1234)
    process.start()

    # Here you can do your stuff, e.g. communicate with the started process

    process.stop()

HTTPExecutor
++++++++++++

Is executor that will be used to start web applications for example.
To start it, you apart from command, you need to pass a URL.
This URL will be used to make a (by default) HEAD request. Once successful,
the executor will be considered started, and a code will return to normal execution.

.. code-block:: python

    from mirakuru import HTTPExecutor

    process = HTTPExecutor('my_special_process', url='http://localhost:6543/status')
    process.start()

    # Here you can do your stuff, e.g. communicate with the started process

    process.stop()

This executor, however, apart from HEAD request, also inherits TCPExecutor,
so it'll try to connect to process over TCP first, to determine,
if it can try to make a HEAD request already.

By default HTTPExecutor waits until its subprocess responds with 2XX HTTP status code.
If you consider other codes as valid you need to specify them in 'status' argument.

.. code-block:: python

    from mirakuru import HTTPExecutor

    process = HTTPExecutor('my_special_process', url='http://localhost:6543/status', status='(200|404)')
    process.start()

The "status" argument can be a single code integer like 200, 404, 500 or a regular expression string -
'^(2|4)00$', '2\d\d', '\d{3}', etc.

There's also a possibility to change the request method used to perform request to the server.
By default it's HEAD, but GET, POST or other are also possible.

.. code-block:: python

    from mirakuru import HTTPExecutor

    process = HTTPExecutor('my_special_process', url='http://localhost:6543/status', status='(200|404)', method='GET')
    process.start()


PidExecutor
+++++++++++

Is an executor that starts the given
process, and then waits for a given file to be found before it gives back control.
An example use for this class is writing integration tests for processes that
notify their running by creating a .pid file.

.. code-block:: python

    from mirakuru import PidExecutor

    process = PidExecutor('my_special_process', filename='/var/msp/my_special_process.pid')
    process.start()

    # Here you can do your stuff, e.g. communicate with the started process

    process.stop()


.. code-block:: python

    from mirakuru import HTTPExecutor
    from httplib import HTTPConnection, OK


    def test_it_works():
        # The ``./http_server`` here launches some HTTP server on the 6543 port,
        # but naturally it is not immediate and takes a non-deterministic time:
        executor = HTTPExecutor("./http_server", url="http://127.0.0.1:6543/")

        # Start the server and wait for it to run (blocking):
        executor.start()
        # Here the server should be running!
        conn = HTTPConnection("127.0.0.1", 6543)
        conn.request("GET", "/")
        assert conn.getresponse().status is OK
        executor.stop()


A command by which executor spawns a process can be defined by either string or list.

.. code-block:: python

    # command as string
    TCPExecutor('python -m smtpd -n -c DebuggingServer localhost:1025', host='localhost', port=1025)
    # command as list
    TCPExecutor(
        ['python', '-m', 'smtpd', '-n', '-c', 'DebuggingServer', 'localhost:1025'],
        host='localhost', port=1025
    )

Use as a Context manager
------------------------

Starting
++++++++

Mirakuru executors can also work as a context managers.

.. code-block:: python

    from mirakuru import HTTPExecutor

    with HTTPExecutor('my_special_process', url='http://localhost:6543/status') as process:

        # Here you can do your stuff, e.g. communicate with the started process
        assert process.running() is True

    assert process.running() is False

Defined process starts upon entering context, and exit upon exiting it.

Stopping
++++++++

Mirakuru also allows to stop process for given context.
To do this, simply use built-in stopped context manager.

.. code-block:: python

    from mirakuru import HTTPExecutor

    process = HTTPExecutor('my_special_process', url='http://localhost:6543/status').start()

    # Here you can do your stuff, e.g. communicate with the started process

    with process.stopped():

        # Here you will not be able to communicate with the process as it is killed here
        assert process.running() is False

    assert process.running() is True

Defined process stops upon entering context, and starts upon exiting it.


Methods chaining
++++++++++++++++

Mirakuru encourages methods chaining so you can inline some operations, e.g.:

.. code-block:: python

    from mirakuru import SimpleExecutor

    command_stdout = SimpleExecutor('my_special_process').start().stop().output

Contributing and reporting bugs
-------------------------------

Source code is available at: `dbfixtures/mirakuru <https://github.com/dbfixtures/mirakuru>`_.
Issue tracker is located at `GitHub Issues <https://github.com/dbfixtures/mirakuru/issues>`_.
Projects `PyPI page <https://pypi.python.org/pypi/mirakuru>`_.

Windows support
---------------

Frankly, there's none, Python's support differs a bit in required places
and the team has no experience in developing for Windows.
However we'd welcome contributions that will allow the windows support.

See:

* `#392 <https://github.com/dbfixtures/mirakuru/issues/392>`_
* `#336 <https://github.com/dbfixtures/mirakuru/issues/336>`_

Also, With the introduction of `WSL <https://docs.microsoft.com/en-us/windows/wsl/install-win10>`_
the need for raw Windows support might not be that urgant... If you've got any thoughts or are willing to contribute,
please start with the issues listed above.


Release
=======

Install pipenv and --dev dependencies first, Then run:

.. code-block::

    pipenv run tbump [NEW_VERSION]
