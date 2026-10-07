from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    app_usage_mode: Literal["development", "noncommercial", "commercial"] = "development"
    demo_mode: bool = True
    database_url: str = "postgresql+psycopg://newsmap:newsmap@localhost:5432/newsmap"
    cors_origins: str = "http://localhost:3000"
    collector_poll_seconds: int = Field(default=60, ge=1)
    article_retention_days: int = Field(default=30, ge=1)
    newswire_partner_id: int | None = Field(default=None, gt=0)
    newswire_api_key: SecretStr | None = None
    newsdata_api_key: SecretStr | None = None
    vworld_api_key: SecretStr | None = None
    vworld_domain: str = "http://localhost:3000"

    @field_validator(
        "newswire_partner_id",
        "newswire_api_key",
        "newsdata_api_key",
        "vworld_api_key",
        mode="before",
    )
    @classmethod
    def empty_optional_credentials(cls, value):
        return None if value == "" else value


settings = Settings()
