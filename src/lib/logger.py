"""Structured logging setup using structlog for DMRG-FTE."""

import sys
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _add_timestamp(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add ISO timestamp to log events."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def _add_service_context(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add service context to log events."""
    event_dict.setdefault("service", "dmrg-fte")
    event_dict.setdefault("version", "0.1.0")
    return event_dict


def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: Path | None = None,
) -> None:
    """Configure structlog for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: If True, output JSON; otherwise human-readable
        log_file: Optional path to write logs to file
    """
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _add_timestamp,
        _add_service_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    import logging

    # Map string level to numeric logging level
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    numeric_level = level_map.get(level.upper(), logging.INFO)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically module name)
        **initial_context: Initial context values to bind

    Returns:
        Configured structlog BoundLogger
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger_name=name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


def bind_correlation_id(correlation_id: str) -> None:
    """Bind a correlation ID to the current context.

    Args:
        correlation_id: Unique identifier for request tracing
    """
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()


def log_validation_start(
    logger: structlog.BoundLogger,
    batch_id: str,
    source: str,
    record_count: int,
) -> None:
    """Log validation start event per FR-020."""
    logger.info(
        "validation_started",
        batch_id=batch_id,
        source=source,
        record_count=record_count,
        event_type="validation_lifecycle",
    )


def log_validation_complete(
    logger: structlog.BoundLogger,
    batch_id: str,
    passed: bool,
    anomaly_count: int,
    duration_ms: float,
    health_score: float,
) -> None:
    """Log validation completion event per FR-020."""
    logger.info(
        "validation_completed",
        batch_id=batch_id,
        passed=passed,
        anomaly_count=anomaly_count,
        duration_ms=duration_ms,
        health_score=health_score,
        event_type="validation_lifecycle",
    )


def log_anomaly_detected(
    logger: structlog.BoundLogger,
    batch_id: str,
    failure_code: str,
    severity: str,
    affected_records: int,
    root_cause: str,
) -> None:
    """Log anomaly detection event per FR-021."""
    logger.warning(
        "anomaly_detected",
        batch_id=batch_id,
        failure_code=failure_code,
        severity=severity,
        affected_records=affected_records,
        root_cause=root_cause,
        event_type="anomaly",
    )


def log_alert_dispatched(
    logger: structlog.BoundLogger,
    alert_id: str,
    severity: str,
    channel: str,
    message: str,
) -> None:
    """Log alert dispatch event per FR-022."""
    logger.info(
        "alert_dispatched",
        alert_id=alert_id,
        severity=severity,
        channel=channel,
        message=message,
        event_type="alert",
    )


def log_checkpoint_saved(
    logger: structlog.BoundLogger,
    batch_id: str,
    checkpoint_id: str,
    position: int,
) -> None:
    """Log checkpoint save event."""
    logger.debug(
        "checkpoint_saved",
        batch_id=batch_id,
        checkpoint_id=checkpoint_id,
        position=position,
        event_type="checkpoint",
    )


def log_heartbeat(
    logger: structlog.BoundLogger,
    status: str,
    uptime_seconds: float,
    batches_processed: int,
) -> None:
    """Log heartbeat event per FR-014."""
    logger.debug(
        "heartbeat",
        status=status,
        uptime_seconds=uptime_seconds,
        batches_processed=batches_processed,
        event_type="heartbeat",
    )
