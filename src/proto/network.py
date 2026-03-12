import asyncio

from .base import BasePackage, read_chunk
from .packages import TYPES_TO_CLASSES


def _read_package_type(data: bytes) -> int:
    if not data:
        raise ValueError("Empty data when trying to read package type")

    type_bytes, _ = read_chunk(data)
    return int.from_bytes(type_bytes, byteorder="big")


async def send_package(package: BasePackage, writer: asyncio.StreamWriter) -> None:
    data = package.to_bytes()
    data_length = len(data).to_bytes(4, byteorder="big")

    writer.write(data_length + data)
    await writer.drain()


async def receive_package(reader: asyncio.StreamReader) -> BasePackage:
    length_data = await reader.readexactly(4)
    data_length = int.from_bytes(length_data, byteorder="big")
    data = await reader.readexactly(data_length)

    type_ = _read_package_type(data)
    if type_ not in TYPES_TO_CLASSES:
        raise ValueError(f"Unknown package type: {type_}")

    package = TYPES_TO_CLASSES[type_].from_bytes(data)

    return package
