"""A module exploring some python asyncio interactions."""


# [ Imports ]
# [ -Python ]
import asyncio
import functools
import contextlib
from typing import Generator, Callable, Any, List, Union
from concurrent import futures
import sys
import concurrent.futures
import select
import termios
# [ -Project ]
from . import helpers


# [ Types ]
# convert AnyCallable to just Callable when https://github.com/python/mypy/issues/1484 is resolved
AnyCallable = Union[Callable, functools.partial]


# [ API Functions ]
@contextlib.contextmanager
def idle_event_loop() -> Generator:
    """
    An idle event loop context manager.

    Leaves the current event loop in place if it's not running.
    Creates and sets a new event loop as the default if the current default IS running.
    Restores the original event loop on exit.

    Args:
        None

    Returns:
        idle_event_loop_manager - a context manager which yields an idle event loop
          for you to run async functions in.
    """
    original_loop = helpers.get_or_create_event_loop()
    try:
        if original_loop.is_running():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            loop = original_loop
        yield loop
    finally:
        asyncio.set_event_loop(original_loop)


def to_async(blocking_func: AnyCallable) -> AnyCallable:
    """
    Convert a blocking function to an async function.

    Args:
        blocking_func - a blocking function

    Returns:
        async_func - an awaitable function

    If the argument is already a coroutine function, it is returned unchanged.

    If the argument is a partial which wraps a coroutine function, it is returned
    unchanged.

    The blocking function is made into an awaitable by wrapping its call inside
    an awaitable function.

    On the assumption that a blocking function is long-running, and that an
    async caller wants to run other things concurrently, the blocking function
    is called from the running loop's thread/process executor, which means
    it runs in a thread.  This allows concurrent running, but introduces possible
    thread-safety issues, which the caller should be aware of.

    XXX - what if the loop isn't running?  We could be in someone else's loop
    space, like the curio kernel.  The 'run_in_executor' function returns a
    coroutine, so it shouldn't matter.

    XXX - possible new function - 'to_concurrent', which does the thread. Update
    this to 'to_awaitable', which just wraps in an awaitable.

    XXX - or, 'to_awaitable' for awaitable wrapping, 'to_concurrent' for thread,
    and 'to_parallel' for multiprocess?  Too much?  Wait for a need?  Want to not
    break code if we add these later, so the current version should probably be
    renamed to 'to_concurrent'.

    Required tests:
        * convert blocking to async
        * keep async as same
        * run something concurrently with a long-running blocking function
        * convert a blocking partial
        * keep an async partial the same
        * validate that it doesn't matter if the loop is running.
    """
    if asyncio.iscoroutinefunction(getattr(blocking_func, 'func', blocking_func)):
        # caller messed up - this is already async
        async_func = blocking_func
    else:
        async def async_func(*args, **kwargs) -> Any:
            """Wrapper for a blocking function."""
            # remove ignore comment when https://github.com/python/mypy/issues/1484 is resolved
            partial = functools.partial(blocking_func, *args, **kwargs)  # type: ignore
            loop = asyncio.get_event_loop()
            # lambda is to get around AbstractEventLoop typing not accepting partials
            # remove lambda when https://github.com/python/mypy/issues/1484 is resolved
            return await loop.run_in_executor(helpers.get_or_create_executor(), lambda: partial())
    return async_func


def to_blocking(async_func: AnyCallable) -> AnyCallable:
    """
    Convert an async function to a blocking function.

    Args:
        async_func - an async function

    Returns:
        blocking_func - a blocking function

    If the argument is already a blocking function, it is returned unchanged.

    If the argument is a partial for an awaitable, it is converted.

    The awaitable function is made blocking by wrapping its call in a blocking
    function, which gets/creates an idle asyncio event loop and runs the
    awaitable in it until it is complete.

    XXX - probably a lighter-weight way to do this - like handling the coroutine
    directly.

    Required tests:
        * convert async to blocking
        * keep blocking the same
        * keep blocking partial the same
        * convert async partial
    """
    if not asyncio.iscoroutinefunction(getattr(async_func, 'func', async_func)):
        # caller messed up - this is already blocking
        blocking = async_func
    else:
        def blocking(*args, **kwargs) -> Any:
            """Wrapper for an async function."""
            with idle_event_loop() as loop:
                return loop.run_until_complete(async_func(*args, **kwargs))
    return blocking


