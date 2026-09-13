from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/v1"

    database_url: str
    redis_url: str

    s3_endpoint_url: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    s3_region: str = "us-east-1"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # fields load from .env / env vars
