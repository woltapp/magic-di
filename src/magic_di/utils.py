from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any

from magic_di import DependencyInjector

if TYPE_CHECKING:
    from collections.abc import Callable


def inject_and_run(fn: Callable, injector: DependencyInjector | None = None) -> Any:
    """
    This function takes a callable, injects dependencies into it using the provided injector,
    and then runs the function. If the function is a coroutine, it will be awaited.

    The function itself is not asynchronous, but it uses asyncio.run
    to run the internal coroutine, so it is suitable for use in synchronous code.

    Args:
        fn (Callable): The function into which dependencies will be injected. This can be
                       a regular function or a coroutine function.
        injector (DependencyInjector, optional): The injector to use for dependency injection.
                                                 If not provided, a default injector will be used.

    Returns:
        Any: The return value of the function `fn` after dependency injection and execution.

    Raises:
        Any exceptions raised by the function `fn` or the injector will be propagated up to
        the caller of this function.
    """
    injector = injector or DependencyInjector()

    injected: Callable = injector.inject(fn)

    async def run():
        async with injector:
            if inspect.iscoroutinefunction(fn):
                return await injected()

            return injected()

    return asyncio.run(run())
