"""Silver Tier freshness skill for FR-001 detection.

This skill checks data staleness:
- FR-001: Data is stale (exceeds freshness threshold)
- Warning at configurable threshold (default 60 minutes)
- Critical at configurable threshold (default 90 minutes)
"""

import time
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.sla_definition import (
    FreshnessState,
    FreshnessStatus,
    FreshnessThreshold,
    SLADefinition,
)
from src.models.silver_anomaly import FreshnessAnomaly

logger = structlog.get_logger(__name__)


class FreshnessCheckResult:
    """Result of freshness check."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[FreshnessAnomaly] = []
        self.sources_checked: int = 0
        self.sources_stale: int = 0
        self.duration_ms: float = 0.0


def check_freshness(
    source: str,
    last_arrival: datetime | None,
    threshold: FreshnessThreshold | None = None,
    sla: SLADefinition | None = None,
) -> FreshnessCheckResult:
    """Check data freshness for a source.

    Args:
        source: Data source name.
        last_arrival: When data last arrived.
        threshold: Freshness thresholds (default: 60/90 minutes).
        sla: Full SLA definition (used if threshold not provided).

    Returns:
        FreshnessCheckResult with any anomalies.
    """
    start_time = time.perf_counter()
    result = FreshnessCheckResult()
    result.sources_checked = 1

    # Use threshold from SLA if not provided
    if threshold is None:
        if sla:
            threshold = sla.freshness_threshold
        else:
            threshold = FreshnessThreshold()  # Default 60/90

    # Calculate age
    now = datetime.utcnow()
    if last_arrival is None:
        age_minutes = float("inf")
        age_seconds = 0
    else:
        age_seconds = int((now - last_arrival).total_seconds())
        age_minutes = age_seconds / 60.0

    # Determine status
    status = threshold.get_status(age_minutes)

    if status == FreshnessStatus.CRITICAL:
        result.sources_stale += 1
        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.DATA_STALE,
                severity=SeverityLevel.CRITICAL,
                source=source,
                sla_id=sla.id if sla else "",
                expected_at=now,
                last_arrival=last_arrival,
                delay_seconds=age_seconds,
                explanation=f"Data is critically stale: {age_minutes:.1f} minutes since last arrival (critical threshold: {threshold.critical_minutes} min)",
                details={
                    "age_minutes": age_minutes,
                    "warning_threshold_minutes": threshold.warning_minutes,
                    "critical_threshold_minutes": threshold.critical_minutes,
                },
            )
        )
    elif status == FreshnessStatus.WARNING:
        result.sources_stale += 1
        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.DATA_STALE,
                severity=SeverityLevel.WARNING,
                source=source,
                sla_id=sla.id if sla else "",
                expected_at=now,
                last_arrival=last_arrival,
                delay_seconds=age_seconds,
                explanation=f"Data freshness warning: {age_minutes:.1f} minutes since last arrival (warning threshold: {threshold.warning_minutes} min)",
                details={
                    "age_minutes": age_minutes,
                    "warning_threshold_minutes": threshold.warning_minutes,
                    "critical_threshold_minutes": threshold.critical_minutes,
                },
            )
        )

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "freshness_check_complete",
        source=source,
        status=status.value,
        age_minutes=age_minutes,
        anomalies=len(result.anomalies),
    )

    return result


def check_freshness_batch(
    states: dict[str, FreshnessState],
    slas: dict[str, SLADefinition],
) -> FreshnessCheckResult:
    """Check freshness for multiple sources.

    Args:
        states: Current freshness states by source.
        slas: SLA definitions by source.

    Returns:
        FreshnessCheckResult with all anomalies.
    """
    start_time = time.perf_counter()
    result = FreshnessCheckResult()

    for source, state in states.items():
        sla = slas.get(source)
        threshold = sla.freshness_threshold if sla else FreshnessThreshold()

        single_result = check_freshness(
            source=source,
            last_arrival=state.last_arrival,
            threshold=threshold,
            sla=sla,
        )

        result.sources_checked += single_result.sources_checked
        result.sources_stale += single_result.sources_stale
        result.anomalies.extend(single_result.anomalies)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "freshness_batch_check_complete",
        sources_checked=result.sources_checked,
        sources_stale=result.sources_stale,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def calculate_freshness_score(
    states: dict[str, FreshnessState],
    slas: dict[str, SLADefinition],
) -> float:
    """Calculate overall freshness health score.

    Args:
        states: Current freshness states.
        slas: SLA definitions.

    Returns:
        Health score 0-100.
    """
    if not states:
        return 100.0

    total_score = 0.0
    source_count = 0

    for source, state in states.items():
        sla = slas.get(source)
        if sla is None:
            continue

        source_count += 1
        threshold = sla.freshness_threshold

        # Calculate age
        if state.last_arrival is None:
            age_minutes = float("inf")
        else:
            age_minutes = state.age_minutes

        # Score based on status
        if age_minutes >= threshold.critical_minutes:
            total_score += 0  # Critical = 0 points
        elif age_minutes >= threshold.warning_minutes:
            total_score += 50  # Warning = 50 points
        else:
            # Scale from 100 (fresh) to 50 (approaching warning)
            freshness_ratio = age_minutes / threshold.warning_minutes
            total_score += 100 - (freshness_ratio * 50)

    if source_count == 0:
        return 100.0

    return max(0.0, min(100.0, total_score / source_count))
