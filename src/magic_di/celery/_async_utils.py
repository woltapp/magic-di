from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Coroutine

R = TypeVar("R")


@dataclass
class EventLoop:
    loop: asyncio.AbstractEventLoop
    running_outside: bool = False


class EventLoopGetter:
    def __init__(self) -> None:
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._loop_thread: threading.Thread | None = None

    def start(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._event_loop:
                return self._event_loop

            self._event_loop = asyncio.get_event_loop()
            self._loop_thread = threading.Thread(
                target=self._event_loop.run_forever,
                daemon=True,
            )
            self._loop_thread.start()
            return self._event_loop

    def __call__(self) -> asyncio.AbstractEventLoop:
        if self._event_loop:
            return self._event_loop

        return self.start()


def run_in_event_loop(
    coroutine: Coroutine[Any, Any, R],
    event_loop: EventLoop,
) -> R | None:
    # If we are inside event loop, we cannot obtain the result of an async task
    # because it will cause the event loop to hang.
    # In this case, we create a background task and return None.
    if event_loop.running_outside:
        event_loop.loop.create_task(coroutine)
        return None

    return asyncio.run_coroutine_threadsafe(coroutine, event_loop.loop).result()
