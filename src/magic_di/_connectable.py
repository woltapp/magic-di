from typing import Protocol, runtime_checkable


@runtime_checkable
class ConnectableProtocol(Protocol):
    """
    Interface for injectable clients.
    Adding these methods to your class will allow it to be dependency injectable.
    The dependency injector uses duck typing to check that the class
    implements the interface.
    This means that you do not need to inherit from this protocol.
    """

    async def __connect__(self) -> None: ...

    async def __disconnect__(self) -> None: ...


class Connectable:
    """
    You can inherit from this class to make the dependency visible for DI
    without adding these empty methods.
    """

    async def __connect__(self) -> None: ...

    async def __disconnect__(self) -> None: ...
