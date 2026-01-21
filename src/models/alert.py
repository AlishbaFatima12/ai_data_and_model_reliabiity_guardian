"""Alert model for DMRG-FTE."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.lib.constants import AlertChannel, SeverityLevel


class Alert(BaseModel):
    """Alert for WARNING or CRITICAL anomalies.

    Per spec FR-011, FR-012, FR-013: Generate alerts for anomalies
    with appropriate severity and timing.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    anomaly_id: str = Field(..., description="ID of the anomaly that triggered this alert")
    batch_id: str = Field(..., description="ID of the batch where anomaly was found")
    severity: SeverityLevel = Field(..., description="Alert severity level")
    message: str = Field(..., description="Alert message")
    channel: AlertChannel = Field(
        default=AlertChannel.CONSOLE,
        description="Output channel for the alert",
    )
    sent_timestamp: datetime | None = Field(
        default=None,
        description="When the alert was sent (None if not yet sent)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the alert was created",
    )
    failure_code: str = Field(default="", description="Associated failure code")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }

    @property
    def is_sent(self) -> bool:
        """Check if the alert has been sent."""
        return self.sent_timestamp is not None

    @property
    def is_critical(self) -> bool:
        """Check if this is a CRITICAL alert."""
        return self.severity == SeverityLevel.CRITICAL

    @property
    def is_warning(self) -> bool:
        """Check if this is a WARNING alert."""
        return self.severity == SeverityLevel.WARNING

    def mark_sent(self) -> None:
        """Mark the alert as sent."""
        self.sent_timestamp = datetime.now(timezone.utc)

    @classmethod
    def from_anomaly(
        cls,
        anomaly_id: str,
        batch_id: str,
        severity: SeverityLevel,
        failure_code: str,
        root_cause: str,
        affected_count: int,
        channel: AlertChannel = AlertChannel.CONSOLE,
    ) -> "Alert":
        """Create an alert from anomaly information.

        Args:
            anomaly_id: ID of the source anomaly.
            batch_id: ID of the batch.
            severity: Severity level.
            failure_code: Failure code (e.g., DV-001).
            root_cause: Brief description of root cause.
            affected_count: Number of affected records.
            channel: Output channel.

        Returns:
            New Alert instance.
        """
        message = (
            f"[{severity.value}] {failure_code}: {root_cause} "
            f"({affected_count} records affected in batch {batch_id})"
        )

        return cls(
            anomaly_id=anomaly_id,
            batch_id=batch_id,
            severity=severity,
            message=message,
            channel=channel,
            failure_code=failure_code,
        )

    def format_console(self) -> str:
        """Format alert for console output.

        Returns:
            Formatted string.
        """
        prefix = "🚨" if self.is_critical else "⚠️"
        return f"{prefix} ALERT: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")
