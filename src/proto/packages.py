from dataclasses import dataclass
from enum import IntEnum

from .base import BasePackage


class RequestType(IntEnum):
    MESSAGE_REQUEST_V1 = 1
    MESSAGE_RESPONSE_V1 = 2
    PING_V1 = 3
    SERVER_INFO_V1 = 4
    USER_LOOKUP_REQUEST_V1 = 5
    USER_LOOKUP_RESPONSE_V1 = 6
    FORWARDED_MESSAGE_REQUEST_V1 = 7
    FORWARDED_MESSAGE_RESPONSE_V1 = 8


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


@dataclass(kw_only=True, frozen=True)
class ServerInfoRequest(BasePackage, type=RequestType.SERVER_INFO_V1):
    server_ip: str
    server_port: int
    server_public_key: bytes


@dataclass(kw_only=True, frozen=True)
class UserLookupRequest(BasePackage, type=RequestType.USER_LOOKUP_REQUEST_V1):
    user_addr: bytes


@dataclass(kw_only=True, frozen=True)
class UserLookupResponse(BasePackage, type=RequestType.USER_LOOKUP_RESPONSE_V1):
    is_reachable: bool


@dataclass(kw_only=True, frozen=True)
class ForwardedMessageRequest(
    BasePackage, type=RequestType.FORWARDED_MESSAGE_REQUEST_V1
):
    original_message_bytes: bytes


@dataclass(kw_only=True, frozen=True)
class ForwardedMessageResponse(
    BasePackage, type=RequestType.FORWARDED_MESSAGE_RESPONSE_V1
):
    is_delivered: bool


TYPES_TO_CLASSES: dict[int, type[BasePackage]] = {
    RequestType.MESSAGE_REQUEST_V1: MessageRequest,
    RequestType.MESSAGE_RESPONSE_V1: MessageResponse,
    RequestType.PING_V1: PingRequest,
    RequestType.SERVER_INFO_V1: ServerInfoRequest,
    RequestType.USER_LOOKUP_REQUEST_V1: UserLookupRequest,
    RequestType.USER_LOOKUP_RESPONSE_V1: UserLookupResponse,
    RequestType.FORWARDED_MESSAGE_REQUEST_V1: ForwardedMessageRequest,
    RequestType.FORWARDED_MESSAGE_RESPONSE_V1: ForwardedMessageResponse,
}
