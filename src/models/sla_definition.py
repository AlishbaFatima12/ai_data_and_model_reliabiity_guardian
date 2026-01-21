"""SLA Definition and Freshness State Models for Silver Tier Layer 4.

This module defines models for freshness and SLA monitoring:
- SLADefinition: Expected arrival times and thresholds for a data source
- FreshnessState: Current freshness state for a data source
- PipelineStage: Tracks individual pipeline stage execution
- DependencyChain: Tracks upstream dependencies
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel


class FreshnessStatus(str, Enum):
    """Freshness status for a data source."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class SLAStatus(str, Enum):
    """SLA compliance status."""

    ON_TRACK = "ON_TRACK"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FreshnessThreshold(BaseModel):
    """Freshness threshold configuration.

    Attributes:
        warning_minutes: Minutes until WARNING status
        critical_minutes: Minutes until CRITICAL status
    """

    warning_minutes: int = Field(default=60, ge=1, description="Minutes until WARNING")
    critical_minutes: int = Field(default=90, ge=1, description="Minutes until CRITICAL")

    def get_status(self, age_minutes: float) -> FreshnessStatus:
        """Determine status based on age.

        Args:
            age_minutes: Age of data in minutes.

        Returns:
            FreshnessStatus based on thresholds.
        """
        if age_minutes >= self.critical_minutes:
            return FreshnessStatus.CRITICAL
        elif age_minutes >= self.warning_minutes:
            return FreshnessStatus.WARNING
        return FreshnessStatus.OK


class SLADefinition(BaseModel):
    """Represents expected arrival times and thresholds for a data source.

    Attributes:
        id: Unique SLA identifier
        source: Data source name
        name: Human-readable SLA name
        description: SLA description
        schedule: Cron expression for expected arrivals (e.g., "0 * * * *" for hourly)
        freshness_threshold: Freshness thresholds for warning/critical
        latency_threshold_seconds: Max allowed end-to-end latency
        expected_record_count: Optional expected record count per batch
        owner: Team/person responsible
        enabled: Whether SLA monitoring is active
        created_at: When SLA was defined
        updated_at: Last modification time
    """

    id: str = Field(..., description="Unique SLA identifier")
    source: str = Field(..., description="Data source name")
    name: str = Field(default="", description="Human-readable SLA name")
    description: str = Field(default="", description="SLA description")
    schedule: str = Field(default="0 * * * *", description="Cron expression for expected arrivals")
    freshness_threshold: FreshnessThreshold = Field(
        default_factory=FreshnessThreshold, description="Freshness thresholds"
    )
    latency_threshold_seconds: int = Field(
        default=1800, ge=1, description="Max end-to-end latency (default 30 min)"
    )
    expected_record_count: int | None = Field(
        None, ge=0, description="Expected records per batch"
    )
    owner: str = Field(default="", description="Responsible team/person")
    enabled: bool = Field(default=True, description="Whether monitoring is active")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last modification"
    )

    def get_next_expected(self, after: datetime | None = None) -> datetime:
        """Calculate next expected arrival time based on schedule.

        Args:
            after: Calculate next occurrence after this time (default: now).

        Returns:
            Next expected arrival datetime.
        """
        try:
            from croniter import croniter
            base = after or datetime.utcnow()
            cron = croniter(self.schedule, base)
            return cron.get_next(datetime)
        except Exception:
            # Fallback to 1 hour from now if croniter fails
            return (after or datetime.utcnow()) + timedelta(hours=1)

    def get_previous_expected(self, before: datetime | None = None) -> datetime:
        """Calculate previous expected arrival time based on schedule.

        Args:
            before: Calculate previous occurrence before this time (default: now).

        Returns:
            Previous expected arrival datetime.
        """
        try:
            from croniter import croniter
            base = before or datetime.utcnow()
            cron = croniter(self.schedule, base)
            return cron.get_prev(datetime)
        except Exception:
            # Fallback to 1 hour ago if croniter fails
            return (before or datetime.utcnow()) - timedelta(hours=1)


