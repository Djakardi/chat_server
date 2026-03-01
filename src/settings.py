from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REDIS_URL: str
