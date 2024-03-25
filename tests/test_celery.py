import contextlib
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Thread
from typing import Iterator, cast
from unittest.mock import MagicMock, call

import pytest
from celery import Celery
from celery.bin.celery import celery  # type: ignore[import]
from fastapi import FastAPI
from magic_di import DependencyInjector
from magic_di.celery import (
    PROVIDE,
    BaseCeleryConnectableDeps,
    InjectableCeleryTask,
    get_celery_loader,
)
from starlette.testclient import TestClient

from tests.conftest import AnotherDatabase, Service

TEST_ERR_MSG = "TEST_ERR_MSG"


@pytest.fixture(scope="module")
def injector() -> DependencyInjector:
    return DependencyInjector()


@contextmanager
def create_celery(
    injector: DependencyInjector,
    *,
    use_broker_and_backend: bool,
) -> Iterator[Celery]:
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        yield Celery(
            loader=get_celery_loader(injector),
            task_cls=InjectableCeleryTask,
            broker="memory://" if use_broker_and_backend else None,
            backend=f"db+sqlite:///{temp_file.name}" if use_broker_and_backend else None,
        )


@pytest.fixture(scope="module")
def celery_app(injector: DependencyInjector) -> Iterator[Celery]:
    with create_celery(injector, use_broker_and_backend=True) as app:
        yield app


@pytest.fixture(scope="module")
def service_ping_task(celery_app: Celery) -> InjectableCeleryTask:
    @celery_app.task
    async def service_ping(arg1: int, arg2: str, service: Service = PROVIDE) -> tuple:
        return arg1, arg2, service.is_alive()

    return cast(InjectableCeleryTask, service_ping)


@pytest.fixture(scope="module")
def service_ping_task_sync(celery_app: Celery) -> InjectableCeleryTask:
    @celery_app.task
    def service_ping_sync(arg1: int, arg2: str, service: Service = PROVIDE) -> tuple:
        return arg1, arg2, service.is_alive()

    return cast(InjectableCeleryTask, service_ping_sync)


@pytest.fixture(scope="module")
def service_ping_class_based_task(celery_app: Celery) -> InjectableCeleryTask:
    @dataclass
    class Deps(BaseCeleryConnectableDeps):
        db: AnotherDatabase

    class SyncServicePingTask(InjectableCeleryTask):
        deps: Deps

        async def run(self, arg1: int, arg2: str):
            return arg1, arg2, self.deps.db.connected

    return SyncServicePingTask()


@pytest.fixture(scope="module")
def service_ping_class_based_task_sync(celery_app: Celery) -> InjectableCeleryTask:
    @dataclass
    class Deps(BaseCeleryConnectableDeps):
        db: AnotherDatabase

    class ServicePingTask(InjectableCeleryTask):
        deps: Deps

        def run(self, arg1: int, arg2: str):
            return arg1, arg2, self.deps.db.connected

    return ServicePingTask()


@pytest.fixture(scope="module")
def run_celery(
    celery_app,
    service_ping_task,
    service_ping_task_sync,
    service_ping_class_based_task,
    service_ping_class_based_task_sync,
):
    celery_app.register_task(service_ping_class_based_task)
    celery_app.register_task(service_ping_class_based_task_sync)

    thread = Thread(
        target=celery_app.worker_main,
        args=(["worker", "--loglevel=DEBUG", "-c 1"],),
        daemon=True,
    )
    thread.start()

    yield celery_app

    with contextlib.suppress(SystemExit):
        (celery.main(args=["control", "shutdown"]))

    thread.join()


def test_async_function_based_tasks(
    run_celery: Celery,
    service_ping_task: InjectableCeleryTask,
):
    result = service_ping_task.apply_async(args=(1337, "leet")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1337, "leet", True]

    result = service_ping_task.apply_async(args=(1010, "wowowo")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "wowowo", True]

    result = service_ping_task.apply(args=(1010, "123")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "123", True]


