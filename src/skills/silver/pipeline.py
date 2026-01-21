"""Silver Tier pipeline skill for FR-004, FR-006, FR-008 detection.

This skill monitors pipeline execution:
- FR-004: Pipeline delay (processing exceeds expected window)
- FR-006: Job failure (scheduled pipeline execution failed)
- FR-008: Latency spike (end-to-end time significantly above baseline)
"""

import time
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.sla_definition import (
    PipelineExecution,
    PipelineStage,
    SLADefinition,
)
from src.models.silver_anomaly import FreshnessAnomaly

logger = structlog.get_logger(__name__)


class PipelineCheckResult:
    """Result of pipeline monitoring check."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[FreshnessAnomaly] = []
        self.pipelines_checked: int = 0
        self.pipelines_delayed: int = 0
        self.pipelines_failed: int = 0
        self.latency_spikes: int = 0
        self.duration_ms: float = 0.0


def monitor_pipeline_duration(
    execution: PipelineExecution,
    latency_threshold_seconds: int | None = None,
) -> PipelineCheckResult:
    """Monitor a pipeline execution for delays and issues.

    Args:
        execution: Pipeline execution to monitor.
        latency_threshold_seconds: Max allowed duration (default from execution).

    Returns:
        PipelineCheckResult with any anomalies.
    """
    start_time = time.perf_counter()
    result = PipelineCheckResult()
    result.pipelines_checked = 1

    threshold = latency_threshold_seconds or execution.latency_threshold_seconds
    now = datetime.utcnow()

    # Calculate current duration
    if execution.completed_at:
        duration_seconds = execution.total_duration_seconds
    else:
        duration_seconds = int((now - execution.started_at).total_seconds())

    # Check for latency spike (FR-008)
    if duration_seconds > threshold:
        result.latency_spikes += 1
        overage_seconds = duration_seconds - threshold

        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.LATENCY_SPIKE,
                severity=SeverityLevel.WARNING if overage_seconds < threshold else SeverityLevel.CRITICAL,
                source=execution.source,
                sla_id=execution.pipeline_id,
                expected_at=execution.started_at + timedelta(seconds=threshold),
                last_arrival=execution.completed_at,
                delay_seconds=overage_seconds,
                explanation=f"Latency spike: pipeline took {duration_seconds}s (threshold: {threshold}s, overage: {overage_seconds}s)",
                pipeline_stage=None,
                details={
                    "pipeline_id": execution.pipeline_id,
                    "pipeline_name": execution.pipeline_name,
                    "duration_seconds": duration_seconds,
                    "threshold_seconds": threshold,
                    "status": execution.status,
                },
            )
        )

    # Check for pipeline delay / stall (FR-004)
    stalled_stage = execution.get_stalled_stage()
    if stalled_stage:
        result.pipelines_delayed += 1
        result.anomalies.append(
            FreshnessAnomaly(
                id=f"FR-{uuid4().hex[:8]}",
                failure_code=FailureCode.PIPELINE_DELAY,
                severity=SeverityLevel.WARNING,
                source=execution.source,
                sla_id=execution.pipeline_id,
                expected_at=now,
                last_arrival=None,
                delay_seconds=0,
                explanation=f"Pipeline stall detected: stage '{stalled_stage.stage_name}' has not started after previous stage completed",
                pipeline_stage=stalled_stage.stage_name,
                details={
                    "pipeline_id": execution.pipeline_id,
                    "stalled_stage_id": stalled_stage.stage_id,
                    "stalled_stage_name": stalled_stage.stage_name,
                },
            )
        )

    # Check for job failures (FR-006)
    for stage in execution.stages:
        if stage.status == "FAILED":
            result.pipelines_failed += 1
            result.anomalies.append(
                FreshnessAnomaly(
                    id=f"FR-{uuid4().hex[:8]}",
                    failure_code=FailureCode.JOB_FAILURE,
                    severity=SeverityLevel.CRITICAL,
                    source=execution.source,
                    sla_id=execution.pipeline_id,
                    expected_at=stage.started_at or now,
                    last_arrival=stage.completed_at,
                    delay_seconds=stage.duration_seconds,
                    explanation=f"Pipeline job failed: stage '{stage.stage_name}' - {stage.error_message or 'Unknown error'}",
                    pipeline_stage=stage.stage_name,
                    details={
                        "pipeline_id": execution.pipeline_id,
                        "stage_id": stage.stage_id,
                        "stage_name": stage.stage_name,
                        "error_message": stage.error_message,
                        "duration_seconds": stage.duration_seconds,
                    },
                )
            )

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.debug(
        "pipeline_check_complete",
        pipeline_id=execution.pipeline_id,
        duration_seconds=duration_seconds,
        anomalies=len(result.anomalies),
    )

    return result


def check_pipeline_batch(
    executions: dict[str, PipelineExecution],
) -> PipelineCheckResult:
    """Check multiple pipeline executions.

    Args:
        executions: Pipeline executions by ID.

    Returns:
        PipelineCheckResult with all anomalies.
    """
    start_time = time.perf_counter()
    result = PipelineCheckResult()

    for pipeline_id, execution in executions.items():
        single_result = monitor_pipeline_duration(execution)

        result.pipelines_checked += single_result.pipelines_checked
        result.pipelines_delayed += single_result.pipelines_delayed
        result.pipelines_failed += single_result.pipelines_failed
        result.latency_spikes += single_result.latency_spikes
        result.anomalies.extend(single_result.anomalies)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "pipeline_batch_check_complete",
        pipelines_checked=result.pipelines_checked,
        pipelines_delayed=result.pipelines_delayed,
        pipelines_failed=result.pipelines_failed,
        latency_spikes=result.latency_spikes,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def create_pipeline_execution(
    pipeline_id: str,
    source: str,
    pipeline_name: str = "",
    stages: list[str] | None = None,
    latency_threshold_seconds: int = 1800,
) -> PipelineExecution:
    """Create a new pipeline execution tracker.

    Args:
        pipeline_id: Unique pipeline identifier.
        source: Data source being processed.
        pipeline_name: Human-readable name.
        stages: List of stage names in order.
        latency_threshold_seconds: Max allowed duration.

    Returns:
        PipelineExecution ready to track stages.
    """
    execution = PipelineExecution(
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name or pipeline_id,
        source=source,
        latency_threshold_seconds=latency_threshold_seconds,
    )

    # Initialize stages if provided
    if stages:
        for i, stage_name in enumerate(stages):
            execution.stages.append(
                PipelineStage(
                    stage_id=f"{pipeline_id}-stage-{i+1}",
                    stage_name=stage_name,
                    pipeline_id=pipeline_id,
                    sequence=i + 1,
                )
            )

    return execution


def start_stage(execution: PipelineExecution, stage_id: str) -> PipelineStage | None:
    """Start a pipeline stage.

    Args:
        execution: Pipeline execution.
        stage_id: Stage to start.

    Returns:
        Started stage or None if not found.
    """
    for stage in execution.stages:
        if stage.stage_id == stage_id:
            stage.start()
            logger.debug(
                "pipeline_stage_started",
                pipeline_id=execution.pipeline_id,
                stage_id=stage_id,
            )
            return stage
    return None


def complete_stage(
    execution: PipelineExecution,
    stage_id: str,
    output_count: int = 0,
) -> PipelineStage | None:
    """Complete a pipeline stage.

    Args:
        execution: Pipeline execution.
        stage_id: Stage to complete.
        output_count: Records produced.

    Returns:
        Completed stage or None if not found.
    """
    for stage in execution.stages:
        if stage.stage_id == stage_id:
            stage.complete(output_count)
            logger.debug(
                "pipeline_stage_completed",
                pipeline_id=execution.pipeline_id,
                stage_id=stage_id,
                duration_seconds=stage.duration_seconds,
            )
            return stage
    return None


def fail_stage(
    execution: PipelineExecution,
    stage_id: str,
    error: str,
) -> PipelineStage | None:
    """Mark a pipeline stage as failed.

    Args:
        execution: Pipeline execution.
        stage_id: Stage that failed.
        error: Error message.

    Returns:
        Failed stage or None if not found.
    """
    for stage in execution.stages:
        if stage.stage_id == stage_id:
            stage.fail(error)
            execution.status = "FAILED"
            logger.warning(
                "pipeline_stage_failed",
                pipeline_id=execution.pipeline_id,
                stage_id=stage_id,
                error=error,
            )
            return stage
    return None


def complete_pipeline(execution: PipelineExecution) -> None:
    """Mark pipeline as complete.

    Args:
        execution: Pipeline execution to complete.
    """
    execution.completed_at = datetime.utcnow()
    execution.status = "COMPLETED"
    execution.total_duration_seconds = int(
        (execution.completed_at - execution.started_at).total_seconds()
    )

    logger.info(
        "pipeline_completed",
        pipeline_id=execution.pipeline_id,
        duration_seconds=execution.total_duration_seconds,
        stages_completed=len([s for s in execution.stages if s.is_complete]),
    )


def calculate_pipeline_score(executions: dict[str, PipelineExecution]) -> float:
    """Calculate overall pipeline health score.

    Args:
        executions: Active pipeline executions.

    Returns:
        Health score 0-100.
    """
    if not executions:
        return 100.0

    total_score = 0.0
    execution_count = 0

    for pipeline_id, execution in executions.items():
        execution_count += 1

        # Check for failures
        has_failure = any(s.status == "FAILED" for s in execution.stages)
        if has_failure:
            total_score += 0
            continue

        # Check for latency issues
        if execution.is_over_threshold:
            overage_ratio = (
                execution.total_duration_seconds - execution.latency_threshold_seconds
            ) / execution.latency_threshold_seconds

            if overage_ratio > 1:
                total_score += 0  # More than 2x threshold
            else:
                total_score += 50 * (1 - overage_ratio)  # Partial score
        else:
            total_score += 100

    if execution_count == 0:
        return 100.0

    return max(0.0, min(100.0, total_score / execution_count))
