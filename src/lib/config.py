"""Configuration loader for DMRG-FTE."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class OrchestratorConfig(BaseModel):
    """Orchestrator configuration settings."""

    watch_path: str = "data/incoming"
    file_patterns: list[str] = Field(default_factory=lambda: ["*.csv", "*.json"])
    scheduler_interval: int = Field(default=30, ge=30)
    heartbeat_interval: int = Field(default=60, ge=1)
    max_concurrent: int = Field(default=1, ge=1)


class ValidationConfig(BaseModel):
    """Validation configuration settings."""

    max_batch_size: int = Field(default=100000, ge=1)
    chunk_size: int = Field(default=10000, ge=1)
    timeout_per_record_ms: int = Field(default=100, ge=1)
    target_10k_seconds: int = Field(default=5, ge=1)


class AlertingConfig(BaseModel):
    """Alerting configuration settings."""

    critical_dispatch_seconds: int = Field(default=60, ge=1)
    warning_dispatch_seconds: int = Field(default=300, ge=1)
    console_enabled: bool = True
    log_enabled: bool = True


class StorageConfig(BaseModel):
    """Storage paths configuration."""

    checkpoints_path: str = "data/checkpoints"
    quarantine_path: str = "data/quarantine"
    health_state_path: str = "data/state/health.json"
    results_path: str = "data/results"
    audit_log_path: str = "logs/audit"
    alert_log_path: str = "logs/alerts"


class RecoveryConfig(BaseModel):
    """Recovery configuration settings."""

    max_recovery_seconds: int = Field(default=60, ge=1)
    checkpoint_on_start: bool = True
    checkpoint_on_complete: bool = True


class LoggingConfig(BaseModel):
    """Logging configuration settings."""

    level: str = "INFO"
    json_format: bool = True
    include_timestamp: bool = True
    include_correlation_id: bool = True

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()


class SeverityWeights(BaseModel):
    """Severity score calculation weights."""

    impact: float = Field(default=0.40, ge=0.0, le=1.0)
    frequency: float = Field(default=0.30, ge=0.0, le=1.0)
    recency: float = Field(default=0.30, ge=0.0, le=1.0)

    @field_validator("recency")
    @classmethod
    def validate_weights_sum(cls, v: float, info: Any) -> float:
        """Validate that weights sum to 1.0."""
        if info.data:
            total = info.data.get("impact", 0.4) + info.data.get("frequency", 0.3) + v
            if not (0.99 <= total <= 1.01):
                raise ValueError(f"Severity weights must sum to 1.0, got {total}")
        return v


class Config(BaseModel):
    """Main application configuration."""

    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    recovery: RecoveryConfig = Field(default_factory=RecoveryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    severity_weights: SeverityWeights = Field(default_factory=SeverityWeights)


_config: Config | None = None
_last_known_good: Config | None = None


def load_config(config_path: str | Path | None = None) -> Config:
    """Load configuration from YAML file.

    Args:
        config_path: Path to configuration file. If None, uses default.

    Returns:
        Parsed and validated Config object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If YAML parsing fails.
        pydantic.ValidationError: If config validation fails.
    """
    global _config, _last_known_good

    if config_path is None:
        config_path = Path("config/default.yaml")
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        # Fall back to last known good if available
        if _last_known_good is not None:
            return _last_known_good
        # Otherwise return defaults
        return Config()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}

        _config = Config(**raw_config)
        _last_known_good = _config
        return _config
    except (yaml.YAMLError, Exception) as e:
        # Fall back to last known good if available
        if _last_known_good is not None:
            return _last_known_good
        raise


def get_config() -> Config:
    """Get the current configuration.

    Returns:
        Current Config object, loading from default if not yet loaded.
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: str | Path | None = None) -> Config:
    """Reload configuration from file.

    Args:
        config_path: Path to configuration file. If None, uses default.

    Returns:
        Newly loaded Config object.
    """
    global _config
    _config = None
    return load_config(config_path)


def validate_config_on_startup(config_path: str | Path | None = None) -> tuple[bool, list[str]]:
    """Validate configuration on application startup.

    Args:
        config_path: Path to configuration file.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    errors: list[str] = []

    try:
        config = load_config(config_path)

        # Validate storage paths exist or can be created
        storage = config.storage
        paths_to_check = [
            storage.checkpoints_path,
            storage.quarantine_path,
            storage.results_path,
            storage.audit_log_path,
            storage.alert_log_path,
        ]

        for path_str in paths_to_check:
            path = Path(path_str)
            if not path.exists():
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create directory {path}: {e}")

        # Validate watch path
        watch_path = Path(config.orchestrator.watch_path)
        if not watch_path.exists():
            try:
                watch_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create watch directory {watch_path}: {e}")

        return len(errors) == 0, errors

    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")
        return False, errors
