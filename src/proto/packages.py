from dataclasses import dataclass
from enum import IntEnum

from .base import BasePackage


class RequestType(IntEnum):
    MESSAGE_REQUEST_V1 = 1
    MESSAGE_RESPONSE_V1 = 2
    PING_V1 = 3


@dataclass(kw_only=True, frozen=True)
class MessageRequest(BasePackage, type=RequestType.MESSAGE_REQUEST_V1):
    to_addr: bytes
    payload: bytes


@dataclass(kw_only=True, frozen=True)
class MessageResponse(BasePackage, type=RequestType.MESSAGE_RESPONSE_V1):
    is_delivered: bool


@dataclass(kw_only=True, frozen=True)
class PingRequest(BasePackage, type=RequestType.PING_V1):
    pass


TYPES_TO_CLASSES: dict[int, type[BasePackage]] = {
    RequestType.MESSAGE_REQUEST_V1: MessageRequest,
    RequestType.MESSAGE_RESPONSE_V1: MessageResponse,
    RequestType.PING_V1: PingRequest,
}
