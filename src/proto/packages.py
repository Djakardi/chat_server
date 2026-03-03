from dataclasses import dataclass
from enum import IntEnum
import uuid

from .base import BasePackage, RequestProto


class RequestType(IntEnum):
    MESSAGE_V1 = 1
    PING_V1 = 2


@dataclass(kw_only=True, frozen=True)
class MessageRequest(BasePackage, RequestProto, type=RequestType.MESSAGE_V1):
    request_id: uuid.UUID
    from_addr: str
    to_addr: str
    timestamp: int
    payload: str
    signature: str


@dataclass(kw_only=True, frozen=True)
class PingRequest(BasePackage, RequestProto, type=RequestType.PING_V1):
    request_id: uuid.UUID
    timestamp: int


TYPES_TO_CLASSES: dict[int, type[BasePackage]] = {
    RequestType.MESSAGE_V1: MessageRequest,
    RequestType.PING_V1: PingRequest,
}