# No async background task here because that depends on knowing the environment
# of the caller, as far as async context goes, and you can't.  For example,
# if the caller is being executed via the curio kernel, and we add a task to the
# current asyncio event loop, that task will never complete.


def queue_background_thread(func: Callable, *args, **kwargs) -> futures.Future:
    """
    Queue the function to be run in a thread, but don't wait for it.

    Args:
        func - the function to run
        args - the args to call the function with
        kwargs - the kwargs to call the function with

    Returns:
        future - a concurrent.futures Future for the function.

    If the thread pool executor is processing on all threads, it will queue this
    task.  There's currently no way to check it or expand it's pool, hence the
    name of the function and the summary have been updated to reflect that..

    XXX - add a mechanism to expand threads if there's compute power available
    on the process.

    XXX - add a function which errors if its function is queued.

    XXX - add a function to let the caller check if their function will be queued.

    Required tests:
        * queue a task
        * queue enough tasks to fill the queue & more.
    """
    return helpers.get_or_create_executor().submit(to_blocking(func), *args, **kwargs)


async def run(func: AnyCallable, *args, **kwargs) -> Any:
    """
    Run a function in an async manner, whether the function is async or blocking.

    Args:
        func - the function (async or blocking) to run
        args - the args to run the function with
        kwargs - the kwargs to run the function with

    Returns:
        coro - a coroutine object to await

    Coro Returns:
        result - whatever the function returns when it's done.

    Required tests:
        * run an async func
        * run a blocking func
    """
    return await to_async(func)(*args, **kwargs)


def block(func: AnyCallable, *args, **kwargs) -> Any:
    """
    Run a function in a blocking manner, whether the function is async or blocking.

    Args:
        func - the function (async or blocking) to run
        args - the args to run the function with
        kwargs - the kwargs to run the function with

    Returns:
        result - whatever the function returns when it's done.

    Required tests:
        * run an async func
        * run a blocking func
    """
    return to_blocking(func)(*args, **kwargs)


async def a_input(prompt: str) -> str:
    """Async input prompt."""
    readable = []  # type: List[int]
    print(prompt, end='')
    sys.stdout.flush()
    while not readable:
        readable, writeable, executable = select.select([sys.stdin], [], [], 0)
        try:
            await asyncio.sleep(0.1)
        except concurrent.futures.CancelledError:
            print("input cancelled...")
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
            raise
    return sys.stdin.readline().rstrip()


