import inspect
from typing import Any, Callable

from magic_di._signature import Signature
from magic_di._utils import get_type_hints


class InjectorError(Exception):
    ...


class InjectionError(InjectorError):
    def __init__(self, obj: Callable, signature: Signature):
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
                if param.name not in self.signature.deps
                and param.default is full_signature.empty
            }

            missing_kwargs_str = "\n".join(
                [f"{name}: {repr(hint)}" for name, hint in missing_kwargs.items()]
            )

            object_location = _get_object_source_location(self.obj)

            return (
                f"Failed to inject {self.obj}. \n"
                f"{object_location}\n\n"
                f"Missing arguments:\n"
                f"{missing_kwargs_str}\n\n"
                f"Hint: Did you forget to make these dependencies connectable? "
                f"(Inherit from Connectable or implement __connect__ and __disconnect__ methods)"
            )
        except Exception:
            return (
                f"Failed to inject {self.obj}. Missing arguments\n"
                f"Hint: Did you forget to make these dependencies connectable? "
                f"(Inherit from Connectable or implement __connect__ and __disconnect__ methods)"
            )


class InspectionError(InjectorError):
    def __init__(self, obj: Any):
        self.obj = obj

    def __str__(self) -> str:
        return self._build_error_message()

    def _build_error_message(self) -> str:
        try:
            object_location = _get_object_source_location(self.obj)

            return (
                f"Failed to inspect {self.obj}. \n"
                f"{object_location}\n"
                "See the exception above"
            )
        except Exception:
            return f"Failed to inspect {self.obj}. \n" "See the exception above"


def _get_object_source_location(obj: Callable) -> str:
    try:
        _, obj_line_number = inspect.getsourcelines(obj)
        source_file = inspect.getsourcefile(obj)
        return f"{source_file}:{obj_line_number}"
    except Exception:
        return ""
