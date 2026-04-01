import base64
import ssl
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str
    MNEMONIC_SERVER: str
    HOST: str = "localhost"
    PORT: int
    PUBLIC_HOST: str
    PUBLIC_PORT: int
    SSL_CERT_BASE64: str | None = None
    SSL_KEY_BASE64: str | None = None
    SSL_CERT_PATH: str | None = None
    SSL_KEY_PATH: str | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_ssl_fields(cls, values):
        cert_provided = (
            values.get("SSL_CERT_PATH") is not None
            or values.get("SSL_CERT_BASE64") is not None
        )
        key_provided = (
            values.get("SSL_KEY_PATH") is not None
            or values.get("SSL_KEY_BASE64") is not None
        )

        if cert_provided != key_provided:
            raise ValueError("SSL certificate and key must be provided together.")

        # If neither provided, it's ok (no SSL)
        return values

    def get_ssl_context(self) -> ssl.SSLContext:
        """Создает SSL контекст из сертификата и ключа."""
        cert_data = None
        key_data = None

        # Приоритет: base64 строки → файлы
        if self.SSL_CERT_BASE64:
            cert_data = base64.b64decode(self.SSL_CERT_BASE64)
        elif self.SSL_CERT_PATH:
            with open(self.SSL_CERT_PATH, "rb") as f:
                cert_data = f.read()

        if self.SSL_KEY_BASE64:
            key_data = base64.b64decode(self.SSL_KEY_BASE64)
        elif self.SSL_KEY_PATH:
            with open(self.SSL_KEY_PATH, "rb") as f:
                key_data = f.read()

        if not cert_data or not key_data:
            raise ValueError(
                "SSL certificate and key must be provided either as base64 or file paths."
            )

        # Создаем временные файлы для OpenSSL
        with NamedTemporaryFile(delete=False, suffix=".pem", mode="wb") as cert_file:
            cert_file.write(cert_data)
            cert_path = cert_file.name

        with NamedTemporaryFile(delete=False, suffix=".pem", mode="wb") as key_file:
            key_file.write(key_data)
            key_path = key_file.name

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_path, key_path)

        # Удаляем временные файлы
        Path(cert_path).unlink()
        Path(key_path).unlink()

        return ssl_ctx