# [ Classes ]
class Parallel:
    """
    Parallel runner.

    Provides a way to:
        * schedule a heterogeneous mix of blocking and awaitable functions
        * run those functions all in parallel
        * to run them in either a blocking or an asynchronous manner
        * to receive the results in the order in which the functions were passed in.
        * to run them as many times as desired (similarly to a partial function)

    It's analogous to a partial function, but instead of supplying args for a function and getting
    a function back, you supply args for as many functions as you like, and get an function back with which
    you can run those functions and arguments in parallel, either synchronously or asynchronously.
    """

    def __init__(self) -> None:
        """
        Init state.

        Sets up an initial (empty) set of functions to run.

        Args:
            None

        Returns:
            Technically, none.

        Required tests:
            None
        """
        self._funcs = []  # type: List[functools.partial]

    def schedule(self, func, *args, **kwargs) -> 'Parallel':
        """
        Schedule a function to be run.

        Args:
            func - the function to schedule
            *args - the args to call the function with
            **kwargs - the kwargs to call the function with

        Returns:
            parallel - the parallel object, to allow chaining.

        Required tests:
            * validate the return
        """
        self._funcs.append(functools.partial(func, *args, **kwargs))
        return self

    async def run(self) -> List[Any]:
        """
        Run the scheduled functions in parallel, asynchronously.

        Args:
            None

        Returns:
            list - a list of the results from the scheduled functions, in the
              order they were scheduled in.

        Note that while this function is awaitable, the scheduled functions are
        run in an asyncio loop in a separate thread.  We cannot create asyncio
        tasks and run them in the current thread because that depends on knowing the environment
        of the caller, as far as async context goes, and you can't.  For example,
        if the caller is being executed via the curio kernel, and we add a task to the
        current asyncio event loop, that task will never complete.

        Our only alternative is to run in an independent loop that we control.  The
        only way to actually make that concurrent instead of blocking in this function
        is to run that loop in its own thread.

        XXX - rename function to better reflect that it runs in a thread?
        XXX - think about the thread queueing that to_async performs right now...
          if other functions are created to do threading/multi-proc/throwing errors,
          we want to use the right one here.

        Required tests:
            * run all async in parallel
            * run all blocking in parallel
            * run a mix
            * run things in parallel when the thread pool is already full
        """
        return await to_async(self.block)()

    def block(self) -> List[Any]:
        """
        Run the scheduled functions in parallel, blocking.

        Args:
            None

        Returns:
            list - a list of the results from the scheduled functions, in the
              order they were scheduled in.

        Required tests:
            * run all async in parallel
            * run all blocking in parallel
            * run a mix
        """
        with idle_event_loop() as loop:
            tasks = [loop.create_task(to_async(f)()) for f in self._funcs]
            # remove ignore comment when https://github.com/python/typeshed/issues/453 is resolved.
            gathered = asyncio.gather(*tasks)  # type: ignore
            return loop.run_until_complete(gathered)


class Serial:
    """
    Serial runner.

    Provides a way to:
        * schedule a heterogeneous mix of blocking and awaitable functions
        * run those functions all in series
        * to run them in either a blocking or an asynchronous manner
        * to receive the results in the order in which the functions were passed in.
        * to run them as many times as desired (similarly to a partial function)

    It's analogous to a partial function, but instead of supplying args for a function and getting
    a function back, you supply args for as many functions as you like, and get an function back with which
    you can run those functions and arguments in series, either synchronously or asynchronously.
    """

    def __init__(self) -> None:
        """
        Init state.

        Sets up an initial (empty) set of functions to run.

        Args:
            None

        Returns:
            Technically, none.

        Required tests:
            None
        """
        self._funcs = []  # type: List[functools.partial]

    def schedule(self, func: Callable, *args, **kwargs) -> 'Serial':
        """
        Schedule a function to be run.

        Args:
            func - the function to schedule
            *args - the args to call the function with
            **kwargs - the kwargs to call the function with

        Returns:
            series - the series object, to allow chaining.

        Required tests:
            * validate the return
        """
        self._funcs.append(functools.partial(func, *args, **kwargs))
        return self

    async def run(self) -> List[Any]:
        """
        Run the scheduled functions in series, asynchronously.

        Args:
            None

        Returns:
            list - a list of the results from the scheduled functions, in the
              order they were scheduled in.

        Required tests:
            * run all async in series
            * run all blocking in series
            * run a mix
        """
        results = []
        for func in self._funcs:
            results.append(await run(func))
        return results

    def block(self) -> List[Any]:
        """
        Run the scheduled functions in series, blocking.

        Args:
            None

        Returns:
            list - a list of the results from the scheduled functions, in the
              order they were scheduled in.

        Required tests:
            * run all async in series
            * run all blocking in series
            * run a mix
        """
        results = []
        for func in self._funcs:
            results.append(block(func))
        return results
