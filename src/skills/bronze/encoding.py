"""Bronze encoding skill - UTF-8 encoding validation."""

from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class EncodingConfig(BaseModel):
    """Configuration for encoding validation."""

    expected_encoding: str = Field(
        default="utf-8",
        description="Expected character encoding",
    )
    strict: bool = Field(
        default=True,
        description="Whether to use strict encoding validation",
    )


class EncodingResult(BaseModel):
    """Result of encoding validation."""

    passed: bool
    error_count: int = 0
    error_fields: dict[str, int] = Field(default_factory=dict)
    anomaly: Anomaly | None = None


class EncodingSkill:
    """Bronze skill for validating UTF-8 encoding (FR-007, DV-007).

    Validates that all string values are properly encoded.
    """

    name: str = "bronze.encoding"

    def __init__(self, config: EncodingConfig | None = None):
        """Initialize the encoding skill.

        Args:
            config: Configuration for encoding validation.
        """
        self.config = config or EncodingConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: EncodingConfig | None = None,
    ) -> EncodingResult:
        """Validate string encoding.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            EncodingResult with validation outcome.
        """
        cfg = config or self.config
        total_records = len(records)
        if total_records == 0:
            return EncodingResult(passed=True)

        error_count = 0
        error_records: list[int] = []
        error_fields: dict[str, int] = {}

        for idx, record in enumerate(records):
            record_has_error = False

            for field, value in record.items():
                if not isinstance(value, str):
                    continue

                if not self._validate_encoding(value, cfg):
                    error_count += 1
                    error_fields[field] = error_fields.get(field, 0) + 1
                    record_has_error = True

            if record_has_error:
                error_records.append(idx)

        if error_count == 0:
            return EncodingResult(passed=True)

        # Calculate severity
        error_pct = (len(error_records) / total_records) * 100
        severity_score = self._calculate_severity_score(error_pct)
        severity = self._determine_severity(severity_score)

        # Build field summary
        field_summary = ", ".join(
            f"'{f}': {c} errors" for f, c in sorted(error_fields.items(), key=lambda x: -x[1])[:5]
        )

        anomaly = Anomaly.create(
            batch_id=batch_id,
            failure_code=FailureCode.ENCODING_ERROR,
            severity=severity,
            severity_score=severity_score,
            root_cause=f"Invalid {cfg.expected_encoding} encoding detected",
            affected_records=error_records,
            affected_fields=list(error_fields.keys()),
            explanation=(
                f"Found {error_count} encoding errors in {len(error_records)} records "
                f"({error_pct:.2f}%). Expected encoding: {cfg.expected_encoding}. "
                f"Affected fields: {field_summary}."
            ),
        )

        return EncodingResult(
            passed=False,
            error_count=error_count,
            error_fields=error_fields,
            anomaly=anomaly,
        )

    def _validate_encoding(self, value: str, config: EncodingConfig) -> bool:
        """Validate that a string is properly encoded.

        Args:
            value: String value to validate.
            config: Encoding configuration.

        Returns:
            True if encoding is valid.
        """
        try:
            # Check for encoding issues by round-tripping
            errors = "strict" if config.strict else "replace"
            encoded = value.encode(config.expected_encoding, errors=errors)
            decoded = encoded.decode(config.expected_encoding, errors=errors)

            # Check for replacement characters indicating encoding issues
            if config.strict:
                # In strict mode, encoding/decoding should round-trip perfectly
                return decoded == value
            else:
                # In non-strict mode, check for replacement characters
                return "\ufffd" not in decoded

        except (UnicodeEncodeError, UnicodeDecodeError):
            return False

    def validate_raw_bytes(
        self,
        data: bytes,
        batch_id: str,
        config: EncodingConfig | None = None,
    ) -> EncodingResult:
        """Validate raw byte data for encoding.

        This is useful when processing raw file content before parsing.

        Args:
            data: Raw bytes to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            EncodingResult with validation outcome.
        """
        cfg = config or self.config

        try:
            errors = "strict" if cfg.strict else "replace"
            decoded = data.decode(cfg.expected_encoding, errors=errors)

            # Check for replacement characters
            replacement_count = decoded.count("\ufffd")
            if replacement_count > 0 and cfg.strict:
                # Found encoding issues
                severity_score = self._calculate_severity_score(
                    (replacement_count / len(decoded)) * 100 if decoded else 100
                )
                severity = self._determine_severity(severity_score)

                anomaly = Anomaly.create(
                    batch_id=batch_id,
                    failure_code=FailureCode.ENCODING_ERROR,
                    severity=severity,
                    severity_score=severity_score,
                    root_cause=f"Invalid {cfg.expected_encoding} encoding in raw data",
                    explanation=(
                        f"Found {replacement_count} invalid byte sequences when decoding "
                        f"raw data as {cfg.expected_encoding}."
                    ),
                )

                return EncodingResult(
                    passed=False,
                    error_count=replacement_count,
                    anomaly=anomaly,
                )

            return EncodingResult(passed=True)

        except (UnicodeDecodeError, Exception) as e:
            severity_score = 85.0  # CRITICAL
            severity = SeverityLevel.CRITICAL

            anomaly = Anomaly.create(
                batch_id=batch_id,
                failure_code=FailureCode.ENCODING_ERROR,
                severity=severity,
                severity_score=severity_score,
                root_cause=f"Failed to decode data as {cfg.expected_encoding}",
                explanation=f"Decoding error: {str(e)}",
            )

            return EncodingResult(
                passed=False,
                error_count=1,
                anomaly=anomaly,
            )

    def _calculate_severity_score(self, error_pct: float) -> float:
        """Calculate severity score based on encoding errors.

        Encoding errors are generally critical as they indicate
        data corruption or incompatibility.

        Args:
            error_pct: Percentage of encoding errors.

        Returns:
            Severity score (0-100).
        """
        if error_pct >= 10:
            return 85.0  # CRITICAL
        elif error_pct >= 5:
            return 75.0  # CRITICAL
        elif error_pct >= 1:
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
