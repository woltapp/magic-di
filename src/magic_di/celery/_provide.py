from typing import Any


def Provide() -> Any:  # noqa: ANN401, N802
    """
    An empty function that returns an ellipsis
    It's used only to pass celery’s strict_typing check.
    It is not necessary to use Provide() if you disable the `strict_typing` option in Celery’s configuration.
    """
    return ...
