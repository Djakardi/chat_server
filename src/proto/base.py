from enum import IntEnum
from typing import Any, ClassVar, get_type_hints
import time
import uuid
from dataclasses import dataclass, field, replace


FIELD_LENGTH_BYTES = 4


def _encode_length(length: int) -> bytes:
    return length.to_bytes(FIELD_LENGTH_BYTES, byteorder="big")


def read_chunk(data: bytes, start: int = 0) -> tuple[bytes, int]:
    if len(data) < start + FIELD_LENGTH_BYTES:
        raise ValueError("Data is too short to read field length")

    data_len = int.from_bytes(data[start : start + FIELD_LENGTH_BYTES], byteorder="big")
    value_start = start + FIELD_LENGTH_BYTES
    value_end = value_start + data_len

    if len(data) < value_end:
        raise ValueError(
            f"Data is too short for declared field length {data_len}: only {len(data) - value_start} bytes available"
        )

    return data[value_start:value_end], value_end


def var_to_bytes(var: Any, type_: type[Any]) -> bytes:
    if isinstance(var, IntEnum) or (
        isinstance(type_, type) and issubclass(type_, IntEnum)
    ):
        return var_to_bytes(int(var), int)
    elif type_ is bool:
        return var_to_bytes(1 if var else 0, int)
    elif type_ is int:
        data_length = (var.bit_length() + 7) // 8 or 1
        len_bytes = _encode_length(data_length)
        data = var.to_bytes(data_length, byteorder="big")
        return len_bytes + data
    elif type_ is str:
        data = var.encode("utf-8")
        len_bytes = _encode_length(len(data))
        return len_bytes + data
    elif type_ is bytes:
        len_bytes = _encode_length(len(var))
        return len_bytes + var
    elif type_ is uuid.UUID:
        data = var.bytes
        len_bytes = _encode_length(len(data))
        return len_bytes + data
    else:
        raise TypeError(f"Unsupported type: {type(var)}")


def bytes_to_var(data: bytes, type_: type[Any]) -> Any:
    if isinstance(type_, type) and issubclass(type_, IntEnum):
        val = int.from_bytes(data, byteorder="big")
        return type_(val)
    if type_ is int:
        return int.from_bytes(data, byteorder="big")
    elif type_ is bool:
        return bool(int.from_bytes(data, byteorder="big"))
    elif type_ is str:
        return data.decode("utf-8")
    elif type_ is bytes:
        return data
    elif type_ is uuid.UUID:
        return uuid.UUID(bytes=data)
    else:
        raise TypeError(f"Unsupported type: {type_}")


@dataclass(kw_only=True, frozen=True)
class BasePackage:
    type: ClassVar[int]
    hints: ClassVar[list[tuple[str, Any]]]

    request_id: uuid.UUID = field(default_factory=uuid.uuid4)
    timestamp: int = field(default_factory=time.time_ns)
    from_addr: bytes = field(default=b"")
    signature: bytes = field(default=b"")

    def __init_subclass__(cls, type: int) -> None:
        cls.type = type

        keys = get_type_hints(cls)
        keys = dict(sorted(keys.items(), key=lambda x: x[0]))

        cls.hints = [i for i in keys.items() if i[0] not in ["type", "hints"]]

        super().__init_subclass__()

    def __post_init__(self):
        if self.from_addr == b"":
            raise ValueError("from_addr cannot be empty")

    def to_bytes(self, *, exclude_signature: bool = False) -> bytes:
        data = var_to_bytes(self.type, int)
        for field_name, field_type in self.hints:
            if field_name == "signature" and exclude_signature:
                continue
            data += var_to_bytes(getattr(self, field_name), field_type)
        return data

    def sign_package(self, signature: bytes) -> "BasePackage":
        return replace(self, signature=signature)

    @classmethod
    def from_bytes(cls, data: bytes) -> "BasePackage":
        i = 0

        data_chunks: list[bytes] = []
        while i < len(data):
            chunk, i = read_chunk(data, i)
            data_chunks.append(chunk)

        if not data_chunks:
            raise ValueError("Package data is empty")

        TYPE = int.from_bytes(data_chunks[0], byteorder="big")
        if TYPE != cls.type:
            raise ValueError(f"Expected type {cls.type}, got {TYPE}")

        if len(data_chunks) != len(cls.hints) + 1:
            raise ValueError(
                f"Expected {len(cls.hints)} fields, got {len(data_chunks) - 1}"
            )

        kwargs = {}
        for (field_name, field_type), chunk in zip(cls.hints, data_chunks[1:]):
            kwargs[field_name] = bytes_to_var(chunk, field_type)

        return cls(**kwargs)
