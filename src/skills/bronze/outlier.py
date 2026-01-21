"""Bronze outlier skill - Z-score based outlier detection.

Detects statistical outliers using Z-score analysis like Gemini does.
"""

from typing import Any
import math

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.anomaly import Anomaly


class OutlierConfig(BaseModel):
    """Configuration for outlier detection."""

    z_threshold: float = Field(
        default=3.0,
        ge=1.0,
        le=5.0,
        description="Z-score threshold for outlier detection (default: 3.0)",
    )
    numeric_fields: list[str] = Field(
        default_factory=list,
        description="Specific numeric fields to check (empty = auto-detect)",
    )
    min_records: int = Field(
        default=30,
        ge=10,
        description="Minimum records needed for statistical analysis",
    )


class OutlierResult(BaseModel):
    """Result of outlier detection."""

    passed: bool
    outliers_by_field: dict[str, list[int]] = Field(default_factory=dict)
    anomalies: list[Anomaly] = Field(default_factory=list)
    statistics: dict[str, dict[str, float]] = Field(default_factory=dict)


class OutlierDetectionSkill:
    """Bronze skill for detecting statistical outliers using Z-score.

    Identifies values that are significantly different from the mean,
    which often indicate data quality issues or exceptional cases
    that need review.
    """

    name: str = "bronze.outlier"

    def __init__(self, config: OutlierConfig | None = None):
        """Initialize the outlier detection skill.

        Args:
            config: Configuration for outlier detection.
        """
        self.config = config or OutlierConfig()

    def validate(
        self,
        records: list[dict[str, Any]],
        batch_id: str,
        config: OutlierConfig | None = None,
    ) -> OutlierResult:
        """Detect outliers in numeric fields.

        Args:
            records: List of records to validate.
            batch_id: ID of the batch being validated.
            config: Optional override configuration.

        Returns:
            OutlierResult with detected outliers.
        """
        cfg = config or self.config
        total_records = len(records)

        if total_records < cfg.min_records:
            return OutlierResult(passed=True)

        # Auto-detect numeric fields if not specified
        numeric_fields = cfg.numeric_fields or self._detect_numeric_fields(records)

        if not numeric_fields:
            return OutlierResult(passed=True)

        outliers_by_field: dict[str, list[int]] = {}
        outlier_values: dict[str, list[tuple[int, float]]] = {}
        statistics: dict[str, dict[str, float]] = {}
        anomalies: list[Anomaly] = []

        for field in numeric_fields:
            # Extract numeric values
            values = []
            value_indices = []

            for idx, record in enumerate(records):
                val = record.get(field)
                if val is not None:
                    try:
                        num_val = float(val)
                        if not math.isnan(num_val) and not math.isinf(num_val):
                            values.append(num_val)
                            value_indices.append(idx)
                    except (TypeError, ValueError):
                        continue

            if len(values) < cfg.min_records:
                continue

            # Calculate statistics
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std = math.sqrt(variance) if variance > 0 else 0

            statistics[field] = {
                "mean": round(mean, 2),
                "std": round(std, 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "count": len(values),
            }

            if std == 0:
                continue

            # Find outliers using Z-score
            field_outliers = []
            field_outlier_values = []

            for i, val in enumerate(values):
                z_score = abs((val - mean) / std)
                if z_score > cfg.z_threshold:
                    record_idx = value_indices[i]
                    field_outliers.append(record_idx)
                    field_outlier_values.append((record_idx, val))

            if field_outliers:
                outliers_by_field[field] = field_outliers
                outlier_values[field] = field_outlier_values

        # Create anomalies for fields with outliers
        for field, outlier_indices in outliers_by_field.items():
            count = len(outlier_indices)
            pct = (count / total_records) * 100
            stats = statistics.get(field, {})

            # Get example values
            examples = outlier_values.get(field, [])[:5]
            example_str = ", ".join(
                f"row {idx}: {val:,.2f}" for idx, val in examples
            )

            severity_score = self._calculate_severity_score(pct, count)
            severity = self._determine_severity(severity_score)

            anomaly = Anomaly.create(
                batch_id=batch_id,
                failure_code=FailureCode.RANGE_VIOLATION,
                severity=severity,
                severity_score=severity_score,
                root_cause=f"Statistical outliers detected in '{field}' (Z-score > {cfg.z_threshold})",
                affected_records=outlier_indices,
                affected_fields=[field],
                explanation=(
                    f"Found {count} outliers ({pct:.2f}%) in field '{field}'. "
                    f"Mean: {stats.get('mean', 0):,.2f}, Std: {stats.get('std', 0):,.2f}. "
                    f"Examples: {example_str}. "
                    f"These values are more than {cfg.z_threshold} standard deviations from the mean."
                ),
                metadata={
                    "detection_method": "z_score",
                    "z_threshold": cfg.z_threshold,
                    "field_statistics": stats,
                    "outlier_count": count,
                },
            )
            anomalies.append(anomaly)

        return OutlierResult(
            passed=len(anomalies) == 0,
            outliers_by_field=outliers_by_field,
            anomalies=anomalies,
            statistics=statistics,
        )

    def _detect_numeric_fields(self, records: list[dict[str, Any]]) -> list[str]:
        """Auto-detect numeric fields from records.

        Args:
            records: Sample of records to analyze.

        Returns:
            List of field names that appear to be numeric.
        """
        if not records:
            return []

        # Check first 100 records
        sample = records[:100]
        numeric_fields = []

        # Get all fields from first record
        all_fields = set()
        for record in sample:
            all_fields.update(record.keys())

        for field in all_fields:
            # Skip ID-like fields
            if field.lower() in ('id', 'index', 'unnamed: 0', '_id', 'row_id'):
                continue

            numeric_count = 0
            for record in sample:
                val = record.get(field)
                if val is not None:
                    try:
                        float(val)
                        numeric_count += 1
                    except (TypeError, ValueError):
                        pass

            # If >80% of values are numeric, consider it a numeric field
            if numeric_count > len(sample) * 0.8:
                numeric_fields.append(field)

        return numeric_fields

    def _calculate_severity_score(self, pct: float, count: int) -> float:
        """Calculate severity score based on outlier statistics.

        Args:
            pct: Percentage of outliers.
            count: Absolute count of outliers.

        Returns:
            Severity score (0-100).
        """
        # Base on percentage
        if pct >= 5:
            base_score = 65.0
        elif pct >= 2:
            base_score = 55.0
        elif pct >= 1:
            base_score = 45.0
        else:
            base_score = 35.0

        # Adjust for absolute count
        if count >= 100:
            base_score = min(85.0, base_score + 15)
        elif count >= 50:
            base_score = min(75.0, base_score + 10)

        return base_score

    def _determine_severity(self, score: float) -> SeverityLevel:
        """Determine severity level from score.

        Args:
            score: Severity score (0-100).

        Returns:
            Severity level.
        """
        if score >= 65:
            return SeverityLevel.WARNING
        elif score >= 40:
            return SeverityLevel.INFO
        else:
            return SeverityLevel.INFO
