# a_sync
An async helper library for Python's async functionality.

# Reason for existing
This library exists because async/await syntax introduces a tension between blocking and asynchronous contexts, and
blocking and asynchronous functions, and most of the documentation and tutorials out there only discuss the very
simplest uses of async in Python.

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
* getting/creating and setting/reverting an independent asyncio event loop to use, regardless of thread or thread-global
asyncio loop run status.

# Under construction
The repo is "under construction" - it serves at the moment as a place to put the project and "get it out there", but there are a lot of project-management tasks to do, including getting a sensible README up.

# Alpha status
The repo is definitely "alpha".  Possibly "pre-alpha", if that's a thing.  At the moment it's got one internal user for code that isn't even published internally yet.

Basically anything is subject to change.  This includes any of the API, the project name, and even the project's existence.  It was initially created to help me understand how Python's async stuff worked, and has grown as I've decided that the asyncio lib is lower-level than I want to deal with, and as I explored different "well now how do I do this?" questions.

Feedback, new issues, suggestions, criticisms, etc are welcomed and encouraged.  If the project turns out to be truly worth it, I'll be happy to have shared it.  If not, I'll be happy to have learned why it's not, and how to do async in python better.

# Thoughts
The below are some thoughts about using the async support in python - they're a little stream-of-consciousness, and
only very lightly edited.

Python runs in a sync context - need to support async calls in the sync context, which means supporting
subcomponents using the event loop.  Or some other loop.  Or some other async runner (like the curio kernel).  Code
should not make any assumptions about the context it's running in.

You can await any number of levels down, but if you want to add something to the current event loop...you'll get an
async future back, which requires knowledge of the loop it was created for to be running in order to use properly. 
Unfortunately, asyncio doesn't yet allow you to figure that out, so you have to be careful about passing those futures 
around.  It seems to me that asyncio futures should only be used at the same level as the asyncio event loop is used.
There is an unfortunate implicit dependency there which is further complicated by the asynchronous nature of the
library and is even harder to reason about in the face of mutliple threads... I would recommend that any use of asyncio
futures be tightly controlled.

Levels of concurrency:
* When to be serial - when you want to do a single operation and don't want anything else to happen till it's done.
* When to be concurrent in a single thread - when you have things you want done concurrently, but none of them are
blocking.
* When to be concurrent in multiple threads - when you have blocking operations.
* When to be multi-process - when your cpu fills up.
* When to be multi-host - when all your cpu's fill up.

So...you want single-threaded-blocking if you want just one thing done at the top level, logical concurrency any
other time, thread-concurrency when you have truly blocking operations, and actual temporal concurrency when you've run out
of computation power in your processor, or when you can actually break things into independent tasks such that actually
running in parallel actually gets you a speed boost that you care about..  (this can be expanded to other hosts, not
just other cpu's, though you want minimal communication the further apart your parts are (single-threaded-blocking ->
single-threaded concurrent -> multi-threaded concurrent -> multiprocess-concurrent -> multi-host concurrent))

The only dependable "top-level" is the `__main__` script area.  Any function calls you define and call in the main
script can be called from within other functions and from other modules, and you can't ever know if they're being run
concurrently or not.  Even the main script is often refactored out into a function call, which can then be used
anywhere.

From that, I'd reason that you always want to be concurrent.  The major advantage of `await` is that you get to pick
where your thread's control moves off to run other things, which allows you to explicitly run areas of code 'atomically'
in your thread without dealing with locks/semaphores/events.  From that, I'd reason that most of the time you want to
use the await-style concurrency instead of thread-level concurrency.

So forget the synchronous context.  Write everything new asynchronously.  Wrap all the blocking calls.

Stretch goals:
* find a way to simulate the await 'atomic' guarantees in threads, because threads are always going to be necessary
for dealing with blocking calls.
* find a way to grow your executor thread pool when you need more blocking concurrency and there's CPU available.
* find a way to grow and load balance into threads on other processors.
* find a way to grow and load balance into processors on other hosts.

Further musings given the stretch goals - this assumes you want python for other reasons than concurrency.  there are 
other languages which are explicitly designed for concurrency from the start, and usually features designed into the
lanugage are easier to work with than libraries built on top are.

# Examples
## Running one function
### Async in async
If you're running the async version in an async context, you do so like:

`await async_hello('foo', 5)`

This behaves as a blocking function locally (it will wait 5s before executing the next line), but it allows
other async functions to run concurrently while the sleep is occurring.  You don't need this library for this use case.

### blocking in blocking
If you're running the blocking version in a blocking context, you do so like:

`hello('foo', 5)`

This blocks the current thread until the function is done and then moves on.  You don't need this library for this use
case.

### async in blocking
If you're running the async version in a blocking context, you have several options:

#### the error way

`await async_hello('foo', 5)`

This will raise an error, because you're not in an async context.

#### the wrong way
`async_hello('foo', 5)`

