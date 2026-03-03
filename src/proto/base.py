from enum import IntEnum
from typing import Any, ClassVar, Protocol, get_type_hints
import uuid


def var_to_bytes(var: Any, type_: type[Any]) -> bytes:
    if isinstance(var, IntEnum) or (
        isinstance(type_, type) and issubclass(type_, IntEnum)
    ):
        return var_to_bytes(int(var), int)
    elif type_ is int:
        data_length = (var.bit_length() + 7) // 8 or 1
        len_bytes = data_length.to_bytes(1, byteorder="big")
        data = var.to_bytes(data_length, byteorder="big")
        return len_bytes + data
    elif type_ is str:
        data = var.encode("utf-8")
        len_bytes = len(data).to_bytes(1, byteorder="big")
        return len_bytes + data
    elif type_ is bytes:
        len_bytes = len(var).to_bytes(1, byteorder="big")
        return len_bytes + var
    elif type_ is uuid.UUID:
        data = var.bytes
        len_bytes = len(data).to_bytes(1, byteorder="big")
        return len_bytes + data
    else:
        raise TypeError(f"Unsupported type: {type(var)}")


def bytes_to_var(data: bytes, type_: type[Any]) -> Any:
    if isinstance(type_, type) and issubclass(type_, IntEnum):
        val = int.from_bytes(data, byteorder="big")
        return type_(val)
    if type_ is int:
        return int.from_bytes(data, byteorder="big")
    elif type_ is str:
        return data.decode("utf-8")
    elif type_ is bytes:
        return data
    elif type_ is uuid.UUID:
        return uuid.UUID(bytes=data)
    else:
        raise TypeError(f"Unsupported type: {type_}")


class RequestProto(Protocol):
    type: int
    request_id: uuid.UUID

    def to_bytes(self) -> bytes: ...


class BasePackage:
    type: ClassVar[int]

    def __init_subclass__(cls, type: int) -> None:
        cls.type = type

        cls.hints = [
            i
            for i in sorted(get_type_hints(cls).items(), key=lambda item: item[0])
            if i[0] != "type"
        ]

        super().__init_subclass__()

    def to_bytes(self) -> bytes:
        data = var_to_bytes(self.type, int)
        for field_name, field_type in self.hints:
            value = getattr(self, field_name)
            data += var_to_bytes(value, field_type)
        return data

    @classmethod
    def from_bytes(cls, data: bytes) -> "BasePackage":
        i = 0

        data_chunks: list[bytes] = []
        while True:
            data_len = data[i]
            data_chunks.append(data[i + 1 : i + 1 + data_len])
            i += 1 + data_len
            if i >= len(data):
                break

        TYPE = int.from_bytes(data_chunks[0], byteorder="big")
        if TYPE != cls.type:
            raise ValueError(f"Expected type {cls.type}, got {TYPE}")

        kwargs = {}
        for (field_name, field_type), chunk in zip(cls.hints, data_chunks[1:]):
            kwargs[field_name] = bytes_to_var(chunk, field_type)

        return cls(**kwargs)
