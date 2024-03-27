from __future__ import annotations

import inspect
from functools import wraps
from typing import TYPE_CHECKING, Any, cast, get_type_hints

from celery.app.task import Task

from magic_di import Connectable, DependencyInjector
from magic_di.celery._async_utils import EventLoop, run_in_event_loop
from magic_di.celery._loader import InjectedCeleryLoaderProtocol

if TYPE_CHECKING:
    from collections.abc import Callable


class BaseCeleryConnectableDeps(Connectable): ...


class InjectableCeleryTaskMetaclass(type):
    def __new__(cls, name: str, bases: tuple[type, ...], dct: dict[str, Any]) -> type:
        run = dct.get("run")
        run_wrapper = dct.get("run_wrapper")

        if not run:
            return super().__new__(cls, name, bases, dct)

        if run_wrapper:
            dct["run"] = run_wrapper(run)
        else:
            for base in bases:
                if hasattr(base, "run_wrapper"):
                    dct["run"] = base.run_wrapper(run)
                    break

        return super().__new__(cls, name, bases, dct)


class InjectableCeleryTask(Task, Connectable, metaclass=InjectableCeleryTaskMetaclass):  # type: ignore[type-arg]
    __annotations__ = {}

    def __init__(
        self,
        # Type hint Any to make it non-injectable
        deps_instance: Any = None,
        injector: DependencyInjector | None = None,
    ) -> None:
        self._injector = injector

        if deps_instance:
            self.deps = deps_instance
            return

        if not self.injector:
            error_msg = (
                "Celery is not injected by magic_di.celery.get_celery_loader "
                "and injector or deps_instance is not passed in task args"
            )
            raise ValueError(error_msg)

        for dep in self.injector.inspect(self.run).deps.values():
            self.injector.lazy_inject(dep)

        deps_cls = get_type_hints(self).get("deps", BaseCeleryConnectableDeps)
        self.deps = self.injector.inject(deps_cls)()

        super().__init__()

    @property
    def injector(self) -> DependencyInjector | None:
        if self._injector:
            return self._injector

        if isinstance(self.app.loader, InjectedCeleryLoaderProtocol):
            loader: InjectedCeleryLoaderProtocol = cast(
                InjectedCeleryLoaderProtocol,
                self.app.loader,
            )

            return loader.injector

        return None

    def load(self) -> None:
        if isinstance(self.app.loader, InjectedCeleryLoaderProtocol):
            loader: InjectedCeleryLoaderProtocol = cast(
                InjectedCeleryLoaderProtocol,
                self.app.loader,
            )
            loader.on_worker_process_init()
            return

        self.app.loader.on_worker_process_init()  # type: ignore[attr-defined]

    @property
    def loaded(self) -> bool:
        if not isinstance(self.app.loader, InjectedCeleryLoaderProtocol):
            return True

        loader: InjectedCeleryLoaderProtocol = cast(
            InjectedCeleryLoaderProtocol,
            self.app.loader,
        )
        return loader.loaded

    def get_event_loop(self) -> EventLoop | None:
        if isinstance(self.app.loader, InjectedCeleryLoaderProtocol):
            loader: InjectedCeleryLoaderProtocol = cast(
                InjectedCeleryLoaderProtocol,
                self.app.loader,
            )

            return loader.get_event_loop()

        return None

    @staticmethod
    def run_wrapper(orig_run: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(orig_run)
        def runner(self: InjectableCeleryTask, *args: Any, **kwargs: Any) -> Any:
            if not self.loaded:
                self.load()

            run = self.injector.inject(orig_run) if self.injector else orig_run

            if "self" in inspect.signature(run).parameters:
                args = (self, *args)

            result = run(*args, **kwargs)

            if inspect.isawaitable(result):
                event_loop = self.get_event_loop()
                if not event_loop:
                    error_msg = (
                        "Cannot run async tasks. "
                        "Celery is not injected by magic_di.celery.get_celery_loader"
                    )
                    raise ValueError(error_msg)

                return run_in_event_loop(
                    result,  # type: ignore[arg-type]
                    event_loop,
                )

            return result

        return runner