This will return a coroutine object, rather than the expected return value (the name), and will not actually run
the function.  Functions defined with `async def` are "coroutine functions", and their actual return value is an
awaitable coroutine.  Running this coroutine to completion is what actually returns your expected value.

You could figure out how to run the co-routine manually, but the asyncio library provides a way to do this which is
simpler:

#### the official way
`asyncio.get_event_loop().run_until_complete(async_hello('foo', 5))`

This will get the current thread's global asyncio event loop, and run your function in it, block until that function
is done, and then return the value to you.

This is what most tutorials for asyncio show you, and this is where they generally stop.  There are, however, some
problems with this method:

* it assumes you're in the main thread, or in a thread which has an event loop set.  New threads do not by default
have an event loop set on them.  If you use this code in a blocking function that gets called from a non-main thread,
it will raise an exception about not having an event loop.
* it assumes you're not already in the main event loop.  It's reasonable to assume that at some point, someone is going
to want to run an async function in a blocking fashion, and run_until_complete makes that possible.  This means it's
possible to create a function which calls this code.  It's also possible to then call that function from within a
running event loop.  You probably don't want to structure your code that way from the start, but hey, re-structuring
happens, libraries get written and used in new and interesting places, so it's important to think about the consequences
of this case.  If you run `run_until_complete` on the default loop inside the default loop, you're going to get a runtime
error telling you the loop is already running.

This is one of the original reasons this library was written.  It provides you with:

#### the a_sync option
`a_sync.block(async_hello, 'foo', 5)`

This takes your async function and the args and returns the same output as if you'd done `await` in an async context.

If you just want to get a blocking function back (and not call it immediately), you can use
`blocking_hello = a_sync.to_blocking(async_hello)`.  You can then call it later like `blocking_hello('foo', 5)`.

### Sync in async

Generally, if you want to run something asynchronously in an async context, you should use `async def` instead of `def`,
but what if you can't, because it's a third party function, or for other reasons?

#### Block the thread

Just running `hello('foo', 5)` will cause the code to run, but will block your thread - nothing else in the thread will
run until it returns.  

#### the official way

`await asyncio.get_event_loop().run_in_executor(None, hello, 'foo', 5)`

This is both awkward syntax, and suffers from similar problems as before: it assumes main thread, and it assumes the
the event loop IS running (but maybe you're using a different event loop - you can do that - someone ELSE could do that
with your code, and it may not be obvious that there are event loops in use in lower levels of code).

This is another of the original reasons for writting this library, which provides you with:

#### the a_sync way

`await a_sync.run(hello, 'foo', 5)`

This takes a blocking function and its args and returns the same value, but does not block the current thread as it runs.

It also:
* is syntactically simpler
* will automatically use a new event loop if the current thread-global event loop is missing
* will automatically use a new event loop if the current thread-global event loop is already running

One unfortunate thing to be aware of here is that the implementation acheives asynchronisity via the same basic mechanism
as the official way - it runs the blocking code in a subthread.  If the underlying threadpool is full, this function will
not block, but it will also not execute until the threadpool has room.  This is not any worse than the official method,
but it is something to be aware of if you run in to problems with function execution piling up.

If you just want an async function to use later, you can use `awaitable_hello = a_sync.to_async(hello)`, and then
later await it as normal: `await awaitable_hello('foo', 5)`.

## Running a single task in the background

If you want to run something in the background, you again have several options, and they all have similar downsides as
the examples above.  `a_sync` provides `queue_background_thread`:

```python
future = queue_background_thread(hello, 'foo', 5)
# do other things
# the 'hello' function is running in the background
result = future.result()  # waits for background task to complete.
```

This function is really just a light wrapper around some of the functions from concurrent.futures.  If you're running
from a blocking context, this is the best you can do - the async/await stuff doesn't help here - that's for running
concurrently within the same thread.

If you're running from the async context, it's best to use the available tools and functions in the asyncio or curio
libraries (such as creating and waiting for tasks).

## Running multiple tasks in the background

If you want to run multiple tasks in the background, you can call `queue_background_thread` multiple times, and manage
the futures yourself.  There's also a convenience class provided by a_sync for that purpose: `Parallel`.

```python
parallel_1 = a_sync.Parallel()
parallel_1.schedule(hello, 'joe', 5)
parallel_1.schedule(hello, 'sam', 3)
parallel_1.schedule(async_hello, 'bob', 1)
```

As you can see, `Parallel` lets you schedule any function, async or blocking.  The really nice part is that it
allows you to run your parallel functions in either a blocking or async context:

`results = await parallel_1.run()`

or 

`results = parallel_1.block()`

In either case, the `results` will be a list of the return values from the scheduled functions, in the order they were
scheduled.

`Parallel` will only convert functions which are of the wrong type (sync for async and vice-versa) when you call the
run/block functions.

## Running multiple tasks serially
Generally, if you want to run multiple tasks serially, I'd just run them, or run them with `a_sync.block`.  However,
for reasons of symmetry and some convenience, a `Serial` class is provided, which mimics the schedule/run/block API of
`Parallel`, but runs all the scheduled tasks serially.

