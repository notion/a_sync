"""Example Use."""


# [ Imports ]
# [ -Python ]
import asyncio
import time
import pprint

# [ -Project ]
import a_sync


# [ Examples ]
if __name__ == '__main__':
    def hello(name, seconds):
        """Hello."""
        print('hello {}'.format(name))
        time.sleep(seconds)
        print('bye {}'.format(name))
        return name

    async def async_hello(name, seconds):
        """Hello."""
        print('hello {}'.format(name))
        await asyncio.sleep(seconds)
        print('bye {}'.format(name))
        return name

    parallel_1 = a_sync.parallel(
        a_sync.to_runnable(hello, 'joe', 5),
        a_sync.to_runnable(hello, 'sam', 3),
        a_sync.to_runnable(async_hello, 'bob', 1),
    )  # expect start in any order, stop in bob, sam, joe
    parallel_2 = a_sync.async_parallel(
        a_sync.to_runnable(async_hello, 'jill', 4),
        a_sync.to_runnable(async_hello, 'jane', 2),
        a_sync.to_runnable(hello, 'mary', 1),
    )  # expect start in any order, stop in mary, jane, jill

    serial_1 = a_sync.serial(
        parallel_1,
        parallel_2
    )  # expect bob/sam/joe to end before mary/jane/jill start

    parallel_3 = a_sync.async_parallel(
        a_sync.to_runnable(async_hello, 'joseph', 5),
        a_sync.to_runnable(hello, 'joey', 3),
        a_sync.to_runnable(async_hello, 'jo', 1),
    )  # expect start in any order, stop in jo, joey, joseph
    parallel_4 = a_sync.parallel(
        a_sync.to_runnable(hello, 'alex', 4),
        a_sync.to_runnable(async_hello, 'alexandria', 2),
        a_sync.to_runnable(hello, 'alexandra', 1),
    )  # expect start in any order, stop in alexandra, alexandria, alex

    serial_2 = a_sync.async_serial(
        parallel_3,
        parallel_4
    )  # expect joe/joey/joseph to stop before alexandra/alexandria/alex start

    all_results = a_sync.parallel(
        serial_1,
        serial_2,
    )()
    pprint.pprint(all_results)
    # expect bob/sam/joe to start with jo/joey/joseph
    # expect jill/jane/mary to start with alex/alexandria/alexandra
    # total expected ordering:
    # start joe/sam/bob/joseph/joey/jo
    # stop bob/jo
    # stop sam/joey
    # stop joe/joseph
    # start jill/jane/mary/alex/alexandria/alexandra
    # stop mary/alexandra
    # stop alexandria/jane
    # stop alex/jill
