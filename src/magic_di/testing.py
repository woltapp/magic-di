from unittest.mock import AsyncMock

from magic_di import ConnectableProtocol


def get_injectable_mock_cls(return_value):
    class ClientMetaclassMock(ConnectableProtocol):
        __annotations__ = {}

        def __new__(cls, *_, **__):
            return return_value

    return ClientMetaclassMock


class InjectableMock(AsyncMock):
    """
    You can use this mock to override dependencies in tests
    and use AsyncMock instead of a real class instance

    Example:
        @pytest.fixture()
        def client():
          injector = DependencyInjector()

          with injector.override({Service: InjectableMock().mock_cls}):
            with TestClient(app) as client:
                yield client

        def test_http_handler(client):
          resp = client.post('/hello-world')

          assert resp.status_code == 200
    """

    @property
    def mock_cls(self):
        return get_injectable_mock_cls(self)

    async def __connect__(self): ...

    async def __disconnect__(self): ...

    def __call__(self, *args, **kwargs):
        return self.__class__(*args, **kwargs)
