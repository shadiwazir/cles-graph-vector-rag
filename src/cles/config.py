"""Application settings.

The only module that reads the environment. Everything else receives a `Settings` object.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """A required setting is missing."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres
    postgres_db: str = "cles_db"
    postgres_user: str = "cles_admin"
    postgres_password: SecretStr | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None

    # LLM provider
    llm_provider: str = "openai"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str | None = None
    openai_api_key: SecretStr | None = None
    allow_external_generator: bool = False

    # Embeddings
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_device: Literal["auto", "cpu", "cuda"] = "auto"

    # Project
    domain_pack: str = "legal_ca_on"
    data_dir: Path = Path("data")
    domain_packs_dir: Path = Path("domain_packs")

    # Tracking and telemetry
    mlflow_tracking_uri: str = "http://localhost:5000"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    telemetry_capture_content: Literal["none", "redacted", "full"] = "redacted"
    telemetry_retention_days: int = 30

    def postgres_dsn(self) -> str:
        """Connection string for Postgres. Fails if the password is not set."""
        password = _require(self.postgres_password, "POSTGRES_PASSWORD")
        return (
            f"postgresql://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def neo4j_auth(self) -> tuple[str, str]:
        """(user, password) for the Neo4j driver. Fails if the password is not set."""
        return self.neo4j_user, _require(self.neo4j_password, "NEO4J_PASSWORD")


def _require(secret: SecretStr | None, name: str) -> str:
    if secret is None or not secret.get_secret_value():
        raise ConfigError(f"{name} is not set. Add it to .env (see .env.example).")
    return secret.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
