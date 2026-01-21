"""Silver Tier Version Comparison Skill.

Compares schema versions and detects breaking changes:
- SC-006: Version mismatch
- SC-007: Breaking change detection (using deepdiff)
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from deepdiff import DeepDiff
import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.schema_contract import SchemaContract, ColumnType
from src.models.silver_anomaly import SchemaAnomaly, ViolationDetail

logger = structlog.get_logger(__name__)


class VersionComparisonResult:
    """Result of version comparison."""

    def __init__(self) -> None:
        self.is_compatible: bool = True
        self.has_breaking_changes: bool = False
        self.anomalies: list[SchemaAnomaly] = []
        self.breaking_changes: list[str] = []
        self.non_breaking_changes: list[str] = []

    def add_anomaly(self, anomaly: SchemaAnomaly) -> None:
        """Add an anomaly to the result."""
        self.anomalies.append(anomaly)
        if anomaly.failure_code == FailureCode.BREAKING_CHANGE:
            self.has_breaking_changes = True
            self.is_compatible = False


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse semantic version string to tuple.

    Args:
        version: Version string like "1.2.3".

    Returns:
        Tuple of (major, minor, patch).
    """
    try:
        parts = version.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except (ValueError, IndexError):
        return (0, 0, 0)


def compare_versions(v1: str, v2: str) -> int:
    """Compare two semantic versions.

    Args:
        v1: First version string.
        v2: Second version string.

    Returns:
        -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2.
    """
    parsed1 = parse_version(v1)
    parsed2 = parse_version(v2)

    if parsed1 < parsed2:
        return -1
    elif parsed1 > parsed2:
        return 1
    return 0


def is_major_version_change(old_version: str, new_version: str) -> bool:
    """Check if there's a major version change.

    Args:
        old_version: Previous version.
        new_version: Current version.

    Returns:
        True if major version changed.
    """
    old_major, _, _ = parse_version(old_version)
    new_major, _, _ = parse_version(new_version)
    return new_major != old_major


def check_version_compatibility(
    current_contract: SchemaContract,
    expected_contract: SchemaContract,
    batch_id: str,
) -> VersionComparisonResult:
    """Check version compatibility between contracts.

    Detects SC-006 (version mismatch) and SC-007 (breaking changes).

    Args:
        current_contract: The contract used by the data.
        expected_contract: The contract expected by the consumer.
        batch_id: ID of the batch being validated.

    Returns:
        VersionComparisonResult with compatibility status and anomalies.
    """
    result = VersionComparisonResult()
    now = datetime.now(timezone.utc)

    current_version = current_contract.version
    expected_version = expected_contract.version

    # Check for version mismatch
    version_cmp = compare_versions(current_version, expected_version)

    if version_cmp != 0:
        # Version mismatch detected
        is_major = is_major_version_change(expected_version, current_version)

        if is_major:
            # Major version change - likely incompatible
            severity = SeverityLevel.WARNING
            result.is_compatible = False
        else:
            # Minor/patch difference - check actual changes
            severity = SeverityLevel.INFO

        anomaly = SchemaAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.VERSION_MISMATCH,
            severity=severity,
            contract_id=current_contract.id,
            contract_version=current_version,
            affected_columns=[],
            violation_details=[
                ViolationDetail(
                    column="__schema_version__",
                    issue="Version mismatch",
                    expected=expected_version,
                    actual=current_version,
                )
            ],
            batch_id=batch_id,
            timestamp=now,
            explanation=f"Schema version {current_version} differs from expected {expected_version}",
            blocking=False,
        )
        result.add_anomaly(anomaly)

    # Check for breaking changes using deepdiff
    breaking_changes = detect_breaking_changes(expected_contract, current_contract)

    for change in breaking_changes:
        result.breaking_changes.append(change["description"])

        anomaly = SchemaAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.BREAKING_CHANGE,
            severity=SeverityLevel.CRITICAL,
            contract_id=current_contract.id,
            contract_version=current_version,
            affected_columns=change.get("affected_columns", []),
            violation_details=[
                ViolationDetail(
                    column=change.get("column", "__schema__"),
                    issue=change["type"],
                    expected=change.get("expected"),
                    actual=change.get("actual"),
                )
            ],
            batch_id=batch_id,
            timestamp=now,
            explanation=change["description"],
            blocking=True,
        )
        result.add_anomaly(anomaly)

    # Detect non-breaking changes for informational purposes
    non_breaking = detect_non_breaking_changes(expected_contract, current_contract)
    result.non_breaking_changes = [c["description"] for c in non_breaking]

    logger.info(
        "version_compatibility_check_complete",
        batch_id=batch_id,
        current_version=current_version,
        expected_version=expected_version,
        is_compatible=result.is_compatible,
        breaking_changes=len(result.breaking_changes),
        non_breaking_changes=len(result.non_breaking_changes),
    )

    return result


