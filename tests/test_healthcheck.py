from dataclasses import dataclass

import pytest
from magic_di import Connectable, DependencyInjector
from magic_di.healthcheck import DependenciesHealthcheck


@dataclass
class PingableDatabase(Connectable):
    ping_count: int = 0

    async def __ping__(self) -> None:
        self.ping_count += 1


@dataclass
class Service(Connectable):
    ping_count: int = 0


@dataclass
class PingableService(Connectable):
    db: PingableDatabase
    ping_count: int = 0

    async def __ping__(self) -> None:
        self.ping_count += 1


@pytest.mark.asyncio()
async def test_healthcheck(injector: DependencyInjector) -> None:
    async def main(_: PingableService) -> None: ...

    await injector.inject(main)()

    injected_db = injector.inject(PingableDatabase)()
    injected_srv = injector.inject(PingableService)()
    injected_srv_not_pingable = injector.inject(Service)()

    assert injected_db.ping_count == 0
    assert injected_srv.ping_count == 0
    assert injected_srv_not_pingable.ping_count == 0

    healthcheck = injector.inject(DependenciesHealthcheck)()

    await healthcheck.ping_dependencies(max_concurrency=1)

    assert injected_db.ping_count == 1
    assert injected_srv.ping_count == 1
    assert injected_srv_not_pingable.ping_count == 0

    await healthcheck.ping_dependencies(max_concurrency=3)

    assert injected_db.ping_count == 2  # noqa: PLR2004
    assert injected_srv.ping_count == 2.0  # noqa: PLR2004
    assert injected_srv_not_pingable.ping_count == 0
