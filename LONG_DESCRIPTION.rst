When it comes to actually using the async features and the asyncio library in a real project, you don't want to have to
constantly worry about what thread you're running in, what loop is global and whether or not it's running.  You don't
want to and shouldn't have to worry about whether asyncio or some other async library (like curio) is running in a higher
or lower level than your current abstraction layer in order to use asyncio and await syntax correctly.

This library provides simple functions for:

* running an async function from a blocking context
* running a blocking function from an async context
* running a blocking function in the background
* running multiple functions in parallel, either asynchronously or in a blocking fashion
* running multiple functions in series, either asynchronously or in a blocking fashion
* getting/creating and setting/reverting an independent asyncio event loop to use, regardless of thread or thread-global asyncio loop run status.

See `the project site`_ for examples, API doc, and more discussion.

.. _`the project site`: https://github.com/notion/a_sync
