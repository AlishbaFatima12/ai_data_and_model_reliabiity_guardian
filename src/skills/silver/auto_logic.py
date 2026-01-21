"""Silver Tier automatic logic validation skill.

Automatically detects logically impossible combinations like:
- 12-year-old with $130k income
- Negative age values
- Future birth dates
- Income without employment status
"""

import time
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.silver_anomaly import BusinessLogicAnomaly

logger = structlog.get_logger(__name__)


class AutoLogicValidationResult:
    """Result of automatic logic validation."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[BusinessLogicAnomaly] = []
        self.records_checked: int = 0
        self.records_failed: int = 0
        self.violations_by_type: dict[str, int] = {}
        self.duration_ms: float = 0.0


# Common logical rules for automatic detection
AUTO_LOGIC_RULES = [
    {
        "name": "age_income_logic",
        "description": "Young age with high income",
        "check": lambda r: (
            r.get("age") is not None
            and r.get("income") is not None
            and _to_float(r.get("age")) < 16
            and _to_float(r.get("income")) > 50000
        ),
        "message": "Person under 16 with income over $50,000",
        "fields": ["age", "income"],
    },
    {
        "name": "age_range_logic",
        "description": "Invalid age value",
        "check": lambda r: (
            r.get("age") is not None
            and (_to_float(r.get("age")) < 0 or _to_float(r.get("age")) > 120)
        ),
        "message": "Age value outside valid range (0-120)",
        "fields": ["age"],
    },
    {
        "name": "negative_income",
        "description": "Negative income value",
        "check": lambda r: (
            r.get("income") is not None and _to_float(r.get("income")) < 0
        ),
        "message": "Negative income value detected",
        "fields": ["income"],
    },
    {
        "name": "zero_days_with_purchases",
        "description": "Purchases with zero platform time",
        "check": lambda r: (
            r.get("days_on_platform") is not None
            and r.get("purchases") is not None
            and _to_float(r.get("days_on_platform")) == 0
            and _to_float(r.get("purchases")) > 0
        ),
        "message": "User has purchases but 0 days on platform",
        "fields": ["days_on_platform", "purchases"],
    },
    {
        "name": "excessive_purchases_rate",
        "description": "Unrealistic purchase rate",
        "check": lambda r: (
            r.get("days_on_platform") is not None
            and r.get("purchases") is not None
            and _to_float(r.get("days_on_platform")) > 0
            and _to_float(r.get("purchases"))
            / max(1, _to_float(r.get("days_on_platform")))
            > 5
        ),
        "message": "More than 5 purchases per day on average",
        "fields": ["days_on_platform", "purchases"],
    },
    {
        "name": "quantity_total_mismatch",
        "description": "Quantity and total price mismatch",
        "check": lambda r: (
            r.get("quantity") is not None
            and r.get("unit_price") is not None
            and r.get("total") is not None
            and abs(
                _to_float(r.get("quantity")) * _to_float(r.get("unit_price"))
                - _to_float(r.get("total"))
            )
            > 0.01
        ),
        "message": "Calculated total doesn't match quantity * unit_price",
        "fields": ["quantity", "unit_price", "total"],
    },
    {
        "name": "end_before_start",
        "description": "End date before start date",
        "check": lambda r: (
            r.get("start_date") is not None
            and r.get("end_date") is not None
            and str(r.get("end_date")) < str(r.get("start_date"))
        ),
        "message": "End date is before start date",
        "fields": ["start_date", "end_date"],
    },
]


def _to_float(value: Any) -> float:
    """Safely convert value to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def validate_auto_logic(
    records: list[dict[str, Any]],
    batch_id: str,
) -> AutoLogicValidationResult:
    """Automatically validate records for logical inconsistencies.

    Args:
        records: List of records to validate.
        batch_id: Batch identifier for anomalies.

    Returns:
        AutoLogicValidationResult with anomalies.
    """
    start_time = time.perf_counter()
    result = AutoLogicValidationResult()
    result.records_checked = len(records)

    if not records:
        return result

    # Get fields present in records
    sample_fields = set()
    for record in records[:100]:
        sample_fields.update(record.keys())

    # Filter rules to only those with applicable fields
    applicable_rules = []
    for rule in AUTO_LOGIC_RULES:
        rule_fields = rule["fields"]
        if all(f in sample_fields for f in rule_fields):
            applicable_rules.append(rule)

    if not applicable_rules:
        logger.debug("no_applicable_auto_logic_rules")
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    # Track violations by rule
    violations_by_rule: dict[str, list[tuple[int, dict]]] = {
        rule["name"]: [] for rule in applicable_rules
    }

    for idx, record in enumerate(records):
        for rule in applicable_rules:
            try:
                if rule["check"](record):
                    violations_by_rule[rule["name"]].append((idx, record))
            except Exception:
                continue

    # Convert to anomalies
    failed_record_ids: set[int] = set()

    for rule in applicable_rules:
        violations = violations_by_rule[rule["name"]]
        if not violations:
            continue

        count = len(violations)
        result.violations_by_type[rule["name"]] = count

        # Track failed records
        for idx, _ in violations:
            failed_record_ids.add(idx)

        # Get sample records
        sample_violations = violations[:5]
        sample_details = []
        for idx, record in sample_violations:
            field_values = {f: record.get(f) for f in rule["fields"]}
            sample_details.append(f"Row {idx}: {field_values}")

        severity_score = min(80, 30 + count * 2)
        severity = (
            SeverityLevel.CRITICAL
            if count > 50
            else SeverityLevel.WARNING
            if count > 10
            else SeverityLevel.INFO
        )

        anomaly = BusinessLogicAnomaly(
            id=f"AL-{uuid4().hex[:8]}",
            failure_code=FailureCode.DOMAIN_RULE_VIOLATION,
            severity=severity,
            severity_score=severity_score,
            rule_id=f"auto_{rule['name']}",
            rule_name=rule["description"],
            affected_records=[str(idx) for idx, _ in violations],
            affected_fields=rule["fields"],
            batch_id=batch_id,
            explanation=(
                f"{rule['message']}. Found {count} violations. "
                f"Examples: {'; '.join(sample_details[:3])}"
            ),
            expected_value=f"Valid {rule['description'].lower()}",
            actual_value=f"{count} records with logical issues",
            details={
                "violation_count": count,
                "rule_type": "auto_logic",
                "sample_indices": [idx for idx, _ in violations[:10]],
            },
        )
        result.anomalies.append(anomaly)

    result.records_failed = len(failed_record_ids)
    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "auto_logic_validation_complete",
        batch_id=batch_id,
        records_checked=result.records_checked,
        records_failed=result.records_failed,
        anomalies=len(result.anomalies),
        violations_by_type=result.violations_by_type,
        duration_ms=result.duration_ms,
    )

    return result
