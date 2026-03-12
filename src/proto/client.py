from abc import ABC
import asyncio
import logging
from typing import Any, Callable, Coroutine
import uuid

from .base import BasePackage
from .crypto import Cryptography
from .network import receive_package, send_package


logger = logging.getLogger(__name__)

HandlerType = Callable[["BaseProtoClient", BasePackage], Any]


class BaseProtoClient(ABC):
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        crypto: Cryptography,
        handler: HandlerType | None,
    ):
        self.crypto = crypto

        self._reader = reader
        self._writer = writer
        self._awaited_requests: dict[uuid.UUID, asyncio.Future] = {}

        self._loop = asyncio.create_task(self._loop_read())
        self._handler = handler
        self._loops: list[asyncio.Task] = []

    def _fail_awaited_requests(self, error: BaseException):
        for future in self._awaited_requests.values():
            if not future.done():
                future.set_exception(error)
        self._awaited_requests.clear()

    def disconnect(self):
        self._fail_awaited_requests(ConnectionError("Connection closed"))

        if self._writer:
            self._writer.close()

        self._loop.cancel()

        for loop in self._loops:
            loop.cancel()
        self._loops.clear()

    def setup_handler(self, handler: HandlerType):
        self._handler = handler

    async def _handle_server_package(self, package: BasePackage):
        if self._handler:
            result = await self._handler(self, package)
            if isinstance(result, BasePackage):
                if not self._writer:
                    raise RuntimeError("Not connected")

                if result.from_addr == self.crypto.public_key_bytes:
                    result = self.crypto.sign_package(result)

                await send_package(result, self._writer)
            return

        logger.warning(
            "No handler inited, request %s did nod proceeded", package.request_id
        )

    async def proxy_request[ReturnT: BasePackage](
        self,
        package: BasePackage,
        return_type: type[ReturnT] | None = None,
        *,
        timeout: int = 30,
    ) -> ReturnT:
        return await self._request(
            package, return_type=return_type, need_sign=False, timeout=timeout
        )

    async def _request[ReturnT: BasePackage](
        self,
        package: BasePackage,
        return_type: type[ReturnT] | None = None,
        *,
        need_sign: bool = True,
        timeout: int = 30,
    ) -> ReturnT:
        if not self._writer:
            raise RuntimeError("Not connected")

        future = asyncio.get_event_loop().create_future()
        self._awaited_requests[package.request_id] = future
        if need_sign:
            package = self.crypto.sign_package(package)

        await send_package(package, self._writer)

        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._awaited_requests.pop(package.request_id, None)
            raise

        if return_type and not isinstance(result, return_type):
            raise TypeError(
                f"Expected response of type {return_type}, got {type(result)}"
            )

        return result

    def _create_loop(self, loop: Coroutine):
        self._loops.append(asyncio.create_task(loop))

    async def _loop_read(self):
        disconnect_error: BaseException | None = None
        while True:
            try:
                package = await receive_package(self._reader)

                if not self.crypto.verify_signature(package):
                    logger.warning("Invalid signature, ignoring package")
                    continue

                logger.debug("Received package: %s", package)
                future = self._awaited_requests.pop(package.request_id, None)
                if not future:
                    await self._handle_server_package(package)
                    logger.debug("Request from server: %s", package)
                    continue

                if future is not None and not future.done():
                    future.set_result(package)

            except asyncio.IncompleteReadError:
                logger.info("Server disconnected")
                disconnect_error = ConnectionError("Connection closed by peer")
                break

            except asyncio.TimeoutError:
                logger.warning("Read timeout, server may be unresponsive")
                disconnect_error = ConnectionError("Connection timed out")
                break

            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                logger.warning("Invalid package received: %s", exc)
                disconnect_error = ConnectionError("Invalid package received")
                break

            except asyncio.CancelledError:
                disconnect_error = ConnectionError("Connection closed")
                break

        if disconnect_error is not None:
            self._fail_awaited_requests(disconnect_error)

        for loop in self._loops:
            loop.cancel()
        self._loops.clear()

    async def wait_loop(self):
        await self._loop
