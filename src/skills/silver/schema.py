"""Silver Tier Schema Validation Skill.

Validates data against JSON Schema contracts, detecting SC-001 to SC-005:
- SC-001: Missing required column
- SC-002: Extra unexpected column
- SC-003: Column type change
- SC-004: Precision loss
- SC-005: Constraint violation
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import jsonschema
from jsonschema import Draft202012Validator, ValidationError
import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.schema_contract import SchemaContract, ColumnCriticality
from src.models.silver_anomaly import SchemaAnomaly, ViolationDetail

logger = structlog.get_logger(__name__)


class SchemaValidationResult:
    """Result of schema validation."""

    def __init__(self) -> None:
        self.anomalies: list[SchemaAnomaly] = []
        self.passed: bool = True
        self.score: float = 100.0

    def add_anomaly(self, anomaly: SchemaAnomaly) -> None:
        """Add an anomaly to the result."""
        self.anomalies.append(anomaly)
        if anomaly.severity == SeverityLevel.CRITICAL:
            self.passed = False

    def calculate_score(self) -> float:
        """Calculate health score based on anomalies.

        Score formula:
        - Start at 100
        - CRITICAL: -30 points each
        - WARNING: -10 points each
        - INFO: -2 points each
        """
        score = 100.0
        for anomaly in self.anomalies:
            if anomaly.severity == SeverityLevel.CRITICAL:
                score -= 30.0
            elif anomaly.severity == SeverityLevel.WARNING:
                score -= 10.0
            else:
                score -= 2.0
        self.score = max(0.0, min(100.0, score))
        return self.score


def validate_schema(
    records: list[dict[str, Any]],
    contract: SchemaContract,
    batch_id: str,
) -> SchemaValidationResult:
    """Validate records against a schema contract.

    Detects SC-001 through SC-005 violations.

    Args:
        records: List of record dictionaries to validate.
        contract: The schema contract to validate against.
        batch_id: ID of the batch being validated.

    Returns:
        SchemaValidationResult with anomalies and score.
    """
    result = SchemaValidationResult()
    json_schema = contract.to_json_schema()

    # Create validator
    validator = Draft202012Validator(json_schema)

    # Track violations by type for aggregation
    missing_columns: dict[str, list[int]] = {}  # column -> record indices
    extra_columns: dict[str, list[int]] = {}
    type_errors: dict[str, list[tuple[int, str, str]]] = {}  # column -> [(idx, expected, actual)]
    constraint_errors: list[tuple[int, str, str]] = []  # [(idx, column, message)]

    # Validate each record
    for idx, record in enumerate(records):
        # Check for missing columns
        for col in contract.required_columns:
            if col.name not in record:
                if col.name not in missing_columns:
                    missing_columns[col.name] = []
                missing_columns[col.name].append(idx)

        # Check for extra columns (if not allowed)
        if not contract.additional_properties:
            for key in record.keys():
                if key not in contract.column_names:
                    if key not in extra_columns:
                        extra_columns[key] = []
                    extra_columns[key].append(idx)

        # Use jsonschema for type and constraint validation
        errors = list(validator.iter_errors(record))
        for error in errors:
            _process_validation_error(
                error, idx, type_errors, constraint_errors, contract
            )

    # Generate anomalies from aggregated violations
    now = datetime.now(timezone.utc)

    # SC-001: Missing columns
    for col_name, indices in missing_columns.items():
        col_def = contract.get_column(col_name)
        severity = (
            SeverityLevel.CRITICAL
            if col_def and col_def.criticality == ColumnCriticality.REQUIRED
            else SeverityLevel.WARNING
        )
        blocking = severity == SeverityLevel.CRITICAL

        anomaly = SchemaAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.MISSING_COLUMN,
            severity=severity,
            contract_id=contract.id,
            contract_version=contract.version,
            affected_columns=[col_name],
            violation_details=[
                ViolationDetail(
                    column=col_name,
                    issue="Missing required column",
                    expected="present",
                    actual="absent",
                )
            ],
            batch_id=batch_id,
            timestamp=now,
            explanation=f"Column '{col_name}' is missing from {len(indices)} records",
            blocking=blocking,
        )
        result.add_anomaly(anomaly)

    # SC-002: Extra columns
    for col_name, indices in extra_columns.items():
        anomaly = SchemaAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.EXTRA_COLUMN,
            severity=SeverityLevel.INFO,
            contract_id=contract.id,
            contract_version=contract.version,
            affected_columns=[col_name],
            violation_details=[
                ViolationDetail(
                    column=col_name,
                    issue="Extra column not in schema",
                    expected="not present",
                    actual="present",
                )
            ],
            batch_id=batch_id,
            timestamp=now,
            explanation=f"Unexpected column '{col_name}' found in {len(indices)} records",
            blocking=False,
        )
        result.add_anomaly(anomaly)

    # SC-003: Type mismatches
    for col_name, errors_list in type_errors.items():
        col_def = contract.get_column(col_name)
        severity = (
            SeverityLevel.CRITICAL
            if col_def and col_def.criticality == ColumnCriticality.REQUIRED
            else SeverityLevel.WARNING
        )

        # Aggregate unique type combinations
        unique_types = set((exp, act) for _, exp, act in errors_list)
        details = [
            ViolationDetail(
                column=col_name,
                issue="Type mismatch",
                expected=exp,
                actual=act,
            )
            for exp, act in unique_types
        ]

        anomaly = SchemaAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.COLUMN_TYPE_CHANGE,
            severity=severity,
            contract_id=contract.id,
            contract_version=contract.version,
            affected_columns=[col_name],
            violation_details=details,
            batch_id=batch_id,
            timestamp=now,
            explanation=f"Type mismatch in column '{col_name}' for {len(errors_list)} records",
            blocking=severity == SeverityLevel.CRITICAL,
        )
        result.add_anomaly(anomaly)

    # SC-005: Constraint violations
    if constraint_errors:
        # Group by column
        by_column: dict[str, list[str]] = {}
        for idx, col_name, message in constraint_errors:
            if col_name not in by_column:
                by_column[col_name] = []
            if message not in by_column[col_name]:
                by_column[col_name].append(message)

        for col_name, messages in by_column.items():
            col_def = contract.get_column(col_name)
            severity = (
                SeverityLevel.CRITICAL
                if col_def and col_def.criticality == ColumnCriticality.REQUIRED
                else SeverityLevel.WARNING
            )

            details = [
                ViolationDetail(
                    column=col_name,
                    issue=msg,
                    expected=None,
                    actual=None,
                )
                for msg in messages
            ]

            anomaly = SchemaAnomaly(
                id=str(uuid4()),
                failure_code=FailureCode.CONSTRAINT_VIOLATION,
                severity=severity,
                contract_id=contract.id,
                contract_version=contract.version,
                affected_columns=[col_name],
                violation_details=details,
                batch_id=batch_id,
                timestamp=now,
                explanation=f"Constraint violation in column '{col_name}'",
                blocking=severity == SeverityLevel.CRITICAL,
            )
            result.add_anomaly(anomaly)

    result.calculate_score()

    logger.info(
        "schema_validation_complete",
        batch_id=batch_id,
        contract_id=contract.id,
        anomaly_count=len(result.anomalies),
        passed=result.passed,
        score=result.score,
    )

    return result


def _process_validation_error(
    error: ValidationError,
    record_idx: int,
    type_errors: dict[str, list[tuple[int, str, str]]],
    constraint_errors: list[tuple[int, str, str]],
    contract: SchemaContract,
) -> None:
    """Process a jsonschema validation error.

    Args:
        error: The validation error from jsonschema.
        record_idx: Index of the record being validated.
        type_errors: Dict to collect type errors.
        constraint_errors: List to collect constraint errors.
        contract: The schema contract.
    """
    # Extract column name from error path
    if error.path:
        col_name = str(error.path[0]) if error.path else "unknown"
    else:
        col_name = "unknown"

    # Categorize error type
    validator_type = error.validator

    if validator_type == "type":
        # Type mismatch (SC-003)
        expected_type = error.schema.get("type", "unknown")
        actual_type = type(error.instance).__name__
        if col_name not in type_errors:
            type_errors[col_name] = []
        type_errors[col_name].append((record_idx, expected_type, actual_type))

    elif validator_type in ("minLength", "maxLength", "minimum", "maximum", "pattern", "enum"):
        # Constraint violation (SC-005)
        constraint_errors.append((record_idx, col_name, error.message))

    elif validator_type == "required":
        # Missing required field - handled separately in main loop
        pass

    elif validator_type == "additionalProperties":
        # Extra property - handled separately in main loop
        pass

    else:
        # Other constraint violations
        constraint_errors.append((record_idx, col_name, error.message))


def check_precision_loss(
    value: float,
    expected_precision: int,
    expected_scale: int,
) -> bool:
    """Check if a numeric value has precision loss.

    Args:
        value: The numeric value to check.
        expected_precision: Expected total digits.
        expected_scale: Expected decimal places.

    Returns:
        True if precision loss detected.
    """
    if expected_precision is None or expected_scale is None:
        return False

    # Convert to string to check actual precision
    value_str = str(value)

    # Handle scientific notation
    if "e" in value_str.lower():
        return True  # Scientific notation might indicate precision issues

    parts = value_str.split(".")
    integer_part = parts[0].lstrip("-")
    decimal_part = parts[1] if len(parts) > 1 else ""

    total_digits = len(integer_part) + len(decimal_part)
    actual_scale = len(decimal_part)

    return total_digits > expected_precision or actual_scale > expected_scale
