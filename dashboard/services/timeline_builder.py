"""TimelineBuilder service for constructing incident timeline events.

Builds timeline events from audit logs, validation results, and anomalies.
Supports both Bronze and Silver tier anomalies (T063).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

from src.models.anomaly import Anomaly
from src.models.validation_result import ValidationResult
from src.models.silver_anomaly import SchemaAnomaly, BusinessLogicAnomaly, FreshnessAnomaly
from src.lib.constants import SeverityLevel


@dataclass
class TimelineEvent:
    """Timeline event for incident visualization."""

    id: str
    event_type: str  # validation_start, validation_complete, anomaly_detected, alert_sent, acknowledged
    timestamp: datetime
    severity: SeverityLevel
    title: str
    description: str
    related_batch_id: str = ""
    related_anomaly_id: str = ""
    layer: str = "Bronze"
    asset: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventGroup:
    """Group of related timeline events."""

    id: str
    event_ids: list[str]
    correlation_type: str  # causal, common_cause, cascade
    title: str
    timestamp: datetime


class TimelineBuilder:
    """Builds timeline events from various data sources.

    Creates events from:
    - Validation results
    - Anomalies
    - Audit log entries
    """

    def __init__(self):
        """Initialize TimelineBuilder."""
        pass

    def get_timeline_events(
        self,
        validation_results: list[ValidationResult],
        anomalies: list[Anomaly] | None = None,
        audit_events: list[dict[str, Any]] | None = None,
        silver_anomalies: tuple[list[SchemaAnomaly], list[BusinessLogicAnomaly], list[FreshnessAnomaly]] | None = None,
        time_range: tuple[datetime, datetime] | None = None,
        severity_filter: list[SeverityLevel] | None = None,
        layer_filter: list[str] | None = None,
        asset_filter: list[str] | None = None,
        group_related: bool = True,
    ) -> tuple[list[TimelineEvent], list[EventGroup]]:
        """Get events for incident timeline.

        Args:
            validation_results: List of validation results.
            anomalies: Optional list of anomalies (extracted if not provided).
            audit_events: Optional list of audit log entries.
            silver_anomalies: Optional tuple of (schema, business_logic, freshness) anomaly lists.
            time_range: Optional (start, end) datetime filter.
            severity_filter: Optional list of severities to include.
            layer_filter: Optional list of layers to include.
            asset_filter: Optional list of assets to include.
            group_related: Whether to group related events.

        Returns:
            Tuple of (events, groups).
        """
        events: list[TimelineEvent] = []

        # Build events from validation results
        for result in validation_results:
            # Validation completion event
            event = TimelineEvent(
                id=f"val_{result.id}",
                event_type="validation_complete",
                timestamp=result.validated_at,
                severity=SeverityLevel.CRITICAL if not result.passed else SeverityLevel.INFO,
                title=f"Validation {'Failed' if not result.passed else 'Passed'}",
                description=f"Batch {result.batch_id}: {result.format_summary()}",
                related_batch_id=result.batch_id,
                layer="Bronze",
                asset=result.batch_id,
                metadata={
                    "health_score": result.health_score,
                    "anomaly_count": result.anomaly_count,
                    "duration_ms": result.duration_ms,
                },
            )

            # Apply filters
            if self._passes_filters(event, time_range, severity_filter, layer_filter, asset_filter):
                events.append(event)

            # Add anomaly events
            for anomaly in result.anomalies:
                anomaly_event = TimelineEvent(
                    id=f"anom_{anomaly.id}",
                    event_type="anomaly_detected",
                    timestamp=anomaly.detected_at,
                    severity=anomaly.severity,
                    title=f"{anomaly.severity.value}: {anomaly.failure_code.description}",
                    description=anomaly.root_cause,
                    related_batch_id=anomaly.batch_id,
                    related_anomaly_id=anomaly.id,
                    layer="Bronze",
                    asset=anomaly.batch_id,
                    metadata={
                        "failure_code": anomaly.failure_code.value,
                        "affected_count": anomaly.affected_count,
                        "severity_score": anomaly.severity_score,
                    },
                )

                if self._passes_filters(anomaly_event, time_range, severity_filter, layer_filter, asset_filter):
                    events.append(anomaly_event)

        # Build events from audit logs
        if audit_events:
            for audit in audit_events:
                event = self._audit_to_event(audit)
                if event and self._passes_filters(event, time_range, severity_filter, layer_filter, asset_filter):
                    events.append(event)

        # Build events from Silver tier anomalies (T063)
        if silver_anomalies:
            schema_anomalies, bl_anomalies, freshness_anomalies = silver_anomalies

            # Schema anomalies
            for anomaly in schema_anomalies:
                event = self._silver_anomaly_to_event(anomaly, "Schema", "Silver")
                if event and self._passes_filters(event, time_range, severity_filter, layer_filter, asset_filter):
                    events.append(event)

            # Business logic anomalies
            for anomaly in bl_anomalies:
                event = self._silver_anomaly_to_event(anomaly, "Business Logic", "Silver")
                if event and self._passes_filters(event, time_range, severity_filter, layer_filter, asset_filter):
                    events.append(event)

            # Freshness anomalies
            for anomaly in freshness_anomalies:
                event = self._silver_anomaly_to_event(anomaly, "Freshness", "Silver")
                if event and self._passes_filters(event, time_range, severity_filter, layer_filter, asset_filter):
                    events.append(event)

        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)

        # Group related events if requested
        groups: list[EventGroup] = []
        if group_related:
            groups = self._group_events(events)

        return events, groups

    def _passes_filters(
        self,
        event: TimelineEvent,
        time_range: tuple[datetime, datetime] | None,
        severity_filter: list[SeverityLevel] | None,
        layer_filter: list[str] | None,
        asset_filter: list[str] | None,
    ) -> bool:
        """Check if event passes all filters."""
        if time_range:
            start, end = time_range
            if not (start <= event.timestamp <= end):
                return False

        if severity_filter and event.severity not in severity_filter:
            return False

        if layer_filter and event.layer not in layer_filter:
            return False

        if asset_filter and event.asset not in asset_filter:
            return False

        return True

    def _silver_anomaly_to_event(
        self,
        anomaly: SchemaAnomaly | BusinessLogicAnomaly | FreshnessAnomaly,
        layer_name: str,
        tier: str,
    ) -> TimelineEvent | None:
        """Convert Silver tier anomaly to timeline event (T063).

        Args:
            anomaly: Silver tier anomaly.
            layer_name: Name of the layer (Schema, Business Logic, Freshness).
            tier: Tier name (Silver).

        Returns:
            TimelineEvent or None if conversion fails.
        """
        try:
            # Build title and description based on anomaly type
            title = f"[{tier}] {anomaly.failure_code.value}: {anomaly.failure_code.description}"

            if isinstance(anomaly, SchemaAnomaly):
                description = f"Affected columns: {', '.join(anomaly.affected_columns[:3])}"
                if len(anomaly.affected_columns) > 3:
                    description += f" (+{len(anomaly.affected_columns) - 3} more)"
                batch_id = anomaly.batch_id
                asset = batch_id
            elif isinstance(anomaly, BusinessLogicAnomaly):
                description = f"Rule: {anomaly.rule_id} - {anomaly.rule_description[:50]}"
                batch_id = anomaly.batch_id
                asset = batch_id
            elif isinstance(anomaly, FreshnessAnomaly):
                description = f"Source: {anomaly.source} | Expected: {anomaly.expected_threshold}m, Actual: {anomaly.actual_minutes}m"
                batch_id = ""
                asset = anomaly.source
            else:
                description = str(anomaly)
                batch_id = getattr(anomaly, "batch_id", "")
                asset = batch_id

            # Determine if blocking
            is_blocking = getattr(anomaly, "blocking", False)
            if is_blocking:
                title = f"🚫 {title}"

            return TimelineEvent(
                id=f"silver_{anomaly.id}",
                event_type="silver_anomaly_detected",
                timestamp=anomaly.timestamp,
                severity=anomaly.severity,
                title=title,
                description=description,
                related_batch_id=batch_id,
                related_anomaly_id=anomaly.id,
                layer=layer_name,
                asset=asset,
                metadata={
                    "tier": tier,
                    "failure_code": anomaly.failure_code.value,
                    "blocking": is_blocking,
                    "layer_name": layer_name,
                },
            )

        except Exception:
            return None

    def _audit_to_event(self, audit: dict[str, Any]) -> TimelineEvent | None:
        """Convert audit log entry to timeline event.

        Args:
            audit: Audit log entry dictionary.

        Returns:
            TimelineEvent or None if conversion fails.
        """
        try:
            timestamp_str = audit.get("timestamp", "")
            if not timestamp_str:
                return None

            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            event_type = audit.get("event_type", audit.get("event", "unknown"))

            # Map log level to severity
            level = audit.get("level", audit.get("log_level", "INFO")).upper()
            severity_map = {
                "CRITICAL": SeverityLevel.CRITICAL,
                "ERROR": SeverityLevel.CRITICAL,
                "WARNING": SeverityLevel.WARNING,
                "INFO": SeverityLevel.INFO,
                "DEBUG": SeverityLevel.INFO,
            }
            severity = severity_map.get(level, SeverityLevel.INFO)

            return TimelineEvent(
                id=f"audit_{audit.get('id', uuid4())}",
                event_type=event_type,
                timestamp=timestamp,
                severity=severity,
                title=audit.get("event", event_type),
                description=audit.get("message", str(audit)),
                related_batch_id=audit.get("batch_id", ""),
                layer=audit.get("layer", "Bronze"),
                asset=audit.get("asset", audit.get("source", "")),
                metadata=audit,
            )

        except Exception:
            return None

    def _group_events(self, events: list[TimelineEvent]) -> list[EventGroup]:
        """Group related events.

        Groups events that:
        - Share the same batch_id
        - Occur within 60 seconds of each other

        Args:
            events: List of timeline events.

        Returns:
            List of event groups.
        """
        groups: list[EventGroup] = []
        grouped_ids: set[str] = set()

        for event in events:
            if event.id in grouped_ids:
                continue

            # Find related events
            related = [event]
            for other in events:
                if other.id == event.id or other.id in grouped_ids:
                    continue

                # Check if related by batch_id
                if event.related_batch_id and event.related_batch_id == other.related_batch_id:
                    # Check temporal proximity (within 60 seconds)
                    time_diff = abs((event.timestamp - other.timestamp).total_seconds())
                    if time_diff <= 60:
                        related.append(other)

            # Create group if multiple events
            if len(related) > 1:
                group = EventGroup(
                    id=f"group_{uuid4()}",
                    event_ids=[e.id for e in related],
                    correlation_type="common_cause" if event.related_batch_id else "coincidental",
                    title=f"{len(related)} related events",
                    timestamp=event.timestamp,
                )
                groups.append(group)

                for e in related:
                    grouped_ids.add(e.id)

        return groups

    def get_event_details(
        self,
        event_id: str,
        events: list[TimelineEvent],
        validation_results: list[ValidationResult],
    ) -> dict[str, Any]:
        """Get full details for a timeline event.

        Args:
            event_id: ID of the event.
            events: List of timeline events.
            validation_results: List of validation results.

        Returns:
            Dict with event, related_anomaly, related_result, technical_details.
        """
        event = None
        for e in events:
            if e.id == event_id:
                event = e
                break

        if not event:
            return {}

        result: dict[str, Any] = {
            "event": event,
            "related_anomaly": None,
            "related_result": None,
            "technical_details": event.metadata,
        }

        # Find related validation result
        for vr in validation_results:
            if vr.batch_id == event.related_batch_id:
                result["related_result"] = vr

                # Find related anomaly
                if event.related_anomaly_id:
                    for anomaly in vr.anomalies:
                        if anomaly.id == event.related_anomaly_id:
                            result["related_anomaly"] = anomaly
                            break

                break

        return result
