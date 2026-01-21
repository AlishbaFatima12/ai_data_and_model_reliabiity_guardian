"""Bronze range skill - Range boundary validation."""

from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class FieldRangeSpec(BaseModel):
    """Range specification for a numeric field."""

    name: str
    min_value: float | None = None
    max_value: float | None = None
    inclusive_min: bool = True
    inclusive_max: bool = True


class RangeConfig(BaseModel):
    """Configuration for range validation."""

    field_specs: list[FieldRangeSpec] = Field(
        default_factory=list,
        description="Range specifications for fields",
    )


class RangeResult(BaseModel):
    """Result of range validation."""

    passed: bool
    violation_counts: dict[str, int] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)


class RangeCheckSkill:
    """Bronze skill for validating range boundaries (FR-004, DV-004).

    Validates that numeric field values fall within expected ranges.
    """

    name: str = "bronze.range"

    def __init__(self, config: RangeConfig | None = None):
        """Initialize the range check skill.

        Args:
            config: Configuration for range validation.
        """
        self.config = config or RangeConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: RangeConfig | None = None,
    ) -> RangeResult:
        """Validate field ranges.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            RangeResult with validation outcome.
        """
        cfg = config or self.config
        total_records = len(records)
        if total_records == 0 or not cfg.field_specs:
            return RangeResult(passed=True)

        violation_counts: dict[str, int] = {}
        violation_records: dict[str, list[int]] = {}
        violation_details: dict[str, list[tuple[int, Any, str]]] = {}
        anomalies: list[Anomaly] = []

        for spec in cfg.field_specs:
            violation_counts[spec.name] = 0
            violation_records[spec.name] = []
            violation_details[spec.name] = []

            for idx, record in enumerate(records):
                value = record.get(spec.name)

                # Skip null values (handled by null skill)
                if value is None:
                    continue

                # Try to convert to numeric
                try:
                    num_value = float(value)
                except (TypeError, ValueError):
                    continue  # Type issues handled by type skill

                violation = self._check_range(num_value, spec)
                if violation:
                    violation_counts[spec.name] += 1
                    violation_records[spec.name].append(idx)
                    violation_details[spec.name].append((idx, num_value, violation))

        # Create anomalies for violations
        for spec in cfg.field_specs:
            count = violation_counts.get(spec.name, 0)
            if count == 0:
                continue

            pct = (count / total_records) * 100
            details = violation_details.get(spec.name, [])

            # Build explanation with examples
            examples = details[:3]  # First 3 examples
            example_str = ", ".join(
                f"record {idx}: {val} ({reason})"
                for idx, val, reason in examples
            )

            severity_score = self._calculate_severity_score(pct, details, spec)
            severity = self._determine_severity(severity_score)

            range_desc = self._describe_range(spec)

            anomaly = Anomaly.create(
                batch_id=batch_id,
                failure_code=FailureCode.RANGE_VIOLATION,
                severity=severity,
                severity_score=severity_score,
                root_cause=f"Values outside range for field '{spec.name}'",
                affected_records=violation_records[spec.name],
                affected_fields=[spec.name],
                explanation=(
                    f"Found {count} records ({pct:.2f}%) with values outside "
                    f"the expected range {range_desc} for field '{spec.name}'. "
                    f"Examples: {example_str}."
                ),
            )
            anomalies.append(anomaly)

        return RangeResult(
            passed=len(anomalies) == 0,
            violation_counts=violation_counts,
            anomalies=anomalies,
        )

    def _check_range(self, value: float, spec: FieldRangeSpec) -> str | None:
        """Check if a value is within the specified range.

        Args:
            value: Value to check.
            spec: Range specification.

        Returns:
            Violation reason or None if valid.
        """
        if spec.min_value is not None:
            if spec.inclusive_min:
                if value < spec.min_value:
                    return f"below minimum {spec.min_value}"
            else:
                if value <= spec.min_value:
                    return f"at or below minimum {spec.min_value}"

        if spec.max_value is not None:
            if spec.inclusive_max:
                if value > spec.max_value:
                    return f"above maximum {spec.max_value}"
            else:
                if value >= spec.max_value:
                    return f"at or above maximum {spec.max_value}"

        return None

    def _describe_range(self, spec: FieldRangeSpec) -> str:
        """Create human-readable range description.

        Args:
            spec: Range specification.

        Returns:
            Range description string.
        """
        parts = []
        if spec.min_value is not None:
            op = ">=" if spec.inclusive_min else ">"
            parts.append(f"{op} {spec.min_value}")
        if spec.max_value is not None:
            op = "<=" if spec.inclusive_max else "<"
            parts.append(f"{op} {spec.max_value}")

        if not parts:
            return "(no constraints)"
        return " and ".join(parts)

    def _calculate_severity_score(
        self,
        violation_pct: float,
        details: list[tuple[int, Any, str]],
        spec: FieldRangeSpec,
    ) -> float:
        """Calculate severity score based on violations.

        Args:
            violation_pct: Percentage of violations.
            details: List of violation details.
            spec: Range specification.

        Returns:
            Severity score (0-100).
        """
        # Base score on percentage
        if violation_pct >= 20:
            base_score = 70.0
        elif violation_pct >= 5:
            base_score = 55.0
        elif violation_pct >= 1:
            base_score = 45.0
        else:
            base_score = 35.0

        # Adjust based on severity of violations (how far outside range)
        if details and spec.min_value is not None and spec.max_value is not None:
            range_size = spec.max_value - spec.min_value
            if range_size > 0:
                max_deviation = max(
                    self._calculate_deviation(val, spec) / range_size
                    for _, val, _ in details
                )
                # Add up to 15 points for extreme deviations
                if max_deviation > 1.0:
                    base_score = min(100.0, base_score + 15.0)

        return base_score

    def _calculate_deviation(self, value: float, spec: FieldRangeSpec) -> float:
        """Calculate how far a value is from the valid range.

        Args:
            value: The value to check.
            spec: Range specification.

        Returns:
            Absolute deviation from range.
        """
        if spec.min_value is not None and value < spec.min_value:
            return spec.min_value - value
        if spec.max_value is not None and value > spec.max_value:
            return value - spec.max_value
        return 0.0

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
