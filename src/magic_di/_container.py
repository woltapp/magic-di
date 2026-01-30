from __future__ import annotations

import functools
import inspect
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterable


T = TypeVar("T")


@dataclass(frozen=True)
class Dependency(Generic[T]):
    object: type[T]
    instance: T | None = None


class SingletonDependencyContainer:
    def __init__(self) -> None:
        self._deps: dict[type, Dependency[Any]] = {}
        self._lock: Lock = Lock()

    def add(self, obj: type[T], **kwargs: Any) -> type[T]:
        with self._lock:
            if dep := self._get(obj):
                return dep

        wrapped = _wrap(obj, **kwargs)
        dependency = Dependency(
            object=wrapped,
            instance=wrapped() if inspect.isclass(obj) else None,
        )

        with self._lock:
            # To avoid deadlocks when an injector is used inside the __init__ method
            if dep := self._get(obj):
                return dep

            self._deps[obj] = dependency

        return wrapped

    def get(self, obj: type[T]) -> type[T] | None:
        with self._lock:
            return self._get(obj)

    def iter_instances(
        self,
        *,
        reverse: bool = False,
    ) -> Iterable[tuple[type, object]]:
        with self._lock:
            deps_iter: Iterable[Dependency[Any]] = list(
                reversed(self._deps.values()) if reverse else self._deps.values(),
            )

        for dep in deps_iter:
            if dep.instance:
                yield dep.object, dep.instance

    def _get(self, obj: type[T]) -> type[T] | None:
        dep = self._deps.get(obj)
        return dep.object if dep else None


def _wrap(obj: type[T], *args: Any, **kwargs: Any) -> type[T]:
    if not inspect.isclass(obj):
        partial: type[T] = functools.wraps(obj)(functools.partial(obj, *args, **kwargs))  # type: ignore[assignment]
        return partial

    _instance: T | None = None

    def new(_: Any) -> T:
        nonlocal _instance

        if _instance is not None:
            return _instance

        _instance = obj(*args, **kwargs)
        return _instance

    # This class wraps obj and creates a singleton class
    # that uses *args and **kwargs for initialization.
    #
    # Please note that it also doesn't allow passing additional args
    # after creating this partial.
    # It was made to make it more obvious that you can't create
    # two different instances with different parameters.
    #
    # Example:
    #   >>> injected_redis = injector.inject(Redis)
    #   >>> injected_redis()  # works
    #   >>> injected_redis(timeout=10)  # doesn't work
    #
    # Here we manually create a new singleton class factory using the `type` metaclass
    # Since the original class was not modified, it will use its own metaclass.
    return functools.wraps(  # type: ignore[return-value]
        obj,
        updated=(),
    )(
        type(
            obj.__name__,
            (),
            {"__new__": new},
        ),
    )
