"""A module exploring some python asyncio interactions."""


# [ Imports ]
from a_sync.a_sync import (
    idle_event_loop,
    to_async,
    to_blocking,
    queue_background_thread,
    run,
    block,
    a_input,
    Parallel,
    Serial
)


# silence pyflakes
assert idle_event_loop
assert to_async
assert to_blocking
assert queue_background_thread
assert run
assert block
assert a_input
assert Parallel
assert Serial