class FreshnessState(BaseModel):
    """Current freshness state for a data source.

    Attributes:
        source: Data source name
        sla_id: Associated SLA definition ID
        last_arrival: When data last arrived
        last_check: When freshness was last checked
        age_seconds: Current age of data in seconds
        status: Current freshness status
        expected_at: When next data was expected
        delay_seconds: How late data is (if delayed)
        record_count: Records in last batch
        consecutive_misses: Number of consecutive missed deliveries
        metadata: Additional state information
    """

    source: str = Field(..., description="Data source name")
    sla_id: str = Field(default="", description="Associated SLA ID")
    last_arrival: datetime | None = Field(None, description="Last data arrival")
    last_check: datetime = Field(
        default_factory=datetime.utcnow, description="Last freshness check"
    )
    age_seconds: int = Field(default=0, ge=0, description="Current data age")
    status: FreshnessStatus = Field(
        default=FreshnessStatus.UNKNOWN, description="Current status"
    )
    expected_at: datetime | None = Field(None, description="Next expected arrival")
    delay_seconds: int = Field(default=0, ge=0, description="Current delay")
    record_count: int = Field(default=0, ge=0, description="Records in last batch")
    consecutive_misses: int = Field(default=0, ge=0, description="Consecutive missed deliveries")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional info")

    @property
    def age_minutes(self) -> float:
        """Return age in minutes."""
        return self.age_seconds / 60.0

    @property
    def delay_minutes(self) -> float:
        """Return delay in minutes."""
        return self.delay_seconds / 60.0

    @property
    def is_stale(self) -> bool:
        """Return True if data is stale (WARNING or CRITICAL)."""
        return self.status in (FreshnessStatus.WARNING, FreshnessStatus.CRITICAL)

    def update(self, arrival_time: datetime, record_count: int = 0) -> None:
        """Update state with new data arrival.

        Args:
            arrival_time: When data arrived.
            record_count: Number of records in batch.
        """
        self.last_arrival = arrival_time
        self.last_check = datetime.utcnow()
        self.age_seconds = 0
        self.delay_seconds = 0
        self.status = FreshnessStatus.OK
        self.record_count = record_count
        self.consecutive_misses = 0

    def refresh(self, threshold: FreshnessThreshold) -> None:
        """Refresh state based on current time and thresholds.

        Args:
            threshold: Freshness thresholds to apply.
        """
        self.last_check = datetime.utcnow()

        if self.last_arrival is None:
            self.status = FreshnessStatus.UNKNOWN
            return

        self.age_seconds = int((self.last_check - self.last_arrival).total_seconds())
        self.status = threshold.get_status(self.age_minutes)

        # Calculate delay if expected_at is set
        if self.expected_at and self.last_check > self.expected_at:
            self.delay_seconds = int((self.last_check - self.expected_at).total_seconds())


class PipelineStage(BaseModel):
    """Tracks individual pipeline stage execution.

    Attributes:
        stage_id: Unique stage identifier
        stage_name: Human-readable stage name
        pipeline_id: Parent pipeline identifier
        sequence: Order in pipeline (1, 2, 3...)
        started_at: When stage started
        completed_at: When stage completed (None if running)
        duration_seconds: Execution duration
        status: Current stage status
        input_count: Records received
        output_count: Records produced
        error_message: Error details if failed
    """

    stage_id: str = Field(..., description="Unique stage identifier")
    stage_name: str = Field(..., description="Human-readable name")
    pipeline_id: str = Field(..., description="Parent pipeline ID")
    sequence: int = Field(default=1, ge=1, description="Order in pipeline")
    started_at: datetime | None = Field(None, description="Start time")
    completed_at: datetime | None = Field(None, description="Completion time")
    duration_seconds: int = Field(default=0, ge=0, description="Execution duration")
    status: str = Field(default="PENDING", description="Current status")
    input_count: int = Field(default=0, ge=0, description="Input records")
    output_count: int = Field(default=0, ge=0, description="Output records")
    error_message: str | None = Field(None, description="Error details")

    @property
    def is_running(self) -> bool:
        """Return True if stage is currently running."""
        return self.started_at is not None and self.completed_at is None

    @property
    def is_complete(self) -> bool:
        """Return True if stage completed."""
        return self.completed_at is not None

    def start(self) -> None:
        """Mark stage as started."""
        self.started_at = datetime.utcnow()
        self.status = "RUNNING"

    def complete(self, output_count: int = 0) -> None:
        """Mark stage as completed.

        Args:
            output_count: Number of output records.
        """
        self.completed_at = datetime.utcnow()
        self.status = "COMPLETED"
        self.output_count = output_count
        if self.started_at:
            self.duration_seconds = int(
                (self.completed_at - self.started_at).total_seconds()
            )

    def fail(self, error: str) -> None:
        """Mark stage as failed.

        Args:
            error: Error message.
        """
        self.completed_at = datetime.utcnow()
        self.status = "FAILED"
        self.error_message = error
        if self.started_at:
            self.duration_seconds = int(
                (self.completed_at - self.started_at).total_seconds()
            )