def detect_breaking_changes(
    old_contract: SchemaContract,
    new_contract: SchemaContract,
) -> list[dict[str, Any]]:
    """Detect breaking (non-backward-compatible) changes.

    Breaking changes:
    - Removed required column
    - Changed column type (narrowing)
    - Narrowed constraints (stricter validation)
    - Changed required status from optional to required

    Args:
        old_contract: The previous contract version.
        new_contract: The new contract version.

    Returns:
        List of breaking change descriptions.
    """
    breaking_changes: list[dict[str, Any]] = []

    old_columns = {col.name: col for col in old_contract.columns}
    new_columns = {col.name: col for col in new_contract.columns}

    # Check for removed required columns
    for col_name, old_col in old_columns.items():
        if col_name not in new_columns and old_col.is_required:
            breaking_changes.append({
                "type": "removed_required_column",
                "column": col_name,
                "affected_columns": [col_name],
                "description": f"Required column '{col_name}' was removed",
                "expected": "present",
                "actual": "absent",
            })

    # Check for type changes and constraint narrowing
    for col_name, new_col in new_columns.items():
        if col_name not in old_columns:
            continue

        old_col = old_columns[col_name]

        # Type change
        if old_col.column_type != new_col.column_type:
            # Some type changes are breaking
            if _is_breaking_type_change(old_col.column_type, new_col.column_type):
                breaking_changes.append({
                    "type": "breaking_type_change",
                    "column": col_name,
                    "affected_columns": [col_name],
                    "description": f"Column '{col_name}' type changed from {old_col.column_type.value} to {new_col.column_type.value}",
                    "expected": old_col.column_type.value,
                    "actual": new_col.column_type.value,
                })

        # Constraint narrowing
        narrowing = _detect_constraint_narrowing(old_col.constraints, new_col.constraints)
        for narrow in narrowing:
            breaking_changes.append({
                "type": "constraint_narrowed",
                "column": col_name,
                "affected_columns": [col_name],
                "description": f"Column '{col_name}': {narrow}",
                "expected": None,
                "actual": None,
            })

        # Optional to required
        if not old_col.is_required and new_col.is_required:
            breaking_changes.append({
                "type": "made_required",
                "column": col_name,
                "affected_columns": [col_name],
                "description": f"Column '{col_name}' changed from optional to required",
                "expected": "optional",
                "actual": "required",
            })

    # Check additionalProperties change (true -> false is breaking)
    if old_contract.additional_properties and not new_contract.additional_properties:
        breaking_changes.append({
            "type": "additional_properties_disabled",
            "column": "__schema__",
            "affected_columns": [],
            "description": "additionalProperties changed from true to false",
            "expected": "true",
            "actual": "false",
        })

    return breaking_changes


def detect_non_breaking_changes(
    old_contract: SchemaContract,
    new_contract: SchemaContract,
) -> list[dict[str, Any]]:
    """Detect non-breaking (backward-compatible) changes.

    Non-breaking changes:
    - Added optional column
    - Widened constraints
    - Changed required to optional

    Args:
        old_contract: The previous contract version.
        new_contract: The new contract version.

    Returns:
        List of non-breaking change descriptions.
    """
    non_breaking: list[dict[str, Any]] = []

    old_columns = {col.name: col for col in old_contract.columns}
    new_columns = {col.name: col for col in new_contract.columns}

    # Added optional columns
    for col_name, new_col in new_columns.items():
        if col_name not in old_columns and not new_col.is_required:
            non_breaking.append({
                "type": "added_optional_column",
                "column": col_name,
                "description": f"Optional column '{col_name}' was added",
            })

    # Required to optional
    for col_name, new_col in new_columns.items():
        if col_name in old_columns:
            old_col = old_columns[col_name]
            if old_col.is_required and not new_col.is_required:
                non_breaking.append({
                    "type": "made_optional",
                    "column": col_name,
                    "description": f"Column '{col_name}' changed from required to optional",
                })

    # Constraint widening
    for col_name, new_col in new_columns.items():
        if col_name in old_columns:
            old_col = old_columns[col_name]
            widening = _detect_constraint_widening(old_col.constraints, new_col.constraints)
            for wide in widening:
                non_breaking.append({
                    "type": "constraint_widened",
                    "column": col_name,
                    "description": f"Column '{col_name}': {wide}",
                })

    return non_breaking


