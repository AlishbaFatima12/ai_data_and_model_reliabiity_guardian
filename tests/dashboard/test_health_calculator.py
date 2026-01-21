"""Unit tests for HealthCalculator service."""

from datetime import datetime, timezone, timedelta

import pytest

from dashboard.services.health_calculator import (
    HealthCalculator,
    HealthColors,
    OverallHealthInfo,
    LayerHealthInfo,
)
from src.models.health_score import HealthScore, ComponentScore
from src.models.anomaly import Anomaly
from src.lib.constants import SeverityLevel, FailureCode


class TestHealthColors:
    """Tests for HealthColors class."""

    def test_excellent_color_for_high_score(self):
        """Test green color for scores >= 90."""
        assert HealthColors.get_color(100) == HealthColors.EXCELLENT
        assert HealthColors.get_color(95) == HealthColors.EXCELLENT
        assert HealthColors.get_color(90) == HealthColors.EXCELLENT

    def test_good_color_for_medium_high_score(self):
        """Test yellow color for scores 70-89."""
        assert HealthColors.get_color(89) == HealthColors.GOOD
        assert HealthColors.get_color(80) == HealthColors.GOOD
        assert HealthColors.get_color(70) == HealthColors.GOOD

    def test_fair_color_for_medium_score(self):
        """Test orange color for scores 50-69."""
        assert HealthColors.get_color(69) == HealthColors.FAIR
        assert HealthColors.get_color(60) == HealthColors.FAIR
        assert HealthColors.get_color(50) == HealthColors.FAIR

    def test_poor_color_for_low_score(self):
        """Test red color for scores < 50."""
        assert HealthColors.get_color(49) == HealthColors.POOR
        assert HealthColors.get_color(25) == HealthColors.POOR
        assert HealthColors.get_color(0) == HealthColors.POOR


class TestGetOverallHealth:
    """Tests for get_overall_health method."""

    @pytest.fixture
    def calculator(self) -> HealthCalculator:
        """Create a HealthCalculator instance."""
        return HealthCalculator()

    def test_returns_overall_health_info(self, calculator: HealthCalculator, sample_health_score: HealthScore):
        """Test returns OverallHealthInfo dataclass."""
        result = calculator.get_overall_health(sample_health_score)

        assert isinstance(result, OverallHealthInfo)
        assert result.score == sample_health_score.overall_score

    def test_excellent_status_for_high_score(self, calculator: HealthCalculator):
        """Test 'Excellent' status for scores >= 90."""
        health = HealthScore(
            overall_score=95.0,
            component_scores={},
            trend="stable",
            active_anomalies=0,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )

        result = calculator.get_overall_health(health)
        assert result.status == "Excellent"

    def test_good_status_for_medium_high_score(self, calculator: HealthCalculator):
        """Test 'Good' status for scores 70-89."""
        health = HealthScore(
            overall_score=75.0,
            component_scores={},
            trend="stable",
            active_anomalies=0,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )

        result = calculator.get_overall_health(health)
        assert result.status == "Good"

    def test_critical_status_for_very_low_score(self, calculator: HealthCalculator):
        """Test 'Critical' status for scores < 30."""
        health = HealthScore(
            overall_score=20.0,
            component_scores={},
            trend="degrading",
            active_anomalies=5,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )

        result = calculator.get_overall_health(health)
        assert result.status == "Critical"

    def test_preserves_trend_from_health_state(self, calculator: HealthCalculator):
        """Test trend is preserved from health state."""
        health = HealthScore(
            overall_score=80.0,
            component_scores={},
            trend="improving",
            active_anomalies=0,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )

        result = calculator.get_overall_health(health)
        assert result.trend == "improving"

    def test_calculates_trend_delta_from_history(self, calculator: HealthCalculator):
        """Test trend delta is calculated from history."""
        now = datetime.now(timezone.utc)
        health = HealthScore(
            overall_score=80.0,
            component_scores={},
            trend="improving",
            active_anomalies=0,
            last_updated=now,
            batches_evaluated=2,
            history=[
                (now - timedelta(hours=1), 70.0),
                (now, 80.0),
            ],
        )

        result = calculator.get_overall_health(health)
        assert result.trend_delta == 10.0  # 80 - 70


class TestGetLayerHealth:
    """Tests for get_layer_health method."""

    @pytest.fixture
    def calculator(self) -> HealthCalculator:
        """Create a HealthCalculator instance."""
        return HealthCalculator()

    def test_returns_list_of_layer_info(self, calculator: HealthCalculator, sample_health_score: HealthScore):
        """Test returns list of LayerHealthInfo."""
        result = calculator.get_layer_health(sample_health_score)

        assert isinstance(result, list)
        assert len(result) == 5  # 5 layers defined
        assert all(isinstance(layer, LayerHealthInfo) for layer in result)

    def test_includes_all_layer_names(self, calculator: HealthCalculator, sample_health_score: HealthScore):
        """Test all expected layers are included."""
        result = calculator.get_layer_health(sample_health_score)

        layer_names = [layer.name for layer in result]
        assert "Data Validation" in layer_names
        assert "Schema Enforcement" in layer_names
        assert "Business Logic" in layer_names
        assert "Freshness & SLA" in layer_names
        assert "Model & Fairness" in layer_names

    def test_uses_component_score_when_available(self, calculator: HealthCalculator):
        """Test uses component score from health state."""
        health = HealthScore(
            overall_score=80.0,
            component_scores={
                "bronze": ComponentScore(
                    name="Data Validation",
                    score=65.0,
                    anomaly_count=2,
                    last_check=datetime.now(timezone.utc),
                ),
            },
            trend="stable",
            active_anomalies=2,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )

        result = calculator.get_layer_health(health)

        bronze_layer = next(l for l in result if l.key == "bronze")
        assert bronze_layer.score == 65.0

    def test_defaults_unimplemented_layers_to_100(self, calculator: HealthCalculator, sample_health_score: HealthScore):
        """Test unimplemented layers default to perfect health."""
        result = calculator.get_layer_health(sample_health_score)

        # Silver and Gold tiers not implemented yet
        schema_layer = next(l for l in result if l.key == "schema")
        assert schema_layer.score == 100.0

    def test_counts_anomalies_per_layer(self, calculator: HealthCalculator, sample_health_score: HealthScore, sample_anomaly: Anomaly):
        """Test anomaly counts are per layer."""
        result = calculator.get_layer_health(sample_health_score, anomalies=[sample_anomaly])

        bronze_layer = next(l for l in result if l.key == "bronze")
        assert bronze_layer.anomaly_count >= 1


