"""
Package containing tools for integrating Dependency Injector with FastAPI framework.
"""

from ._app import inject_app
from ._provide import Provide  # type: ignore[attr-defined]

__all__ = ("inject_app", "Provide")
