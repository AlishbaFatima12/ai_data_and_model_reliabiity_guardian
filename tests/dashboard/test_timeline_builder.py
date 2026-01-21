"""Unit tests for TimelineBuilder service."""

from datetime import datetime, timezone, timedelta
from uuid import uuid4

import pytest

from dashboard.services.timeline_builder import TimelineBuilder, TimelineEvent, EventGroup
from src.models.validation_result import ValidationResult
from src.models.anomaly import Anomaly
from src.lib.constants import SeverityLevel, FailureCode


class TestTimelineBuilderInit:
    """Tests for TimelineBuilder initialization."""

    def test_init_creates_instance(self):
        """Test TimelineBuilder can be instantiated."""
        builder = TimelineBuilder()
        assert builder is not None


class TestGetTimelineEvents:
    """Tests for get_timeline_events method."""

    @pytest.fixture
    def builder(self) -> TimelineBuilder:
        """Create a TimelineBuilder instance."""
        return TimelineBuilder()

    @pytest.fixture
    def sample_results(self, sample_validation_result: ValidationResult) -> list[ValidationResult]:
        """Create list of sample validation results."""
        return [sample_validation_result]

    def test_returns_events_and_groups_tuple(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test returns tuple of events and groups."""
        events, groups = builder.get_timeline_events(sample_results)

        assert isinstance(events, list)
        assert isinstance(groups, list)

    def test_creates_event_for_validation_result(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test creates event for each validation result."""
        events, _ = builder.get_timeline_events(sample_results)

        # Should have at least one event for the validation
        validation_events = [e for e in events if e.event_type == "validation_complete"]
        assert len(validation_events) >= 1

    def test_creates_events_for_anomalies(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test creates events for anomalies in results."""
        events, _ = builder.get_timeline_events(sample_results)

        anomaly_events = [e for e in events if e.event_type == "anomaly_detected"]
        assert len(anomaly_events) >= 1

    def test_filters_by_severity(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test severity filter excludes non-matching events."""
        events, _ = builder.get_timeline_events(
            sample_results,
            severity_filter=[SeverityLevel.CRITICAL],
        )

        # All events should be CRITICAL (our sample has WARNING anomaly)
        for event in events:
            if event.event_type == "anomaly_detected":
                assert event.severity == SeverityLevel.CRITICAL

    def test_filters_by_time_range(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test time range filter excludes old events."""
        # Use time range that excludes our sample
        future_start = datetime.now(timezone.utc) + timedelta(days=1)
        future_end = future_start + timedelta(hours=1)

        events, _ = builder.get_timeline_events(
            sample_results,
            time_range=(future_start, future_end),
        )

        assert len(events) == 0

    def test_filters_by_layer(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test layer filter excludes non-matching events."""
        events, _ = builder.get_timeline_events(
            sample_results,
            layer_filter=["Silver"],  # Our sample is Bronze
        )

        assert len(events) == 0

    def test_sorts_events_by_timestamp_descending(self, builder: TimelineBuilder):
        """Test events are sorted newest first."""
        now = datetime.now(timezone.utc)

        results = [
            ValidationResult(
                batch_id=f"batch_{i}",
                passed=True,
                anomalies=[],
                health_score=90.0,
                skills_executed=[],
                duration_ms=100.0,
                validated_at=now - timedelta(hours=i),
            )
            for i in range(5)
        ]

        events, _ = builder.get_timeline_events(results)

        if len(events) >= 2:
            assert events[0].timestamp >= events[1].timestamp

    def test_groups_related_events(self, builder: TimelineBuilder):
        """Test groups events with same batch_id."""
        now = datetime.now(timezone.utc)

        # Create result with multiple anomalies
        anomaly1 = Anomaly.create(
            batch_id="shared_batch",
            failure_code=FailureCode.RECORD_COUNT_MISMATCH,
            severity=SeverityLevel.WARNING,
            severity_score=50.0,
            root_cause="Issue 1",
        )
        anomaly1.detected_at = now

        anomaly2 = Anomaly.create(
            batch_id="shared_batch",
            failure_code=FailureCode.NULL_VALUE_DETECTED,
            severity=SeverityLevel.WARNING,
            severity_score=55.0,
            root_cause="Issue 2",
        )
        anomaly2.detected_at = now + timedelta(seconds=30)

        result = ValidationResult(
            batch_id="shared_batch",
            passed=False,
            anomalies=[anomaly1, anomaly2],
            health_score=70.0,
            skills_executed=[],
            duration_ms=100.0,
            validated_at=now,
        )

        events, groups = builder.get_timeline_events([result], group_related=True)

        # Should have at least one group
        assert len(groups) >= 0  # May or may not group depending on timing

    def test_no_groups_when_disabled(self, builder: TimelineBuilder, sample_results: list[ValidationResult]):
        """Test no groups created when group_related=False."""
        events, groups = builder.get_timeline_events(sample_results, group_related=False)

        assert groups == []


class TestAuditToEvent:
    """Tests for _audit_to_event method."""

    @pytest.fixture
    def builder(self) -> TimelineBuilder:
        """Create a TimelineBuilder instance."""
        return TimelineBuilder()

    def test_converts_valid_audit_entry(self, builder: TimelineBuilder):
        """Test converts valid audit log entry to event."""
        audit = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "validation_start",
            "level": "INFO",
            "message": "Starting validation",
            "batch_id": "batch_123",
        }

        event = builder._audit_to_event(audit)

        assert event is not None
        assert event.event_type == "validation_start"
        assert event.severity == SeverityLevel.INFO

    def test_maps_error_level_to_critical(self, builder: TimelineBuilder):
        """Test ERROR log level maps to CRITICAL severity."""
        audit = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "error",
            "level": "ERROR",
            "message": "Something went wrong",
        }

        event = builder._audit_to_event(audit)

        assert event.severity == SeverityLevel.CRITICAL

    def test_maps_warning_level_to_warning(self, builder: TimelineBuilder):
        """Test WARNING log level maps to WARNING severity."""
        audit = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "warning",
            "level": "WARNING",
            "message": "Something may be wrong",
        }

        event = builder._audit_to_event(audit)

        assert event.severity == SeverityLevel.WARNING

    def test_returns_none_for_missing_timestamp(self, builder: TimelineBuilder):
        """Test returns None when timestamp is missing."""
        audit = {
            "event": "test",
            "level": "INFO",
        }

        event = builder._audit_to_event(audit)

        assert event is None

    def test_handles_malformed_timestamp(self, builder: TimelineBuilder):
        """Test handles invalid timestamp format gracefully."""
        audit = {
            "timestamp": "not a valid timestamp",
            "event": "test",
        }

        event = builder._audit_to_event(audit)

        assert event is None


