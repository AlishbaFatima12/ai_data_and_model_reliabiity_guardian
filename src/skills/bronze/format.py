"""Bronze format skill - Pattern/format validation."""

import re
from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class FieldFormatSpec(BaseModel):
    """Format specification for a field."""

    name: str
    pattern: str  # Regex pattern
    pattern_description: str = ""  # Human-readable description


class FormatConfig(BaseModel):
    """Configuration for format validation."""

    field_specs: list[FieldFormatSpec] = Field(
        default_factory=list,
        description="Format specifications for fields",
    )


class FormatResult(BaseModel):
    """Result of format validation."""

    passed: bool
    violation_counts: dict[str, int] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)


class FormatSkill:
    """Bronze skill for validating field formats (FR-005, DV-005).

    Validates that field values match expected patterns (regex).
    """

    name: str = "bronze.format"

    # Common pre-defined patterns
    COMMON_PATTERNS = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "phone_us": r"^\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$",
        "uuid": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        "date_iso": r"^\d{4}-\d{2}-\d{2}$",
        "datetime_iso": r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}",
        "zipcode_us": r"^\d{5}(-\d{4})?$",
        "ipv4": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
        "url": r"^https?://[^\s]+$",
    }

    def __init__(self, config: FormatConfig | None = None):
        """Initialize the format skill.

        Args:
            config: Configuration for format validation.
        """
        self.config = config or FormatConfig()
        self._compiled_patterns: dict[str, re.Pattern] = {}

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: FormatConfig | None = None,
    ) -> FormatResult:
        """Validate field formats.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            FormatResult with validation outcome.
        """
        cfg = config or self.config
        total_records = len(records)
        if total_records == 0 or not cfg.field_specs:
            return FormatResult(passed=True)

        violation_counts: dict[str, int] = {}
        violation_records: dict[str, list[int]] = {}
        violation_examples: dict[str, list[tuple[int, str]]] = {}
        anomalies: list[Anomaly] = []

        for spec in cfg.field_specs:
            violation_counts[spec.name] = 0
            violation_records[spec.name] = []
            violation_examples[spec.name] = []

            # Get compiled pattern
            pattern = self._get_pattern(spec)
            if pattern is None:
                continue

            for idx, record in enumerate(records):
                value = record.get(spec.name)

                # Skip null values (handled by null skill)
                if value is None:
                    continue

                # Convert to string
                str_value = str(value)

                # Check pattern match
                if not pattern.match(str_value):
                    violation_counts[spec.name] += 1
                    violation_records[spec.name].append(idx)
                    if len(violation_examples[spec.name]) < 3:
                        violation_examples[spec.name].append((idx, str_value))

        # Create anomalies for violations
        for spec in cfg.field_specs:
            count = violation_counts.get(spec.name, 0)
            if count == 0:
                continue

            pct = (count / total_records) * 100
            examples = violation_examples.get(spec.name, [])

            # Build example string
            example_str = ", ".join(
                f"record {idx}: '{val[:50]}...'" if len(val) > 50 else f"record {idx}: '{val}'"
                for idx, val in examples
            )

            severity_score = self._calculate_severity_score(pct)
            severity = self._determine_severity(severity_score)

            desc = spec.pattern_description or f"pattern /{spec.pattern}/"

            anomaly = Anomaly.create(
                batch_id=batch_id,
                failure_code=FailureCode.FORMAT_VIOLATION,
                severity=severity,
                severity_score=severity_score,
                root_cause=f"Format violation in field '{spec.name}'",
                affected_records=violation_records[spec.name],
                affected_fields=[spec.name],
                explanation=(
                    f"Found {count} records ({pct:.2f}%) with values not matching "
                    f"expected format ({desc}) for field '{spec.name}'. "
                    f"Examples: {example_str}."
                ),
            )
            anomalies.append(anomaly)

        return FormatResult(
            passed=len(anomalies) == 0,
            violation_counts=violation_counts,
            anomalies=anomalies,
        )

    def _get_pattern(self, spec: FieldFormatSpec) -> re.Pattern | None:
        """Get compiled regex pattern for a specification.

        Args:
            spec: Format specification.

        Returns:
            Compiled regex pattern or None if invalid.
        """
        cache_key = f"{spec.name}:{spec.pattern}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]

        # Check if pattern is a common pattern name
        pattern_str = self.COMMON_PATTERNS.get(spec.pattern, spec.pattern)

        try:
            compiled = re.compile(pattern_str, re.IGNORECASE)
            self._compiled_patterns[cache_key] = compiled
            return compiled
        except re.error:
            return None

    def _calculate_severity_score(self, violation_pct: float) -> float:
        """Calculate severity score based on violations.

        Format violations are generally less severe than type mismatches.

        Args:
            violation_pct: Percentage of violations.

        Returns:
            Severity score (0-100).
        """
        if violation_pct >= 50:
            return 55.0  # WARNING
        elif violation_pct >= 20:
            return 45.0  # WARNING
        elif violation_pct >= 5:
            return 35.0  # INFO
        else:
            return 25.0  # INFO

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
