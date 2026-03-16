from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://flowforge:flowforge@localhost:5432/flowforge"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "dev-secret-change-in-production"
    jwt_secret: str = "dev-secret-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    health_port: int = 8081
    allowed_origins: list[str] = ["http://localhost:5173"]
    litellm_url: str = "http://localhost:4000"
    litellm_master_key: str = "sk-flowforge-local"

    model_config = {"env_file": ".env", "env_prefix": "FLOWFORGE_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