def _is_breaking_type_change(old_type: ColumnType, new_type: ColumnType) -> bool:
    """Check if a type change is breaking.

    Some type changes are widening (non-breaking):
    - integer -> number
    - Any -> string (in some contexts)

    Most type changes are breaking.
    """
    # Widening conversions (non-breaking)
    widening_pairs = [
        (ColumnType.INTEGER, ColumnType.NUMBER),
    ]

    for old_t, new_t in widening_pairs:
        if old_type == old_t and new_type == new_t:
            return False

    return old_type != new_type


def _detect_constraint_narrowing(old_constraints, new_constraints) -> list[str]:
    """Detect constraints that became stricter."""
    narrowing = []

    # Max length decreased
    if (
        old_constraints.max_length is not None
        and new_constraints.max_length is not None
        and new_constraints.max_length < old_constraints.max_length
    ):
        narrowing.append(
            f"maxLength narrowed from {old_constraints.max_length} to {new_constraints.max_length}"
        )

    # Min length increased
    if (
        new_constraints.min_length is not None
        and (
            old_constraints.min_length is None
            or new_constraints.min_length > old_constraints.min_length
        )
    ):
        narrowing.append(
            f"minLength increased to {new_constraints.min_length}"
        )

    # Maximum decreased
    if (
        old_constraints.maximum is not None
        and new_constraints.maximum is not None
        and new_constraints.maximum < old_constraints.maximum
    ):
        narrowing.append(
            f"maximum narrowed from {old_constraints.maximum} to {new_constraints.maximum}"
        )

    # Minimum increased
    if (
        new_constraints.minimum is not None
        and (
            old_constraints.minimum is None
            or new_constraints.minimum > old_constraints.minimum
        )
    ):
        narrowing.append(
            f"minimum increased to {new_constraints.minimum}"
        )

    # Pattern added or changed
    if (
        new_constraints.pattern is not None
        and old_constraints.pattern != new_constraints.pattern
    ):
        if old_constraints.pattern is None:
            narrowing.append("pattern constraint added")
        else:
            narrowing.append("pattern constraint changed")

    # Enum values reduced
    if old_constraints.enum_values and new_constraints.enum_values:
        old_set = set(old_constraints.enum_values)
        new_set = set(new_constraints.enum_values)
        removed = old_set - new_set
        if removed:
            narrowing.append(f"enum values removed: {removed}")

    # Nullable changed from true to false
    if old_constraints.nullable and not new_constraints.nullable:
        narrowing.append("nullable changed from true to false")

    return narrowing


def _detect_constraint_widening(old_constraints, new_constraints) -> list[str]:
    """Detect constraints that became more lenient."""
    widening = []

    # Max length increased
    if (
        new_constraints.max_length is not None
        and old_constraints.max_length is not None
        and new_constraints.max_length > old_constraints.max_length
    ):
        widening.append(
            f"maxLength widened from {old_constraints.max_length} to {new_constraints.max_length}"
        )

    # Min length decreased
    if (
        old_constraints.min_length is not None
        and (
            new_constraints.min_length is None
            or new_constraints.min_length < old_constraints.min_length
        )
    ):
        widening.append("minLength constraint relaxed")

    # Maximum increased
    if (
        new_constraints.maximum is not None
        and old_constraints.maximum is not None
        and new_constraints.maximum > old_constraints.maximum
    ):
        widening.append(
            f"maximum widened from {old_constraints.maximum} to {new_constraints.maximum}"
        )

    # Nullable changed from false to true
    if not old_constraints.nullable and new_constraints.nullable:
        widening.append("nullable changed from false to true")

    return widening
