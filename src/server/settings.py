from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str
    MNEMONIC_SERVER: str
    HOST: str = "localhost"
    PORT: int = 8080