class PipelineExecution(BaseModel):
    """Tracks a complete pipeline execution.

    Attributes:
        pipeline_id: Unique pipeline identifier
        pipeline_name: Human-readable name
        source: Data source being processed
        started_at: Pipeline start time
        completed_at: Pipeline completion time
        stages: Individual stage executions
        total_duration_seconds: End-to-end duration
        status: Overall pipeline status
        latency_threshold_seconds: Max allowed latency
    """

    pipeline_id: str = Field(..., description="Unique pipeline identifier")
    pipeline_name: str = Field(..., description="Human-readable name")
    source: str = Field(..., description="Data source")
    started_at: datetime = Field(
        default_factory=datetime.utcnow, description="Start time"
    )
    completed_at: datetime | None = Field(None, description="Completion time")
    stages: list[PipelineStage] = Field(default_factory=list, description="Stage executions")
    total_duration_seconds: int = Field(default=0, ge=0, description="Total duration")
    status: str = Field(default="RUNNING", description="Overall status")
    latency_threshold_seconds: int = Field(default=1800, description="Max latency")

    @property
    def is_over_threshold(self) -> bool:
        """Return True if pipeline exceeded latency threshold."""
        return self.total_duration_seconds > self.latency_threshold_seconds

    def get_current_stage(self) -> PipelineStage | None:
        """Get currently running stage."""
        for stage in self.stages:
            if stage.is_running:
                return stage
        return None

    def get_stalled_stage(self, max_idle_seconds: int = 600) -> PipelineStage | None:
        """Get stage that appears stalled.

        Args:
            max_idle_seconds: Max seconds between stage completions.

        Returns:
            Stalled stage or None.
        """
        for i, stage in enumerate(self.stages):
            if stage.is_complete and i + 1 < len(self.stages):
                next_stage = self.stages[i + 1]
                if not next_stage.started_at and stage.completed_at:
                    idle_time = (datetime.utcnow() - stage.completed_at).total_seconds()
                    if idle_time > max_idle_seconds:
                        return next_stage
        return None


class DependencyStatus(BaseModel):
    """Status of an upstream dependency.

    Attributes:
        dependency_id: Dependency identifier
        dependency_name: Human-readable name
        source: Upstream data source
        last_completion: When dependency last completed
        status: Current dependency status
        delay_seconds: How late the dependency is
        blocking: Whether this blocks downstream
    """

    dependency_id: str = Field(..., description="Dependency identifier")
    dependency_name: str = Field(..., description="Human-readable name")
    source: str = Field(..., description="Upstream source")
    last_completion: datetime | None = Field(None, description="Last completion")
    status: str = Field(default="UNKNOWN", description="Current status")
    delay_seconds: int = Field(default=0, ge=0, description="Current delay")
    blocking: bool = Field(default=False, description="Blocks downstream")

    @property
    def is_late(self) -> bool:
        """Return True if dependency is delayed."""
        return self.delay_seconds > 0 and self.status != "OK"


class DependencyChain(BaseModel):
    """Tracks upstream dependencies for a data source.

    Attributes:
        source: Data source with dependencies
        dependencies: List of upstream dependencies
        all_satisfied: Whether all dependencies are met
        blocking_dependency: ID of blocking dependency (if any)
        last_check: When dependencies were last checked
    """

    source: str = Field(..., description="Data source")
    dependencies: list[DependencyStatus] = Field(
        default_factory=list, description="Upstream dependencies"
    )
    all_satisfied: bool = Field(default=True, description="All dependencies met")
    blocking_dependency: str | None = Field(None, description="Blocking dependency ID")
    last_check: datetime = Field(
        default_factory=datetime.utcnow, description="Last check time"
    )

    def check(self) -> bool:
        """Check if all dependencies are satisfied.

        Returns:
            True if all dependencies are satisfied.
        """
        self.last_check = datetime.utcnow()
        self.blocking_dependency = None
        self.all_satisfied = True

        for dep in self.dependencies:
            if dep.blocking and dep.status != "OK":
                self.blocking_dependency = dep.dependency_id
                self.all_satisfied = False
                break

        return self.all_satisfied

    def get_late_dependencies(self) -> list[DependencyStatus]:
        """Get list of late dependencies."""
        return [d for d in self.dependencies if d.is_late]
