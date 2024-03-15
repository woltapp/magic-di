import inspect
from collections.abc import Callable
from typing import Any

from magic_di._signature import Signature
from magic_di._utils import get_type_hints


class InjectorError(Exception): ...


class InjectionError(InjectorError):
    def __init__(self, obj: Callable[..., Any], signature: Signature[Any]):
        self.obj = obj
        self.signature = signature

    def __str__(self) -> str:
        return self._build_error_message()

    def _build_error_message(self) -> str:
        try:
            full_signature = inspect.signature(self.obj)
            type_hints = get_type_hints(self.obj)

            missing_kwargs = {
                param.name: type_hints.get(param.annotation) or param.annotation
                for param in full_signature.parameters.values()
                if param.name not in self.signature.deps and param.default is full_signature.empty
            }

            missing_kwargs_str = "\n".join(
                [f"{name}: {hint!r}" for name, hint in missing_kwargs.items()],
            )

            object_location = _get_object_source_location(self.obj)
        except Exception:  # noqa: BLE001
            return (
                f"Failed to inject {self.obj}. Missing arguments\n"
                f"Hint: Did you forget to make these dependencies connectable? "
                f"(Inherit from Connectable or "
                f"implement __connect__ and __disconnect__ methods)"
            )

        return (
            f"Failed to inject {self.obj}. \n"
            f"{object_location}\n\n"
            f"Missing arguments:\n"
            f"{missing_kwargs_str}\n\n"
            f"Hint: Did you forget to make these dependencies connectable? "
            f"(Inherit from Connectable or "
            f"implement __connect__ and __disconnect__ methods)"
        )


class InspectionError(InjectorError):
    def __init__(self, obj: Any):
        self.obj = obj

    def __str__(self) -> str:
        return self._build_error_message()

    def _build_error_message(self) -> str:
        object_location = _get_object_source_location(self.obj)

        return f"Failed to inspect {self.obj}. \n{object_location}\nSee the exception above"


def _get_object_source_location(obj: Callable[..., Any]) -> str:
    try:
        _, obj_line_number = inspect.getsourcelines(obj)
        source_file = inspect.getsourcefile(obj)
    except Exception:  # noqa: BLE001
        return ""

    return f"{source_file}:{obj_line_number}"
