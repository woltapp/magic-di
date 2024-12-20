from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

import pytest

from magic_di import Connectable, DependencyInjector


class ConnectableClient(Connectable):
    connected: bool = False

    async def __connect__(self) -> None:
        self.connected = True

    async def __disconnect__(self) -> None:
        self.connected = False


class Database(ConnectableClient): ...


class AnotherDatabase(ConnectableClient): ...


class Repository(ConnectableClient):
    def __init__(self, db: Database, some_params: int = 1) -> None:
        self.db = db
        self.some_params = some_params

    async def do_something(self) -> bool:
        await asyncio.sleep(0.1)
        return self.connected and self.db.connected


class AsyncWorkers(ConnectableClient): ...


@dataclass
class Service(ConnectableClient):
    repo: Repository
    workers: AsyncWorkers | None

    def is_alive(self) -> bool:
        assert self.workers
        return self.repo.connected and self.workers.connected


class NonConnectableDatabase: ...


@dataclass
class BrokenRepo:
    db: NonConnectableDatabase


@dataclass
class BrokenService:
    repo: BrokenRepo


class RepoInterface(Protocol): ...


@dataclass
class ServiceWithBindings:
    repo: RepoInterface


@pytest.fixture
def injector() -> DependencyInjector:
    return DependencyInjector()