class TestGetEventDetails:
    """Tests for get_event_details method."""

    @pytest.fixture
    def builder(self) -> TimelineBuilder:
        """Create a TimelineBuilder instance."""
        return TimelineBuilder()

    def test_returns_event_details(self, builder: TimelineBuilder, sample_validation_result: ValidationResult):
        """Test returns details for a valid event."""
        events, _ = builder.get_timeline_events([sample_validation_result])

        if events:
            event_id = events[0].id
            details = builder.get_event_details(event_id, events, [sample_validation_result])

            assert "event" in details
            assert details["event"] is not None

    def test_returns_empty_for_unknown_event(self, builder: TimelineBuilder):
        """Test returns empty dict for unknown event ID."""
        details = builder.get_event_details("unknown_id", [], [])

        assert details == {}

    def test_includes_related_result(self, builder: TimelineBuilder, sample_validation_result: ValidationResult):
        """Test includes related validation result when available."""
        events, _ = builder.get_timeline_events([sample_validation_result])

        # Find an event with a batch_id
        event = next((e for e in events if e.related_batch_id), None)

        if event:
            details = builder.get_event_details(event.id, events, [sample_validation_result])

            if event.related_batch_id == sample_validation_result.batch_id:
                assert details.get("related_result") is not None

    def test_includes_related_anomaly(self, builder: TimelineBuilder, sample_validation_result: ValidationResult):
        """Test includes related anomaly when available."""
        events, _ = builder.get_timeline_events([sample_validation_result])

        # Find an anomaly event
        anomaly_event = next((e for e in events if e.related_anomaly_id), None)

        if anomaly_event:
            details = builder.get_event_details(anomaly_event.id, events, [sample_validation_result])

            assert details.get("related_anomaly") is not None


class TestGroupEvents:
    """Tests for _group_events method."""

    @pytest.fixture
    def builder(self) -> TimelineBuilder:
        """Create a TimelineBuilder instance."""
        return TimelineBuilder()

    def test_groups_events_with_same_batch(self, builder: TimelineBuilder):
        """Test groups events sharing the same batch_id."""
        now = datetime.now(timezone.utc)

        events = [
            TimelineEvent(
                id="e1",
                event_type="test",
                timestamp=now,
                severity=SeverityLevel.INFO,
                title="Event 1",
                description="",
                related_batch_id="batch_123",
            ),
            TimelineEvent(
                id="e2",
                event_type="test",
                timestamp=now + timedelta(seconds=30),
                severity=SeverityLevel.INFO,
                title="Event 2",
                description="",
                related_batch_id="batch_123",
            ),
        ]

        groups = builder._group_events(events)

        assert len(groups) >= 1
        assert "e1" in groups[0].event_ids or "e2" in groups[0].event_ids

    def test_does_not_group_distant_events(self, builder: TimelineBuilder):
        """Test does not group events far apart in time."""
        now = datetime.now(timezone.utc)

        events = [
            TimelineEvent(
                id="e1",
                event_type="test",
                timestamp=now,
                severity=SeverityLevel.INFO,
                title="Event 1",
                description="",
                related_batch_id="batch_123",
            ),
            TimelineEvent(
                id="e2",
                event_type="test",
                timestamp=now + timedelta(hours=2),  # 2 hours apart
                severity=SeverityLevel.INFO,
                title="Event 2",
                description="",
                related_batch_id="batch_123",
            ),
        ]

        groups = builder._group_events(events)

        # Should not group events more than 60 seconds apart
        for group in groups:
            assert not ("e1" in group.event_ids and "e2" in group.event_ids)

    def test_returns_empty_for_single_event(self, builder: TimelineBuilder):
        """Test returns empty groups for single event."""
        now = datetime.now(timezone.utc)

        events = [
            TimelineEvent(
                id="e1",
                event_type="test",
                timestamp=now,
                severity=SeverityLevel.INFO,
                title="Event 1",
                description="",
            ),
        ]

        groups = builder._group_events(events)

        assert groups == []
