"""Silver Tier dependency skill for FR-007 detection.

This skill tracks dependency chains:
- FR-007: Dependency delay (upstream dependency late, blocking downstream)
"""

import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.sla_definition import (
    DependencyChain,
    DependencyStatus,
)
from src.models.silver_anomaly import FreshnessAnomaly

logger = structlog.get_logger(__name__)


class DependencyCheckResult:
    """Result of dependency chain check."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[FreshnessAnomaly] = []
        self.chains_checked: int = 0
        self.dependencies_checked: int = 0
        self.dependencies_delayed: int = 0
        self.blocking_delays: int = 0
        self.duration_ms: float = 0.0


def track_dependency_chain(
    chain: DependencyChain,
) -> DependencyCheckResult:
    """Track dependency chain status.

    Args:
        chain: Dependency chain to check.

    Returns:
        DependencyCheckResult with any anomalies.
    """
    start_time = time.perf_counter()
    result = DependencyCheckResult()
    result.chains_checked = 1

    # Check chain status
    chain.check()

    for dep in chain.dependencies:
        result.dependencies_checked += 1

        if dep.is_late:
            result.dependencies_delayed += 1

            severity = SeverityLevel.CRITICAL if dep.blocking else SeverityLevel.WARNING
            if dep.blocking:
                result.blocking_delays += 1

            result.anomalies.append(
                FreshnessAnomaly(
                    id=f"FR-{uuid4().hex[:8]}",
                    failure_code=FailureCode.DEPENDENCY_DELAY,
                    severity=severity,
                    source=chain.source,
                    sla_id=dep.dependency_id,
                    expected_at=datetime.utcnow(),
                    last_arrival=dep.last_completion,
                    delay_seconds=dep.delay_seconds,
                    explanation=f"Upstream dependency '{dep.dependency_name}' is delayed by {dep.delay_seconds // 60} minutes{' (blocking downstream)' if dep.blocking else ''}",
                    details={
                        "dependency_id": dep.dependency_id,
                        "dependency_name": dep.dependency_name,
                        "upstream_source": dep.source,
                        "blocking": dep.blocking,
                        "delay_minutes": dep.delay_seconds / 60,
                        "status": dep.status,
                    },
                )
            )

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "dependency_check_complete",
        source=chain.source,
        dependencies_checked=result.dependencies_checked,
        dependencies_delayed=result.dependencies_delayed,
        anomalies=len(result.anomalies),
    )

    return result


def check_dependency_batch(
    chains: dict[str, DependencyChain],
) -> DependencyCheckResult:
    """Check multiple dependency chains.

    Args:
        chains: Dependency chains by source.

    Returns:
        DependencyCheckResult with all anomalies.
    """
    start_time = time.perf_counter()
    result = DependencyCheckResult()

    for source, chain in chains.items():
        single_result = track_dependency_chain(chain)

        result.chains_checked += single_result.chains_checked
        result.dependencies_checked += single_result.dependencies_checked
        result.dependencies_delayed += single_result.dependencies_delayed
        result.blocking_delays += single_result.blocking_delays
        result.anomalies.extend(single_result.anomalies)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "dependency_batch_check_complete",
        chains_checked=result.chains_checked,
        dependencies_checked=result.dependencies_checked,
        dependencies_delayed=result.dependencies_delayed,
        blocking_delays=result.blocking_delays,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def create_dependency_chain(
    source: str,
    dependencies: list[dict[str, Any]] | None = None,
) -> DependencyChain:
    """Create a new dependency chain.

    Args:
        source: Data source with dependencies.
        dependencies: List of dependency configs.

    Returns:
        DependencyChain ready to track.
    """
    chain = DependencyChain(source=source)

    if dependencies:
        for dep_config in dependencies:
            chain.dependencies.append(
                DependencyStatus(
                    dependency_id=dep_config.get("id", f"dep-{len(chain.dependencies)}"),
                    dependency_name=dep_config.get("name", ""),
                    source=dep_config.get("source", ""),
                    blocking=dep_config.get("blocking", True),
                )
            )

    return chain


def add_dependency(
    chain: DependencyChain,
    dependency_id: str,
    dependency_name: str,
    upstream_source: str,
    blocking: bool = True,
) -> DependencyStatus:
    """Add a dependency to a chain.

    Args:
        chain: Chain to add dependency to.
        dependency_id: Unique dependency identifier.
        dependency_name: Human-readable name.
        upstream_source: Upstream data source.
        blocking: Whether this blocks downstream.

    Returns:
        Created DependencyStatus.
    """
    status = DependencyStatus(
        dependency_id=dependency_id,
        dependency_name=dependency_name,
        source=upstream_source,
        blocking=blocking,
    )
    chain.dependencies.append(status)

    logger.debug(
        "dependency_added",
        source=chain.source,
        dependency_id=dependency_id,
        upstream_source=upstream_source,
        blocking=blocking,
    )

    return status


def update_dependency_status(
    chain: DependencyChain,
    dependency_id: str,
    status: str,
    last_completion: datetime | None = None,
    delay_seconds: int = 0,
) -> DependencyStatus | None:
    """Update a dependency's status.

    Args:
        chain: Chain containing the dependency.
        dependency_id: Dependency to update.
        status: New status ("OK", "DELAYED", "FAILED", etc).
        last_completion: When dependency last completed.
        delay_seconds: Current delay in seconds.

    Returns:
        Updated DependencyStatus or None if not found.
    """
    for dep in chain.dependencies:
        if dep.dependency_id == dependency_id:
            dep.status = status
            dep.last_completion = last_completion
            dep.delay_seconds = delay_seconds

            logger.debug(
                "dependency_status_updated",
                source=chain.source,
                dependency_id=dependency_id,
                status=status,
                delay_seconds=delay_seconds,
            )

            return dep

    return None


def mark_dependency_complete(
    chain: DependencyChain,
    dependency_id: str,
    completion_time: datetime | None = None,
) -> DependencyStatus | None:
    """Mark a dependency as completed on time.

    Args:
        chain: Chain containing the dependency.
        dependency_id: Dependency that completed.
        completion_time: When it completed (default: now).

    Returns:
        Updated DependencyStatus or None if not found.
    """
    return update_dependency_status(
        chain=chain,
        dependency_id=dependency_id,
        status="OK",
        last_completion=completion_time or datetime.utcnow(),
        delay_seconds=0,
    )


def mark_dependency_delayed(
    chain: DependencyChain,
    dependency_id: str,
    delay_seconds: int,
    last_completion: datetime | None = None,
) -> DependencyStatus | None:
    """Mark a dependency as delayed.

    Args:
        chain: Chain containing the dependency.
        dependency_id: Dependency that is delayed.
        delay_seconds: How late it is.
        last_completion: Last known completion time.

    Returns:
        Updated DependencyStatus or None if not found.
    """
    return update_dependency_status(
        chain=chain,
        dependency_id=dependency_id,
        status="DELAYED",
        last_completion=last_completion,
        delay_seconds=delay_seconds,
    )


def get_blocking_dependencies(chain: DependencyChain) -> list[DependencyStatus]:
    """Get list of dependencies that are blocking downstream.

    Args:
        chain: Chain to check.

    Returns:
        List of blocking delayed dependencies.
    """
    return [d for d in chain.dependencies if d.blocking and d.is_late]


def can_proceed(chain: DependencyChain) -> bool:
    """Check if downstream can proceed (no blocking delays).

    Args:
        chain: Chain to check.

    Returns:
        True if all blocking dependencies are satisfied.
    """
    chain.check()
    return chain.all_satisfied


def calculate_dependency_score(chains: dict[str, DependencyChain]) -> float:
    """Calculate overall dependency health score.

    Args:
        chains: Dependency chains by source.

    Returns:
        Health score 0-100.
    """
    if not chains:
        return 100.0

    total_score = 0.0
    chain_count = 0

    for source, chain in chains.items():
        chain_count += 1
        chain.check()

        if not chain.dependencies:
            total_score += 100
            continue

        # Calculate score based on dependency health
        satisfied_count = sum(
            1 for d in chain.dependencies if d.status == "OK" or not d.is_late
        )
        total_deps = len(chain.dependencies)

        chain_score = (satisfied_count / total_deps) * 100

        # Penalize blocking delays more heavily
        blocking_delays = len(get_blocking_dependencies(chain))
        if blocking_delays > 0:
            chain_score *= 0.5  # 50% penalty for any blocking delay

        total_score += chain_score

    if chain_count == 0:
        return 100.0

    return max(0.0, min(100.0, total_score / chain_count))
