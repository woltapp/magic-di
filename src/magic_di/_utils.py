from typing import Any, Type, TypeVar, Union, cast, get_args
from typing import get_type_hints as _get_type_hints

from magic_di import ConnectableProtocol

LegacyUnionType = type(Union[object, None])

try:
    from types import UnionType  # type: ignore
except ImportError:
    UnionType = LegacyUnionType  # type: ignore[misc, assignment]


T = TypeVar("T")

NONE_TYPE: Type = type(None)


def is_class(obj: Any) -> bool:
    return isinstance(obj, type)


def get_cls_from_optional(cls: T) -> T:
    """
    Extract the actual class from a union that includes None.
    If it is not a union type hint, it returns the same type hint.
    Example:
        >>> get_cls_from_optional(Union[str, None])
        str
        >>> get_cls_from_optional(str | None)
        str
        >>> get_cls_from_optional(str | None)
        str
        >>> get_cls_from_optional(int)
        int
    Args:
        cls (T): Type hint for class
    Returns:
        T: Extracted class
    """
    if not isinstance(cls, (UnionType, LegacyUnionType)):
        return cls

    args = get_args(cls)
    if len(args) != 2:
        return cast(T, cls)

    if NONE_TYPE not in args:
        return cast(T, cls)

    for typo in args:
        try:
            if not issubclass(typo, NONE_TYPE):
                return cast(T, typo)
        except TypeError:
            ...

    return cast(T, cls)


def safe_is_subclass(sub_cls: Any, cls: Type) -> bool:
    try:
        return issubclass(sub_cls, cls)
    except TypeError:
        return False


def is_injectable(cls: Any) -> bool:
    """
    Check if a class is a subclass of ConnectableProtocol.

    Args:
        cls (Any): The class to check.

    Returns:
        bool: True if the class is a subclass of ConnectableProtocol, False otherwise.
    """
    return safe_is_subclass(cls, ConnectableProtocol)


def get_type_hints(obj: Any, *, include_extras=False) -> dict[str, type]:
    try:
        if is_class(obj):
            return _get_type_hints(obj.__init__, include_extras=include_extras)  # type: ignore[misc]
        else:
            return _get_type_hints(obj, include_extras=include_extras)
    except TypeError:
        return {}
