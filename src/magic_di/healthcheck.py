import asyncio
from asyncio import Future
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol

from magic_di import Connectable, ConnectableProtocol, DependencyInjector


class PingableProtocol(ConnectableProtocol, Protocol):
    async def __ping__(self) -> None: ...


@dataclass
class DependenciesHealthcheck(Connectable):
    """
    Injectable Healthcheck component that pings all injected dependencies
    that implement the PingableProtocol

    Example usage:

    ``` py
    from app.components.services.health import DependenciesHealthcheck

    async def main(redis: Redis, deps_healthcheck: DependenciesHealthcheck) -> None:
        await deps_healthcheck.ping_dependencies()  # redis will be pinged if it has method __ping__

    inject_and_run(main)
    ```
    """

    injector: DependencyInjector

    async def ping_dependencies(self, max_concurrency: int = 1) -> None:
        """
        Ping all dependencies that implement the PingableProtocol

        :param max_concurrency: Maximum number of concurrent pings
        """
        tasks: set[Future[Any]] = set()

        try:
            for dependency in self.injector.get_dependencies_by_interface(PingableProtocol):
                future = asyncio.ensure_future(self.ping(dependency))
                tasks.add(future)

                if len(tasks) >= max_concurrency:
                    tasks, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

            if tasks:
                await asyncio.gather(*tasks)
                tasks = set()

        finally:
            for task in tasks:
                task.cancel()

            if tasks:
                with suppress(asyncio.CancelledError):
                    await asyncio.gather(*tasks)

    async def ping(self, dependency: PingableProtocol) -> None:
        """
        Ping a single dependency

        :param dependency: Dependency to ping
        """
        dependency_name = dependency.__class__.__name__
        self.injector.logger.debug("Pinging dependency %s...", dependency_name)

        await dependency.__ping__()

        self.injector.logger.debug("Dependency %s is healthy", dependency_name)
