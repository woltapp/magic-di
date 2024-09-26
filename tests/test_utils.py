import asyncio

from magic_di import ConnectableProtocol, DependencyInjector
from magic_di.utils import inject_and_run

from tests.conftest import Repository


def test_inject_and_run_sync(injector: DependencyInjector) -> None:
    def main(repo: Repository) -> Repository:
        assert repo.connected
        assert repo.db.connected
        return repo

    repo = inject_and_run(main, injector=injector)
    assert not repo.connected
    assert not repo.db.connected


def test_inject_and_run_async(injector: DependencyInjector) -> None:
    async def main(repo: Repository) -> Repository:
        assert await repo.do_something()
        assert repo.connected
        assert repo.db.connected
        return repo

    repo = inject_and_run(main, injector=injector)
    assert not repo.connected
    assert not repo.db.connected


def test_inject_and_run_async_proper_event_loop(injector: DependencyInjector) -> None:
    class DependencyWithEventLoop(ConnectableProtocol):
        def __init__(self) -> None:
            self.event_loop = asyncio.get_event_loop()

    async def main(dependency: DependencyWithEventLoop) -> None:
        event_loop = asyncio.get_running_loop()
        assert event_loop is dependency.event_loop

    inject_and_run(main, injector=injector)
