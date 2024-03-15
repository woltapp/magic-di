import functools
import inspect
from dataclasses import dataclass
from threading import Lock
from typing import Generic, Iterable, Type, TypeVar, cast

T = TypeVar("T")


@dataclass(frozen=True)
class Dependency(Generic[T]):
    object: Type[T]
    instance: T | None = None


class SingletonDependencyContainer:
    def __init__(self):
        self._deps: dict[Type[T], Dependency[T]] = {}
        self._lock: Lock = Lock()

    def add(self, obj: Type[T], **kwargs) -> Type[T]:
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

    def get(self, obj: Type[T]) -> Type[T] | None:
        with self._lock:
            return self._get(obj)

    def iter_instances(self, *, reverse: bool = False) -> Iterable[tuple[Type[T], T]]:
        with self._lock:
            deps_iter: Iterable = list(
                reversed(self._deps.values()) if reverse else self._deps.values()
            )

        for dep in deps_iter:
            if dep.instance:
                yield dep.object, dep.instance

    def _get(self, obj: Type[T]) -> Type[T] | None:
        dep = self._deps.get(obj)
        return dep.object if dep else None


def _wrap(obj: Type[T], *args, **kwargs) -> Type[T]:
    if not inspect.isclass(obj):
        partial = functools.wraps(obj)(functools.partial(obj, *args, **kwargs))
        return cast(Type[T], partial)

    _instance = None

    def __new__(cls):
        nonlocal _instance

        if _instance is not None:
            return _instance

        _instance = obj(*args, **kwargs)
        return _instance

    # This class wraps obj and creates a singleton class that uses *args and **kwargs for initialization.
    # Please note that it also doesn’t allow passing additional args after creating this partial.
    # It was made to make it more obvious that you can’t create two different instances with different parameters.
    # Example:
    #   injected_redis = injector.inject(Redis)
    #   injected_redis()  # works
    #   injected_redis(timeout=10)  # doesn’t work
    #
    # Here we manually create a new class using the `type` metaclass to prevent possible overrides of it.
    # We copy all object attributes (__dict__) so that upon inspection,
    # the class should look exactly like the wrapped class.
    # However, we override the __new__ method to return an instance of the original class.
    # Since the original class was not modified, it will use its own metaclass.
    SingletonPartialCls = functools.wraps(
        obj,
        updated=(),
    )(
        type(
            obj.__name__,
            (obj,),
            {
                **obj.__dict__,
                "__new__": __new__,
            },
        )
    )

    return SingletonPartialCls
