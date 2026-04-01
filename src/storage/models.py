from dataclasses import dataclass


@dataclass
class ServerInfo:
    server_ip: str
    server_port: int
    server_public_key: bytes
