"""Application settings.

The only module that reads the environment. Everything else receives a `Settings` object.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    # Extra JSON fields sent with every chat request, e.g. {"chat_template_kwargs":
    # {"enable_thinking": false}} for Qwen3 models served by vLLM.
    llm_extra_body: dict = Field(default_factory=dict)
    llm_concurrency: int = 4
    llm_timeout_seconds: float = 600  # slow local models need more
    # Prices change, so they are settings and not code. Without them, cost is not computed.
    llm_price_input_per_mtok: float | None = None
    llm_price_output_per_mtok: float | None = None
    extraction_output_tokens_estimate: int = 2500  # used for dry-run cost estimates

    # Embeddings
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_device: Literal["auto", "cpu", "cuda"] = "auto"
    embedding_batch_size: int = 32

    audit_environment: str = "live"  # "test" for tests and smoke runs: drift checks ignore them
    adapter_version: str | None = None  # for example "cles-advisor v1"; default: the model name
    audit_store_question: bool = False  # store question text in request_audit (privacy: off)

    # Retrieval
    retrieval_k: int = 8  # passages in the context pack
    retrieval_candidates: int = 30  # per search before fusion
    rrf_k: int = 60
    reranker_model: str | None = None  # e.g. BAAI/bge-reranker-base; None disables reranking
    evidence_strong_distance: float = 0.35  # cosine distance
    evidence_weak_distance: float = 0.45

    sft_config: Path = Path("configs/sft/qwen3_8b_qlora.yaml")
    conversation_history_tokens: int = 1500  # budget for earlier turns folded into the case text
    # Model evaluation (stages eval_generate and eval_score)
    eval_system: str = "openai"  # which entry of eval_systems_file to generate with
    eval_systems_file: Path = Path("eval/systems.yaml")
    eval_out_dir: Path = Path("artifacts/eval")
    eval_metrics_file: Path = Path("metrics/eval.json")  # git-tracked, for `dvc metrics`
    drift_thresholds_file: Path = Path("eval/thresholds.yaml")
    drift_baseline_file: Path = Path("eval/baseline.json")  # git-tracked
    drift_update_baseline: bool = False  # make the latest evaluation the new baseline
    judge_model: str = "gpt-5.4-mini"  # prefer another model family than the generator
    eval_labels_file: Path = Path("eval/labels/labels.jsonl")  # human review, git-tracked
    eval_max_new_tokens: int = 2000
    eval_batch_size: int = 4
    # Hosts we control that may receive case text besides localhost (for example a rented GPU
    # running the fine-tuned model). Comma-separated in the environment.
    trusted_generator_hosts: list[str] = Field(default_factory=list)

    # Training data
    training_eval_fraction: float = 0.1  # newest share of documents held out for evaluation
    training_out_dir: Path = Path("artifacts/datasets")
    dataset_dir: Path | None = None  # dataset to check; default: the newest in training_out_dir

    # Project
    domain_pack: str = "legal_ca_on"
    data_dir: Path = Path("data")
    domain_packs_dir: Path = Path("domain_packs")

    # Tracking and telemetry
    mlflow_enabled: bool = True  # track every stage and evaluation (best effort, never blocks)
    mlflow_tracking_uri: str = "http://localhost:5000"
    # Where the console links to and checks the platform tools
    grafana_url: str = "http://localhost:3000"
    phoenix_url: str = "http://127.0.0.1:6006"
    prometheus_url: str = "http://localhost:9090"
    mlflow_registered_model: str | None = None  # register the adapter under this name when set
    telemetry_enabled: bool = False  # export traces and metrics to the OTLP endpoint
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"  # OTLP over HTTP
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
