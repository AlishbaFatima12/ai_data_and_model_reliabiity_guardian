"""Silver Tier distrib skill for BL-007 detection.

This skill detects distribution shifts using Population Stability Index (PSI):
- PSI < 0.1: No significant change
- 0.1 <= PSI < 0.25: Some change (WARNING)
- PSI >= 0.25: Significant change (CRITICAL)
"""

import json
import math
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.silver_anomaly import BusinessLogicAnomaly

logger = structlog.get_logger(__name__)

# PSI thresholds per spec
PSI_WARNING_THRESHOLD = 0.1
PSI_CRITICAL_THRESHOLD = 0.25

# Small constant to avoid log(0)
EPSILON = 0.0001


class DistributionProfile:
    """Baseline distribution profile for a column."""

    def __init__(
        self,
        column: str,
        is_numeric: bool = False,
        bins: list[tuple[float, float]] | None = None,
        categories: list[str] | None = None,
        frequencies: dict[str, float] | None = None,
        null_rate: float = 0.0,
        record_count: int = 0,
        created_at: datetime | None = None,
    ) -> None:
        """Initialize distribution profile.

        Args:
            column: Column name.
            is_numeric: Whether column is numeric.
            bins: Bin ranges for numeric columns [(min, max), ...].
            categories: Category values for categorical columns.
            frequencies: Normalized frequencies per bin/category.
            null_rate: Proportion of null values.
            record_count: Number of records in baseline.
            created_at: When baseline was created.
        """
        self.column = column
        self.is_numeric = is_numeric
        self.bins = bins or []
        self.categories = categories or []
        self.frequencies = frequencies or {}
        self.null_rate = null_rate
        self.record_count = record_count
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "column": self.column,
            "is_numeric": self.is_numeric,
            "bins": self.bins,
            "categories": self.categories,
            "frequencies": self.frequencies,
            "null_rate": self.null_rate,
            "record_count": self.record_count,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DistributionProfile":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            column=data.get("column", ""),
            is_numeric=data.get("is_numeric", False),
            bins=data.get("bins"),
            categories=data.get("categories"),
            frequencies=data.get("frequencies"),
            null_rate=data.get("null_rate", 0.0),
            record_count=data.get("record_count", 0),
            created_at=created_at,
        )


