"""Unit tests for ImpactTranslator service."""

from pathlib import Path
from datetime import datetime, timezone

import pytest
import yaml

from dashboard.services.impact_translator import ImpactTranslator, BusinessImpact
from src.models.health_score import HealthScore
from src.models.anomaly import Anomaly
from src.lib.constants import SeverityLevel, FailureCode


class TestImpactTranslatorInit:
    """Tests for ImpactTranslator initialization."""

    def test_init_with_default_path(self):
        """Test initializes with default translations path."""
        translator = ImpactTranslator()
        assert translator.translations_path == Path.cwd() / "config" / "translations.yaml"

    def test_init_with_custom_path(self, tmp_path: Path):
        """Test initializes with custom translations path."""
        custom_path = tmp_path / "custom_translations.yaml"
        translator = ImpactTranslator(custom_path)
        assert translator.translations_path == custom_path

    def test_loads_translations_from_file(self, tmp_path: Path, mock_translations: dict):
        """Test loads translations from YAML file."""
        trans_file = tmp_path / "translations.yaml"
        with open(trans_file, "w") as f:
            yaml.dump(mock_translations, f)

        translator = ImpactTranslator(trans_file)

        assert translator._translations == mock_translations

    def test_handles_missing_file_gracefully(self, tmp_path: Path):
        """Test handles missing translations file without crashing."""
        missing_path = tmp_path / "nonexistent.yaml"
        translator = ImpactTranslator(missing_path)

        # Should have empty translations
        assert translator._translations == {}


class TestTranslateHealthSummary:
    """Tests for translate_health_summary method."""

    @pytest.fixture
    def translator(self, tmp_path: Path, mock_translations: dict) -> ImpactTranslator:
        """Create translator with mock translations."""
        trans_file = tmp_path / "translations.yaml"
        with open(trans_file, "w") as f:
            yaml.dump(mock_translations, f)
        return ImpactTranslator(trans_file)

    def test_excellent_summary_for_high_score_no_issues(self, translator: ImpactTranslator):
        """Test excellent summary when score >= 90 and no issues."""
        health = HealthScore(
            overall_score=95.0,
            component_scores={},
            trend="stable",
            active_anomalies=0,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )
        counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}

        summary = translator.translate_health_summary(health, counts)

        assert "healthy" in summary.lower() or "All systems" in summary

    def test_good_summary_for_medium_score(self, translator: ImpactTranslator):
        """Test good summary when score 70-89."""
        health = HealthScore(
            overall_score=75.0,
            component_scores={},
            trend="stable",
            active_anomalies=2,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )
        counts = {"CRITICAL": 0, "WARNING": 2, "INFO": 0}

        summary = translator.translate_health_summary(health, counts)

        # Should mention the warning count
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_critical_summary_for_critical_issues(self, translator: ImpactTranslator):
        """Test alert summary when critical issues exist."""
        health = HealthScore(
            overall_score=40.0,
            component_scores={},
            trend="degrading",
            active_anomalies=3,
            last_updated=datetime.now(timezone.utc),
            batches_evaluated=1,
            history=[],
        )
        counts = {"CRITICAL": 3, "WARNING": 0, "INFO": 0}

        summary = translator.translate_health_summary(health, counts)

        assert "ALERT" in summary or "critical" in summary.lower()

    def test_returns_string_always(self, translator: ImpactTranslator, sample_health_score: HealthScore):
        """Test always returns a non-empty string."""
        counts = {"CRITICAL": 1, "WARNING": 2, "INFO": 3}

        summary = translator.translate_health_summary(sample_health_score, counts)

        assert isinstance(summary, str)
        assert len(summary) > 0