class TestGetHealthHistory:
    """Tests for get_health_history method."""

    @pytest.fixture
    def calculator(self) -> HealthCalculator:
        """Create a HealthCalculator instance."""
        return HealthCalculator()

    def test_returns_timestamps_and_scores(self, calculator: HealthCalculator, sample_health_score: HealthScore):
        """Test returns tuple of timestamps and scores lists."""
        timestamps, scores = calculator.get_health_history(sample_health_score)

        assert isinstance(timestamps, list)
        assert isinstance(scores, list)
        assert len(timestamps) == len(scores)

    def test_limits_to_requested_hours(self, calculator: HealthCalculator):
        """Test respects hours parameter."""
        now = datetime.now(timezone.utc)
        health = HealthScore(
            overall_score=80.0,
            component_scores={},
            trend="stable",
            active_anomalies=0,
            last_updated=now,
            batches_evaluated=1,
            history=[
                (now - timedelta(hours=i), 80.0) for i in range(48)
            ],
        )

        timestamps, scores = calculator.get_health_history(health, hours=24)

        # Should only include last 24 hours
        if timestamps:
            oldest = min(timestamps)
            assert oldest >= now - timedelta(hours=24)

    def test_caps_at_168_hours(self, calculator: HealthCalculator, sample_health_score: HealthScore):
        """Test maximum is 168 hours (7 days)."""
        timestamps, scores = calculator.get_health_history(sample_health_score, hours=500)

        # Should not crash with large values
        assert isinstance(timestamps, list)


class TestCalculateOverallFromLayers:
    """Tests for calculate_overall_from_layers method."""

    @pytest.fixture
    def calculator(self) -> HealthCalculator:
        """Create a HealthCalculator instance."""
        return HealthCalculator()

    def test_returns_minimum_of_all_layers(self, calculator: HealthCalculator):
        """Test overall is minimum of all layer scores."""
        layers = [
            LayerHealthInfo(name="A", key="a", tier="Bronze", score=90.0, trend="stable", trend_delta=0, anomaly_count=0, color="#00A67E"),
            LayerHealthInfo(name="B", key="b", tier="Silver", score=70.0, trend="stable", trend_delta=0, anomaly_count=0, color="#FFB020"),
            LayerHealthInfo(name="C", key="c", tier="Gold", score=85.0, trend="stable", trend_delta=0, anomaly_count=0, color="#00A67E"),
        ]

        result = calculator.calculate_overall_from_layers(layers)

        assert result == 70.0  # Minimum

    def test_returns_100_for_empty_layers(self, calculator: HealthCalculator):
        """Test returns 100 when no layers provided."""
        result = calculator.calculate_overall_from_layers([])
        assert result == 100.0


class TestGetSeverityCounts:
    """Tests for get_severity_counts method."""

    @pytest.fixture
    def calculator(self) -> HealthCalculator:
        """Create a HealthCalculator instance."""
        return HealthCalculator()

    def test_counts_all_severities(self, calculator: HealthCalculator):
        """Test counts anomalies by severity."""
        anomalies = [
            Anomaly.create(
                batch_id="b1",
                failure_code=FailureCode.RECORD_COUNT_MISMATCH,
                severity=SeverityLevel.CRITICAL,
                severity_score=90.0,
                root_cause="Critical issue",
            ),
            Anomaly.create(
                batch_id="b2",
                failure_code=FailureCode.NULL_VALUE_DETECTED,
                severity=SeverityLevel.WARNING,
                severity_score=60.0,
                root_cause="Warning issue",
            ),
            Anomaly.create(
                batch_id="b3",
                failure_code=FailureCode.TYPE_MISMATCH,
                severity=SeverityLevel.WARNING,
                severity_score=55.0,
                root_cause="Another warning",
            ),
        ]

        counts = calculator.get_severity_counts(anomalies)

        assert counts["CRITICAL"] == 1
        assert counts["WARNING"] == 2
        assert counts["INFO"] == 0

    def test_returns_zero_counts_for_empty_list(self, calculator: HealthCalculator):
        """Test returns zero counts when no anomalies."""
        counts = calculator.get_severity_counts([])

        assert counts["CRITICAL"] == 0
        assert counts["WARNING"] == 0
        assert counts["INFO"] == 0
