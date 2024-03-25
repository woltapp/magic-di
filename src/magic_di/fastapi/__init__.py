"""
Package containing tools for integrating Dependency Injector with FastAPI framework.
"""

from ._app import inject_app
from ._provide import Provide, Provider

__all__ = ("inject_app", "Provide", "Provider")
