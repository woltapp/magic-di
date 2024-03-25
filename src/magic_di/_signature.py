from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Signature(Generic[T]):
    obj: T
    is_injectable: bool
    deps: dict[str, type] = field(default_factory=dict)
    kwargs: dict[str, type] = field(default_factory=dict)
    injector_arg: str | None = None
