"""A module exploring some python asyncio interactions."""


# [ Imports ]
# [ -Python ]
import asyncio
import contextlib
import enum
import functools
import select
import sys
import termios
import threading
from concurrent import futures
from typing import Any, Callable, Generator, List, Optional, Union
# [ -Third Party ]
import utaw
# [ -Project ]
from . import helpers


# [ Types ]
# convert AnyCallable to just Callable when https://github.com/python/mypy/issues/1484 is resolved
# this is a type definition, which pylint doesn't recoginize
AnyCallable = Union[Callable, functools.partial]  # pylint: disable=invalid-name


# [ Flake8 ]
assert Optional


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
            # remove lambda & pylint disable when https://github.com/python/mypy/issues/1484 is resolved
            return await loop.run_in_executor(
                helpers.get_or_create_executor(), lambda: partial()  # pylint: disable=unnecessary-lambda
            )
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
    # remove the type-ignore statement as part of https://github.com/notion/a_sync/issues/34
    return helpers.get_or_create_executor().submit(to_blocking(func), *args, **kwargs)  # type: ignore


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
        readable, _, _ = select.select([sys.stdin], [], [], 0)
        try:
            await asyncio.sleep(0.1)
        except futures.CancelledError:
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
            gathered = asyncio.gather(*tasks)
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


class ThreadFuture(futures.Future):
    """
    Thread Future.

    Inherits from `concurrent.futures.Future`.

    Adds:  abandon(), is_abandoned()
    Implements:  None
    Overwrites:  None

    As with `concurrent.futures.Future`, this class should not be instantiated directly, but only
    by an executor or unit tests.

    Required Tests:
        Init:
            * When the future is created
            * Then it is not abandoned
        Abandon:
            * When the future is abandoned
            * Then it is abandoned
        Multiple Abandon:
            * Given the future is already abandoned
            * When it is abandoned again
            * Then it is still abandoned
    """

    def __init__(self) -> None:
        """
        Init the state.

        Args:  None
        Returns:  None
        Raises:  None
        Requred Tests:  None
        """
        super().__init__()
        self._is_abandoned = False

    def is_abandoned(self) -> bool:
        """
        Return abandonment state.

        Args:  None
        Returns:  A bool indicating whether or not the ThreadFuture has been abandoned.
        Raises:  None
        Required Tests:  None
        """
        return self._is_abandoned

    def abandon(self) -> None:
        """
        Abandon the future.

        There is an intended effect on the executor:  it should no longer maintain/monitor/update this future.

        There is no direct effect on the future.  A thread cannot be stopped, so any results or errors or
        side-effects of the future will still take place, including any registered callbacks.

        Args:  None
        Returns:  None
        Raises:  None
        Required Tests:  None
        """
        self._is_abandoned = True


def test_thread_future_init() -> None:
    """
    Test thread future init.

    When:  the future is created
    Then:  it is not abandoned
    """
    # When
    future = ThreadFuture()

    # Then
    utaw.assertFalse(future.is_abandoned())  # pylint: disable=no-member


def test_thread_future_abandon() -> None:
    """
    Test thread future abandon.

    When:  the future is abandoned
    Then:  the future is abandoned
    """
    # Given
    future = ThreadFuture()

    # When
    future.abandon()

    # Then
    utaw.assertTrue(future.is_abandoned())  # pylint: disable=no-member


def test_tf_multiple_abandon() -> None:
    """
    Test thread future multiple abandon.

    Given:  the future is abandoned
    When:   the future is abandoned again
    Then:  the future is abandoned
    """
    # Given
    future = ThreadFuture()
    future.abandon()

    # When
    future.abandon()

    # Then
    utaw.assertTrue(future.is_abandoned())  # pylint: disable=no-member


class ExitOption(enum.Enum):
    """Exit option."""

    ABANDON = enum.auto()  # type: ignore
    NO_WAIT = enum.auto()  # type: ignore
    WAIT = enum.auto()  # type: ignore


