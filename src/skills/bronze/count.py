"""Bronze count skill - Record count validation."""

from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class CountConfig(BaseModel):
    """Configuration for count validation."""

    expected_min: int | None = Field(default=None, description="Minimum expected count")
    expected_max: int | None = Field(default=None, description="Maximum expected count")
    expected_exact: int | None = Field(default=None, description="Exact expected count")


class CountResult(BaseModel):
    """Result of count validation."""

    passed: bool
    actual_count: int
    expected_min: int | None = None
    expected_max: int | None = None
    expected_exact: int | None = None
    anomaly: Anomaly | None = None


class CountSkill:
    """Bronze skill for validating record counts (FR-001, DV-001).

    Validates that the batch has the expected number of records.
    """

    name: str = "bronze.count"

    def __init__(self, config: CountConfig | None = None):
        """Initialize the count skill.

        Args:
            config: Configuration for count validation.
        """
        self.config = config or CountConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: CountConfig | None = None,
    ) -> CountResult:
        """Validate record count.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            CountResult with validation outcome.
        """
        cfg = config or self.config
        actual_count = len(records)
        passed = True
        anomaly = None
        root_cause = ""

        # Check exact count
        if cfg.expected_exact is not None:
            if actual_count != cfg.expected_exact:
                passed = False
                root_cause = (
                    f"Expected exactly {cfg.expected_exact} records, "
                    f"but found {actual_count}"
                )

        # Check min count
        if cfg.expected_min is not None and actual_count < cfg.expected_min:
            passed = False
            root_cause = (
                f"Expected at least {cfg.expected_min} records, "
                f"but found {actual_count}"
            )

        # Check max count
        if cfg.expected_max is not None and actual_count > cfg.expected_max:
            passed = False
            root_cause = (
                f"Expected at most {cfg.expected_max} records, "
                f"but found {actual_count}"
            )

        if not passed:
            # Calculate severity based on deviation
            severity_score = self._calculate_severity_score(
                actual_count, cfg
            )
            severity = self._determine_severity(severity_score)

            anomaly = Anomaly.create(
                batch_id=batch_id,
                failure_code=FailureCode.RECORD_COUNT_MISMATCH,
                severity=severity,
                severity_score=severity_score,
                root_cause=root_cause,
                affected_records=list(range(actual_count)),
                explanation=f"Record count validation failed: {root_cause}",
            )

        return CountResult(
            passed=passed,
            actual_count=actual_count,
            expected_min=cfg.expected_min,
            expected_max=cfg.expected_max,
            expected_exact=cfg.expected_exact,
            anomaly=anomaly,
        )

    def _calculate_severity_score(
        self, actual: int, config: CountConfig
    ) -> float:
        """Calculate severity score based on count deviation.

        Args:
            actual: Actual record count.
            config: Validation configuration.

        Returns:
            Severity score (0-100).
        """
        if config.expected_exact is not None:
            expected = config.expected_exact
            if expected == 0:
                return 50.0  # Default if can't calculate percentage
            deviation_pct = abs(actual - expected) / expected * 100
        elif config.expected_min is not None and actual < config.expected_min:
            expected = config.expected_min
            deviation_pct = (expected - actual) / expected * 100
        elif config.expected_max is not None and actual > config.expected_max:
            expected = config.expected_max
            deviation_pct = (actual - expected) / expected * 100
        else:
            return 30.0  # Default

        # Map deviation to score (higher deviation = higher score = more severe)
        if deviation_pct >= 50:
            return 75.0  # CRITICAL
        elif deviation_pct >= 20:
            return 55.0  # WARNING
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
