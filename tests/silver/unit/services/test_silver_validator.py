"""Unit tests for SilverValidator service.

Tests T057: Silver health calculation functionality.
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.silver_validator import SilverValidator
from src.models.data_batch import DataBatch
from src.models.schema_contract import SchemaContract, ColumnDefinition
from src.models.health_score import SilverTierHealthScore, SilverLayerScore
from src.models.silver_anomaly import SchemaAnomaly, BusinessLogicAnomaly, FreshnessAnomaly
from src.lib.constants import SeverityLevel, FailureCode


class TestSilverHealthCalculation:
    """Tests for Silver tier health score calculation (T057)."""

    def test_create_initial_health_score(self):
        """Test initial health score is 100% across all layers."""
        health = SilverTierHealthScore.create_initial()

        assert health.overall_score == 100.0
        assert health.schema_layer.score == 100.0
        assert health.business_logic_layer.score == 100.0
        assert health.freshness_layer.score == 100.0
        assert health.trend == "stable"
        assert health.total_anomalies == 0
        assert health.blocking_issues == 0

    def test_health_score_uses_minimum_of_layers(self):
        """Test overall score is minimum of all layer scores (Constitution 6.3)."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=90.0,
            anomaly_count=0,
            last_check=now,
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic",
            layer_number=3,
            score=70.0,  # Lowest score
            anomaly_count=2,
            last_check=now,
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness",
            layer_number=4,
            score=85.0,
            anomaly_count=1,
            last_check=now,
        )

        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
        )

        # Per Constitution 6.3: Overall Health = Minimum(All Layer Scores)
        assert health.overall_score == 70.0
        assert health.total_anomalies == 3

    def test_health_score_with_critical_issues(self):
        """Test health score with blocking/critical issues."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=30.0,  # Low due to critical issues
            anomaly_count=3,
            critical_count=2,  # Blocking issues
            warning_count=1,
            last_check=now,
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic",
            layer_number=3,
            score=80.0,
            anomaly_count=1,
            last_check=now,
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness",
            layer_number=4,
            score=100.0,
            anomaly_count=0,
            last_check=now,
        )

        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
        )

        assert health.overall_score == 30.0  # Minimum of layers
        assert health.blocking_issues == 2
        assert health.is_critical is True

    def test_health_score_trend_improving(self):
        """Test trend detection for improving scores."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema", layer_number=2, score=90.0, last_check=now
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic", layer_number=3, score=85.0, last_check=now
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness", layer_number=4, score=95.0, last_check=now
        )

        # Previous score was 70
        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
            previous_score=70.0,
        )

        assert health.trend == "improving"

    def test_health_score_trend_degrading(self):
        """Test trend detection for degrading scores."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema", layer_number=2, score=60.0, last_check=now
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic", layer_number=3, score=55.0, last_check=now
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness", layer_number=4, score=70.0, last_check=now
        )

        # Previous score was 85
        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
            previous_score=85.0,
        )

        assert health.trend == "degrading"

    def test_health_score_trend_stable(self):
        """Test trend detection for stable scores."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema", layer_number=2, score=85.0, last_check=now
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic", layer_number=3, score=85.0, last_check=now
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness", layer_number=4, score=85.0, last_check=now
        )

        # Previous score was 85.5 (within ±1.0)
        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
            previous_score=85.5,
        )

        assert health.trend == "stable"

    def test_is_healthy_all_layers_pass(self):
        """Test is_healthy when all layers are healthy."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=90.0,
            critical_count=0,
            last_check=now,
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic",
            layer_number=3,
            score=85.0,
            critical_count=0,
            last_check=now,
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness",
            layer_number=4,
            score=95.0,
            critical_count=0,
            last_check=now,
        )

        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
        )

        assert health.is_healthy is True

    def test_is_healthy_fails_on_low_score(self):
        """Test is_healthy fails when layer score < 70."""
        now = datetime.now(timezone.utc)

        schema_layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=60.0,  # Below threshold
            critical_count=0,
            last_check=now,
        )
        bl_layer = SilverLayerScore(
            layer_name="business_logic",
            layer_number=3,
            score=85.0,
            critical_count=0,
            last_check=now,
        )
        freshness_layer = SilverLayerScore(
            layer_name="freshness",
            layer_number=4,
            score=95.0,
            critical_count=0,
            last_check=now,
        )

        health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
        )

        assert health.is_healthy is False

    def test_get_layer_by_number(self):
        """Test retrieving layers by Constitution layer number."""
        health = SilverTierHealthScore.create_initial()

        assert health.get_layer_by_number(2) == health.schema_layer
        assert health.get_layer_by_number(3) == health.business_logic_layer
        assert health.get_layer_by_number(4) == health.freshness_layer
        assert health.get_layer_by_number(1) is None  # Bronze tier
        assert health.get_layer_by_number(5) is None  # Gold tier

    def test_status_labels(self):
        """Test status labels at different score thresholds."""
        now = datetime.now(timezone.utc)

        def create_health(score: float) -> SilverTierHealthScore:
            layer = SilverLayerScore(
                layer_name="test", layer_number=2, score=score, last_check=now
            )
            return SilverTierHealthScore(
                overall_score=score,
                schema_layer=layer,
                business_logic_layer=layer,
                freshness_layer=layer,
            )

        assert create_health(95.0).status_label == "Excellent"
        assert create_health(85.0).status_label == "Good"
        assert create_health(60.0).status_label == "Fair"
        assert create_health(35.0).status_label == "Poor"
        assert create_health(20.0).status_label == "Critical"

    def test_format_summary(self):
        """Test formatted summary string."""
        health = SilverTierHealthScore.create_initial()
        summary = health.format_summary()

        assert "Silver Health: 100.0/100" in summary
        assert "Excellent" in summary
        assert "Schema: 100.0" in summary
        assert "BizLogic: 100.0" in summary
        assert "Freshness: 100.0" in summary

    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        health = SilverTierHealthScore.create_initial()
        data = health.to_dict()

        assert "overall_score" in data
        assert "schema_layer" in data
        assert "business_logic_layer" in data
        assert "freshness_layer" in data
        assert data["overall_score"] == 100.0


class TestSilverValidatorHealthUpdate:
    """Tests for SilverValidator health score updates."""

    @pytest.fixture
    def mock_validator(self, tmp_path):
        """Create a SilverValidator with mock directories."""
        schema_dir = tmp_path / "schemas"
        rules_dir = tmp_path / "rules"
        sla_dir = tmp_path / "sla"
        reference_dir = tmp_path / "reference"

        for d in [schema_dir, rules_dir, sla_dir, reference_dir]:
            d.mkdir(parents=True)

        # Create minimal config files
        (sla_dir / "sla.yaml").write_text("sla_definitions: []\ndefaults:\n  freshness_threshold:\n    warning_minutes: 60\n    critical_minutes: 120")

        with patch("src.services.silver_validator.SchemaRegistry") as mock_registry:
            mock_registry.return_value.load_schemas.return_value = None
            mock_registry.return_value.get_contract_for_source.return_value = None

            validator = SilverValidator(
                schema_dir=schema_dir,
                rules_dir=rules_dir,
                sla_dir=sla_dir,
                reference_dir=reference_dir,
            )
            return validator

    def test_get_health_score_initial(self, mock_validator):
        """Test initial health score retrieval."""
        health = mock_validator.get_health_score()

        assert health is not None
        assert health.overall_score == 100.0
        assert health.trend == "stable"

    def test_reset_health_score(self, mock_validator):
        """Test health score reset."""
        # Modify health
        mock_validator._current_health = SilverTierHealthScore.create_initial()
        mock_validator._current_health = mock_validator._current_health.model_copy(
            update={"overall_score": 50.0}
        )

        # Reset
        mock_validator.reset_health()

        health = mock_validator.get_health_score()
        assert health.overall_score == 100.0


class TestSilverLayerScore:
    """Tests for SilverLayerScore model."""

    def test_layer_score_healthy(self):
        """Test healthy layer conditions."""
        layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=90.0,
            anomaly_count=1,
            critical_count=0,
            warning_count=1,
            last_check=datetime.now(timezone.utc),
        )

        assert layer.is_healthy is True

    def test_layer_score_unhealthy_critical(self):
        """Test unhealthy due to critical anomalies."""
        layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=80.0,
            anomaly_count=2,
            critical_count=1,  # Has critical
            warning_count=1,
            last_check=datetime.now(timezone.utc),
        )

        assert layer.is_healthy is False

    def test_layer_score_unhealthy_low_score(self):
        """Test unhealthy due to low score."""
        layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=60.0,  # Below 70
            anomaly_count=0,
            critical_count=0,
            warning_count=0,
            last_check=datetime.now(timezone.utc),
        )

        assert layer.is_healthy is False
