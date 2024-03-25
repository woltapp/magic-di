from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from magic_di import DependencyInjector
from magic_di.fastapi import Provide, inject_app
from magic_di.fastapi._provide import FastAPIInjectionError
from starlette.testclient import TestClient

from tests.conftest import Database, Service


def test_app_injection(injector: DependencyInjector) -> None:
    app = inject_app(FastAPI(), injector=injector)

    @app.get(path="/hello-world")
    def hello_world(service: Provide[Service], some_query: str) -> dict[str, str | bool]:  # noqa: FA102
        assert isinstance(service, Service)
        return {"query": some_query, "is_alive": service.is_alive()}

    with TestClient(app) as client:
        resp = client.get("/hello-world?some_query=my-query")
        assert resp.json() == {"query": "my-query", "is_alive": True}


def test_app_injection_with_depends(injector: DependencyInjector) -> None:
    connected_global_dependency = False

    class GlobalConnect(Database): ...

    def global_dependency(dep: Provide[GlobalConnect]) -> None:
        nonlocal connected_global_dependency
        connected_global_dependency = dep.connected

    app = inject_app(
        FastAPI(
            dependencies=[Depends(global_dependency)],
        ),
        injector=injector,
    )

    class MiddlewareNonConnectable:
        creds: str = "secret_creds"

        def get_creds(self, value: str | None = None) -> str:  # noqa: FA102
            return value or self.creds

    class AnotherDatabase(Database): ...

    def assert_db_connected(db: Provide[AnotherDatabase]) -> bool:
        assert db.connected
        return db.connected

    def get_creds(
        mw: Provide[MiddlewareNonConnectable],
        *,
        db_connect: bool = Depends(assert_db_connected),
    ) -> str:
        if db_connect:
            return mw.get_creds()

        raise ValueError

    @app.get(path="/hello-world", dependencies=[])
    def hello_world(
        service: Provide[Service],
        creds: Annotated[str, Depends(get_creds)],
    ) -> dict[str, str | bool]:  # noqa: FA102
        assert isinstance(service, Service)
        return {"creds": creds, "is_alive": service.is_alive()}

    with TestClient(app) as client:
        resp = client.get("/hello-world?some_query=my-query")
        assert resp.json() == {"creds": "secret_creds", "is_alive": True}
        assert connected_global_dependency


@pytest.mark.parametrize("use_deprecated_events", [False, True])
def test_app_injection_clients_connect(
    injector: DependencyInjector,
    *,
    use_deprecated_events: bool,
) -> None:
    app = inject_app(
        FastAPI(),
        injector=injector,
        use_deprecated_events=use_deprecated_events,
    )

    router = APIRouter()

    @router.get(path="/hello-world")
    def hello_world(service: Provide[Service]) -> dict[str, bool]:  # noqa: FA102
        assert service.workers

        return {
            "service_connected": service.connected,
            "workers_connected": service.workers.connected,
            "repo_connected": service.repo.connected,
            "db_connected": service.repo.db.connected,
        }

    app.include_router(router)

    with TestClient(app) as client:
        resp = client.get("/hello-world")
        assert resp.json() == {
            "db_connected": True,
            "repo_connected": True,
            "service_connected": True,
            "workers_connected": True,
        }

    resp = client.get("/hello-world")
    assert resp.json() == {
        "db_connected": False,
        "repo_connected": False,
        "service_connected": False,
        "workers_connected": False,
    }


def test_app_injection_without_registered_injector(injector: DependencyInjector) -> None:
    app = FastAPI()

    @app.get(path="/hello-world")
    def hello_world(service: Provide[Service]) -> str:
        return "OK"

    with TestClient(app) as client, pytest.raises(FastAPIInjectionError):
        client.get("/hello-world")
