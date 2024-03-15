import inspect
import logging
from contextlib import contextmanager
from threading import Lock
from typing import Annotated, Any, Callable, Iterable, Type, TypeVar, cast, get_origin

from magic_di._connectable import ConnectableProtocol
from magic_di._container import SingletonDependencyContainer
from magic_di._signature import Signature
from magic_di._utils import (
    get_cls_from_optional,
    get_type_hints,
    is_injectable,
    safe_is_subclass,
)
from magic_di.exceptions import InjectionError, InspectionError

# flag to use in typing.Annotated
# to forcefully mark dependency as injectable
# even if dependency is not connectable
# Example: typing.Annotated[MyDependency, Injectable]
Injectable = type("Injectable", (), {})()


def is_injector(cls: Type) -> bool:
    """
    Check if a class is a subclass of DependencyInjector.

    Args:
        cls (Type): The class to check.

    Returns:
        bool: True if the class is a subclass of DependencyInjector, False otherwise.
    """
    return safe_is_subclass(cls, DependencyInjector)


def is_forcefully_marked_as_injectable(cls: Any) -> bool:
    if get_origin(cls) is Annotated:
        return Injectable in cls.__metadata__

    return False


T = TypeVar("T")
AnyObject = TypeVar("AnyObject")


class DependencyInjector:
    def __init__(
        self,
        bindings: dict | None = None,
        logger: logging.Logger = logging.getLogger("injector"),
    ):
        self.bindings: dict = bindings or {}
        self.logger: logging.Logger = logger

        self._deps = SingletonDependencyContainer()
        self._postponed: list[Callable[..., T]] = []
        self._lock = Lock()

    def inject(self, obj: Callable[..., T]) -> Callable[..., T]:
        """
        Inject dependencies into a class/function.
        This method is idempotent, always returns the same instance

        Args:
            obj (Callable[..., T]): The class/function to inject dependencies into.

        Returns:
            Callable[..., T]: Partial for class/function with dependencies injected.
        """
        obj = self._unwrap_type_hint(obj)  # type: ignore[arg-type]

        if dep := self._deps.get(obj):  # type: ignore[arg-type]
            return dep

        signature = self.inspect(obj)

        clients: dict[str, object] = {}
        for name, dep in signature.deps.items():
            clients[name] = self.inject(dep)()  # type: ignore[misc]

        if signature.injector_arg is not None:
            clients[signature.injector_arg] = self

        try:
            return self._deps.add(obj, **clients)
        except TypeError as exc:
            raise InjectionError(obj, signature) from exc

    def inspect(self, obj: AnyObject) -> Signature[AnyObject]:
        try:
            hints = get_type_hints(obj)
            hints_with_extras = get_type_hints(obj, include_extras=True)

            if not hints:
                return Signature(obj, is_injectable=is_injectable(obj))

            if inspect.ismethod(obj):
                hints.pop("self", None)

            hints.pop("return", None)

            signature = Signature(obj, is_injectable=is_injectable(obj))

            for name, hint in hints.items():
                hint = self._unwrap_type_hint(hint)
                hint_with_extra = hints_with_extras[name]

                if is_injector(hint):
                    signature.injector_arg = name
                    continue
                elif not is_injectable(hint) and not is_forcefully_marked_as_injectable(
                    hint_with_extra
                ):
                    signature.kwargs[name] = hint
                    continue

                signature.deps[name] = hint
        except Exception as exc:
            raise InspectionError(obj) from exc

        return signature

    async def connect(self):
        """
        Connect all injected dependencies
        """
        # unpack to create copy of list
        for postponed in [*self._postponed]:
            # First, we need to create instances of postponed injection in order to connect them.
            self.inject(postponed)

        for cls, instance in self._deps.iter_instances():
            if is_injectable(cls):
                self.logger.debug(f"Connecting {cls}...")
                await instance.__connect__()

    async def disconnect(self):
        """
        Disconnect all injected dependencies
        """
        for cls, instance in self._deps.iter_instances(reverse=True):
            if is_injectable(cls):
                try:
                    await instance.__disconnect__()
                except Exception:
                    self.logger.exception(f"Failed to disconnect {cls}")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args, **kwargs):
        await self.disconnect()

    def iter_deps(self) -> Iterable[ConnectableProtocol]:
        instance: ConnectableProtocol

        for _, instance in self._deps.iter_instances():
            yield instance

    def lazy_inject(self, obj: Callable[..., T]) -> Callable[..., T]:
        """
        Lazily inject dependencies into a class or function.

        Args:
            obj (Callable[..., T]): The class or function to inject dependencies into.

        Returns:
            Callable[..., T]: A function that, when called,
            will inject the dependencies and return the injected class instance or function.
        """

        with self._lock:
            self._postponed.append(obj)  # type: ignore[arg-type]
            # incompatible type "Callable[..., T]"; expected "Callable[..., T]"

        injected = None

        def inject():
            nonlocal injected

            if injected is not None:
                return injected

            injected = self.inject(obj)()
            return injected

        return cast(Type[T], inject)

    def bind(self, bindings: dict[Type, Type]):
        """
        Bind new bindings to the injector.

        This method is used to add new bindings to the injector. Bindings are a dictionary where the keys are the
        classes used in dependencies type hints, and the values are the classes that should replace them.

        For example, if you have a class `Foo` that depends on an interface `Bar`, and you have a class `BarImpl`
        that implements `Bar`, you would add a binding like this: `injector.bind({Bar: BarImpl})`. Then, whenever
        `Foo` is injected, it will receive an instance of `BarImpl` instead of `Bar`.

        If a binding for a particular class or type already exists, this method will update that binding with the
        new value

        Args:
            bindings (dict[Type, Type]): The bindings to add. This should be a dictionary where the keys are
            classes and the values are the classes that should replace them.
        """
        with self._lock:
            self.bindings = self.bindings | bindings

    @contextmanager
    def override(self, bindings: dict[Type, Type]):
        """
        Temporarily override the bindings and dependencies of the injector.

        Args:
            bindings (dict): The bindings to use for the override.
        """
        with self._lock:
            actual_deps = self._deps
            actual_bindings = self.bindings

            self._deps = SingletonDependencyContainer()
            self.bindings = self.bindings | bindings

        try:
            yield
        finally:
            with self._lock:
                self._deps = actual_deps
                self.bindings = actual_bindings

    def _unwrap_type_hint(self, obj: Type[AnyObject]) -> Type[AnyObject]:
        obj = get_cls_from_optional(obj)
        obj = self.bindings.get(obj, obj)
        return obj

    def __hash__(self) -> int:
        """Injector is always unique"""
        return id(self)
