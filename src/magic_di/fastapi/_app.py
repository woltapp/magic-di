from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Protocol,
    get_origin,
    runtime_checkable,
)

from fastapi.params import Depends

from magic_di._injector import DependencyInjector

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from fastapi import FastAPI, routing


@runtime_checkable
class RouterProtocol(Protocol):
    endpoint: Callable[..., Any]


@runtime_checkable
class FastAPIRouterProtocol(RouterProtocol, Protocol):
    dependencies: list[Depends]


def inject_app(
    app: FastAPI,
    *,
    injector: DependencyInjector | None = None,
    use_deprecated_events: bool = False,
) -> FastAPI:
    """
    Inject dependencies into a FastAPI application using the provided injector.

    This function sets up the FastAPI application to connect and disconnect the injector
    at startup and shutdown, respectively.

    This ensures that all dependencies are properly
    connected when the application starts, and properly disconnected when the application
    shuts down.

    If no injector is provided, a default injector is used.

    Args:
        app (FastAPI): The FastAPI application

        injector (DependencyInjector, optional): The injector to use for dependency injection.
                                                 If not provided, a default injector will be used.

        use_deprecated_events (bool, optional): Indicate whether the app should be injected
                                                with starlette events (which are deprecated)
                                                or use app lifespans.
                                                Important: Use this flag only
                                                if you still use app events,
                                                because if lifespans are defined,
                                                events will be ignored by Starlette.

    Returns:
        FastAPI: The FastAPI application with dependencies injected.
    """
    injector = injector or DependencyInjector()

    def collect_deps() -> None:
        _collect_dependencies(injector, app.router)

    app.state.dependency_injector = injector

    if use_deprecated_events:
        _inject_app_with_events(app, collect_deps_fn=collect_deps)
    else:
        _inject_app_with_lifespan(app, collect_deps_fn=collect_deps)

    return app


def _inject_app_with_lifespan(app: FastAPI, collect_deps_fn: Callable[[], None]) -> None:
    app_router: routing.APIRouter = app.router
    app_lifespan = app_router.lifespan_context

    @asynccontextmanager
    async def injector_lifespan(app: FastAPI) -> AsyncIterator[None]:
        collect_deps_fn()

        injector = app.state.dependency_injector
        await injector.connect()

        async with app_lifespan(app):
            yield

        await injector.disconnect()

    app_router.lifespan_context = injector_lifespan


def _inject_app_with_events(app: FastAPI, collect_deps_fn: Callable[[], None]) -> None:
    app.on_event("startup")(collect_deps_fn)
    app.on_event("startup")(app.state.dependency_injector.connect)
    app.on_event("shutdown")(app.state.dependency_injector.disconnect)


def _collect_dependencies(
    injector: DependencyInjector,
    app_router: routing.APIRouter,
) -> None:
    """
    It walks through all routers and collects all app dependencies to connect them later
    """
    for dependencies in app_router.dependencies:
        if not dependencies.dependency:
            continue

        for dependency in _find_fastapi_dependencies(dependencies.dependency):
            _inspect_and_lazy_inject(dependency, injector)

    for route in app_router.routes:
        if not isinstance(route, RouterProtocol):
            error_msg = (
                "Unexpected router class. "
                f"Router must contain .endpoint property with handler function: {route}"
            )
            raise TypeError(error_msg)

        if isinstance(route, FastAPIRouterProtocol):
            for dependencies in route.dependencies:
                for dependency in _find_fastapi_dependencies(dependencies.dependency):
                    _inspect_and_lazy_inject(dependency, injector)

        for dependency in _find_fastapi_dependencies(route.endpoint):
            _inspect_and_lazy_inject(dependency, injector)


def _inspect_and_lazy_inject(obj: object, injector: DependencyInjector) -> None:
    for dependency in injector.inspect(obj).deps.values():
        injector.lazy_inject(dependency)


def _find_fastapi_dependencies(dependency: Callable[..., Any]) -> Iterator[Callable[..., Any]]:
    """
    Recursively finds all FastAPI dependencies.
    It looks for FastAPI's Depends() in default arguments and in type annotations.
    """
    signature = inspect.signature(dependency)

    for param in signature.parameters.values():
        if isinstance(param.default, Depends) and param.default.dependency:
            yield from _find_fastapi_dependencies(param.default.dependency)

        type_hint = param.annotation
        if get_origin(type_hint) is not Annotated:
            continue

        for annotation in type_hint.__metadata__:
            if not isinstance(annotation, Depends):
                continue

            if annotation.dependency:
                yield from _find_fastapi_dependencies(annotation.dependency)

    yield dependency
