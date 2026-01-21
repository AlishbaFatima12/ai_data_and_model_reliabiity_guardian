"""Bronze type skill - Data type conformance validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class FieldTypeSpec(BaseModel):
    """Type specification for a field."""

    name: str
    expected_type: str  # "string", "integer", "float", "boolean", "datetime"
    nullable: bool = True


class TypeConfig(BaseModel):
    """Configuration for type validation."""

    field_specs: list[FieldTypeSpec] = Field(
        default_factory=list,
        description="Type specifications for fields",
    )
    tolerance_percent: float = Field(
        default=1.0,
        ge=0.0,
        le=100.0,
        description="Percentage of type mismatches tolerated",
    )


class TypeResult(BaseModel):
    """Result of type validation."""

    passed: bool
    mismatch_counts: dict[str, int] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)


class TypeCheckSkill:
    """Bronze skill for verifying data type conformance (FR-003, DV-003).

    Validates that field values match their expected data types.
    """

    name: str = "bronze.type"

    # Type mapping for validation
    TYPE_VALIDATORS = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "datetime": lambda v: isinstance(v, (datetime, str)),
    }

    def __init__(self, config: TypeConfig | None = None):
        """Initialize the type check skill.

        Args:
            config: Configuration for type validation.
        """
        self.config = config or TypeConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: TypeConfig | None = None,
    ) -> TypeResult:
        """Validate field types.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            TypeResult with validation outcome.
        """
        cfg = config or self.config
        total_records = len(records)
        if total_records == 0 or not cfg.field_specs:
            return TypeResult(passed=True)

        mismatch_counts: dict[str, int] = {}
        mismatch_records: dict[str, list[int]] = {}
        anomalies: list[Anomaly] = []

        for spec in cfg.field_specs:
            mismatch_counts[spec.name] = 0
            mismatch_records[spec.name] = []

            validator = self.TYPE_VALIDATORS.get(spec.expected_type)
            if validator is None:
                continue

            for idx, record in enumerate(records):
                value = record.get(spec.name)

                # Handle null values
                if value is None:
                    if not spec.nullable:
                        mismatch_counts[spec.name] += 1
                        mismatch_records[spec.name].append(idx)
                    continue

                # Check type
                if not validator(value):
                    # Try type coercion for string representations
                    if not self._try_coerce(value, spec.expected_type):
                        mismatch_counts[spec.name] += 1
                        mismatch_records[spec.name].append(idx)

        # Check for anomalies
        for spec in cfg.field_specs:
            count = mismatch_counts.get(spec.name, 0)
            if count == 0:
                continue

            pct = (count / total_records) * 100

            # Type mismatches are always significant
            if count > 0:
                severity_score = self._calculate_severity_score(pct)
                severity = self._determine_severity(severity_score)

                anomaly = Anomaly.create(
                    batch_id=batch_id,
                    failure_code=FailureCode.TYPE_MISMATCH,
                    severity=severity,
                    severity_score=severity_score,
                    root_cause=(
                        f"Type mismatch in field '{spec.name}': "
                        f"expected {spec.expected_type}"
                    ),
                    affected_records=mismatch_records[spec.name],
                    affected_fields=[spec.name],
                    explanation=(
                        f"Found {count} records ({pct:.2f}%) with type mismatch "
                        f"in field '{spec.name}'. Expected type: {spec.expected_type}."
                    ),
                )
                anomalies.append(anomaly)

        return TypeResult(
            passed=len(anomalies) == 0,
            mismatch_counts=mismatch_counts,
            anomalies=anomalies,
        )

    def _try_coerce(self, value: Any, expected_type: str) -> bool:
        """Try to coerce a value to the expected type.

        Args:
            value: Value to coerce.
            expected_type: Expected type name.

        Returns:
            True if coercion would succeed.
        """
        if not isinstance(value, str):
            return False

        try:
            if expected_type == "integer":
                int(value)
                return True
            elif expected_type == "float":
                float(value)
                return True
            elif expected_type == "boolean":
                return value.lower() in ("true", "false", "1", "0", "yes", "no")
            elif expected_type == "datetime":
                # Try common datetime formats
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%dT%H:%M:%SZ",
                ]:
                    try:
                        datetime.strptime(value, fmt)
                        return True
                    except ValueError:
                        continue
        except (ValueError, TypeError):
            pass

        return False

    def _calculate_severity_score(self, mismatch_pct: float) -> float:
        """Calculate severity score based on mismatch percentage.

        Type mismatches are generally more severe as they indicate
        data corruption or schema violations.

        Args:
            mismatch_pct: Percentage of type mismatches.

        Returns:
            Severity score (0-100).
        """
        if mismatch_pct >= 20:
            return 85.0  # CRITICAL
        elif mismatch_pct >= 5:
            return 75.0  # CRITICAL
        elif mismatch_pct >= 1:
            return 55.0  # WARNING
        else:
            return 45.0  # WARNING

    def _determine_severity(self, score: float) -> SeverityLevel:
        """Determine severity level from score.

        Args:
            score: Severity score (0-100).

        Returns:
            Severity level.
        """
        if score >= 70:
            return SeverityLevel.CRITICAL
        elif score >= 40:
            return SeverityLevel.WARNING
        else:
            return SeverityLevel.INFO
