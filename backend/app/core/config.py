from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    database_url: str
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "qwen2.5:7b-instruct"
    llm_timeout: float = 240.0
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/google/callback"
    frontend_url: str = "http://localhost:5173"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    token_encryption_key: str = ""
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_days: int = 7
    oauth_state_minutes: int = 10

    @field_validator(
        "google_client_id",
        "google_client_secret",
        "google_redirect_uri",
        "frontend_url",
        "token_encryption_key",
        "llm_api_key",
        mode="before",
    )
    @classmethod
    def strip_secret_whitespace(cls, value):
        if isinstance(value, str):
            return value.strip().strip('"').strip("'")
        return value

    @property
    def origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def cookie_secure_flag(self) -> bool:
        return self.cookie_secure or self.cookie_samesite == "none"

    @model_validator(mode="after")
    def https_cookies_when_public(self):
        public = self.frontend_url.startswith("https://") or self.google_redirect_uri.startswith("https://")
        if public:
            self.cookie_secure = True
            frontend_host = (urlparse(self.frontend_url).hostname or "").casefold()
            api_host = (urlparse(self.google_redirect_uri).hostname or "").casefold()
            if frontend_host and api_host and frontend_host != api_host:
                self.cookie_samesite = "none"
        if self.cookie_samesite == "none":
            self.cookie_secure = True
        return self

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
    )

settings = Settings()
