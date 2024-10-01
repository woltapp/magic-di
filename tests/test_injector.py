from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Generic, TypeVar

import pytest
from magic_di import Connectable, DependencyInjector, Injectable
from magic_di.exceptions import InjectionError

from tests.conftest import (
    AnotherDatabase,
    AsyncWorkers,
    BrokenService,
    Database,
    NonConnectableDatabase,
    RepoInterface,
    Repository,
    Service,
    ServiceWithBindings,
)


@pytest.mark.asyncio()
async def test_class_injection_success(injector: DependencyInjector) -> None:
    injected_service = injector.inject(Service)()
    assert not injected_service.is_alive()

    assert isinstance(injected_service.repo, Repository)
    assert isinstance(injected_service.repo.db, Database)
    assert isinstance(injected_service.workers, AsyncWorkers)

    assert not injected_service.repo.connected
    assert not injected_service.repo.db.connected
    assert not injected_service.workers.connected

    await injector.connect()

    assert injected_service.repo.connected
    assert injected_service.repo.db.connected
    assert injected_service.workers.connected
    assert injected_service.is_alive()

    await injector.disconnect()

    assert not injected_service.repo.connected
    assert not injected_service.repo.db.connected
    assert not injected_service.workers.connected


@pytest.mark.asyncio()
async def test_function_injection_success(injector: DependencyInjector) -> None:
    def run_service(service: Service) -> Service:
        return service

    injected = injector.inject(run_service)

    async with injector:
        service = injected()
        assert service.is_alive()

    assert isinstance(service, Service)


@pytest.mark.asyncio()
async def test_function_injection_success_legacy_optional(injector: DependencyInjector) -> None:
    def run_service(service: Service | None) -> Service:
        assert service is not None
        return service

    injected = injector.inject(run_service)

    async with injector:
        service = injected()
        assert service.is_alive()

    assert isinstance(service, Service)


def test_class_injection_missing_class(injector: DependencyInjector) -> None:
    with pytest.raises(InjectionError):
        injector.inject(BrokenService)


@pytest.mark.asyncio()
async def test_class_injection_with_bindings(injector: DependencyInjector) -> None:
    injector.bind({RepoInterface: Repository})

    injected_service = injector.inject(ServiceWithBindings)()

    assert isinstance(injected_service.repo, Repository)
    assert isinstance(injected_service.repo.db, Database)

    await injector.connect()

    assert injected_service.repo.connected
    assert injected_service.repo.db.connected

    await injector.disconnect()

    assert not injected_service.repo.connected
    assert not injected_service.repo.db.connected


def test_lazy_inject(injector: DependencyInjector) -> None:
    get_injected_cls = injector.lazy_inject(Service)
    injected_service = get_injected_cls()

    assert isinstance(injected_service, Service)
    assert injected_service is get_injected_cls()


def test_overriden_injection(injector: DependencyInjector) -> None:
    service = injector.inject(Service)()

    with injector.override({Database: AnotherDatabase}):
        service_with_overriden_deps = injector.inject(Service)()

        assert isinstance(service_with_overriden_deps, Service)
        assert isinstance(service_with_overriden_deps.repo.db, AnotherDatabase)
        assert isinstance(service.repo.db, Database)
        assert service is not service_with_overriden_deps

    service_after_overriden_injection = injector.inject(Service)()
    assert isinstance(service_after_overriden_injection.repo.db, Database)
    assert service is service_after_overriden_injection


def test_embedded_injection(injector: DependencyInjector) -> None:
    class ClsWithEmbeddedInjection(Connectable):
        def __init__(self, injected_injector: DependencyInjector):
            assert injected_injector is injector
            self.service = injector.inject(Service)()

    injected = injector.inject(ClsWithEmbeddedInjection)()
    assert isinstance(injected.service, Service)


def test_injector_iter_deps(injector: DependencyInjector) -> None:
    injector.inject(Service)()

    deps = [type(dep) for dep in injector.iter_deps()]
    assert deps == [Database, Repository, AsyncWorkers, Service]


def test_injector_with_metaclass(injector: DependencyInjector) -> None:
    class _ServiceMetaClass(type):
        def __new__(cls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> type[Any]:
            for _ in attrs["__orig_bases__"]:
                ...

            new_type: type = super().__new__(cls, name, bases, attrs)
            return new_type

    tv = TypeVar("tv")

    class ServiceGeneric(Generic[tv], metaclass=_ServiceMetaClass): ...

    @dataclass(frozen=True)
    class WrappedService(ServiceGeneric[Service]):
        repo: Repository
        workers: AsyncWorkers | None

    injector.inject(WrappedService)()


def test_injector_flag_injectable(injector: DependencyInjector) -> None:
    @dataclass
    class ServiceWithNonConnectable:
        db: Annotated[NonConnectableDatabase, Injectable]

    injected = injector.inject(ServiceWithNonConnectable)()
    assert isinstance(injected.db, NonConnectableDatabase)


def test_injector_pydantic_metaclass_doesnt_break(injector: DependencyInjector) -> None:
    from pydantic import BaseModel

    class PydanticClass(BaseModel, Connectable):
        var: int = 1

    injected = injector.inject(PydanticClass)()
    assert isinstance(injected, PydanticClass)
    assert injected.var == 1
