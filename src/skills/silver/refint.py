"""Silver Tier refint skill for BL-002 and BL-008 detection.

This skill validates referential integrity:
- BL-002: Foreign key references exist in reference data
- BL-008: Orphan records (no valid parent/owner)
"""

import time
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.reference_data import (
    ReferenceDataSet,
    ReferenceDataConfig,
    ReferenceDataFormat,
    ReferenceIntegrityCheck,
    LookupResult,
)
from src.models.silver_anomaly import BusinessLogicAnomaly

logger = structlog.get_logger(__name__)


class RefintValidationResult:
    """Result of referential integrity validation."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[BusinessLogicAnomaly] = []
        self.records_checked: int = 0
        self.records_failed: int = 0
        self.orphan_records: int = 0
        self.invalid_references: int = 0
        self.duration_ms: float = 0.0


def check_referential_integrity(
    records: list[dict[str, Any]],
    reference_data: dict[str, set[str]] | ReferenceDataSet,
    checks: list[ReferenceIntegrityCheck | dict[str, Any]] | None = None,
    batch_id: str = "unknown",
    source_field: str | None = None,
    reference_id: str | None = None,
) -> RefintValidationResult:
    """Check referential integrity of records against reference data.

    Args:
        records: List of records to validate.
        reference_data: Reference data for lookups (dict or ReferenceDataSet).
        checks: Optional list of integrity checks to perform.
        batch_id: Batch identifier for anomalies.
        source_field: Field in records containing FK (used if checks not provided).
        reference_id: Reference data key (used if checks not provided).

    Returns:
        RefintValidationResult with anomalies.
    """
    start_time = time.perf_counter()
    result = RefintValidationResult()
    result.records_checked = len(records)

    # Convert simple dict format to lookup format
    if isinstance(reference_data, dict) and not isinstance(reference_data, ReferenceDataSet):
        reference_lookup = reference_data
    else:
        reference_lookup = _build_lookup_from_dataset(reference_data)

    # Build checks from parameters if not provided
    if checks is None and source_field and reference_id:
        checks = [
            ReferenceIntegrityCheck(
                id=f"check-{source_field}",
                source_field=source_field,
                reference_id=reference_id,
                failure_code="BL-002",
            )
        ]
    elif checks is None:
        # Auto-detect FK fields ending with _id
        checks = _auto_detect_fk_fields(records, reference_lookup)

    # Parse checks to proper objects
    parsed_checks = _parse_checks(checks)

    if not parsed_checks:
        logger.debug("no_refint_checks_configured")
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    # Track violations by check
    violations_by_check: dict[str, list[dict[str, Any]]] = {}

    for record in records:
        record_id = _get_record_id(record)

        for check in parsed_checks:
            # Get FK value from record
            fk_value = record.get(check.source_field)

            # Skip null FKs if allowed
            if fk_value is None:
                if not check.allow_null:
                    # Null FK is a violation
                    if check.id not in violations_by_check:
                        violations_by_check[check.id] = []
                    violations_by_check[check.id].append({
                        "record_id": record_id,
                        "field": check.source_field,
                        "value": None,
                        "reason": "null_fk",
                    })
                continue

            # Look up reference
            ref_keys = reference_lookup.get(check.reference_id, set())
            found = str(fk_value) in ref_keys

            if not found:
                result.invalid_references += 1
                if check.id not in violations_by_check:
                    violations_by_check[check.id] = []
                violations_by_check[check.id].append({
                    "record_id": record_id,
                    "field": check.source_field,
                    "value": fk_value,
                    "reason": "not_found",
                })

    # Count failed records
    failed_record_ids: set[str] = set()
    for violations in violations_by_check.values():
        for v in violations:
            if v.get("record_id"):
                failed_record_ids.add(v["record_id"])
    result.records_failed = len(failed_record_ids)

    # Convert to anomalies
    result.anomalies = _create_anomalies(violations_by_check, parsed_checks, batch_id)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "refint_validation_complete",
        batch_id=batch_id,
        records_checked=result.records_checked,
        records_failed=result.records_failed,
        invalid_references=result.invalid_references,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def detect_orphan_records(
    records: list[dict[str, Any]],
    parent_field: str,
    valid_parents: set[str],
    batch_id: str = "unknown",
) -> RefintValidationResult:
    """Detect orphan records with no valid parent.

    Args:
        records: List of records to check.
        parent_field: Field containing parent reference.
        valid_parents: Set of valid parent IDs.
        batch_id: Batch identifier for anomalies.

    Returns:
        RefintValidationResult with orphan anomalies (BL-008).
    """
    start_time = time.perf_counter()
    result = RefintValidationResult()
    result.records_checked = len(records)

    orphan_records: list[dict[str, Any]] = []

    for record in records:
        parent_value = record.get(parent_field)

        # Skip if no parent field or null (might be root)
        if parent_value is None:
            continue

        # Check if parent exists
        if str(parent_value) not in valid_parents:
            result.orphan_records += 1
            orphan_records.append({
                "record_id": _get_record_id(record),
                "parent_field": parent_field,
                "parent_value": parent_value,
            })

    result.records_failed = result.orphan_records

    # Create BL-008 anomaly if orphans found
    if orphan_records:
        affected_records = [r["record_id"] for r in orphan_records if r["record_id"]]

        anomaly = BusinessLogicAnomaly(
            id=f"BL-{uuid4().hex[:8]}",
            failure_code=FailureCode.ORPHAN_RECORD,
            severity=SeverityLevel.WARNING,  # Orphans are WARNING by default
            severity_score=min(100, 20 + len(orphan_records) * 5),
            rule_id="orphan-check",
            rule_name=f"Orphan check on {parent_field}",
            affected_records=affected_records,
            affected_fields=[parent_field],
            batch_id=batch_id,
            explanation=f"{len(orphan_records)} orphan record(s) with no valid parent in {parent_field}",
            expected_value="Valid parent reference",
            actual_value=f"Missing parents: {set(r['parent_value'] for r in orphan_records[:5])}",
            details={
                "orphan_count": len(orphan_records),
                "parent_field": parent_field,
                "sample_orphans": orphan_records[:5],
            },
        )
        result.anomalies.append(anomaly)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "orphan_detection_complete",
        batch_id=batch_id,
        records_checked=result.records_checked,
        orphan_records=result.orphan_records,
        duration_ms=result.duration_ms,
    )

    return result


def _build_lookup_from_dataset(
    dataset: ReferenceDataSet,
) -> dict[str, set[str]]:
    """Build simple lookup dict from ReferenceDataSet."""
    return {dataset.config.id: dataset.keys}


def _auto_detect_fk_fields(
    records: list[dict[str, Any]],
    reference_lookup: dict[str, set[str]],
) -> list[ReferenceIntegrityCheck]:
    """Auto-detect FK fields based on naming convention."""
    checks: list[ReferenceIntegrityCheck] = []

    if not records:
        return checks

    sample = records[0]

    for field in sample.keys():
        # Look for fields ending in _id
        if field.endswith("_id") and field != "id":
            # Try to match to a reference data set
            base_name = field[:-3]  # Remove _id

            for ref_id in reference_lookup.keys():
                if ref_id.lower().startswith(base_name.lower()):
                    checks.append(
                        ReferenceIntegrityCheck(
                            id=f"auto-{field}",
                            source_field=field,
                            reference_id=ref_id,
                            failure_code="BL-002",
                        )
                    )
                    break

    return checks


def _parse_checks(
    checks: list[ReferenceIntegrityCheck | dict[str, Any]] | None,
) -> list[ReferenceIntegrityCheck]:
    """Parse checks from mixed list."""
    if checks is None:
        return []

    parsed: list[ReferenceIntegrityCheck] = []

    for check in checks:
        if isinstance(check, ReferenceIntegrityCheck):
            parsed.append(check)
        elif isinstance(check, dict):
            try:
                parsed.append(
                    ReferenceIntegrityCheck(
                        id=check.get("id", f"check-{len(parsed)}"),
                        source_field=check.get("source_field", ""),
                        reference_id=check.get("reference_id", ""),
                        check_active=check.get("check_active", True),
                        allow_null=check.get("allow_null", False),
                        failure_code=check.get("failure_code", "BL-002"),
                    )
                )
            except Exception as e:
                logger.warning("check_parse_error", error=str(e))

    return parsed


def _get_record_id(record: dict[str, Any]) -> str | None:
    """Extract record ID from common fields."""
    for field in ["id", "order_id", "customer_id", "_id", "record_id"]:
        if field in record and record[field] is not None:
            return str(record[field])
    return None


def _create_anomalies(
    violations_by_check: dict[str, list[dict[str, Any]]],
    checks: list[ReferenceIntegrityCheck],
    batch_id: str,
) -> list[BusinessLogicAnomaly]:
    """Create anomalies from violations."""
    anomalies: list[BusinessLogicAnomaly] = []

    check_lookup = {c.id: c for c in checks}

    for check_id, violations in violations_by_check.items():
        if not violations:
            continue

        check = check_lookup.get(check_id)
        if check is None:
            continue

        affected_records = [v["record_id"] for v in violations if v.get("record_id")]
        invalid_values = set(str(v["value"]) for v in violations if v.get("value"))

        # Determine failure code
        failure_code = (
            FailureCode.REFERENTIAL_BREAK
            if check.failure_code == "BL-002"
            else FailureCode.ORPHAN_RECORD
        )

        anomaly = BusinessLogicAnomaly(
            id=f"BL-{uuid4().hex[:8]}",
            failure_code=failure_code,
            severity=SeverityLevel.CRITICAL,  # BL-002 is CRITICAL by default
            severity_score=min(100, 40 + len(violations) * 10),
            rule_id=check_id,
            rule_name=f"Reference check: {check.source_field} -> {check.reference_id}",
            affected_records=affected_records,
            affected_fields=[check.source_field],
            batch_id=batch_id,
            explanation=f"{len(violations)} record(s) reference non-existent {check.reference_id}",
            expected_value=f"Valid {check.reference_id} reference",
            actual_value=f"Invalid values: {list(invalid_values)[:5]}",
            details={
                "violation_count": len(violations),
                "source_field": check.source_field,
                "reference_id": check.reference_id,
                "invalid_values": list(invalid_values)[:10],
            },
        )
        anomalies.append(anomaly)

    return anomalies