class ThreadExecutor(futures.Executor):
    """
    Thread Executor.

    Inherits from `concurrent.futures.Executor`

    Adds:
        abandon: Abandons all threads monitored by the executor and shuts down.

    Implements:  submit
    Overwrites:  __init__, __exit__, shutdown

    The `ThreadExecutor` is distinct from the `concurrent.futures.ThreadPoolExecutor` in the following ways:
        * A new thread is spawned for every submitted task, and there is no limit
        * All outstanding threads can be abandoned (see `abandon` docs for more info)
        * Context-manager exit behavior is to abandon all outstanding threads, by default
        * Context-manager exit behavior is customizable

    Required Tests:
        default exit:  abandons outstanding threads on exit from managed context
        abandoned futures:  abandoned futures are abandoned by the executor
        done futures:  done futures are abandoned by the executor
        monitor no threads:  when there are no threads, the monitor thread returns
        monitor single thread:  when there is a single thread, the monitor thread is running.
        monitor multiple threads:  when there are multiple threads, the monitor thread is running.
        single monitor:  With no monitor thread running, starting one starts one.
        multi-monitor:  With a monitor thread running, starting one leaves the running one and does not start another.
        submit function adds thread:  Submitting a function adds a thread to the monitor list.
        submit launches monitor:  Submitting a function starts the monitor thread.
        shutdown:  Submit after shutdown raises a RuntimeError
        repeat shutdown:  Repeating shutdown has no effect.
        abandon:  outstanding threads are abandoned, and the executor is shutdown with wait
        repeat abandon:  Repeating abandon has no effect.
    """

    # https://github.com/python/mypy/issues/2306
    def __init__(self, on_exit: ExitOption=ExitOption.ABANDON) -> None:
        """
        Init the state.

        Args:
            on_exit:  determines the behavior on exit when the executor is used as a context manager
                ExitOption.ABANDON:  this is the default.  All remaining threads are abandoned.
                ExitOption.NO_WAIT:   shuts down without waiting for remaining threads to complete.
                ExitOption.WAIT:     shuts down and waits for remaining threads to complete.  This is the
                    default behavior for a vanilla `futures.Executor`, but not for `ThreadExecutor`.

        Returns:  None
        Raises:  None
        Required Tests:  None
        """
        # shared state
        self._monitored_threads = {}  # type: dict
        self._monitor_thread = None  # type: Optional[threading.Thread]
        # lock for ^
        self._monitored_thread_lock = threading.RLock()
        # main thread state
        self._is_shutdown = False
        self._abandon = False
        self._on_exit = on_exit

    def _exit_function(self, on_exit: ExitOption) -> AnyCallable:
        """
        Get the function to run on exit from managed context.

        This is a core function meant to be called by the __exit__ context manager function.

        Args:
            on_exit:  the ExitOption to use to select the exit function.

        Returns:  the exit function to call.
        Raises:  None
        Required Tests:
            abandon on exit:  abandons outstanding threads on exit from managed context
            no wait on exit:  shuts down without waiting on exit from managed context
            wait on exit:  shuts down and waits on exit from managed context
        """
        return {  # type: ignore
            ExitOption.ABANDON: self.abandon,
            ExitOption.NO_WAIT: functools.partial(self.shutdown, wait=False),
            ExitOption.WAIT: functools.partial(self.shutdown, wait=True),
        }[on_exit]

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Exit the context manager.

        The default behavior of a `futures.Executor` is to shutdown and wait.  `ThreadExecutor`
        does whatever is specified in the `on_exit` parameter to `__init__`

        Args:
            exc_type, exc_val, exc_tb:  the exception data for any exception raised in the managed context, or None,
              if no exception was raised.

        Returns:
            a bool indicating whether or not the function handled the exception, if one was raised in the managed
            context.  If False, and there was an exception, the python runtime will raise the exception.
        Raises:  None
        Required Tests:  None
        """
        assert exc_type or exc_val or exc_tb or True  # Vulture
        self._exit_function(self._on_exit)()
        return False

    def _monitor(self) -> None:
        """
        Monitor and maintain the internal thread/future map.

        For every thread/future pair in the map:
            * if the executor is abandoned, abandon the future
            * if the future is done or abandoned, remove it from monitoring
            * if there are no more things to monitor, return

        Args:  None
        Returns:  None
        Raises:  None
        Tests Required:  None
        """
        should_run = True
        thread_lock_held = False
        while should_run:
            # Get the current pairs, so that we're not getting into wierd states with
            # some other thread adding pairs while we're evaluating them.
            current_pairs = list(self._monitored_threads.items())
            # check for executor abandonment
            if self._abandon:
                for _, future in current_pairs:
                    future.abandon()
            # check for completed/abandoned threads
            for thread, future in list(self._monitored_threads.items()):
                if future.done() or future.is_abandoned():
                    # acquire the thread prior to modifying the instance thread/future map
                    if not thread_lock_held:
                        self._monitored_thread_lock.acquire()
                        thread_lock_held = True
                    del self._monitored_threads[thread]
            # stop monitor
            if not self._monitored_threads:
                with self._monitored_thread_lock:
                    self._monitor_thread = None
                    should_run = False
            # release lock if held
            if thread_lock_held:
                thread_lock_held = False
                self._monitored_thread_lock.release()

    def _start_monitor(self) -> None:
        """
        Start the monitor thread if not running.

        Args:  None
        Returns:  None
        Raises:  None
        Tests Required: None
        """
        # lock starting the thread - only want one at a time
        # https://docs.python.org/3.6/library/threading.html#lock-objects says threading locks are context managers
        with self._monitored_thread_lock:
            if not self._monitor_thread:
                self._monitor_thread = threading.Thread(target=self._monitor, daemon=False)
                self._monitor_thread.start()

    def submit(self, fn: Callable, *args, **kwargs) -> ThreadFuture:
        """
        Submit a function to be run in a new thread.

        Args:
            fn:  The callable to be run in the thread.
            *args:  The positional arguments to pass to `fn`
            *kwargs:  The keyword args to pass to `fn`

        Returns:  A `ThreadFuture` with which to access the state/return/exception of `fn`.
        Raises:  None
        Tests Required:
            Future:  A future is returned when submit is called.
            Callable:  The given callable is run with no args if no args/kwargs are passed in
            Args:  The given callable is passed the args when called with just args
            Kwargs:  The given callable is passed the kwargs when called with just kwargs
            All:  The given callable is passed all the given args/kwargs
            Returns:  The correct return value is received from `fn`
            Raises:  The correct exception is received from `fn`
        """
        if self._is_shutdown:
            raise RuntimeError("Cannot submit functions to the executor - it has been shut down.")

        with self._monitored_thread_lock:
            this_future = ThreadFuture()  # type: ThreadFuture

            def wrapped_fn(*args, **kwargs) -> None:
                """
                A wrapped version of the fn.

                This will record the exceptions/returns of the fn in the future.

                Args:
                    *args:  the args to pass to the wrapped function
                    *kwargs:  the keyword args to pass to the wrapped function

                Returns:  None
                Raises:  None
                Required Tests:  None
                """
                # start the future
                # mypy says this function doesn't return anything, but
                # https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.set_running_or_notify_cancel
                # disagrees.
                if this_future.set_running_or_notify_cancel():  # type: ignore
                    try:
                        this_future.set_result(fn(*args, **kwargs))
                    # necessarily broad except - passing any exception back up to caller
                    except Exception as exception:  # pylint: disable=broad-except
                        this_future.set_exception(exception)

            thread = threading.Thread(target=wrapped_fn, args=args, kwargs=kwargs, daemon=True)
            self._monitored_threads[thread] = this_future
            thread.start()
            self._start_monitor()
            return this_future

    # map is inherited

    def shutdown(self, wait: bool=True) -> None:
        """
        Shutdown the executor.

        Once shut down, any further attempts to submit or map new tasks will result in RuntimeErrors.

        Args:
            wait:  If truthy, wait for the outstanding threads to complete before returning.

        Returns:  None
        Raises:  None
        Requires Tests:  None
        """
        self._is_shutdown = True
        if wait:
            # https://docs.python.org/3.6/library/threading.html#lock-objects says threading locks are context managers
            try:
                self._monitor_thread.join()
            except AttributeError:
                # if monitor thread doesn't exist, that's ok.
                # checking for existence first would be a race condition
                pass

    def abandon(self) -> None:
        """
        Abandon all futures spawned by this executor and shut down.

        Args:  None
        Returns:  None
        Raises:  None
        Requires Tests:  None
        """
        self._abandon = True
        self.shutdown(wait=True)


def test_default_exit() -> None:
    """Test Thread Executor default exit."""
    # When
    executor = ThreadExecutor()

    # Then
    utaw.assertEqual(executor._on_exit, ExitOption.ABANDON)  # pylint: disable=protected-access,no-member


def test_abandon_on_exit() -> None:
    """Test abandon on exit."""
    # Given
    executor = ThreadExecutor()

    # When
    exit_func = executor._exit_function(ExitOption.ABANDON)  # pylint: disable=protected-access

    # Then
    utaw.assertEqual(exit_func, executor.abandon)  # pylint: disable=no-member


def test_no_wait_on_exit() -> None:
    """Test no_wait on exit."""
    # Given
    executor = ThreadExecutor()

    # When
    exit_func = executor._exit_function(ExitOption.NO_WAIT)  # pylint: disable=protected-access

    # Then
    utaw.assertIsInstance(exit_func, functools.partial)  # pylint: disable=no-member
    if isinstance(exit_func, functools.partial):
        utaw.assertEqual(exit_func.func, executor.shutdown)  # pylint: disable=no-member
        utaw.assertEqual(exit_func.args, tuple())  # pylint: disable=no-member
        utaw.assertEqual(exit_func.keywords, {'wait': False})  # pylint: disable=no-member


def test_wait_on_exit() -> None:
    """Test wait on exit."""
    # Given
    executor = ThreadExecutor()

    # When
    exit_func = executor._exit_function(ExitOption.WAIT)  # pylint: disable=protected-access

    # Then
    utaw.assertIsInstance(exit_func, functools.partial)  # pylint: disable=no-member
    if isinstance(exit_func, functools.partial):
        utaw.assertEqual(exit_func.func, executor.shutdown)  # pylint: disable=no-member
        utaw.assertEqual(exit_func.args, tuple())  # pylint: disable=no-member
        utaw.assertEqual(exit_func.keywords, {'wait': True})  # pylint: disable=no-member
