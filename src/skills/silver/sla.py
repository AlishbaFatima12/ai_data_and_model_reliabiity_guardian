"""Silver Tier sla skill for FR-002, FR-003, FR-005 detection.

This skill tracks SLA compliance:
- FR-002: SLA breach (deadline missed)
- FR-003: SLA warning (at risk of breach)
- FR-005: Missing delivery (expected data not arrived)
"""

import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.sla_definition import (
    SLADefinition,
    SLAStatus,
    FreshnessState,
)
from src.models.silver_anomaly import FreshnessAnomaly

logger = structlog.get_logger(__name__)


class SLACheckResult:
    """Result of SLA compliance check."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[FreshnessAnomaly] = []
        self.slas_checked: int = 0
        self.slas_breached: int = 0
        self.slas_at_risk: int = 0
        self.duration_ms: float = 0.0


def track_sla_compliance(
    source: str,
    sla: SLADefinition,
    last_arrival: datetime | None,
    expected_at: datetime | None = None,
) -> SLACheckResult:
    """Track SLA compliance for a data source.

    Args:
        source: Data source name.
        sla: SLA definition.
        last_arrival: When data last arrived.
        expected_at: When data was expected (calculated from schedule if None).

    Returns:
        SLACheckResult with any anomalies.
    """
    start_time = time.perf_counter()
    result = SLACheckResult()
    result.slas_checked = 1

    now = datetime.utcnow()

    # Calculate expected arrival if not provided
    if expected_at is None:
        expected_at = sla.get_previous_expected(before=now)

    # Calculate delay
    if last_arrival is None:
        # No arrival yet - check if we're past expected time
        if now > expected_at:
            delay_seconds = int((now - expected_at).total_seconds())
            delay_minutes = delay_seconds / 60.0
        else:
            delay_seconds = 0
            delay_minutes = 0.0
    else:
        # Data arrived - check if it was on time
        if last_arrival > expected_at:
            delay_seconds = int((last_arrival - expected_at).total_seconds())
            delay_minutes = delay_seconds / 60.0
        else:
            delay_seconds = 0
            delay_minutes = 0.0

    # Determine SLA status
    status = _determine_sla_status(delay_minutes, sla)

    if status == SLAStatus.BREACHED:
        result.slas_breached += 1
        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.SLA_BREACH,
                severity=SeverityLevel.CRITICAL,
                source=source,
                sla_id=sla.id,
                expected_at=expected_at,
                last_arrival=last_arrival,
                delay_seconds=delay_seconds,
                explanation=f"SLA breach: data was expected at {expected_at.isoformat()} but arrived {delay_minutes:.1f} minutes late",
                details={
                    "sla_name": sla.name,
                    "sla_owner": sla.owner,
                    "delay_minutes": delay_minutes,
                    "schedule": sla.schedule,
                },
            )
        )
    elif status == SLAStatus.AT_RISK:
        result.slas_at_risk += 1
        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.SLA_WARNING,
                severity=SeverityLevel.WARNING,
                source=source,
                sla_id=sla.id,
                expected_at=expected_at,
                last_arrival=last_arrival,
                delay_seconds=delay_seconds,
                explanation=f"SLA at risk: data is {delay_minutes:.1f} minutes late (expected at {expected_at.isoformat()})",
                details={
                    "sla_name": sla.name,
                    "sla_owner": sla.owner,
                    "delay_minutes": delay_minutes,
                    "schedule": sla.schedule,
                },
            )
        )

    # Check for missing delivery
    if last_arrival is None and now > expected_at + timedelta(minutes=30):
        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.MISSING_DELIVERY,
                severity=SeverityLevel.CRITICAL,
                source=source,
                sla_id=sla.id,
                expected_at=expected_at,
                last_arrival=None,
                delay_seconds=delay_seconds,
                explanation=f"Missing delivery: data expected at {expected_at.isoformat()} has not arrived",
                details={
                    "sla_name": sla.name,
                    "sla_owner": sla.owner,
                    "time_since_expected_minutes": delay_minutes,
                },
            )
        )

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "sla_check_complete",
        source=source,
        status=status.value,
        delay_minutes=delay_minutes,
        anomalies=len(result.anomalies),
    )

    return result


def check_sla_batch(
    states: dict[str, FreshnessState],
    slas: dict[str, SLADefinition],
) -> SLACheckResult:
    """Check SLA compliance for multiple sources.

    Args:
        states: Current freshness states by source.
        slas: SLA definitions by source.

    Returns:
        SLACheckResult with all anomalies.
    """
    start_time = time.perf_counter()
    result = SLACheckResult()

    for source, sla in slas.items():
        if not sla.enabled:
            continue

        state = states.get(source)
        last_arrival = state.last_arrival if state else None
        expected_at = state.expected_at if state else None

        single_result = track_sla_compliance(
            source=source,
            sla=sla,
            last_arrival=last_arrival,
            expected_at=expected_at,
        )

        result.slas_checked += single_result.slas_checked
        result.slas_breached += single_result.slas_breached
        result.slas_at_risk += single_result.slas_at_risk
        result.anomalies.extend(single_result.anomalies)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "sla_batch_check_complete",
        slas_checked=result.slas_checked,
        slas_breached=result.slas_breached,
        slas_at_risk=result.slas_at_risk,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def get_next_expected_arrival(sla: SLADefinition) -> datetime:
    """Get next expected arrival time for an SLA.

    Args:
        sla: SLA definition.

    Returns:
        Next expected arrival datetime.
    """
    return sla.get_next_expected()


def calculate_sla_score(
    states: dict[str, FreshnessState],
    slas: dict[str, SLADefinition],
) -> float:
    """Calculate overall SLA compliance score.

    Args:
        states: Current freshness states.
        slas: SLA definitions.

    Returns:
        Compliance score 0-100.
    """
    if not slas:
        return 100.0

    total_score = 0.0
    sla_count = 0

    now = datetime.utcnow()

    for source, sla in slas.items():
        if not sla.enabled:
            continue

        sla_count += 1
        state = states.get(source)

        if state is None or state.last_arrival is None:
            # No data - check if we're past expected time
            expected_at = sla.get_previous_expected()
            if now > expected_at:
                total_score += 0  # Missing = 0 points
            else:
                total_score += 100  # Not yet due = 100 points
            continue

        # Calculate delay
        expected_at = sla.get_previous_expected()
        if state.last_arrival > expected_at:
            delay_minutes = (state.last_arrival - expected_at).total_seconds() / 60.0
        else:
            delay_minutes = 0.0

        # Score based on delay
        status = _determine_sla_status(delay_minutes, sla)
        if status == SLAStatus.BREACHED:
            total_score += 0
        elif status == SLAStatus.AT_RISK:
            total_score += 50
        else:
            total_score += 100

    if sla_count == 0:
        return 100.0

    return max(0.0, min(100.0, total_score / sla_count))


def _determine_sla_status(delay_minutes: float, sla: SLADefinition) -> SLAStatus:
    """Determine SLA status based on delay.

    Args:
        delay_minutes: How late the data is.
        sla: SLA definition.

    Returns:
        SLA status.
    """
    # Use freshness thresholds as SLA thresholds
    warning_threshold = sla.freshness_threshold.warning_minutes / 2  # Half of freshness warning
    breach_threshold = sla.freshness_threshold.warning_minutes  # Full freshness warning = breach

    if delay_minutes >= breach_threshold:
        return SLAStatus.BREACHED
    elif delay_minutes >= warning_threshold:
        return SLAStatus.AT_RISK
    return SLAStatus.ON_TRACK
