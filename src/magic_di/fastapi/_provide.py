from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, Type, TypeVar

from fastapi import Depends, Request
from magic_di import DependencyInjector
from magic_di._injector import Injectable

T = TypeVar("T")


class FastAPIInjectionError(Exception):
    ...


class Provider:
    def __getitem__(self, obj: Type[T]) -> Type[T]:
        @lru_cache(maxsize=1)
        def get_dependency(injector: DependencyInjector) -> T:
            return injector.inject(obj)()

        def inject(request: Request) -> T:
            if not hasattr(request.app.state, "dependency_injector"):
                raise FastAPIInjectionError(
                    "FastAPI application is not injected. Did you forget to add `inject_app(app)`?"
                )

            injector = request.app.state.dependency_injector
            return get_dependency(injector)

        return Annotated[obj, Depends(inject), Injectable]  # type: ignore[return-value]


if TYPE_CHECKING:
    from typing import Union as Provide  # hack for mypy
else:
    Provide = Provider()
