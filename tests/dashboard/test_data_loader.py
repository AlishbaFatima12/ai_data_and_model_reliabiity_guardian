"""Unit tests for DataLoader service."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from dashboard.services.data_loader import DataLoader, DataLoaderResult, AnomalyResult
from src.lib.constants import SeverityLevel


class TestDataLoaderInit:
    """Tests for DataLoader initialization."""

    def test_init_with_default_path(self):
        """Test DataLoader initializes with current directory."""
        loader = DataLoader()
        assert loader.base_path == Path.cwd()

    def test_init_with_custom_path(self, temp_data_dir: Path):
        """Test DataLoader initializes with custom path."""
        loader = DataLoader(temp_data_dir)
        assert loader.base_path == temp_data_dir


class TestGetLatestResults:
    """Tests for get_latest_results method."""

    def test_returns_empty_when_no_results_dir(self, temp_data_dir: Path):
        """Test returns empty result when results directory doesn't exist."""
        # Remove the results directory
        results_dir = temp_data_dir / "data" / "results"
        if results_dir.exists():
            results_dir.rmdir()

        loader = DataLoader(temp_data_dir)
        result = loader.get_latest_results()

        assert isinstance(result, DataLoaderResult)
        assert result.results == []
        assert result.total_count == 0
        assert result.has_more is False

    def test_returns_results_from_files(self, populated_data_dir: Path):
        """Test returns validation results from JSON files."""
        loader = DataLoader(populated_data_dir)
        result = loader.get_latest_results()

        assert len(result.results) >= 1
        assert result.total_count >= 1

    def test_respects_limit_parameter(self, populated_data_dir: Path):
        """Test limit parameter restricts results."""
        loader = DataLoader(populated_data_dir)
        result = loader.get_latest_results(limit=1)

        assert len(result.results) <= 1

    def test_filters_by_since_parameter(self, populated_data_dir: Path):
        """Test since parameter filters old results."""
        loader = DataLoader(populated_data_dir)

        # Use future date to filter out all results
        future = datetime.now(timezone.utc) + timedelta(days=1)
        result = loader.get_latest_results(since=future)

        assert len(result.results) == 0

    def test_handles_invalid_json_gracefully(self, temp_data_dir: Path):
        """Test handles corrupted JSON files without crashing."""
        results_dir = temp_data_dir / "data" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        bad_file = results_dir / "bad.json"
        bad_file.write_text("not valid json {{{")

        loader = DataLoader(temp_data_dir)
        result = loader.get_latest_results()

        # Should not crash, just skip bad file
        assert isinstance(result, DataLoaderResult)


class TestGetHealthState:
    """Tests for get_health_state method."""

    def test_returns_default_when_no_file(self, temp_data_dir: Path):
        """Test returns default health when state file doesn't exist."""
        loader = DataLoader(temp_data_dir)
        health, is_stale = loader.get_health_state()

        assert health is not None
        assert health.overall_score >= 0
        assert is_stale is True

    def test_returns_health_from_file(self, populated_data_dir: Path):
        """Test returns health state from file."""
        loader = DataLoader(populated_data_dir)
        health, is_stale = loader.get_health_state()

        assert health is not None
        assert health.overall_score == 75.0

    def test_detects_stale_data(self, temp_data_dir: Path):
        """Test correctly identifies stale health data."""
        # Create health file with old timestamp
        health_file = temp_data_dir / "data" / "state" / "health.json"
        health_file.parent.mkdir(parents=True, exist_ok=True)

        old_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        health_data = {
            "overall_score": 80.0,
            "component_scores": {},
            "trend": "stable",
            "active_anomalies": 0,
            "last_updated": old_time.isoformat(),
            "batches_evaluated": 5,
            "history": [],
        }

        with open(health_file, "w") as f:
            json.dump(health_data, f)

        loader = DataLoader(temp_data_dir)
        health, is_stale = loader.get_health_state()

        assert is_stale is True


class TestGetAnomalies:
    """Tests for get_anomalies method."""

    def test_returns_empty_when_no_data(self, temp_data_dir: Path):
        """Test returns empty result when no anomalies."""
        loader = DataLoader(temp_data_dir)
        result = loader.get_anomalies()

        assert isinstance(result, AnomalyResult)
        assert result.anomalies == []

    def test_returns_anomalies_from_results(self, populated_data_dir: Path):
        """Test extracts anomalies from validation results."""
        loader = DataLoader(populated_data_dir)
        result = loader.get_anomalies()

        assert len(result.anomalies) >= 1

    def test_filters_by_severity(self, populated_data_dir: Path):
        """Test severity filter works correctly."""
        loader = DataLoader(populated_data_dir)

        # Filter for CRITICAL only (our sample has WARNING)
        result = loader.get_anomalies(severity_filter=[SeverityLevel.CRITICAL])

        # Should return empty since sample is WARNING
        for anomaly in result.anomalies:
            assert anomaly.severity == SeverityLevel.CRITICAL

    def test_counts_by_severity(self, populated_data_dir: Path):
        """Test severity counts are calculated correctly."""
        loader = DataLoader(populated_data_dir)
        result = loader.get_anomalies()

        assert "CRITICAL" in result.by_severity
        assert "WARNING" in result.by_severity
        assert "INFO" in result.by_severity

    def test_respects_limit(self, populated_data_dir: Path):
        """Test limit parameter restricts anomalies."""
        loader = DataLoader(populated_data_dir)
        result = loader.get_anomalies(limit=1)

        assert len(result.anomalies) <= 1


class TestHasData:
    """Tests for has_data method."""

    def test_returns_false_when_no_results(self, temp_data_dir: Path):
        """Test returns False when no validation data exists."""
        loader = DataLoader(temp_data_dir)
        assert loader.has_data() is False

    def test_returns_true_when_results_exist(self, populated_data_dir: Path):
        """Test returns True when validation data exists."""
        loader = DataLoader(populated_data_dir)
        assert loader.has_data() is True


class TestGetAuditEvents:
    """Tests for get_audit_events method."""

    def test_returns_empty_when_no_logs(self, temp_data_dir: Path):
        """Test returns empty list when no audit logs exist."""
        loader = DataLoader(temp_data_dir)
        events = loader.get_audit_events()

        assert events == []

    def test_returns_events_from_jsonl(self, populated_data_dir: Path):
        """Test reads events from JSONL audit files."""
        loader = DataLoader(populated_data_dir)
        events = loader.get_audit_events()

        assert len(events) >= 1
        assert "timestamp" in events[0]

    def test_respects_limit(self, populated_data_dir: Path):
        """Test limit parameter restricts events."""
        loader = DataLoader(populated_data_dir)
        events = loader.get_audit_events(limit=2)

        assert len(events) <= 2

    def test_sorts_by_timestamp_descending(self, populated_data_dir: Path):
        """Test events are sorted newest first."""
        loader = DataLoader(populated_data_dir)
        events = loader.get_audit_events()

        if len(events) >= 2:
            # First event should be newer than second
            t1 = events[0].get("timestamp", "")
            t2 = events[1].get("timestamp", "")
            assert t1 >= t2
