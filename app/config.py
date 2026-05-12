from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///data/auto-halo.db"
    host: str = "0.0.0.0"
    port: int = 8808
    secret_key: str = "change-me-in-production"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()