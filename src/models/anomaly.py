"""Anomaly model for DMRG-FTE."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel


class Anomaly(BaseModel):
    """Represents a detected data quality anomaly.

    Per spec: Anomalies have failure codes (DV-001 to DV-008), severity levels,
    and detailed information about affected records.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str = Field(..., description="ID of the batch where anomaly was found")
    failure_code: FailureCode = Field(..., description="Failure code (DV-001 to DV-008)")
    severity: SeverityLevel = Field(..., description="Severity level (INFO/WARNING/CRITICAL)")
    severity_score: float = Field(
        ge=0.0, le=100.0,
        description="Calculated severity score (0-100)",
    )
    affected_records: list[int] = Field(
        default_factory=list,
        description="Indices of affected records",
    )
    affected_fields: list[str] = Field(
        default_factory=list,
        description="Names of affected fields",
    )
    root_cause: str = Field(..., description="Brief description of the root cause")
    explanation: str = Field(
        default="",
        description="Detailed explanation of the anomaly",
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the anomaly was detected",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the anomaly",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @property
    def affected_count(self) -> int:
        """Get the count of affected records."""
        return len(self.affected_records)

    @property
    def requires_alert(self) -> bool:
        """Check if this anomaly requires an alert."""
        return self.severity.requires_alert

    @property
    def requires_quarantine(self) -> bool:
        """Check if this anomaly requires quarantine."""
        return self.severity.requires_quarantine

    @classmethod
    def create(
        cls,
        batch_id: str,
        failure_code: FailureCode,
        severity: SeverityLevel,
        severity_score: float,
        root_cause: str,
        affected_records: list[int] | None = None,
        affected_fields: list[str] | None = None,
        explanation: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "Anomaly":
        """Create a new anomaly instance.

        Args:
            batch_id: ID of the batch where anomaly was found.
            failure_code: The failure code.
            severity: Severity level.
            severity_score: Calculated severity score.
            root_cause: Brief description of root cause.
            affected_records: List of affected record indices.
            affected_fields: List of affected field names.
            explanation: Detailed explanation.
            metadata: Additional metadata.

        Returns:
            New Anomaly instance.
        """
        return cls(
            batch_id=batch_id,
            failure_code=failure_code,
            severity=severity,
            severity_score=severity_score,
            root_cause=root_cause,
            affected_records=affected_records or [],
            affected_fields=affected_fields or [],
            explanation=explanation,
            metadata=metadata or {},
        )

    def format_summary(self) -> str:
        """Format a human-readable summary of the anomaly.

        Returns:
            Summary string.
        """
        return (
            f"[{self.severity.value}] {self.failure_code.value}: {self.root_cause} "
            f"(Score: {self.severity_score:.1f}, Affected: {self.affected_count} records)"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")
