from __future__ import annotations

from typing import Any, Optional, TypeVar, cast, get_args
from typing import get_type_hints as _get_type_hints

from magic_di import ConnectableProtocol

LegacyUnionType = type(object | None)
LegacyOptionalType = type(Optional[object])  # noqa: UP007

try:
    from types import UnionType  # type: ignore[import-error,unused-ignore]
except ImportError:
    UnionType = LegacyUnionType  # type: ignore[misc]


T = TypeVar("T")

NONE_TYPE: type = type(None)


def is_class(obj: Any) -> bool:
    return isinstance(obj, type)


def get_cls_from_optional(cls: T) -> T:
    """
    Extract the actual class from a union that includes None.
    If it is not a union type hint, it returns the same type hint.
    Example:
    ``` py
        >>> get_cls_from_optional(Union[str, None])
        str
        >>> get_cls_from_optional(str | None)
        str
        >>> get_cls_from_optional(str | None)
        str
        >>> get_cls_from_optional(int)
        int
        >>> get_cls_from_optional(Optional[str])
        str
    ```
    Args:
        cls (T): Type hint for class
    Returns:
        T: Extracted class
    """
    if not isinstance(cls, UnionType | LegacyUnionType | LegacyOptionalType):
        return cls

    args = get_args(cls)

    optional_type_hint_args_len = 2
    if len(args) != optional_type_hint_args_len:
        return cast(T, cls)

    if NONE_TYPE not in args:
        return cast(T, cls)

    for typo in args:
        if not safe_is_subclass(typo, NONE_TYPE):
            return cast(T, typo)

    return cast(T, cls)


def safe_is_subclass(sub_cls: Any, cls: type) -> bool:
    try:
        return issubclass(sub_cls, cls)
    except TypeError:
        return False


def safe_is_instance(sub_cls: Any, cls: type) -> bool:
    try:
        return isinstance(sub_cls, cls)
    except TypeError:
        return False


def is_connectable(cls: Any) -> ConnectableProtocol | None:
    """
    Check if a class is a subclass of ConnectableProtocol.

    Args:
        cls (Any): The class to check.

    Returns:
        ConnectableProtocol | None: return instance if the class
        is a subclass of ConnectableProtocol, None otherwise.
    """
    connectable = safe_is_subclass(cls, ConnectableProtocol) or safe_is_instance(
        cls,
        ConnectableProtocol,
    )
    return cls if connectable else None


def get_type_hints(obj: Any, *, include_extras: bool = False) -> dict[str, type]:
    try:
        if is_class(obj):
            return _get_type_hints(obj.__init__, include_extras=include_extras)

        return _get_type_hints(obj, include_extras=include_extras)
    except TypeError:
        return {}