The drawback to using this method is that you have to wait for the results, and you cannot pass them around.  The benefits are:
* you can ignore function type (sync/async)
* you can run blocking or async

## Getting an asyncio loop to operate on
If you want to use an asyncio loop directly, most tutorials say to do `loop = asyncio.get_event_loop()`.  This has
similar problems as discussed before:
* it assumes you are in the main thread
* it requires you to actually check whether the loop is running before you use it, and use it differently based
on the result - unnaturally coupling your code to external conditions.
* it opens up the possibility of polluting your caller's state (for instance if you add tasks to the event loop
which the caller was not expecting, because your use of an event loop is a detail abstracted away from the caller)

`a_sync` provides the `idle_event_loop` function for this case.  If you want an event loop to use, which behaves to you
and the code you call as if you did `asyncio.get_event_loop()`, but which is safe from the listed problems, do:

```python
with a_sync.idle_event_loop() as loop:
    # use loop
```

You can use this loop, confident that:
* it exists
* it's not yet running
* asyncio functions you call will use this loop (unless you pass another loop in, or another loop is retrieved from 
some object state)
* when the context manager is left, the original global thread loop will be restored, so calling code will not be affected.

# API

## Functions
### `idle_event_loop() -> Generator`

An idle event loop context manager.

Leaves the current event loop in place if it's not running.
Creates and sets a new event loop as the default if the current default IS running.
Restores the original event loop on exit.

**Args:**
* None

**Returns:**
* idle_event_loop_manager - a context manager which yields an idle event loop
    for you to run async functions in.


### `to_async(blocking_func: AnyCallable) -> AnyCallable`
    
Convert a blocking function to an async function.

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

**Args:**
* blocking_func - a blocking function

**Returns:**
* async_func - an awaitable function


### `to_blocking(async_func: AnyCallable) -> AnyCallable`

Convert an async function to a blocking function.

If the argument is already a blocking function, it is returned unchanged.

If the argument is a partial for an awaitable, it is converted.

The awaitable function is made blocking by wrapping its call in a blocking
function, which gets/creates an idle asyncio event loop and runs the
awaitable in it until it is complete.

**Args:**
* async_func - an async function

**Returns:**
* blocking_func - a blocking function



### `async queue_background_thread` *not provided*

No async background task here because that depends on knowing the environment
of the caller, as far as async context goes, and you can't.  For example,
if the caller is being executed via the curio kernel, and we add a task to the
current asyncio event loop, that task will never complete.


### `queue_background_thread(func: Callable, *args, **kwargs) -> futures.Future`
    
Queue the function to be run in a thread, but don't wait for it.

If the thread pool executor is processing on all threads, it will queue this
task.  There's currently no way to check it or expand it's pool, hence the
name of the function and the summary have been updated to reflect that..

**Args:**
* func - the function to run
* `*args` - the args to call the function with
* `**kwargs` - the kwargs to call the function with

**Returns:**
* future - a concurrent.futures Future for the function.



### `async run(func: AnyCallable, *args, **kwargs) -> Any`
Run a function in an async manner, whether the function is async or blocking.

**Args:**
* func - the function (async or blocking) to run
* `*args` - the args to run the function with
* `**kwargs` - the kwargs to run the function with

**Returns:**
* coro - a coroutine object to await

**Coro Returns:**
* result - whatever the function returns when it's done.


### `block(func: AnyCallable, *args, **kwargs) -> Any`

Run a function in a blocking manner, whether the function is async or blocking.

Args:
* func - the function (async or blocking) to run
* `*args` - the args to run the function with
* `**kwargs` - the kwargs to run the function with

**Returns:**
* result - whatever the function returns when it's done.


## Parallel Class
### `class Parallel`

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

**Args:**
* None


### `schedule(self, func, *args, **kwargs) -> 'Parallel'`
Schedule a function to be run.

**Args:**
* func - the function to schedule
* `*args` - the args to call the function with
* `**kwargs` - the kwargs to call the function with

**Returns:**
* parallel - the parallel object, to allow chaining.


### `async run(self) -> List[Any]`
Run the scheduled functions in parallel, asynchronously.

**Args:**
* None

**Returns:**
* list - a list of the results from the scheduled functions, in the
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


### `block(self) -> List[Any]`
Run the scheduled functions in parallel, blocking.

**Args:**
* None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.


## Serial Class
### `class Serial`
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

**Args:**
* None


### `schedule(self, func: Callable, *args, **kwargs) -> 'Serial'`

Schedule a function to be run.

**Args:**
* func - the function to schedule
* `*args` - the args to call the function with
* `**kwargs` - the kwargs to call the function with

**Returns:**
* series - the series object, to allow chaining.


### `async run(self) -> List[Any]`

Run the scheduled functions in series, asynchronously.

**Args:**
    None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.


### `block(self) -> List[Any]`

Run the scheduled functions in series, blocking.

**Args:**
* None

**Returns:**
* list - a list of the results from the scheduled functions, in the
    order they were scheduled in.
