from magic_di.utils import inject_and_run
from tests.conftest import Repository


def test_inject_and_run_sync(injector):
    def main(repo: Repository) -> Repository:
        assert repo.connected
        assert repo.db.connected
        return repo

    repo = inject_and_run(main, injector=injector)
    assert not repo.connected
    assert not repo.db.connected


def test_inject_and_run_async(injector):
    async def main(repo: Repository) -> Repository:
        assert await repo.do_something()
        assert repo.connected
        assert repo.db.connected
        return repo

    repo = inject_and_run(main, injector=injector)
    assert not repo.connected
    assert not repo.db.connected
