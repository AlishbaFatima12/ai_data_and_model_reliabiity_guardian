"""Integration tests for Dashboard Silver tier integration (T058).

Tests that the dashboard correctly loads, displays, and integrates
Silver tier health data and anomalies.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from dashboard.services.data_loader import (
    DataLoader,
    SilverDataLoaderResult,
    SilverAnomalyResult,
)
from dashboard.services.health_calculator import HealthCalculator, LayerHealthInfo
from src.models.health_score import (
    HealthScore,
    SilverTierHealthScore,
    SilverLayerScore,
)
from src.models.validation_result import SilverValidationResult
from src.models.silver_anomaly import (
    SchemaAnomaly,
    BusinessLogicAnomaly,
    FreshnessAnomaly,
)
from src.lib.constants import SeverityLevel, FailureCode


class TestDashboardSilverDataLoading:
    """Tests for Silver tier data loading in dashboard."""

    @pytest.fixture
    def data_loader(self, tmp_path):
        """Create DataLoader with temporary paths."""
        # Create required directories
        (tmp_path / "data" / "results").mkdir(parents=True)
        (tmp_path / "data" / "silver_results").mkdir(parents=True)
        (tmp_path / "data" / "state").mkdir(parents=True)
        (tmp_path / "logs" / "audit").mkdir(parents=True)

        loader = DataLoader(tmp_path)
        return loader

    def test_load_silver_health_state_no_file(self, data_loader):
        """Test loading Silver health when no state file exists."""
        health, is_stale = data_loader.get_silver_health_state()

        assert health is not None
        assert health.overall_score == 100.0
        assert is_stale is True

    def test_load_silver_health_state_from_file(self, data_loader, tmp_path):
        """Test loading Silver health from state file."""
        # Create Silver health state file
        now = datetime.now(timezone.utc)
        health_data = {
            "overall_score": 85.0,
            "schema_layer": {
                "layer_name": "schema",
                "layer_number": 2,
                "score": 90.0,
                "weight": 1.0,
                "anomaly_count": 1,
                "critical_count": 0,
                "warning_count": 1,
                "last_check": now.isoformat(),
            },
            "business_logic_layer": {
                "layer_name": "business_logic",
                "layer_number": 3,
                "score": 85.0,
                "weight": 1.0,
                "anomaly_count": 2,
                "critical_count": 0,
                "warning_count": 2,
                "last_check": now.isoformat(),
            },
            "freshness_layer": {
                "layer_name": "freshness",
                "layer_number": 4,
                "score": 95.0,
                "weight": 1.0,
                "anomaly_count": 0,
                "critical_count": 0,
                "warning_count": 0,
                "last_check": now.isoformat(),
            },
            "trend": "stable",
            "total_anomalies": 3,
            "blocking_issues": 0,
            "last_updated": now.isoformat(),
            "history": [],
        }

        state_file = tmp_path / "data" / "state" / "silver_health.json"
        with open(state_file, "w") as f:
            json.dump(health_data, f)

        health, is_stale = data_loader.get_silver_health_state()

        assert health is not None
        assert health.overall_score == 85.0
        assert health.schema_layer.score == 90.0
        assert health.business_logic_layer.score == 85.0
        assert health.freshness_layer.score == 95.0

    def test_load_silver_anomalies_empty(self, data_loader):
        """Test loading Silver anomalies when none exist."""
        result = data_loader.get_silver_anomalies()

        assert isinstance(result, SilverAnomalyResult)
        assert len(result.schema_anomalies) == 0
        assert len(result.business_logic_anomalies) == 0
        assert len(result.freshness_anomalies) == 0

    def test_load_silver_results(self, data_loader, tmp_path):
        """Test loading Silver validation results."""
        # Create a Silver result file
        now = datetime.now(timezone.utc)
        result_data = {
            "id": "silver-result-001",
            "batch_id": "batch-001",
            "validated_at": now.isoformat(),
            "passed": True,
            "blocked": False,
            "schema_score": 95.0,
            "business_logic_score": 90.0,
            "freshness_score": 100.0,
            "overall_score": 90.0,
            "schema_anomalies": [],
            "business_logic_anomalies": [],
            "freshness_anomalies": [],
            "duration_ms": 150.0,
            "skills_executed": ["schema", "bizrule", "freshness"],
            "metadata": {},
        }

        result_file = tmp_path / "data" / "silver_results" / "result_001.json"
        with open(result_file, "w") as f:
            json.dump(result_data, f)

        results = data_loader.get_silver_results(limit=10)

        assert isinstance(results, SilverDataLoaderResult)
        assert results.total_count == 1
        assert len(results.results) == 1
        assert results.results[0].batch_id == "batch-001"

    def test_has_silver_data_false(self, data_loader):
        """Test has_silver_data returns False when no data."""
        assert data_loader.has_silver_data() is False

    def test_has_silver_data_true(self, data_loader, tmp_path):
        """Test has_silver_data returns True when data exists."""
        result_file = tmp_path / "data" / "silver_results" / "result.json"
        result_file.write_text("{}")

        assert data_loader.has_silver_data() is True


class TestHealthCalculatorSilverIntegration:
    """Tests for HealthCalculator Silver tier integration."""

    @pytest.fixture
    def calculator(self):
        """Create HealthCalculator instance."""
        return HealthCalculator()

    @pytest.fixture
    def bronze_health(self):
        """Create sample Bronze tier health state."""
        return HealthScore(
            overall_score=90.0,
            trend="stable",
            active_anomalies=1,
            batches_evaluated=100,
        )

    @pytest.fixture
    def silver_health(self):
        """Create sample Silver tier health state."""
        now = datetime.now(timezone.utc)
        return SilverTierHealthScore(
            overall_score=85.0,
            schema_layer=SilverLayerScore(
                layer_name="schema",
                layer_number=2,
                score=90.0,
                anomaly_count=2,
                critical_count=0,
                warning_count=2,
                last_check=now,
            ),
            business_logic_layer=SilverLayerScore(
                layer_name="business_logic",
                layer_number=3,
                score=85.0,
                anomaly_count=3,
                critical_count=1,
                warning_count=2,
                last_check=now,
            ),
            freshness_layer=SilverLayerScore(
                layer_name="freshness",
                layer_number=4,
                score=100.0,
                anomaly_count=0,
                critical_count=0,
                warning_count=0,
                last_check=now,
            ),
            trend="stable",
            total_anomalies=5,
            blocking_issues=1,
        )

    def test_get_layer_health_with_silver(
        self, calculator, bronze_health, silver_health
    ):
        """Test layer health includes Silver tier data."""
        layers = calculator.get_layer_health(
            bronze_health, anomalies=[], silver_health=silver_health
        )

        assert len(layers) == 5  # Bronze + 3 Silver + Gold

        # Check Bronze layer
        bronze_layer = next(l for l in layers if l.key == "bronze")
        assert bronze_layer.tier == "Bronze"
        assert bronze_layer.score == bronze_health.overall_score

        # Check Silver layers use Silver health data
        schema_layer = next(l for l in layers if l.key == "schema")
        assert schema_layer.tier == "Silver"
        assert schema_layer.score == 90.0
        assert schema_layer.anomaly_count == 2

        bl_layer = next(l for l in layers if l.key == "business")
        assert bl_layer.tier == "Silver"
        assert bl_layer.score == 85.0
        assert bl_layer.anomaly_count == 3

        freshness_layer = next(l for l in layers if l.key == "freshness")
        assert freshness_layer.tier == "Silver"
        assert freshness_layer.score == 100.0
        assert freshness_layer.anomaly_count == 0

    def test_get_layer_health_without_silver(self, calculator, bronze_health):
        """Test layer health without Silver data shows defaults."""
        layers = calculator.get_layer_health(
            bronze_health, anomalies=[], silver_health=None
        )

        # Silver layers should default to 100%
        schema_layer = next(l for l in layers if l.key == "schema")
        assert schema_layer.score == 100.0

        bl_layer = next(l for l in layers if l.key == "business")
        assert bl_layer.score == 100.0

    def test_calculate_overall_from_layers(self, calculator, bronze_health, silver_health):
        """Test overall score uses minimum of all layers (Constitution 6.3)."""
        layers = calculator.get_layer_health(
            bronze_health, anomalies=[], silver_health=silver_health
        )

        overall = calculator.calculate_overall_from_layers(layers)

        # Should be minimum: min(90, 90, 85, 100, 100) = 85
        assert overall == 85.0


class TestSilverAnomalyDisplay:
    """Tests for Silver anomaly display in dashboard."""

    def test_schema_anomaly_severity_counts(self):
        """Test severity counting for schema anomalies."""
        now = datetime.now(timezone.utc)

        anomalies = SilverAnomalyResult(
            schema_anomalies=[
                SchemaAnomaly(
                    id="sa-001",
                    batch_id="batch-001",
                    timestamp=now,
                    failure_code=FailureCode.MISSING_COLUMN,
                    severity=SeverityLevel.CRITICAL,
                    contract_id="contract-001",
                    contract_version="1.0.0",
                    affected_columns=["col1"],
                    expected_columns=["col1", "col2"],
                    actual_columns=["col1"],
                    explanation="Missing required column col2",
                    blocking=True,
                ),
                SchemaAnomaly(
                    id="sa-002",
                    batch_id="batch-001",
                    timestamp=now,
                    failure_code=FailureCode.EXTRA_COLUMN,
                    severity=SeverityLevel.WARNING,
                    contract_id="contract-001",
                    contract_version="1.0.0",
                    affected_columns=["extra_col"],
                    expected_columns=[],
                    actual_columns=["extra_col"],
                    explanation="Unexpected extra column",
                    blocking=False,
                ),
            ],
            business_logic_anomalies=[],
            freshness_anomalies=[],
            by_layer={"schema": 2, "business_logic": 0, "freshness": 0},
            by_severity={
                SeverityLevel.CRITICAL.value: 1,
                SeverityLevel.WARNING.value: 1,
                SeverityLevel.INFO.value: 0,
            },
        )

        assert anomalies.by_severity["CRITICAL"] == 1
        assert anomalies.by_severity["WARNING"] == 1
        assert anomalies.by_layer["schema"] == 2

    def test_combined_severity_counts(self):
        """Test combined severity counts across all layers."""
        now = datetime.now(timezone.utc)

        anomalies = SilverAnomalyResult(
            schema_anomalies=[
                SchemaAnomaly(
                    id="sa-001",
                    batch_id="batch-001",
                    timestamp=now,
                    failure_code=FailureCode.MISSING_COLUMN,
                    severity=SeverityLevel.CRITICAL,
                    contract_id="contract-001",
                    contract_version="1.0.0",
                    affected_columns=["col1"],
                    expected_columns=["col1", "col2"],
                    actual_columns=["col1"],
                    explanation="Missing required column",
                    blocking=True,
                ),
            ],
            business_logic_anomalies=[
                BusinessLogicAnomaly(
                    id="bl-001",
                    batch_id="batch-001",
                    timestamp=now,
                    failure_code=FailureCode.CROSS_FIELD_INCONSISTENCY,
                    severity=SeverityLevel.WARNING,
                    severity_score=60,
                    rule_id="rule-001",
                    rule_name="Cross-field Consistency",
                    affected_records=[],
                    explanation="Cross-field check failed: A should be greater than B",
                    expected_value="A > B",
                    actual_value="A < B",
                ),
            ],
            freshness_anomalies=[
                FreshnessAnomaly(
                    id="fr-001",
                    source="orders",
                    timestamp=now,
                    failure_code=FailureCode.DATA_STALE,
                    severity=SeverityLevel.WARNING,
                    sla_id="sla-orders",
                    expected_at=now,
                    delay_seconds=1800,  # 30 minutes
                    explanation="Data is stale: expected refresh 30 minutes ago",
                ),
            ],
            by_layer={"schema": 1, "business_logic": 1, "freshness": 1},
            by_severity={
                SeverityLevel.CRITICAL.value: 1,
                SeverityLevel.WARNING.value: 2,
                SeverityLevel.INFO.value: 0,
            },
        )

        total_anomalies = (
            len(anomalies.schema_anomalies)
            + len(anomalies.business_logic_anomalies)
            + len(anomalies.freshness_anomalies)
        )

        assert total_anomalies == 3
        assert anomalies.by_severity["CRITICAL"] == 1
        assert anomalies.by_severity["WARNING"] == 2


class TestSilverTimelineIntegration:
    """Tests for Silver anomalies in incident timeline."""

    def test_silver_anomalies_can_be_converted_to_events(self):
        """Test Silver anomalies can be converted to timeline events."""
        from dashboard.services.timeline_builder import TimelineEvent

        now = datetime.now(timezone.utc)

        # Create a schema anomaly
        schema_anomaly = SchemaAnomaly(
            id="sa-001",
            batch_id="batch-001",
            timestamp=now,
            failure_code=FailureCode.MISSING_COLUMN,
            severity=SeverityLevel.CRITICAL,
            contract_id="contract-001",
            contract_version="1.0.0",
            affected_columns=["required_col"],
            expected_columns=["required_col", "other_col"],
            actual_columns=["other_col"],
            explanation="Missing required column",
            blocking=True,
        )

        # Convert to timeline event
        event = TimelineEvent(
            id=schema_anomaly.id,
            timestamp=schema_anomaly.timestamp,
            event_type="silver_anomaly",
            severity=schema_anomaly.severity,
            title=f"[Silver] {schema_anomaly.failure_code.value}",
            description=schema_anomaly.failure_code.description,
            related_batch_id=schema_anomaly.batch_id,
            layer="Schema",
            asset=schema_anomaly.batch_id,
            metadata={
                "layer": "schema",
                "failure_code": schema_anomaly.failure_code.value,
                "blocking": schema_anomaly.blocking,
            },
        )

        assert event.event_type == "silver_anomaly"
        assert "Silver" in event.title
        assert event.severity == SeverityLevel.CRITICAL
        assert event.metadata["layer"] == "schema"
        assert event.metadata["blocking"] is True


class TestDashboardSilverSection:
    """Tests for dedicated Silver tier section in dashboard."""

    @pytest.fixture
    def silver_health(self):
        """Create sample Silver health with varying scores."""
        now = datetime.now(timezone.utc)
        return SilverTierHealthScore(
            overall_score=75.0,  # Minimum of 75, 85, 95
            schema_layer=SilverLayerScore(
                layer_name="schema",
                layer_number=2,
                score=85.0,
                anomaly_count=2,
                critical_count=0,
                warning_count=2,
                last_check=now,
            ),
            business_logic_layer=SilverLayerScore(
                layer_name="business_logic",
                layer_number=3,
                score=75.0,  # Lowest
                anomaly_count=5,
                critical_count=2,
                warning_count=3,
                last_check=now,
            ),
            freshness_layer=SilverLayerScore(
                layer_name="freshness",
                layer_number=4,
                score=95.0,
                anomaly_count=1,
                critical_count=0,
                warning_count=1,
                last_check=now,
            ),
            trend="degrading",
            total_anomalies=8,
            blocking_issues=2,
        )

    def test_silver_section_displays_three_layers(self, silver_health):
        """Test Silver section shows all three layer scores."""
        # Verify structure
        assert silver_health.schema_layer is not None
        assert silver_health.business_logic_layer is not None
        assert silver_health.freshness_layer is not None

        # Verify each layer has required display data
        for layer in [
            silver_health.schema_layer,
            silver_health.business_logic_layer,
            silver_health.freshness_layer,
        ]:
            assert hasattr(layer, "score")
            assert hasattr(layer, "anomaly_count")
            assert hasattr(layer, "critical_count")
            assert hasattr(layer, "layer_name")

    def test_silver_overall_score_is_minimum(self, silver_health):
        """Test overall Silver score is minimum of layers."""
        layer_scores = [
            silver_health.schema_layer.score,
            silver_health.business_logic_layer.score,
            silver_health.freshness_layer.score,
        ]

        assert silver_health.overall_score == min(layer_scores)

    def test_silver_blocking_issues_displayed(self, silver_health):
        """Test blocking issues are tracked and can be displayed."""
        assert silver_health.blocking_issues == 2
        assert silver_health.is_critical is True  # Has blocking issues

    def test_silver_trend_available(self, silver_health):
        """Test trend is available for display."""
        assert silver_health.trend in ["improving", "stable", "degrading"]
        assert silver_health.trend == "degrading"
