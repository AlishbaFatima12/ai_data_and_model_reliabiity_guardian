"""Bronze null skill - Null/missing value detection."""

from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class NullConfig(BaseModel):
    """Configuration for null validation."""

    required_fields: list[str] = Field(
        default_factory=list,
        description="Fields that must not be null",
    )
    tolerance_percent: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Percentage of null values tolerated before anomaly",
    )


class NullResult(BaseModel):
    """Result of null validation."""

    passed: bool
    null_counts: dict[str, int] = Field(default_factory=dict)
    null_percentages: dict[str, float] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)


class NullSkill:
    """Bronze skill for detecting null/missing values (FR-002, DV-002).

    Detects unexpected null or missing values in required fields.
    """

    name: str = "bronze.null"

    def __init__(self, config: NullConfig | None = None):
        """Initialize the null skill.

        Args:
            config: Configuration for null validation.
        """
        self.config = config or NullConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: NullConfig | None = None,
    ) -> NullResult:
        """Validate for null/missing values.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            NullResult with validation outcome.
        """
        cfg = config or self.config
        total_records = len(records)
        if total_records == 0:
            return NullResult(passed=True)

        null_counts: dict[str, int] = {}
        null_records: dict[str, list[int]] = {}
        anomalies: list[Anomaly] = []

        # Check each required field
        fields_to_check = cfg.required_fields
        if not fields_to_check and records:
            # If no specific fields, check all fields from first record
            fields_to_check = list(records[0].keys())

        for field in fields_to_check:
            null_counts[field] = 0
            null_records[field] = []

            for idx, record in enumerate(records):
                value = record.get(field)
                if self._is_null_or_empty(value):
                    null_counts[field] += 1
                    null_records[field].append(idx)

        # Calculate percentages and check tolerance
        null_percentages: dict[str, float] = {}
        for field, count in null_counts.items():
            pct = (count / total_records) * 100
            null_percentages[field] = pct

            # Check if field is required (in required_fields list)
            is_required = field in cfg.required_fields

            # For required fields, any null is an anomaly
            # For other fields, check against tolerance
            if is_required and count > 0:
                severity_score = self._calculate_severity_score(pct, is_required=True)
                severity = self._determine_severity(severity_score)

                anomaly = Anomaly.create(
                    batch_id=batch_id,
                    failure_code=FailureCode.NULL_VALUE_DETECTED,
                    severity=severity,
                    severity_score=severity_score,
                    root_cause=f"Null values in required field '{field}'",
                    affected_records=null_records[field],
                    affected_fields=[field],
                    explanation=(
                        f"Found {count} null values ({pct:.2f}%) in required field '{field}'. "
                        f"Required fields must not contain null values."
                    ),
                )
                anomalies.append(anomaly)

            elif not is_required and pct > cfg.tolerance_percent:
                severity_score = self._calculate_severity_score(pct, is_required=False)
                severity = self._determine_severity(severity_score)

                anomaly = Anomaly.create(
                    batch_id=batch_id,
                    failure_code=FailureCode.NULL_VALUE_DETECTED,
                    severity=severity,
                    severity_score=severity_score,
                    root_cause=f"Null values in field '{field}' exceed tolerance",
                    affected_records=null_records[field],
                    affected_fields=[field],
                    explanation=(
                        f"Found {count} null values ({pct:.2f}%) in field '{field}', "
                        f"exceeding tolerance of {cfg.tolerance_percent}%."
                    ),
                )
                anomalies.append(anomaly)

        return NullResult(
            passed=len(anomalies) == 0,
            null_counts=null_counts,
            null_percentages=null_percentages,
            anomalies=anomalies,
        )

    def _is_null_or_empty(self, value: Any) -> bool:
        """Check if a value is null or empty.

        Args:
            value: Value to check.

        Returns:
            True if null or empty.
        """
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

    def _calculate_severity_score(self, null_pct: float, is_required: bool) -> float:
        """Calculate severity score based on null percentage.

        Args:
            null_pct: Percentage of null values.
            is_required: Whether the field is required.

        Returns:
            Severity score (0-100).
        """
        if is_required:
            # Required fields with nulls are always more severe
            if null_pct >= 50:
                return 85.0  # CRITICAL
            elif null_pct >= 10:
                return 70.0  # CRITICAL
            elif null_pct >= 1:
                return 55.0  # WARNING
            else:
                return 45.0  # WARNING

        # Non-required fields
        if null_pct >= 50:
            return 60.0  # WARNING
        elif null_pct >= 20:
            return 45.0  # WARNING
        else:
            return 30.0  # INFO

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
