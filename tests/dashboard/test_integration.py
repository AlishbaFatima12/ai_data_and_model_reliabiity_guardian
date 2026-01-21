"""Integration tests for Dashboard components."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from dashboard.services.data_loader import DataLoader
from dashboard.services.health_calculator import HealthCalculator
from dashboard.services.impact_translator import ImpactTranslator
from dashboard.services.timeline_builder import TimelineBuilder
from src.models.anomaly import Anomaly
from src.models.health_score import HealthScore, ComponentScore
from src.models.validation_result import ValidationResult
from src.lib.constants import FailureCode, SeverityLevel


class TestEndToEndDataFlow:
    """Test complete data flow from loader through services."""

    @pytest.fixture
    def full_data_dir(self, tmp_path: Path) -> Path:
        """Create populated data directory with realistic data."""
        # Create directories
        (tmp_path / "data" / "results").mkdir(parents=True)
        (tmp_path / "data" / "state").mkdir(parents=True)
        (tmp_path / "logs" / "audit").mkdir(parents=True)
        (tmp_path / "config").mkdir(parents=True)

        now = datetime.now(timezone.utc)

        # Create multiple validation results
        for i in range(5):
            anomalies = []
            if i % 2 == 0:  # Add anomaly to even batches
                anomaly = Anomaly.create(
                    batch_id=f"batch_{i:03d}",
                    failure_code=FailureCode.NULL_VALUE_DETECTED,
                    severity=SeverityLevel.WARNING if i < 4 else SeverityLevel.CRITICAL,
                    severity_score=50.0 + i * 10,
                    root_cause=f"Issue in batch {i}",
                )
                anomaly.detected_at = now - timedelta(hours=i)
                anomalies.append(anomaly)

            result = ValidationResult(
                batch_id=f"batch_{i:03d}",
                passed=len(anomalies) == 0,
                anomalies=anomalies,
                health_score=90.0 - i * 5,
                skills_executed=["null_check", "type_check"],
                duration_ms=100.0 + i * 10,
                validated_at=now - timedelta(hours=i),
            )

            with open(tmp_path / "data" / "results" / f"result_{i:03d}.json", "w") as f:
                json.dump(result.to_dict(), f)

        # Create health state
        health = HealthScore(
            overall_score=72.0,
            component_scores={
                "bronze": ComponentScore(
                    name="Data Validation",
                    score=72.0,
                    anomaly_count=3,
                    last_check=now,
                ),
            },
            trend="degrading",
            active_anomalies=3,
            last_updated=now,
            batches_evaluated=5,
            history=[
                (now - timedelta(hours=i), 75.0 - i) for i in range(24)
            ],
        )

        with open(tmp_path / "data" / "state" / "health.json", "w") as f:
            json.dump(health.model_dump(mode="json"), f)

        # Create audit logs
        with open(tmp_path / "logs" / "audit" / "audit.jsonl", "w") as f:
            for i in range(10):
                event = {
                    "timestamp": (now - timedelta(minutes=i * 10)).isoformat(),
                    "event": "validation_complete" if i % 2 == 0 else "anomaly_detected",
                    "level": "INFO" if i % 3 != 0 else "WARNING",
                    "message": f"Event {i}",
                    "batch_id": f"batch_{i % 5:03d}",
                }
                f.write(json.dumps(event) + "\n")

        # Create translations config
        translations = {
            "health_summary": {
                "excellent": {"template": "All systems healthy."},
                "good": {"template": "{warning_count} minor issues detected."},
                "fair": {"template": "{issue_count} issues need attention."},
                "critical": {"template": "ALERT: {critical_count} critical issues!"},
            },
            "failure_codes": {
                "DV-002": {
                    "name": "Missing Required Data",
                    "business_description": "Required data is missing.",
                    "impact_template": "Data completeness affected.",
                    "affected_processes": ["Data processing", "Reporting"],
                    "recommended_actions": ["Review data entry", "Check sources"],
                    "severity_impact": "Medium",
                },
            },
        }

        import yaml
        with open(tmp_path / "config" / "translations.yaml", "w") as f:
            yaml.dump(translations, f)

        return tmp_path

    def test_loader_to_calculator_flow(self, full_data_dir: Path):
        """Test data flows from loader to calculator."""
        loader = DataLoader(full_data_dir)
        calculator = HealthCalculator()

        # Load data
        health, is_stale = loader.get_health_state()
        anomaly_result = loader.get_anomalies()

        # Process with calculator
        overall_health = calculator.get_overall_health(health)
        layer_health = calculator.get_layer_health(health, anomaly_result.anomalies)
        severity_counts = calculator.get_severity_counts(anomaly_result.anomalies)

        # Verify integration
        assert overall_health.score == 72.0
        assert overall_health.trend == "degrading"
        assert len(layer_health) == 5  # All tiers
        assert severity_counts["WARNING"] + severity_counts["CRITICAL"] > 0

    def test_loader_to_translator_flow(self, full_data_dir: Path):
        """Test data flows from loader to translator."""
        loader = DataLoader(full_data_dir)
        translator = ImpactTranslator(full_data_dir / "config" / "translations.yaml")
        calculator = HealthCalculator()

        # Load data
        health, _ = loader.get_health_state()
        anomaly_result = loader.get_anomalies()

        # Calculate severity counts
        severity_counts = calculator.get_severity_counts(anomaly_result.anomalies)

        # Translate
        summary = translator.translate_health_summary(health, severity_counts)

        # Verify integration
        assert isinstance(summary, str)
        assert len(summary) > 0

        # Translate anomalies
        if anomaly_result.anomalies:
            impact = translator.translate_anomaly(anomaly_result.anomalies[0])
            assert impact.business_description != ""
            assert len(impact.affected_processes) >= 1

    def test_loader_to_timeline_flow(self, full_data_dir: Path):
        """Test data flows from loader to timeline builder."""
        loader = DataLoader(full_data_dir)
        builder = TimelineBuilder()

        # Load data
        results = loader.get_latest_results()
        audit_events = loader.get_audit_events()

        # Build timeline
        events, groups = builder.get_timeline_events(
            results.results,
            audit_events=audit_events,
            group_related=True,
        )

        # Verify integration
        assert len(events) > 0
        assert all(hasattr(e, "timestamp") for e in events)
        assert all(hasattr(e, "event_type") for e in events)

    def test_full_dashboard_data_pipeline(self, full_data_dir: Path):
        """Test complete dashboard data pipeline."""
        loader = DataLoader(full_data_dir)
        calculator = HealthCalculator()
        translator = ImpactTranslator(full_data_dir / "config" / "translations.yaml")
        builder = TimelineBuilder()

        # Step 1: Load all data
        health, is_stale = loader.get_health_state()
        results = loader.get_latest_results()
        anomaly_result = loader.get_anomalies()
        audit_events = loader.get_audit_events()

        # Step 2: Calculate health metrics
        overall_health = calculator.get_overall_health(health)
        layer_health = calculator.get_layer_health(health, anomaly_result.anomalies)
        severity_counts = calculator.get_severity_counts(anomaly_result.anomalies)
        timestamps, scores = calculator.get_health_history(health)

        # Step 3: Translate to business impact
        summary = translator.translate_health_summary(health, severity_counts)
        business_impacts = [
            translator.translate_anomaly(a) for a in anomaly_result.anomalies[:3]
        ]

        # Step 4: Build timeline
        events, groups = builder.get_timeline_events(
            results.results,
            audit_events=audit_events,
        )

        # Verify complete pipeline
        assert overall_health.score == 72.0
        assert len(layer_health) == 5
        assert severity_counts["CRITICAL"] >= 0
        assert severity_counts["WARNING"] >= 0
        assert len(summary) > 0
        assert len(events) >= 1
        assert len(timestamps) == len(scores)


class TestFilterIntegration:
    """Test filter functionality across services."""

    @pytest.fixture
    def mixed_data_dir(self, tmp_path: Path) -> Path:
        """Create data with mixed severity levels."""
        (tmp_path / "data" / "results").mkdir(parents=True)

        now = datetime.now(timezone.utc)

        # Create results with different severities
        severities = [
            SeverityLevel.INFO,
            SeverityLevel.WARNING,
            SeverityLevel.WARNING,
            SeverityLevel.CRITICAL,
        ]

        for i, severity in enumerate(severities):
            anomaly = Anomaly.create(
                batch_id=f"batch_{i:03d}",
                failure_code=FailureCode.NULL_VALUE_DETECTED,
                severity=severity,
                severity_score=30.0 + i * 20,
                root_cause=f"Issue {i}",
            )
            anomaly.detected_at = now - timedelta(hours=i)

            result = ValidationResult(
                batch_id=f"batch_{i:03d}",
                passed=False,
                anomalies=[anomaly],
                health_score=80.0 - i * 10,
                skills_executed=["null_check"],
                duration_ms=100.0,
                validated_at=now - timedelta(hours=i),
            )

            with open(tmp_path / "data" / "results" / f"result_{i:03d}.json", "w") as f:
                json.dump(result.to_dict(), f)

        return tmp_path

    def test_severity_filter_propagates(self, mixed_data_dir: Path):
        """Test severity filters work across loader and timeline."""
        loader = DataLoader(mixed_data_dir)
        builder = TimelineBuilder()

        # Get all results
        results = loader.get_latest_results()

        # Filter timeline by severity
        events, _ = builder.get_timeline_events(
            results.results,
            severity_filter=[SeverityLevel.CRITICAL],
        )

        # Verify only CRITICAL events
        anomaly_events = [e for e in events if e.event_type == "anomaly_detected"]
        for event in anomaly_events:
            assert event.severity == SeverityLevel.CRITICAL

    def test_time_filter_propagates(self, mixed_data_dir: Path):
        """Test time filters work across services."""
        loader = DataLoader(mixed_data_dir)
        builder = TimelineBuilder()

        now = datetime.now(timezone.utc)

        # Get results from last 2 hours only
        results = loader.get_latest_results(since=now - timedelta(hours=2))

        # Build timeline from filtered results
        events, _ = builder.get_timeline_events(results.results)

        # Verify timeline respects time filter
        for event in events:
            assert event.timestamp >= now - timedelta(hours=2, minutes=1)


class TestErrorRecovery:
    """Test error handling integration."""

    def test_handles_empty_data_gracefully(self, tmp_path: Path):
        """Test all services handle empty data."""
        (tmp_path / "data" / "results").mkdir(parents=True)
        (tmp_path / "data" / "state").mkdir(parents=True)

        loader = DataLoader(tmp_path)
        calculator = HealthCalculator()
        translator = ImpactTranslator()
        builder = TimelineBuilder()

        # Load empty data
        results = loader.get_latest_results()
        health, is_stale = loader.get_health_state()
        anomaly_result = loader.get_anomalies()

        # Process empty data
        overall = calculator.get_overall_health(health)
        layers = calculator.get_layer_health(health)
        counts = calculator.get_severity_counts([])

        # Translate
        summary = translator.translate_health_summary(health, counts)

        # Build empty timeline
        events, groups = builder.get_timeline_events([])

        # All should return valid defaults
        assert results.results == []
        assert is_stale is True
        assert overall.score >= 0
        assert len(layers) == 5
        assert counts["CRITICAL"] == 0
        assert isinstance(summary, str)
        assert events == []

    def test_handles_partial_data_gracefully(self, tmp_path: Path):
        """Test services handle partially corrupted data."""
        (tmp_path / "data" / "results").mkdir(parents=True)
        (tmp_path / "data" / "state").mkdir(parents=True)

        # Write valid result
        now = datetime.now(timezone.utc)
        result = ValidationResult(
            batch_id="good_batch",
            passed=True,
            anomalies=[],
            health_score=95.0,
            skills_executed=["test"],
            duration_ms=50.0,
            validated_at=now,
        )

        with open(tmp_path / "data" / "results" / "good.json", "w") as f:
            json.dump(result.to_dict(), f)

        # Write invalid result
        with open(tmp_path / "data" / "results" / "bad.json", "w") as f:
            f.write("not valid json {{{")

        loader = DataLoader(tmp_path)
        results = loader.get_latest_results()

        # Should still get the valid result
        assert len(results.results) >= 1
        assert results.results[0].batch_id == "good_batch"


class TestStateConsistency:
    """Test state consistency across dashboard operations."""

    def test_health_score_consistency(self, tmp_path: Path):
        """Test health scores are consistent across calculator methods."""
        calculator = HealthCalculator()

        now = datetime.now(timezone.utc)
        health = HealthScore(
            overall_score=65.0,
            component_scores={
                "bronze": ComponentScore(
                    name="Data Validation",
                    score=65.0,
                    anomaly_count=5,
                    last_check=now,
                ),
            },
            trend="degrading",
            active_anomalies=5,
            last_updated=now,
            batches_evaluated=10,
            history=[],
        )

        # Get health info multiple ways
        overall = calculator.get_overall_health(health)
        layers = calculator.get_layer_health(health)

        # Verify consistency
        assert overall.score == health.overall_score
        bronze_layer = next(l for l in layers if l.key == "bronze")
        assert bronze_layer.score == 65.0

    def test_anomaly_count_consistency(self, tmp_path: Path):
        """Test anomaly counts are consistent across services."""
        calculator = HealthCalculator()

        anomalies = [
            Anomaly.create(
                batch_id=f"b{i}",
                failure_code=FailureCode.NULL_VALUE_DETECTED,
                severity=SeverityLevel.WARNING,
                severity_score=50.0,
                root_cause=f"Issue {i}",
            )
            for i in range(5)
        ]

        # Count via calculator
        counts = calculator.get_severity_counts(anomalies)

        # Total should match input
        total = counts["CRITICAL"] + counts["WARNING"] + counts["INFO"]
        assert total == 5
        assert counts["WARNING"] == 5