class DistribValidationResult:
    """Result of distribution shift detection."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[BusinessLogicAnomaly] = []
        self.columns_checked: int = 0
        self.columns_shifted: int = 0
        self.psi_scores: dict[str, float] = {}
        self.null_rate_changes: dict[str, float] = {}
        self.duration_ms: float = 0.0


def detect_distribution_shift(
    records: list[dict[str, Any]],
    baseline: dict[str, DistributionProfile],
    batch_id: str = "unknown",
    columns: list[str] | None = None,
) -> DistribValidationResult:
    """Detect distribution shifts in data compared to baseline.

    Args:
        records: Current batch of records.
        baseline: Baseline distribution profiles by column.
        batch_id: Batch identifier for anomalies.
        columns: Specific columns to check (None = all with baselines).

    Returns:
        DistribValidationResult with PSI scores and anomalies.
    """
    start_time = time.perf_counter()
    result = DistribValidationResult()

    if not records or not baseline:
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    # Determine columns to check
    columns_to_check = columns or list(baseline.keys())
    columns_to_check = [c for c in columns_to_check if c in baseline]

    result.columns_checked = len(columns_to_check)

    for column in columns_to_check:
        profile = baseline[column]

        # Calculate current distribution
        current_dist = _calculate_distribution(records, column, profile)

        # Calculate PSI
        psi = _calculate_psi(profile.frequencies, current_dist)
        result.psi_scores[column] = psi

        # Check null rate change
        current_null_rate = _calculate_null_rate(records, column)
        null_rate_change = abs(current_null_rate - profile.null_rate)
        result.null_rate_changes[column] = null_rate_change

        # Determine if shift is significant
        if psi >= PSI_CRITICAL_THRESHOLD:
            result.columns_shifted += 1
            result.anomalies.append(
                _create_anomaly(
                    column=column,
                    psi=psi,
                    severity=SeverityLevel.CRITICAL,
                    batch_id=batch_id,
                    baseline_profile=profile,
                    current_distribution=current_dist,
                )
            )
        elif psi >= PSI_WARNING_THRESHOLD:
            result.columns_shifted += 1
            result.anomalies.append(
                _create_anomaly(
                    column=column,
                    psi=psi,
                    severity=SeverityLevel.WARNING,
                    batch_id=batch_id,
                    baseline_profile=profile,
                    current_distribution=current_dist,
                )
            )

        # Also check for significant null rate change
        if null_rate_change > 0.1:  # 10% change in null rate
            logger.info(
                "null_rate_shift",
                column=column,
                baseline_null_rate=profile.null_rate,
                current_null_rate=current_null_rate,
                change=null_rate_change,
            )

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "distribution_check_complete",
        batch_id=batch_id,
        columns_checked=result.columns_checked,
        columns_shifted=result.columns_shifted,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def create_baseline_profile(
    records: list[dict[str, Any]],
    column: str,
    num_bins: int = 10,
) -> DistributionProfile:
    """Create a baseline distribution profile from data.

    Args:
        records: Records to build baseline from.
        column: Column to profile.
        num_bins: Number of bins for numeric columns.

    Returns:
        DistributionProfile for the column.
    """
    values = [r.get(column) for r in records]
    non_null_values = [v for v in values if v is not None]

    null_rate = (len(values) - len(non_null_values)) / len(values) if values else 0.0

    # Determine if numeric
    is_numeric = all(isinstance(v, (int, float)) for v in non_null_values[:100])

    if is_numeric and non_null_values:
        # Create numeric bins
        numeric_values = [float(v) for v in non_null_values]
        bins, frequencies = _create_numeric_bins(numeric_values, num_bins)

        return DistributionProfile(
            column=column,
            is_numeric=True,
            bins=bins,
            frequencies=frequencies,
            null_rate=null_rate,
            record_count=len(records),
        )
    else:
        # Create categorical frequencies
        categories, frequencies = _create_categorical_frequencies(non_null_values)

        return DistributionProfile(
            column=column,
            is_numeric=False,
            categories=categories,
            frequencies=frequencies,
            null_rate=null_rate,
            record_count=len(records),
        )


def save_baseline(baseline: dict[str, DistributionProfile], file_path: Path) -> None:
    """Save baseline profiles to file.

    Args:
        baseline: Baseline profiles by column.
        file_path: Path to save to.
    """
    data = {col: profile.to_dict() for col, profile in baseline.items()}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("baseline_saved", path=str(file_path), columns=len(baseline))


def load_baseline(file_path: Path) -> dict[str, DistributionProfile]:
    """Load baseline profiles from file.

    Args:
        file_path: Path to load from.

    Returns:
        Baseline profiles by column.
    """
    if not file_path.exists():
        logger.warning("baseline_file_not_found", path=str(file_path))
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    baseline = {col: DistributionProfile.from_dict(profile) for col, profile in data.items()}

    logger.info("baseline_loaded", path=str(file_path), columns=len(baseline))
    return baseline


def calculate_psi(expected: dict[str, float], actual: dict[str, float]) -> float:
    """Calculate Population Stability Index.

    PSI = sum((actual% - expected%) * ln(actual%/expected%))

    Args:
        expected: Expected (baseline) distribution.
        actual: Actual (current) distribution.

    Returns:
        PSI value.
    """
    return _calculate_psi(expected, actual)


def _calculate_psi(expected: dict[str, float], actual: dict[str, float]) -> float:
    """Calculate PSI between two distributions."""
    psi = 0.0

    # Get all keys
    all_keys = set(expected.keys()) | set(actual.keys())

    for key in all_keys:
        exp_pct = expected.get(key, EPSILON)
        act_pct = actual.get(key, EPSILON)

        # Ensure non-zero
        exp_pct = max(exp_pct, EPSILON)
        act_pct = max(act_pct, EPSILON)

        psi += (act_pct - exp_pct) * math.log(act_pct / exp_pct)

    return psi


def _calculate_distribution(
    records: list[dict[str, Any]],
    column: str,
    profile: DistributionProfile,
) -> dict[str, float]:
    """Calculate distribution for current data matching baseline profile."""
    values = [r.get(column) for r in records]
    non_null_values = [v for v in values if v is not None]

    if not non_null_values:
        return {}

    total = len(non_null_values)

    if profile.is_numeric:
        # Bin numeric values
        frequencies: dict[str, float] = {}
        for value in non_null_values:
            try:
                num_value = float(value)
                bin_key = _find_bin(num_value, profile.bins)
                frequencies[bin_key] = frequencies.get(bin_key, 0) + 1
            except (ValueError, TypeError):
                pass

        # Normalize
        return {k: v / total for k, v in frequencies.items()}
    else:
        # Count categories
        counter = Counter(str(v) for v in non_null_values)
        return {k: v / total for k, v in counter.items()}


def _calculate_null_rate(records: list[dict[str, Any]], column: str) -> float:
    """Calculate null rate for a column."""
    values = [r.get(column) for r in records]
    null_count = sum(1 for v in values if v is None)
    return null_count / len(values) if values else 0.0


def _create_numeric_bins(
    values: list[float], num_bins: int
) -> tuple[list[tuple[float, float]], dict[str, float]]:
    """Create equal-frequency bins for numeric values."""
    if not values:
        return [], {}

    sorted_values = sorted(values)
    n = len(sorted_values)
    bin_size = n // num_bins

    bins: list[tuple[float, float]] = []
    frequencies: dict[str, float] = {}

    for i in range(num_bins):
        start_idx = i * bin_size
        end_idx = (i + 1) * bin_size if i < num_bins - 1 else n

        bin_min = sorted_values[start_idx]
        bin_max = sorted_values[end_idx - 1]

        bins.append((bin_min, bin_max))
        bin_key = f"bin_{i}"
        frequencies[bin_key] = (end_idx - start_idx) / n

    return bins, frequencies


def _create_categorical_frequencies(
    values: list[Any],
) -> tuple[list[str], dict[str, float]]:
    """Create frequency distribution for categorical values."""
    counter = Counter(str(v) for v in values)
    total = len(values)

    categories = list(counter.keys())
    frequencies = {k: v / total for k, v in counter.items()}

    return categories, frequencies


def _find_bin(value: float, bins: list[tuple[float, float]]) -> str:
    """Find which bin a value belongs to."""
    for i, (bin_min, bin_max) in enumerate(bins):
        if bin_min <= value <= bin_max:
            return f"bin_{i}"

    # Value outside all bins - assign to nearest
    if bins:
        if value < bins[0][0]:
            return "bin_0"
        return f"bin_{len(bins) - 1}"

    return "bin_0"


def _create_anomaly(
    column: str,
    psi: float,
    severity: SeverityLevel,
    batch_id: str,
    baseline_profile: DistributionProfile,
    current_distribution: dict[str, float],
) -> BusinessLogicAnomaly:
    """Create a distribution shift anomaly."""
    severity_score = min(100, int(psi * 200))  # Scale PSI to 0-100

    return BusinessLogicAnomaly(
        id=f"BL-{uuid4().hex[:8]}",
        failure_code=FailureCode.DISTRIBUTION_SHIFT,
        severity=severity,
        severity_score=severity_score,
        rule_id=f"distrib-{column}",
        rule_name=f"Distribution check: {column}",
        affected_records=[],  # Distribution shift is aggregate
        affected_fields=[column],
        batch_id=batch_id,
        explanation=f"Distribution shift detected in {column}: PSI={psi:.3f}",
        expected_value=f"Baseline: {_format_dist(baseline_profile.frequencies)}",
        actual_value=f"Current: {_format_dist(current_distribution)}",
        details={
            "psi": psi,
            "psi_threshold_warning": PSI_WARNING_THRESHOLD,
            "psi_threshold_critical": PSI_CRITICAL_THRESHOLD,
            "baseline_record_count": baseline_profile.record_count,
            "baseline_created": baseline_profile.created_at.isoformat(),
        },
    )


def _format_dist(dist: dict[str, float]) -> str:
    """Format distribution for display (top 5 entries)."""
    sorted_items = sorted(dist.items(), key=lambda x: x[1], reverse=True)[:5]
    return ", ".join(f"{k}={v:.2%}" for k, v in sorted_items)
