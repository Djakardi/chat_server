from collections import defaultdict
from typing import Any, Callable
import inspect

from proto import BasePackage, BaseProtoClient


def safe_call(func: Callable, package: BasePackage, kwargs: dict[str, Any]) -> Any:
    sig = inspect.signature(func)
    params = list(sig.parameters.values())[1:]
    filtered_kwargs = {}
    for param in params:
        if param.name in kwargs:
            filtered_kwargs[param.name] = kwargs[param.name]
    return func(package, **filtered_kwargs)


class NotHandledException(Exception):
    pass


class HandlerData[PackageT: BasePackage]:
    def __init__(
        self,
        handler: Callable[[PackageT], Any],
        filters: list[Callable[[PackageT], bool]],
    ):
        self.handler = handler
        self.filters = filters

    async def handle_package(self, package: PackageT, context: dict[str, Any]) -> Any:
        for filter_func in self.filters:
            if not filter_func(package):
                raise NotHandledException("Package did not pass filter")
        return await safe_call(self.handler, package, context)


class Dispatcher:
    def __init__(self, context: dict[str, Any] | None = None):
        self._handlers: dict[type, list[HandlerData]] = defaultdict(list)
        self.context = context or {}

    def register_handler[PackageT: BasePackage](
        self,
        package_type: type[PackageT],
        handler: Callable[[PackageT], Any],
        *filters: Callable[[PackageT], bool],
    ) -> None:
        self._handlers[package_type].append(HandlerData(handler, list(filters)))

    def register[PackageT: BasePackage](
        self, package_type: type[PackageT], *filters: Callable[[PackageT], bool]
    ) -> Callable[..., None]:
        def decorator(handler: Callable[[PackageT], Any]) -> Any:
            self.register_handler(package_type, handler, *filters)

        return decorator

    async def __call__(self, client: BaseProtoClient, package: BasePackage):
        return await self.dispatch(package, {"client": client})

    async def dispatch(
        self, package: BasePackage, current_context: dict[str, Any]
    ) -> Any:
        context = self.context.copy()
        context.update(current_context)

        for handler_data in self._handlers.get(type(package), []):
            try:
                return await handler_data.handle_package(package, context)
            except NotHandledException:
                continue
