"""Pytest configuration and fixtures for DMRG-FTE tests."""

import pytest
from pathlib import Path
from typing import Any


@pytest.fixture
def sample_records() -> list[dict[str, Any]]:
    """Sample valid records for testing."""
    return [
        {
            "id": 1,
            "name": "Test Record 1",
            "email": "test1@example.com",
            "amount": 100.50,
            "quantity": 5,
            "created_at": "2026-01-18 10:00:00",
            "status": "active",
        },
        {
            "id": 2,
            "name": "Test Record 2",
            "email": "test2@example.com",
            "amount": 250.00,
            "quantity": 10,
            "created_at": "2026-01-18 11:00:00",
            "status": "pending",
        },
        {
            "id": 3,
            "name": "Test Record 3",
            "email": None,
            "amount": 75.25,
            "quantity": 3,
            "created_at": "2026-01-18 12:00:00",
            "status": "inactive",
        },
    ]


@pytest.fixture
def invalid_records() -> list[dict[str, Any]]:
    """Sample invalid records for testing anomaly detection."""
    return [
        {
            "id": "not_an_int",  # Type mismatch
            "name": "Invalid Record",
            "email": "invalid-email",  # Format violation
            "amount": -50.00,  # Range violation
            "quantity": 0,  # Range violation
            "created_at": "invalid-date",
            "status": "unknown",  # Invalid enum
        },
        {
            "id": None,  # Null in required field
            "name": "",  # Empty string
            "email": "test@example.com",
            "amount": 2000000.00,  # Above max
            "quantity": 50000,  # Above max
            "created_at": "2026-01-18 13:00:00",
            "status": "active",
        },
    ]


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create temporary data directory structure."""
    dirs = [
        "incoming",
        "checkpoints",
        "quarantine",
        "state",
        "batches",
        "results",
    ]
    for d in dirs:
        (tmp_path / "data" / d).mkdir(parents=True, exist_ok=True)

    logs_dirs = ["audit", "alerts"]
    for d in logs_dirs:
        (tmp_path / "logs" / d).mkdir(parents=True, exist_ok=True)

    return tmp_path


@pytest.fixture
def sample_config() -> dict[str, Any]:
    """Sample configuration for testing."""
    return {
        "orchestrator": {
            "watch_path": "data/incoming",
            "file_patterns": ["*.csv", "*.json"],
            "scheduler_interval": 30,
            "heartbeat_interval": 60,
            "max_concurrent": 1,
        },
        "validation": {
            "max_batch_size": 100000,
            "chunk_size": 10000,
            "timeout_per_record_ms": 100,
            "target_10k_seconds": 5,
        },
        "severity_weights": {
            "impact": 0.40,
            "frequency": 0.30,
            "recency": 0.30,
        },
    }
