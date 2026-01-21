"""Silver Tier Test Fixtures."""

import pytest
from datetime import datetime, timedelta
from pathlib import Path


# Sample schema contract for testing
@pytest.fixture
def sample_schema_contract():
    """Sample schema contract for testing schema validation."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "id": "orders-v1.0",
        "name": "Orders Schema",
        "version": "1.0.0",
        "source": "orders",
        "type": "object",
        "required": ["order_id", "customer_id", "order_total", "created_at"],
        "properties": {
            "order_id": {"type": "string", "pattern": "^ORD-[0-9]{8}$"},
            "customer_id": {"type": "string"},
            "order_total": {"type": "number", "minimum": 0},
            "discount": {"type": "number", "minimum": 0, "default": 0},
            "status": {
                "type": "string",
                "enum": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"],
            },
            "created_at": {"type": "string", "format": "date-time"},
        },
        "additionalProperties": False,
        "x-column-criticality": {
            "order_id": "required",
            "customer_id": "required",
            "order_total": "required",
            "discount": "optional",
            "status": "required",
            "created_at": "required",
        },
    }


@pytest.fixture
def valid_order_data():
    """Sample valid order data."""
    return [
        {
            "order_id": "ORD-00000001",
            "customer_id": "CUST-001",
            "order_total": 100.00,
            "discount": 10.00,
            "status": "PENDING",
            "created_at": "2026-01-18T10:00:00Z",
        },
        {
            "order_id": "ORD-00000002",
            "customer_id": "CUST-002",
            "order_total": 250.50,
            "discount": 0,
            "status": "CONFIRMED",
            "created_at": "2026-01-18T11:00:00Z",
        },
    ]


@pytest.fixture
def invalid_schema_data():
    """Data with schema violations for testing."""
    return {
        "missing_column": [
            {
                "order_id": "ORD-00000001",
                # Missing customer_id
                "order_total": 100.00,
                "created_at": "2026-01-18T10:00:00Z",
            }
        ],
        "type_mismatch": [
            {
                "order_id": "ORD-00000001",
                "customer_id": "CUST-001",
                "order_total": "not-a-number",  # Should be number
                "created_at": "2026-01-18T10:00:00Z",
            }
        ],
        "extra_column": [
            {
                "order_id": "ORD-00000001",
                "customer_id": "CUST-001",
                "order_total": 100.00,
                "created_at": "2026-01-18T10:00:00Z",
                "extra_field": "unexpected",  # Not in schema
            }
        ],
    }


@pytest.fixture
def sample_business_rules():
    """Sample business rules for testing."""
    return [
        {
            "id": "BL-001-discount-limit",
            "name": "Discount cannot exceed order total",
            "type": "domain",
            "expression": "discount <= order_total",
            "severity": "critical",
            "enabled": True,
            "failure_code": "BL-006",
        },
        {
            "id": "BL-002-date-order",
            "name": "End date must be after start date",
            "type": "crossfield",
            "expression": "end_date > start_date",
            "severity": "critical",
            "enabled": True,
            "failure_code": "BL-001",
        },
        {
            "id": "BL-003-valid-status",
            "name": "Valid order status transition",
            "type": "state_transition",
            "field": "status",
            "allowed_values": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"],
            "severity": "critical",
            "enabled": True,
            "failure_code": "BL-004",
        },
    ]


@pytest.fixture
def invalid_business_data():
    """Data with business rule violations for testing."""
    return {
        "discount_exceeds_total": {
            "order_id": "ORD-00000001",
            "customer_id": "CUST-001",
            "order_total": 100.00,
            "discount": 150.00,  # Exceeds order_total
        },
        "date_order_violation": {
            "start_date": "2026-01-15",
            "end_date": "2026-01-01",  # Before start_date
        },
        "invalid_state_transition": {
            "order_id": "ORD-00000001",
            "previous_status": "PENDING",
            "new_status": "DELIVERED",  # Skipped CONFIRMED and SHIPPED
        },
        "referential_break": {
            "order_id": "ORD-00000001",
            "customer_id": "CUST-999",  # Non-existent customer
        },
    }


@pytest.fixture
def sample_reference_data():
    """Sample reference data for referential integrity testing."""
    return {
        "customers": {"CUST-001", "CUST-002", "CUST-003"},
        "products": {"PROD-001", "PROD-002", "PROD-003"},
        "accounts": {"ACC-001", "ACC-002", "ACC-003"},
    }


@pytest.fixture
def sample_sla_definition():
    """Sample SLA definition for freshness testing."""
    return {
        "id": "sla-orders-hourly",
        "source": "orders",
        "schedule": "0 * * * *",  # Every hour
        "freshness_threshold": {
            "warning_minutes": 60,
            "critical_minutes": 90,
        },
        "latency_threshold": 1800,  # 30 minutes
        "enabled": True,
        "owner": "data-platform-team",
    }


@pytest.fixture
def freshness_state():
    """Sample freshness state for testing."""
    now = datetime.utcnow()
    return {
        "fresh": {
            "source": "orders",
            "last_arrival": now - timedelta(minutes=30),
            "age_seconds": 1800,
            "status": "OK",
        },
        "warning": {
            "source": "orders",
            "last_arrival": now - timedelta(minutes=65),
            "age_seconds": 3900,
            "status": "WARNING",
        },
        "critical": {
            "source": "orders",
            "last_arrival": now - timedelta(minutes=100),
            "age_seconds": 6000,
            "status": "CRITICAL",
        },
    }


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory with sample files."""
    schemas_dir = tmp_path / "schemas"
    rules_dir = tmp_path / "rules"
    sla_dir = tmp_path / "sla"
    reference_dir = tmp_path / "reference"

    schemas_dir.mkdir()
    rules_dir.mkdir()
    sla_dir.mkdir()
    reference_dir.mkdir()

    return {
        "schemas": schemas_dir,
        "rules": rules_dir,
        "sla": sla_dir,
        "reference": reference_dir,
    }
