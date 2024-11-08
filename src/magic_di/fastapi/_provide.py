from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, TypeVar

from fastapi import Depends, Request

from magic_di._injector import Injectable

if TYPE_CHECKING:
    from magic_di import DependencyInjector

T = TypeVar("T")


class FastAPIInjectionError(Exception): ...


if TYPE_CHECKING:
    from typing import Union as Provide  # hack for mypy # noqa: FIX004
else:

    class Provide:
        def __class_getitem__(cls, obj: T) -> T:
            @lru_cache(maxsize=1)
            def get_dependency(injector: DependencyInjector) -> T:
                return injector.inject(obj)()

            def inject(request: Request) -> T:
                if not hasattr(request.app.state, "dependency_injector"):
                    error_msg = (
                        "FastAPI application is not injected. "
                        "Did you forget to add `inject_app(app)`?"
                    )
                    raise FastAPIInjectionError(error_msg)

                injector = request.app.state.dependency_injector
                return get_dependency(injector)

            return Annotated[obj, Depends(inject), Injectable]  # type: ignore[return-value]
