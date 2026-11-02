"""Application settings, read from environment variables.

Locally, values come from a .env file (loaded with python-dotenv) or from
local.settings.json when running under the Functions host. In Azure, they come
from the Function App's Application Settings. Code elsewhere should call
get_settings() rather than reading os.environ directly.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


class LLMProvider(str, Enum):
    MOCK = "mock"
    AZURE_OPENAI = "azure_openai"
    ANTHROPIC = "anthropic"


class ConfigError(ValueError):
    """Raised when settings are missing or invalid."""


@dataclass(frozen=True)
class Settings:
    # frozen=True makes settings read-only after startup.
    # repr=False keeps secrets out of logs and error messages.

    # LLM
    llm_provider: LLMProvider = LLMProvider.MOCK
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = field(default=None, repr=False)
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"
    # None = don't send it (reasoning deployments such as gpt-5 / o-series reject it).
    azure_openai_temperature: float | None = None
    anthropic_api_key: str | None = field(default=None, repr=False)
    anthropic_model: str = "claude-opus-5-5"

    # Blob Storage ("UseDevelopmentStorage=true" = local Azurite emulator)
    storage_connection_string: str = field(default="UseDevelopmentStorage=true", repr=False)

    # Database: None = local SQLite file in output_dir. Accepts a SQLAlchemy URL
    # or an Azure SQL ODBC string ("Driver={ODBC Driver 18 for SQL Server};...").
    sql_connection_string: str | None = field(default=None, repr=False)

    # Output / logging
    output_dir: Path = Path("output")
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build Settings from a mapping (defaults to os.environ) and validate it."""
        env = os.environ if env is None else env

        def get(name: str, default: str | None = None) -> str | None:
            value = env.get(name, "").strip()
            return value or default

        provider_raw = get("LLM_PROVIDER", LLMProvider.MOCK.value).lower()
        try:
            provider = LLMProvider(provider_raw)
        except ValueError:
            allowed = ", ".join(p.value for p in LLMProvider)
            raise ConfigError(f"LLM_PROVIDER={provider_raw!r} is invalid; use one of: {allowed}") from None

        temperature_raw = get("AZURE_OPENAI_TEMPERATURE")
        try:
            temperature = float(temperature_raw) if temperature_raw else None
        except ValueError:
            raise ConfigError("AZURE_OPENAI_TEMPERATURE must be a number") from None

        settings = cls(
            llm_provider=provider,
            azure_openai_endpoint=get("AZURE_OPENAI_ENDPOINT"),
            azure_openai_api_key=get("AZURE_OPENAI_API_KEY"),
            azure_openai_deployment=get("AZURE_OPENAI_DEPLOYMENT"),
            azure_openai_api_version=get("AZURE_OPENAI_API_VERSION", cls.azure_openai_api_version),
            azure_openai_temperature=temperature,
            anthropic_api_key=get("ANTHROPIC_API_KEY"),
            anthropic_model=get("ANTHROPIC_MODEL", cls.anthropic_model),
            storage_connection_string=get("STORAGE_CONNECTION_STRING", cls.storage_connection_string),
            sql_connection_string=get("SQL_CONNECTION_STRING"),
            output_dir=Path(get("OUTPUT_DIR", str(cls.output_dir))),
            log_level=get("LOG_LEVEL", cls.log_level).upper(),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        """Fail fast if the chosen LLM provider is missing what it needs."""
        required: dict[str, str | None] = {}
        if self.llm_provider is LLMProvider.AZURE_OPENAI:
            required = {
                "AZURE_OPENAI_ENDPOINT": self.azure_openai_endpoint,
                "AZURE_OPENAI_API_KEY": self.azure_openai_api_key,
                "AZURE_OPENAI_DEPLOYMENT": self.azure_openai_deployment,
            }
        elif self.llm_provider is LLMProvider.ANTHROPIC:
            required = {"ANTHROPIC_API_KEY": self.anthropic_api_key}

        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ConfigError(
                f"LLM_PROVIDER={self.llm_provider.value} requires: {', '.join(missing)}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process (.env first, without overriding real env vars)."""
    load_dotenv(override=False)
    return Settings.from_env()
