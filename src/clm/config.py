"""
Configuration (v2).
Pydantic v2 moved BaseSettings into the separate `pydantic-settings` package,
so v1's `from pydantic import BaseSettings` no longer works.
    pip install "pydantic>=2" pydantic-settings openai azure-identity
Auth note: prefer certificate-based auth (or a managed identity when hosted as
an Azure Function) over a client secret. A secret is included only as a
fallback for local Phase-1 development.
"""
from __future__ import annotations

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    tenant_id: str = Field(alias="TENANT_ID")
    client_id: str = Field(alias="CLIENT_ID")
    site_id: str = Field(alias="SITE_ID")
    drive_id: str = Field(alias="DRIVE_ID")
    cert_path: Optional[str] = Field(default=None, alias="CERT_PATH")
    cert_thumbprint: Optional[str] = Field(default=None, alias="CERT_THUMBPRINT")
    client_secret: Optional[str] = Field(default=None, alias="CLIENT_SECRET")
    azure_openai_endpoint: Optional[str] = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(default="2024-10-21", alias="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment_extract: str = Field(default="gpt-4.1", alias="AZURE_OPENAI_DEPLOYMENT_EXTRACT")
    azure_openai_deployment_judge: str = Field(default="o4-mini", alias="AZURE_OPENAI_DEPLOYMENT_JUDGE")
    azure_openai_api_key: Optional[str] = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    use_dummy_ai: bool = Field(default=False, alias="USE_DUMMY_AI")

    def validate_auth(self) -> None:
        if not ((self.cert_path and self.cert_thumbprint) or self.client_secret):
            raise RuntimeError(
                "No usable credential: set CERT_PATH + CERT_THUMBPRINT (preferred) "
                "or CLIENT_SECRET (local dev fallback)."
            )

settings = Settings()
