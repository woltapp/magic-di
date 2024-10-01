# magic-di

[![PyPI](https://img.shields.io/pypi/v/magic-di?style=flat-square)](https://pypi.python.org/pypi/magic-di/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/magic-di?style=flat-square)](https://pypi.python.org/pypi/magic-di/)
[![PyPI - License](https://img.shields.io/pypi/l/magic-di?style=flat-square)](https://pypi.python.org/pypi/magic-di/)
[![Coookiecutter - Wolt](https://img.shields.io/badge/cookiecutter-Wolt-00c2e8?style=flat-square&logo=cookiecutter&logoColor=D4AA00&link=https://github.com/woltapp/wolt-python-package-cookiecutter)](https://github.com/woltapp/wolt-python-package-cookiecutter)


---

**Documentation**: [https://woltapp.github.io/magic-di](https://woltapp.github.io/magic-di)

**Source Code**: [https://github.com/woltapp/magic-di](https://github.com/woltapp/magic-di)

**PyPI**: [https://pypi.org/project/magic-di/](https://pypi.org/project/magic-di/)

---

Dependency Injector with minimal boilerplate code, built-in support for FastAPI and Celery, and seamless integration to basically anything.

## Contents
* [Install](#install)
* [Getting Started](#getting-started)
* [Clients Configuration](#clients-configuration)
  * [Zero config clients](#zero-config-clients)
  * [Clients with Config](#clients-with-config)
* [Using interfaces instead of implementations](#using-interfaces-instead-of-implementations)
* [Integration with Celery](#integration-with-celery)
  * [Function based tasks](#function-based-celery-tasks)
  * [Class based tasks](#class-based-celery-tasks)
* [Custom integrations](#custom-integrations)
  * [Manual injection](#manual-injection)
* [Forced injections](#forced-injections)
* [Healthcheck](#healthcheck)
* [Testing](#testing)
  * [Default simple mock](#default-simple-mock)
  * [Custom mocks](#custom-mocks)
* [Alternatives](#alternatives)
* [Development](#development)


## Install
```bash
pip install magic-di
```

With FastAPI integration:
```bash
pip install 'magic-di[fastapi]'
```

With Celery integration:
```bash
pip install 'magic-di[celery]'
```

## Getting Started

```python
from fastapi import FastAPI

from magic_di import Connectable
from magic_di.fastapi import inject_app, Provide

app = inject_app(FastAPI())


class Database:
    connected: bool = False

    def __connect__(self):
        self.connected = True

    def __disconnect__(self):
        self.connected = False


class Service(Connectable):
    def __init__(self, db: Database):
        self.db = db

    def is_connected(self):
        return self.db.connected


@app.get(path="/hello-world")
def hello_world(service: Provide[Service]) -> dict:
    return {
        "is_connected": service.is_connected()
    }
```

That's all!

This simple code will recursively inject all dependencies and connect them using the `__connect__` and `__disconnect__` magic methods.

But what happened there?
1) We created a new FastAPI app and injected it. The `inject_app` function makes the injector connect all clients on app startup and disconnect them on shutdown. That’s how you can open and close all connections (e.g., session to DB).
2) We defined new classes with `__connect__` and `__disconnect__` magic methods. __That’s how the injector finds classes that need to be injected__. The injector uses duck typing to check if some class has these methods. It means you don’t need to inherit from `ClientProtocol` (but you can to reduce the number of code lines).
3) Wrapped the `Service` type hint into `Provide` so that FastAPI can use our DI. __Please note__: you need to use `Provide` only in FastAPI endpoints, which makes your codebase independent from FastAPI and this Dependency Injector.
4) PROFIT!

As you can see, in this example, you don’t need to write special constructors to store your dependencies in global variables. All you need to do to complete the startup logic is to write it in the `__connect__` method.


## Clients Configuration
This dependency injector promotes the idea of ‘zero-config clients’, but you can still use configurations if you prefer

### Zero config clients
Simply fetch everything needed from the environment. There is no need for an additional configuration file

```python
from dataclasses import dataclass, field

from pydantic import Field
from pydantic_settings import BaseSettings
from redis.asyncio import Redis as RedisClient, from_url


class RedisConfig(BaseSettings):
    url: str = Field(validation_alias='REDIS_URL')
    decode_responses: bool = Field(validation_alias='REDIS_DECODE_RESPONSES')


@dataclass
class Redis:
    config: RedisConfig = field(default_factory=RedisConfig)
    client: RedisClient = field(init=False)

    async def __connect__(self):
        self.client = await from_url(self.config.url, decode_responses=self.config.decode_responses)
        await self.client.ping()

    async def __disconnect__(self):
        await self.client.close()

    @property
    def db(self) -> RedisClient:
        return self.client


Redis()  # works even without passing arguments in the constructor.
```

As an alternative, you can inject configs instead of using default factories.

```python
from dataclasses import dataclass, field

from pydantic import Field
from pydantic_settings import BaseSettings
from redis.asyncio import Redis as RedisClient, from_url

from magic_di import Connectable, DependencyInjector


class RedisConfig(Connectable, BaseSettings):
    url: str = Field(validation_alias='REDIS_URL')
    decode_responses: bool = Field(validation_alias='REDIS_DECODE_RESPONSES')


@dataclass
class Redis:
    config: RedisConfig
    client: RedisClient = field(init=False)

    async def __connect__(self):
        self.client = await from_url(self.config.url, decode_responses=self.config.decode_responses)
        await self.client.ping()

    async def __disconnect__(self):
        await self.client.close()

    @property
    def db(self) -> RedisClient:
        return self.client


injector = DependencyInjector()
redis = injector.inject(Redis)()  # works even without passing arguments in the constructor.

async with injector:
    await redis.db.ping()
```

## Using interfaces instead of implementations
Sometimes, you may not want to stick to a certain interface implementation everywhere. Therefore, you can use interfaces (protocols, abstract classes) with Dependency Injection (DI). With DI, you can effortlessly bind an implementation to an interface and subsequently update it if necessary.

```python
from typing import Protocol

from fastapi import FastAPI

from magic_di import Connectable, DependencyInjector
from magic_di.fastapi import inject_app, Provide


class MyInterface(Protocol):
    def do_something(self) -> bool:
        ...


class MyInterfaceImplementation(Connectable):
    def do_something(self) -> bool:
        return True


app = inject_app(FastAPI())

injector = DependencyInjector()
injector.bind({MyInterface: MyInterfaceImplementation})


@app.get(path="/hello-world")
def hello_world(service: Provide[MyInterface]) -> dict:
    return {
        "result": service.do_something(),
    }
```

Using `injector.bind`, you can bind implementations that will be injected everywhere the bound interface is used.

## Integration with Celery

### Function based celery tasks

```python
from celery import Celery

from magic_di.celery import get_celery_loader, InjectableCeleryTask, PROVIDE

app = Celery(
    loader=get_celery_loader(),
    task_cls=InjectableCeleryTask,
)


@app.task
async def calculate(x: int, y: int, calculator: Calculator = PROVIDE):
    await calculator.calculate(x, y)
```


### Class based celery tasks

```python
from dataclasses import dataclass

from celery import Celery

from magic_di.celery import get_celery_loader, InjectableCeleryTask, BaseCeleryConnectableDeps, PROVIDE

app = Celery(
    loader=get_celery_loader(),
    task_cls=InjectableCeleryTask,
)


@dataclass
class CalculatorTaskDeps(BaseCeleryConnectableDeps):
    calculator: Calculator


class CalculatorTask(InjectableCeleryTask):
    deps: CalculatorTaskDeps

    async def run(self, x: int, y: int, smart_processor: SmartProcessor = PROVIDE):
        return smart_processor.process(
            await self.deps.calculator.calculate(x, y)
        )


app.register_task(CalculatorTask)
```

### Limitations
You could notice that in these examples tasks are using Python async/await.
`InjectableCeleryTask` provides support for writing async code. However, it still executes code synchronously.
**Due to this, getting results from async tasks is not possible in the following cases:**
* When the `task_always_eager` config flag is enabled and task creation occurs inside the running event loop (e.g., inside an async FastAPI endpoint)
* When calling the `.apply()` method inside running event loop (e.g., inside an async FastAPI endpoint)



## Custom integrations
For custom integration you can either use helper function `inject_and_run` or by using DependencyInjector manually
```python
from magic_di.utils import inject_and_run


async def main(worker: Worker):
    await worker.run()

if __name__ == '__main__':
    inject_and_run(main)
```

### Manual injection

```python
import asyncio

from magic_di import DependencyInjector


async def run_worker(worker: Worker):
    await worker.run()


async def main():
    injector = DependencyInjector()

    injected_fn = injector.inject(run_worker)

    async with injector:
        await injected_fn()

if __name__ == '__main__':
    asyncio.run(main())
```

## Forced injections
You can force injector to inject non-connectable dependencies with type hint annotation `Injectable`
```python
from typing import Annotated

from magic_di import Injectable, Connectable


class Service(Connectable):
    dependency: Annotated[NonConnectableDependency, Injectable]
```

## Healthcheck
You can implement `Pingable` protocol to define healthchecks for your clients. The `DependenciesHealthcheck` will call the `__ping__` method on all injected clients that implement this protocol.

```python
from magic_di.healthcheck import DependenciesHealthcheck


class Service(Connectable):
    def __init__(self, db: Database):
        self.db = db

    def is_connected(self):
        return self.db.connected

    async def __ping__(self) -> None:
        if not self.is_connected():
            raise Exception("Service is not connected")


@app.get(path="/hello-world")
def hello_world(service: Provide[Service]) -> dict:
    return {
        "is_connected": service.is_connected()
    }


@app.get(path="/healthcheck")
async def healthcheck_handler(healthcheck: Provide[DependenciesHealthcheck]) -> dict:
    await healthcheck.ping_dependencies()
    return {"alive": True}
```

## Testing
If you need to mock a dependency in tests, you can easily do so by using the `injector.override` context manager and still use this dependency injector.

To mock clients, you can use `InjectableMock` from the `testing` module.

### Default simple mock

```python
import pytest
from fastapi.testclient import TestClient
from my_app import app

from magic_di import DependencyInjector
from magic_di.testing import InjectableMock


@pytest.fixture()
def injector():
    return DependencyInjector()


@pytest.fixture()
def service_mock() -> Service:
    return InjectableMock()


@pytest.fixture()
def client(injector: DependencyInjector, service_mock: InjectableMock):
    with injector.override({Service: service_mock.mock_cls}):
        with TestClient(app) as client:
            yield client


def test_http_handler(client):
    resp = client.post('/hello-world')

    assert resp.status_code == 200
```

### Custom mocks
As an alternative, you can your use custom mocks.

```python
from magic_di.testing import get_injectable_mock_cls


@pytest.fixture()
def service_mock() -> Service:
    return SomeSmartServiceMock()


@pytest.fixture()
def client(injector: DependencyInjector, service_mock: Service):
    with injector.override({Service: get_injectable_mock_cls(service_mock)}):
        with TestClient(app) as client:
            yield client
```

## Alternatives

### [FastAPI's built-in dependency injection](https://fastapi.tiangolo.com/tutorial/dependencies/)

FastAPI's built-in DI is great, but it makes the project (and its business logic) dependent on FastAPI, `fastapi.Depends` specifically.

`magic-di` decouples DI from other dependencies while still offering seamless integration to FastAPI, for example.

### [python-dependency-injector](https://github.com/ets-labs/python-dependency-injector)

[python-dependency-injector](https://github.com/ets-labs/python-dependency-injector) is great, but it requires a notable amount of boilerplate code.

The goal of `magic-di` is to __reduce the amount of code as much as possible__ and get rid of enterprise code with countless configs, containers, and fabrics.
The philosophy of `magic-di` is that clients know how to configure themselves and perform all startup routines.


## Development

* Clone this repository
* Requirements:
  * [Poetry](https://python-poetry.org/)
  * Python 3.10+
* Create a virtual environment and install the dependencies

```sh
poetry install --all-extras
```

* Activate the virtual environment

```sh
poetry shell
```

### Testing

```sh
pytest
```

### Documentation

The documentation is automatically generated from the content of the [docs directory](https://github.com/woltapp/magic-di/tree/master/docs) and from the docstrings
 of the public signatures of the source code. The documentation is updated and published as a [Github Pages page](https://pages.github.com/) automatically as part each release.

### Releasing

Trigger the [Draft release workflow](https://github.com/woltapp/magic-di/actions/workflows/draft_release.yml)
(press _Run workflow_). This will update the changelog & version and create a GitHub release which is in _Draft_ state.

Find the draft release from the
[GitHub releases](https://github.com/woltapp/magic-di/releases) and publish it. When
 a release is published, it'll trigger [release](https://github.com/woltapp/magic-di/blob/master/.github/workflows/release.yml) workflow which creates PyPI
 release and deploys updated documentation.

### Pre-commit

Pre-commit hooks run all the auto-formatting (`ruff format`), linters (e.g. `ruff` and `mypy`), and other quality
 checks to make sure the changeset is in good shape before a commit/push happens.

You can install the hooks with (runs for each commit):

```sh
pre-commit install
```

Or if you want them to run only for each push:

```sh
pre-commit install -t pre-push
```

Or if you want e.g. want to run all checks manually for all files:

```sh
pre-commit run --all-files
```

---

This project was generated using the [wolt-python-package-cookiecutter](https://github.com/woltapp/wolt-python-package-cookiecutter) template.