class TestTranslateAnomaly:
    """Tests for translate_anomaly method."""

    @pytest.fixture
    def translator(self, tmp_path: Path, mock_translations: dict) -> ImpactTranslator:
        """Create translator with mock translations."""
        trans_file = tmp_path / "translations.yaml"
        with open(trans_file, "w") as f:
            yaml.dump(mock_translations, f)
        return ImpactTranslator(trans_file)

    def test_returns_business_impact(self, translator: ImpactTranslator, sample_anomaly: Anomaly):
        """Test returns BusinessImpact dataclass."""
        result = translator.translate_anomaly(sample_anomaly)

        assert isinstance(result, BusinessImpact)

    def test_includes_technical_metric(self, translator: ImpactTranslator, sample_anomaly: Anomaly):
        """Test includes the failure code as technical metric."""
        result = translator.translate_anomaly(sample_anomaly)

        assert result.technical_metric == sample_anomaly.failure_code.value

    def test_includes_business_description(self, translator: ImpactTranslator, sample_anomaly: Anomaly):
        """Test includes business-friendly description."""
        result = translator.translate_anomaly(sample_anomaly)

        assert isinstance(result.business_description, str)
        assert len(result.business_description) > 0

    def test_includes_affected_processes(self, translator: ImpactTranslator, sample_anomaly: Anomaly):
        """Test includes affected business processes."""
        result = translator.translate_anomaly(sample_anomaly)

        assert isinstance(result.affected_processes, list)
        assert len(result.affected_processes) >= 1

    def test_includes_recommended_actions(self, translator: ImpactTranslator, sample_anomaly: Anomaly):
        """Test includes recommended actions."""
        result = translator.translate_anomaly(sample_anomaly)

        assert isinstance(result.recommended_actions, list)
        assert len(result.recommended_actions) >= 1

    def test_sets_high_impact_for_critical_severity(self, translator: ImpactTranslator):
        """Test critical severity results in High impact."""
        critical_anomaly = Anomaly.create(
            batch_id="test",
            failure_code=FailureCode.RECORD_COUNT_MISMATCH,
            severity=SeverityLevel.CRITICAL,
            severity_score=95.0,
            root_cause="Critical issue",
        )

        result = translator.translate_anomaly(critical_anomaly)

        assert result.estimated_impact == "High"

    def test_sets_low_impact_for_info_severity(self, translator: ImpactTranslator):
        """Test info severity results in Low impact."""
        info_anomaly = Anomaly.create(
            batch_id="test",
            failure_code=FailureCode.FORMAT_VIOLATION,
            severity=SeverityLevel.INFO,
            severity_score=20.0,
            root_cause="Minor issue",
        )

        result = translator.translate_anomaly(info_anomaly)

        assert result.estimated_impact == "Low"

    def test_handles_unknown_failure_code(self, translator: ImpactTranslator):
        """Test handles anomaly with unknown failure code gracefully."""
        anomaly = Anomaly.create(
            batch_id="test",
            failure_code=FailureCode.SCHEMA_VIOLATION,  # May not be in mock translations
            severity=SeverityLevel.WARNING,
            severity_score=50.0,
            root_cause="Unknown issue type",
        )

        result = translator.translate_anomaly(anomaly)

        # Should still return a valid BusinessImpact
        assert isinstance(result, BusinessImpact)
        assert len(result.business_description) > 0


class TestTranslateFreshness:
    """Tests for translate_freshness method."""

    @pytest.fixture
    def translator(self) -> ImpactTranslator:
        """Create translator with default translations."""
        return ImpactTranslator()

    def test_current_data_message(self, translator: ImpactTranslator):
        """Test message for current data (< 1 hour)."""
        result = translator.translate_freshness(0.5)

        assert "current" in result.lower() or "updated" in result.lower()

    def test_stale_data_message(self, translator: ImpactTranslator):
        """Test message for stale data."""
        result = translator.translate_freshness(5.0)

        assert "5" in result or "hours" in result.lower()

    def test_returns_string(self, translator: ImpactTranslator):
        """Test always returns a string."""
        result = translator.translate_freshness(24.0, source="orders")

        assert isinstance(result, str)
        assert len(result) > 0


class TestGetFailureCodeName:
    """Tests for get_failure_code_name method."""

    @pytest.fixture
    def translator(self, tmp_path: Path, mock_translations: dict) -> ImpactTranslator:
        """Create translator with mock translations."""
        trans_file = tmp_path / "translations.yaml"
        with open(trans_file, "w") as f:
            yaml.dump(mock_translations, f)
        return ImpactTranslator(trans_file)

    def test_returns_name_for_known_code(self, translator: ImpactTranslator):
        """Test returns human-readable name for known code."""
        name = translator.get_failure_code_name("DV-002")

        assert name == "Missing Required Data"

    def test_returns_code_for_unknown_code(self, translator: ImpactTranslator):
        """Test returns the code itself for unknown codes."""
        name = translator.get_failure_code_name("UNKNOWN-999")

        assert name == "UNKNOWN-999"
