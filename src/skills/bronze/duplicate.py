"""Bronze duplicate skill - Duplicate record detection."""

from typing import Any
import hashlib
import json

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class DuplicateConfig(BaseModel):
    """Configuration for duplicate detection."""

    key_fields: list[str] | None = Field(
        default=None,
        description="Fields to use for duplicate detection (None = all fields)",
    )
    tolerance_percent: float = Field(
        default=0.5,
        ge=0.0,
        le=100.0,
        description="Percentage of duplicates tolerated",
    )
    case_sensitive: bool = Field(
        default=True,
        description="Whether string comparison is case-sensitive",
    )


class DuplicateResult(BaseModel):
    """Result of duplicate detection."""

    passed: bool
    duplicate_count: int = 0
    duplicate_groups: list[list[int]] = Field(default_factory=list)
    anomaly: Anomaly | None = None


class DuplicateSkill:
    """Bronze skill for detecting duplicate records (FR-006, DV-006).

    Detects exact duplicate records in the batch.
    """

    name: str = "bronze.duplicate"

    def __init__(self, config: DuplicateConfig | None = None):
        """Initialize the duplicate skill.

        Args:
            config: Configuration for duplicate detection.
        """
        self.config = config or DuplicateConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: DuplicateConfig | None = None,
    ) -> DuplicateResult:
        """Detect duplicate records.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            DuplicateResult with validation outcome.
        """
        cfg = config or self.config
        total_records = len(records)
        if total_records < 2:
            return DuplicateResult(passed=True)

        # Build hash -> indices mapping
        hash_to_indices: dict[str, list[int]] = {}

        for idx, record in enumerate(records):
            record_hash = self._hash_record(record, cfg)
            if record_hash not in hash_to_indices:
                hash_to_indices[record_hash] = []
            hash_to_indices[record_hash].append(idx)

        # Find duplicate groups (groups with more than one record)
        duplicate_groups: list[list[int]] = []
        duplicate_indices: set[int] = set()

        for indices in hash_to_indices.values():
            if len(indices) > 1:
                duplicate_groups.append(indices)
                duplicate_indices.update(indices)

        duplicate_count = len(duplicate_indices)

        if duplicate_count == 0:
            return DuplicateResult(passed=True)

        # Check against tolerance
        duplicate_pct = (duplicate_count / total_records) * 100
        passed = duplicate_pct <= cfg.tolerance_percent

        anomaly = None
        if not passed:
            severity_score = self._calculate_severity_score(duplicate_pct, len(duplicate_groups))
            severity = self._determine_severity(severity_score)

            # Build examples
            examples = []
            for group in duplicate_groups[:3]:
                if len(group) >= 2:
                    examples.append(f"records {group[0]} and {group[1]}")

            example_str = "; ".join(examples) if examples else "N/A"

            anomaly = Anomaly.create(
                batch_id=batch_id,
                failure_code=FailureCode.DUPLICATE_DETECTED,
                severity=severity,
                severity_score=severity_score,
                root_cause=f"Duplicate records detected ({duplicate_count} duplicates)",
                affected_records=list(duplicate_indices),
                explanation=(
                    f"Found {duplicate_count} records ({duplicate_pct:.2f}%) that are duplicates "
                    f"across {len(duplicate_groups)} duplicate groups, exceeding tolerance of "
                    f"{cfg.tolerance_percent}%. Examples: {example_str}."
                ),
            )

        return DuplicateResult(
            passed=passed,
            duplicate_count=duplicate_count,
            duplicate_groups=duplicate_groups,
            anomaly=anomaly,
        )

    def _hash_record(self, record: dict[str, Any], config: DuplicateConfig) -> str:
        """Create a hash for a record based on configured fields.

        Args:
            record: Record to hash.
            config: Duplicate detection configuration.

        Returns:
            Hash string for the record.
        """
        # Select fields to hash
        if config.key_fields:
            fields_to_hash = config.key_fields
        else:
            fields_to_hash = sorted(record.keys())

        # Build value tuple
        values = []
        for field in fields_to_hash:
            value = record.get(field)
            if not config.case_sensitive and isinstance(value, str):
                value = value.lower()
            values.append((field, value))

        # Create stable JSON representation and hash it
        try:
            json_str = json.dumps(values, sort_keys=True, default=str)
            return hashlib.md5(json_str.encode()).hexdigest()
        except Exception:
            # Fallback to string representation
            return hashlib.md5(str(values).encode()).hexdigest()

    def _calculate_severity_score(self, duplicate_pct: float, group_count: int) -> float:
        """Calculate severity score based on duplicates.

        Args:
            duplicate_pct: Percentage of duplicate records.
            group_count: Number of duplicate groups.

        Returns:
            Severity score (0-100).
        """
        # Base score on percentage
        if duplicate_pct >= 20:
            base_score = 70.0  # CRITICAL
        elif duplicate_pct >= 10:
            base_score = 55.0  # WARNING
        elif duplicate_pct >= 5:
            base_score = 45.0  # WARNING
        else:
            base_score = 35.0  # INFO

        # Adjust based on number of groups (many groups = likely systematic issue)
        if group_count >= 50:
            base_score = min(100.0, base_score + 10.0)
        elif group_count >= 20:
            base_score = min(100.0, base_score + 5.0)

        return base_score

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
