from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from magic_di import ConnectableProtocol


def get_injectable_mock_cls(return_value: Any) -> type[ConnectableProtocol]:
    class ClientMetaclassMock(ConnectableProtocol):
        __annotations__ = {}

        def __new__(cls, *_: Any, **__: Any) -> Any:
            return return_value

    return ClientMetaclassMock


class InjectableMock(AsyncMock):
    """
    You can use this mock to override dependencies in tests
    and use AsyncMock instead of a real class instance

    Example:
    ``` py
    @pytest.fixture()
    def client():
      injector = DependencyInjector()

      with injector.override({Service: InjectableMock().mock_cls}):
        with TestClient(app) as client:
            yield client

    def test_http_handler(client):
      resp = client.post('/hello-world')

      assert resp.status_code == 200
    ```
    """

    @property
    def mock_cls(self) -> type[ConnectableProtocol]:
        return get_injectable_mock_cls(self)

    async def __connect__(self) -> None: ...

    async def __disconnect__(self) -> None: ...

    def __call__(self, *args: Any, **kwargs: Any) -> InjectableMock:
        return self.__class__(*args, **kwargs)
