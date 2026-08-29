from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dify_api_key: str = ""
    dify_api_base_url: str = "https://api.dify.ai/v1"
    amap_web_service_key: str = ""
    internal_api_token: str = ""

    default_longitude: float = 116.3260
    default_latitude: float = 40.0030
    default_location_name: str = "清华大学"

    allowed_origins: str = "http://localhost:8000"
    request_timeout_seconds: float = Field(default=20, gt=0, le=120)

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

