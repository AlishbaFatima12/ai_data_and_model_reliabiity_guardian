"""Bronze log skill - Audit logging."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.anomaly import Anomaly
from src.models.validation_result import ValidationResult
from src.lib.logger import get_logger


class LogConfig(BaseModel):
    """Configuration for audit logging."""

    audit_log_dir: str = Field(
        default="logs/audit",
        description="Directory for audit log files",
    )
    log_format: str = Field(
        default="jsonl",
        description="Log format (jsonl or json)",
    )


class LogSkill:
    """Bronze skill for writing audit entries (FR-020, FR-021, FR-022).

    Writes validation decisions and anomalies to audit logs.
    """

    name: str = "bronze.log"

    def __init__(self, config: LogConfig | None = None):
        """Initialize the log skill.

        Args:
            config: Configuration for audit logging.
        """
        self.config = config or LogConfig()
        self._logger = get_logger("bronze.log")

    def log_validation_start(
        self,
        batch_id: str,
        source: str,
        record_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log validation start event.

        Args:
            batch_id: ID of the batch being validated.
            source: Source of the batch.
            record_count: Number of records.
            metadata: Optional additional metadata.
        """
        entry = {
            "event_type": "validation_start",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batch_id": batch_id,
            "source": source,
            "record_count": record_count,
            "metadata": metadata or {},
        }

        self._write_audit_entry(entry)
        self._logger.info(
            "validation_start",
            batch_id=batch_id,
            source=source,
            record_count=record_count,
        )

    def log_validation_complete(
        self,
        result: ValidationResult,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log validation completion event.

        Args:
            result: The validation result.
            metadata: Optional additional metadata.
        """
        entry = {
            "event_type": "validation_complete",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "batch_id": result.batch_id,
            "passed": result.passed,
            "anomaly_count": result.anomaly_count,
            "health_score": result.health_score,
            "duration_ms": result.duration_ms,
            "skills_executed": result.skills_executed,
            "metadata": metadata or {},
        }

        self._write_audit_entry(entry)
        self._logger.info(
            "validation_complete",
            batch_id=result.batch_id,
            passed=result.passed,
            anomaly_count=result.anomaly_count,
            health_score=result.health_score,
            duration_ms=result.duration_ms,
        )

    def log_anomaly(
        self,
        anomaly: Anomaly,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an anomaly detection event.

        Args:
            anomaly: The detected anomaly.
            metadata: Optional additional metadata.
        """
        entry = {
            "event_type": "anomaly_detected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anomaly_id": anomaly.id,
            "batch_id": anomaly.batch_id,
            "failure_code": anomaly.failure_code.value,
            "severity": anomaly.severity.value,
            "severity_score": anomaly.severity_score,
            "affected_count": anomaly.affected_count,
            "root_cause": anomaly.root_cause,
            "explanation": anomaly.explanation,
            "metadata": metadata or {},
        }

        self._write_audit_entry(entry)

        log_method = self._logger.warning if anomaly.severity.requires_alert else self._logger.info
        log_method(
            "anomaly_detected",
            anomaly_id=anomaly.id,
            batch_id=anomaly.batch_id,
            failure_code=anomaly.failure_code.value,
            severity=anomaly.severity.value,
            affected_count=anomaly.affected_count,
        )

    def log_skill_execution(
        self,
        skill_name: str,
        batch_id: str,
        duration_ms: float,
        passed: bool,
        anomaly_count: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log skill execution event.

        Args:
            skill_name: Name of the skill executed.
            batch_id: ID of the batch.
            duration_ms: Execution duration.
            passed: Whether the skill passed.
            anomaly_count: Number of anomalies detected.
            metadata: Optional additional metadata.
        """
        entry = {
            "event_type": "skill_execution",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skill_name": skill_name,
            "batch_id": batch_id,
            "duration_ms": duration_ms,
            "passed": passed,
            "anomaly_count": anomaly_count,
            "metadata": metadata or {},
        }

        self._write_audit_entry(entry)
        self._logger.debug(
            "skill_execution",
            skill_name=skill_name,
            batch_id=batch_id,
            duration_ms=duration_ms,
            passed=passed,
        )

    def log_custom_event(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Log a custom audit event.

        Args:
            event_type: Type of event.
            data: Event data.
        """
        entry = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }

        self._write_audit_entry(entry)
        self._logger.info(event_type, **data)

    def _write_audit_entry(self, entry: dict[str, Any]) -> None:
        """Write an entry to the audit log file.

        Args:
            entry: Log entry to write.
        """
        log_dir = Path(self.config.audit_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use date-based file naming
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{date_str}.jsonl"
        filepath = log_dir / filename

        try:
            with open(filepath, "a", encoding="utf-8") as f:
                json.dump(entry, f, default=str)
                f.write("\n")
        except Exception as e:
            self._logger.error("audit_write_failed", error=str(e), entry=entry)

    def read_audit_log(
        self,
        date: datetime | None = None,
        event_type: str | None = None,
        batch_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read entries from the audit log.

        Args:
            date: Date to read logs from (default: today).
            event_type: Filter by event type.
            batch_id: Filter by batch ID.
            limit: Maximum entries to return.

        Returns:
            List of matching log entries.
        """
        log_dir = Path(self.config.audit_log_dir)
        if not log_dir.exists():
            return []

        if date is None:
            date = datetime.now(timezone.utc)

        date_str = date.strftime("%Y-%m-%d")
        filename = f"{date_str}.jsonl"
        filepath = log_dir / filename

        if not filepath.exists():
            return []

        entries = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    entry = json.loads(line)

                    # Apply filters
                    if event_type and entry.get("event_type") != event_type:
                        continue
                    if batch_id and entry.get("batch_id") != batch_id:
                        continue

                    entries.append(entry)

                    if len(entries) >= limit:
                        break

        except Exception:
            pass

        return entries
