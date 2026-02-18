.. image:: https://raw.githubusercontent.com/dbfixtures/mirakuru/master/logo.png
    :height: 100px

mirakuru
========

Mirakuru is a process orchestration tool designed for functional and integration tests.

When your application or tests rely on external processes (like databases, APIs, or other services),
ensuring these processes are started and ready *before* your main code executes can be challenging.
**Mirakuru** solves this by orchestrating the startup of these processes and waiting until they
are fully operational (e.g., accepting connections, producing specific output) before allowing
your program or tests to continue.


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

Installation
------------

Install mirakuru using pip:

.. code-block:: bash

    pip install mirakuru

Quick Start
-----------

Here's a simple example showing how mirakuru ensures a Redis server is ready before your code runs:

.. code-block:: python

    from mirakuru import TCPExecutor

    # Start Redis server and wait until it accepts connections on port 6379
    redis_executor = TCPExecutor('redis-server', host='localhost', port=6379)
    redis_executor.start()

    # Redis is now running and ready to accept connections
    # ... your code that uses Redis here ...

    # Clean up - stop the Redis server
    redis_executor.stop()

The key benefit: ``start()`` blocks until Redis is actually ready, so you never try to connect too early.



Usage
-----

In projects that rely on multiple processes, there might be a need to guard code
with tests that verify interprocess communication. You need to set up all the
required databases, auxiliary and application services to verify their cooperation.
Synchronizing (or orchestrating) test procedures with tested processes can be challenging.

If so, then **mirakuru** is what you need.

``Mirakuru`` starts your process and waits for a clear indication that it's running.
The library provides seven executors to fit different cases:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Executor
     - Use When
   * - **SimpleExecutor**
     - You just need to start/stop a process without waiting for readiness. Base class for all other executors.
   * - **Executor**
     - Base class for executors that verify process startup.
   * - **OutputExecutor**
     - Your process prints a specific message when ready (e.g., "Server started on port 8080")
   * - **TCPExecutor**
     - Your process opens a TCP port when ready (e.g., Redis, PostgreSQL, Memcached)
   * - **UnixSocketExecutor**
     - Your process opens a Unix socket when ready (e.g., Docker daemon, some databases)
   * - **HTTPExecutor**
     - Your process serves HTTP requests when ready (e.g., web servers, REST APIs)
   * - **PidExecutor**
     - Your process creates a .pid file when ready (e.g., traditional Unix daemons)

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

OutputExecutor starts a process and monitors its output for a specific text marker
(banner). The process is not reported as started until this marker appears in the output.

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

TCPExecutor should be used to start processes that communicate over TCP connections.
This executor tries to connect to the process on the specified host and port to check
if it started accepting connections. Once it successfully connects, the process is
reported as started and control returns to your code.

.. code-block:: python

    from mirakuru import TCPExecutor

    process = TCPExecutor('my_special_process', host='localhost', port=1234)
    process.start()

    # Here you can do your stuff, e.g. communicate with the started process

    process.stop()

HTTPExecutor
++++++++++++

HTTPExecutor is designed for starting web applications and HTTP services.
In addition to the command, you need to pass a URL that will be used to check
if the service is ready. By default, it makes a HEAD request to this URL.
Once the request succeeds, the executor reports the process as started and
control returns to your code.

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
    from http.client import HTTPConnection, OK


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

Limited native Windows support is available.

- Supported: SimpleExecutor, Executor, TCPExecutor, HTTPExecutor, PidExecutor.
- Not supported on Windows: UnixSocketExecutor (UNIX domain sockets).
- Notes: process termination semantics differ; on Windows we use terminate() instead of POSIX signals, and output polling falls back to select.select.

We welcome contributions to improve Windows support.

See:

* `#392 <https://github.com/dbfixtures/mirakuru/issues/392>`_
* `#336 <https://github.com/dbfixtures/mirakuru/issues/336>`_

Also, with the introduction of `WSL <https://docs.microsoft.com/en-us/windows/wsl/install-win10>`_
the need for raw Windows support might not be that urgent... If you've got any thoughts or are willing to contribute,
please start with the issues listed above.