@pytest.mark.asyncio()
async def test_sync_function_based_tasks(
    run_celery: Celery,
    service_ping_task_sync: InjectableCeleryTask,
):
    result = service_ping_task_sync.apply_async(args=(1337, "leet")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1337, "leet", True]

    result = service_ping_task_sync.apply_async(args=(1010, "wowowo")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "wowowo", True]

    result = service_ping_task_sync.apply(args=(1010, "123")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "123", True]


def test_async_class_based_tasks(
    run_celery: Celery,
    service_ping_class_based_task: InjectableCeleryTask,
):
    result = service_ping_class_based_task.apply_async(args=(1337, "leet")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1337, "leet", True]

    result = service_ping_class_based_task.apply_async(args=(1010, "wowowo")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "wowowo", True]

    result = service_ping_class_based_task.apply(args=(1010, "123")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "123", True]


def test_sync_class_based_tasks(
    run_celery: Celery,
    service_ping_class_based_task_sync: InjectableCeleryTask,
):
    result = service_ping_class_based_task_sync.apply_async(args=(1337, "leet")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1337, "leet", True]

    result = service_ping_class_based_task_sync.apply_async(args=(1010, "wowowo")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "wowowo", True]

    result = service_ping_class_based_task_sync.apply(args=(1010, "123")).get(
        disable_sync_subtasks=False,
    )
    assert list(result) == [1010, "123", True]


def test_retries_func_based_task():
    with create_celery(DependencyInjector(), use_broker_and_backend=False) as app:
        app.conf.update({"task_always_eager": True})
        mock = MagicMock()

        @app.task(max_retries=3, autoretry_for=(ValueError,), retry_backoff=0)
        async def ping_task(service: Service = PROVIDE) -> None:
            assert service.is_alive()
            mock()
            raise ValueError(TEST_ERR_MSG)

        with pytest.raises(ValueError, match=TEST_ERR_MSG):
            _ = ping_task.apply_async().get(disable_sync_subtasks=False)


def test_retries_class_based_task():
    with create_celery(DependencyInjector(), use_broker_and_backend=False) as app:
        app.conf.update({"task_always_eager": True})

        mock = MagicMock()

        class PingTask(InjectableCeleryTask):
            max_retries = 3
            autoretry_for = (ValueError,)
            retry_backoff = 0

            async def run(self, service: Service = PROVIDE):
                assert service.is_alive()
                mock()
                raise ValueError(TEST_ERR_MSG)

        ping_class_task = app.register_task(PingTask)

        with pytest.raises(ValueError, match=TEST_ERR_MSG):
            ping_class_task.apply_async().get(disable_sync_subtasks=False)

        assert len(mock.call_args_list) == PingTask.max_retries + 1


@pytest.mark.parametrize(
    ("task_always_eager", "use_broker_and_backend", "expected_mock_calls"),
    [
        (False, True, [call()]),
        (True, False, [call(), call()]),
        (True, True, [call(), call()]),
    ],
)
@pytest.mark.asyncio()
async def test_async_function_based_tasks_inside_event_loop(
    service_ping_task: InjectableCeleryTask,
    *,
    task_always_eager: bool,
    use_broker_and_backend: bool,
    expected_mock_calls: list,
):
    injector = DependencyInjector()

    with create_celery(injector, use_broker_and_backend=use_broker_and_backend) as app:
        app.conf.update({"task_always_eager": task_always_eager})

        mock = MagicMock()

        @app.task
        async def ping_task(
            arg1: int,
            arg2: str,
            service: Service = PROVIDE,
        ) -> tuple:
            mock()
            return arg1, arg2, service.is_alive()

        fastapi_app = FastAPI()

        @fastapi_app.get("/")
        async def handler():
            ping_task.apply_async(args=(1337, "leet"))
            ping_task.apply(args=(1337, "leet-2"))
            return {"ok": True}

        with TestClient(fastapi_app) as client:
            resp = client.get("/")
            assert resp.json() == {"ok": True}

        assert mock.call_args_list == expected_mock_calls
