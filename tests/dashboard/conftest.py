"""Dashboard test fixtures and configuration."""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator
from uuid import uuid4

import pytest

from src.models.anomaly import Anomaly
from src.models.health_score import HealthScore, ComponentScore
from src.models.validation_result import ValidationResult
from src.lib.constants import FailureCode, SeverityLevel


@pytest.fixture
def sample_anomaly() -> Anomaly:
    """Create a sample anomaly for testing."""
    return Anomaly.create(
        batch_id="test-batch-001",
        failure_code=FailureCode.NULL_VALUE_DETECTED,
        severity=SeverityLevel.WARNING,
        severity_score=65.0,
        root_cause="Missing required field 'email' in 15 records",
        affected_records=[1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70],
        affected_fields=["email"],
        explanation="The 'email' field is required but was empty or missing.",
    )


@pytest.fixture
def sample_health_score() -> HealthScore:
    """Create a sample health score for testing."""
    return HealthScore(
        overall_score=75.0,
        component_scores={
            "bronze": ComponentScore(
                name="Data Validation",
                score=75.0,
                anomaly_count=3,
                last_check=datetime.now(timezone.utc),
            ),
        },
        trend="stable",
        active_anomalies=3,
        last_updated=datetime.now(timezone.utc),
        batches_evaluated=10,
        history=[
            (datetime.now(timezone.utc) - timedelta(hours=i), 70.0 + i)
            for i in range(24)
        ],
    )


@pytest.fixture
def sample_validation_result(sample_anomaly: Anomaly) -> ValidationResult:
    """Create a sample validation result for testing."""
    return ValidationResult(
        batch_id="test-batch-001",
        passed=False,
        anomalies=[sample_anomaly],
        health_score=75.0,
        skills_executed=["null_check", "type_check", "range_check"],
        duration_ms=150.5,
    )


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create temporary data directory structure."""
    # Create directory structure
    (tmp_path / "data" / "results").mkdir(parents=True)
    (tmp_path / "data" / "state").mkdir(parents=True)
    (tmp_path / "data" / "dashboard").mkdir(parents=True)
    (tmp_path / "logs" / "audit").mkdir(parents=True)
    (tmp_path / "config").mkdir(parents=True)

    return tmp_path


@pytest.fixture
def populated_data_dir(
    temp_data_dir: Path,
    sample_validation_result: ValidationResult,
    sample_health_score: HealthScore,
) -> Path:
    """Create temporary data directory with sample data."""
    # Write validation result
    result_file = temp_data_dir / "data" / "results" / "result_001.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(sample_validation_result.to_dict(), f)

    # Write health state
    health_file = temp_data_dir / "data" / "state" / "health.json"
    with open(health_file, "w", encoding="utf-8") as f:
        json.dump(sample_health_score.model_dump(mode="json"), f)

    # Write sample audit log
    audit_file = temp_data_dir / "logs" / "audit" / "audit_001.jsonl"
    with open(audit_file, "w", encoding="utf-8") as f:
        for i in range(5):
            event = {
                "timestamp": (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                "event": "validation_complete",
                "level": "INFO",
                "message": f"Validation completed for batch {i}",
                "batch_id": f"batch_{i}",
            }
            f.write(json.dumps(event) + "\n")

    return temp_data_dir


@pytest.fixture
def mock_translations() -> dict:
    """Create mock translations for testing."""
    return {
        "health_summary": {
            "excellent": {"template": "All systems healthy."},
            "good": {"template": "{warning_count} minor issues."},
            "fair": {"template": "{issue_count} issues detected."},
            "critical": {"template": "ALERT: {critical_count} critical issues."},
        },
        "failure_codes": {
            "DV-002": {
                "name": "Missing Required Data",
                "business_description": "Required information is missing.",
                "impact_template": "{field} is missing in {count} records.",
                "affected_processes": ["Data processing"],
                "recommended_actions": ["Review data entry"],
                "severity_impact": "High",
            },
        },
    }
