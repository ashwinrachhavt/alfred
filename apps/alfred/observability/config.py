from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class TracingBackend(str, Enum):
    """Supported tracing backends."""

    MLFLOW = "mlflow"
    LANGFUSE = "langfuse"
    OPENTELEMETRY = "opentelemetry"
    NOOP = "noop"


class ObservabilityConfig(BaseSettings):
    """Observability and tracing configuration."""

    model_config = SettingsConfigDict(
        env_prefix="OBSERVABILITY_",
        case_sensitive=False,
        extra="ignore",
    )

    # Global toggle
    enabled: bool = Field(default=True, description="Master switch for observability")

    # Backend selection
    backend: TracingBackend = Field(
        default=TracingBackend.MLFLOW, description="Tracing backend to use"
    )

    # MLflow configuration
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5000", validation_alias="MLFLOW_TRACKING_URI"
    )
    mlflow_experiment_name: str = Field(default="alfred", validation_alias="MLFLOW_EXPERIMENT_NAME")
    mlflow_run_name_prefix: str = Field(default="", validation_alias="MLFLOW_RUN_NAME_PREFIX")

    # Langfuse configuration (legacy support)
    langfuse_public_key: Optional[str] = Field(default=None, validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr | None = Field(
        default=None, validation_alias="LANGFUSE_SECRET_KEY"
    )
    langfuse_host: Optional[str] = Field(default=None, validation_alias="LANGFUSE_HOST")

    # OpenTelemetry configuration (future)
    otel_endpoint: HttpUrl | None = Field(default=None, validation_alias="OTEL_ENDPOINT")
    otel_service_name: str = Field(default="alfred", validation_alias="OTEL_SERVICE_NAME")

    # Sampling and performance
    sample_rate: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Trace sampling rate (0.0-1.0)"
    )

    # Enrichment
    capture_input: bool = Field(default=True, description="Capture function inputs in traces")
    capture_output: bool = Field(default=True, description="Capture function outputs in traces")
    max_payload_size: int = Field(
        default=10000, ge=0, description="Max size of input/output to capture (chars)"
    )
