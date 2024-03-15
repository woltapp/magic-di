from __future__ import annotations

import asyncio
import os
import threading
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from celery import signals
from celery.loaders.app import AppLoader  # type: ignore[import-untyped]

from magic_di import DependencyInjector
from magic_di.celery._async_utils import EventLoop, EventLoopGetter, run_in_event_loop

if TYPE_CHECKING:
    from collections.abc import Callable

    from celery.loaders.base import BaseLoader


@runtime_checkable
class InjectedCeleryLoaderProtocol(Protocol):
    injector: DependencyInjector
    loaded: bool

    def on_worker_process_init(self) -> None: ...

    def get_event_loop(self) -> EventLoop: ...


def get_celery_loader(
    injector: DependencyInjector | None = None,
    event_loop_getter: Callable[[], asyncio.AbstractEventLoop] | None = None,
    log_fn: Callable[[str], None] = print,
) -> type[BaseLoader]:
    _injector = injector or DependencyInjector()
    _event_loop_getter = event_loop_getter or EventLoopGetter()

    class CeleryLoader(AppLoader):  # type: ignore[no-any-unimported, misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.injector = _injector
            self.loaded = False
            self._event_loop: EventLoop | None = None
            self._lock = threading.Lock()
            self._event_loop_lock = threading.Lock()

        def on_worker_process_init(self) -> None:
            with self._lock:
                if self.loaded:
                    return

                log_fn(f"Trying to connect celery deps for pid {os.getpid()}...")
                run_in_event_loop(
                    self.injector.connect(),
                    self.get_event_loop(),
                )
                super().on_worker_process_init()
                log_fn(f"Celery deps are connected for pid {os.getpid()}")

                signals.worker_process_shutdown.connect(
                    self._disconnect,
                    weak=False,
                )
                self.loaded = True

        def get_event_loop(self) -> EventLoop:
            if self._event_loop is not None:
                return self._event_loop

            try:
                return EventLoop(asyncio.get_running_loop(), running_outside=True)
            except RuntimeError:
                # If a RuntimeError was raised,
                # it means that the task was called outside event loop.
                # And it also means that we can get the result of the coroutine.
                ...

            with self._event_loop_lock:
                if self._event_loop is None:
                    self._event_loop = EventLoop(
                        _event_loop_getter(),
                        running_outside=False,
                    )

                return self._event_loop

        def _disconnect(self, *_: Any, pid: str, **__: Any) -> None:
            log_fn(f"Trying to disconnect celery deps for pid {pid}...")
            run_in_event_loop(self.injector.disconnect(), self.get_event_loop())
            log_fn(f"Celery deps are disconnected for pid {pid}")

    return CeleryLoader
