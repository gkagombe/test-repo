"""
Application configuration.

Settings are loaded from environment variables (and a local .env file in
development). This module only assembles and validates configuration — it
never reads from GitHub, the database, or any other runtime system. Import
`get_settings()`, not `Settings()` directly: the cache means the app fails
fast once at startup rather than silently re-validating on every request.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "trustops"
    user: str = "trustops"
    password: str = "trustops_pass" # required — no default, must come from env

    @property
    def url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )

 # this is my chang
class GitHubAppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GITHUB_APP_")

    app_id: str
    webhook_secret: str
    # Path to the .pem file, not the raw key as a string. Keeps the key out
    # of `.env`, out of `os.environ` dumps in error logs, and lets file
    # permissions (chmod 600) actually mean something.
    private_key_path: str

    @field_validator("private_key_path")
    @classmethod
    def key_file_must_exist(cls, v: str) -> str:
        if not Path(v).exists():
            raise ValueError(f"GitHub App private key not found at {v}")
        return v


class QueueSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QUEUE_")

    # Matches the architecture decision: Postgres-backed job table to avoid
    # a second piece of infra at MVP scale, with SQS as the drop-in upgrade
    # once evidence-collection volume actually needs it.
    backend: Literal["postgres", "sqs"] = "postgres"
    sqs_queue_url: str | None = None

    @field_validator("sqs_queue_url")
    @classmethod
    def sqs_url_required_if_sqs_backend(cls, v, info):
        if info.data.get("backend") == "sqs" and not v:
            raise ValueError(
                "QUEUE_SQS_QUEUE_URL is required when QUEUE_BACKEND=sqs"
            )
        return v


class FeatureFlags(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FEATURE_")

    # Off until the Phase 3 IDE plugin actually exists — flips the
    # evidence/sources/ide_plugin.py path on when it's ready, without a
    # code change.
    ide_plugin_source_enabled: bool = False

    # The evidence-completeness override from the activity diagram: forces
    # human_review on sensitive-path changes with unknown authorship,
    # regardless of trust score. On by default — this should be an
    # explicit, logged decision to turn off, not a silent default.
    enforce_evidence_completeness: bool = True


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Bump this whenever trust_score/calculator.py's weights change.
    # Every row in trust_scores stores whichever value was active when it
    # was computed — never overwrite what an old version meant.
    algorithm_version: str = "rules-v1"

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    github_app: GitHubAppSettings = Field(default_factory=GitHubAppSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)


@lru_cache
def get_settings() -> Settings:
    return Settings()

