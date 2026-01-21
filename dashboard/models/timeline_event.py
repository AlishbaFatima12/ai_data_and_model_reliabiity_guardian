"""TimelineEvent model for incident timeline visualization.

Represents events displayed on the incident timeline per FR-018 to FR-022.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.lib.constants import SeverityLevel


@dataclass
class TimelineEvent:
    """Timeline event for incident visualization.

    Attributes:
        id: Unique event identifier.
        event_type: Type of event (validation_start, validation_complete, etc.).
        timestamp: When the event occurred.
        severity: Severity level for color coding.
        title: Short title (plain language).
        description: Detailed description.
        related_batch_id: Associated batch ID.
        related_anomaly_id: Associated anomaly ID (if applicable).
        layer: Intelligence layer (Bronze, Silver, Gold).
        asset: Affected asset name.
        metadata: Additional event data.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    severity: SeverityLevel = SeverityLevel.INFO
    title: str = ""
    description: str = ""
    related_batch_id: str = ""
    related_anomaly_id: str = ""
    layer: str = "Bronze"
    asset: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "related_batch_id": self.related_batch_id,
            "related_anomaly_id": self.related_anomaly_id,
            "layer": self.layer,
            "asset": self.asset,
            "metadata": self.metadata,
        }


@dataclass
class EventGroup:
    """Group of related timeline events.

    Attributes:
        id: Unique group identifier.
        event_ids: List of event IDs in this group.
        correlation_type: Type of correlation (causal, common_cause, cascade).
        title: Group title.
        timestamp: Representative timestamp for the group.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    event_ids: list[str] = field(default_factory=list)
    correlation_type: str = "common_cause"
    title: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "event_ids": self.event_ids,
            "correlation_type": self.correlation_type,
            "title": self.title,
            "timestamp": self.timestamp.isoformat(),
        }
