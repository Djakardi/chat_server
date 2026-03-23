import base64
import ssl
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str
    MNEMONIC_SERVER: str
    HOST: str = "localhost"
    PORT_PLAINTEXT: int | None = None
    PORT_SSL: int | None = None
    RUN_ONLY_SSL: bool = False
    RUN_ONLY_PLAINTEXT: bool = True
    SSL_CERT_BASE64: str | None = None
    SSL_KEY_BASE64: str | None = None
    SSL_CERT_PATH: str | None = None
    SSL_KEY_PATH: str | None = None

    @field_validator("PORT_PLAINTEXT", "PORT_SSL", mode="before")
    def convert_none_string(cls, v):
        if v == "None" or v == "":
            return None
        return v

    def get_ssl_context(self) -> ssl.SSLContext | None:
        """Создает SSL контекст из сертификата и ключа."""
        if not self.RUN_ONLY_PLAINTEXT or self.RUN_ONLY_SSL:
            # Если нужен SSL, подготавливаем сертификат и ключ
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

            if cert_data and key_data:
                # Создаем временные файлы для OpenSSL
                with NamedTemporaryFile(
                    delete=False, suffix=".pem", mode="wb"
                ) as cert_file:
                    cert_file.write(cert_data)
                    cert_path = cert_file.name

                with NamedTemporaryFile(
                    delete=False, suffix=".pem", mode="wb"
                ) as key_file:
                    key_file.write(key_data)
                    key_path = key_file.name

                ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_ctx.load_cert_chain(cert_path, key_path)

                # Удаляем временные файлы
                Path(cert_path).unlink()
                Path(key_path).unlink()

                return ssl_ctx

        return None
