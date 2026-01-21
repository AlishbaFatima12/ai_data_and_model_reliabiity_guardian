"""FreshnessWatcher service for Silver Tier Layer 4.

This service monitors data freshness and SLA compliance:
- Tracks data arrival times for each monitored source
- Detects stale data (FR-001)
- Monitors SLA compliance (FR-002, FR-003)
- Tracks pipeline execution (FR-004, FR-006)
- Monitors dependency chains (FR-007)
- Detects latency spikes (FR-008)
"""

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import structlog
import yaml

from src.lib.constants import FailureCode, SeverityLevel
from src.models.sla_definition import (
    SLADefinition,
    FreshnessState,
    FreshnessStatus,
    FreshnessThreshold,
    PipelineExecution,
    PipelineStage,
    DependencyChain,
    DependencyStatus,
)
from src.models.silver_anomaly import FreshnessAnomaly

logger = structlog.get_logger(__name__)

# Default check interval (30 seconds per spec)
DEFAULT_CHECK_INTERVAL_SECONDS = 30


class FreshnessWatcher:
    """Monitors data freshness and SLA compliance.

    Per spec: Runs parallel to main validation pipeline on 30-second timer.
    Detects FR-001 through FR-008 anomalies.
    """

    def __init__(
        self,
        sla_dir: Path | None = None,
        state_file: Path | None = None,
        check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the freshness watcher.

        Args:
            sla_dir: Directory containing SLA definition YAML files.
            state_file: Path to freshness state JSON file.
            check_interval_seconds: Seconds between freshness checks.
        """
        self.sla_dir = sla_dir or Path("config/sla")
        self.state_file = state_file or Path("data/state/freshness.json")
        self.check_interval_seconds = max(check_interval_seconds, 10)

        # SLA definitions by source
        self._sla_definitions: dict[str, SLADefinition] = {}

        # Current freshness state by source
        self._freshness_state: dict[str, FreshnessState] = {}

        # Pipeline executions by pipeline_id
        self._pipeline_executions: dict[str, PipelineExecution] = {}

        # Dependency chains by source
        self._dependency_chains: dict[str, DependencyChain] = {}

        # Anomaly callbacks
        self._anomaly_callbacks: list[Callable[[FreshnessAnomaly], None]] = []

        # Background thread
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Load SLA definitions
        self._load_sla_definitions()

        # Load persisted state
        self._load_state()

        logger.info(
            "freshness_watcher_initialized",
            sla_dir=str(self.sla_dir),
            state_file=str(self.state_file),
            check_interval=self.check_interval_seconds,
            sla_count=len(self._sla_definitions),
        )

    def _load_sla_definitions(self) -> None:
        """Load SLA definitions from YAML files."""
        if not self.sla_dir.exists():
            logger.warning("sla_dir_not_found", dir=str(self.sla_dir))
            return

        for file_path in self.sla_dir.glob("*.yaml"):
            self._load_sla_file(file_path)

        for file_path in self.sla_dir.glob("*.yml"):
            self._load_sla_file(file_path)

    def _load_sla_file(self, file_path: Path) -> None:
        """Load SLA definitions from a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                return

            # Check for both 'slas' and 'sla_definitions' keys
            slas = data.get("slas") or data.get("sla_definitions", [])
            if not isinstance(slas, list):
                slas = [data]  # Single SLA file

            for sla_data in slas:
                if not isinstance(sla_data, dict):
                    continue

                # Parse freshness threshold
                threshold_data = sla_data.get("freshness_threshold", {})
                threshold = FreshnessThreshold(
                    warning_minutes=threshold_data.get("warning_minutes", 60),
                    critical_minutes=threshold_data.get("critical_minutes", 90),
                )

                sla = SLADefinition(
                    id=sla_data.get("id", f"sla-{len(self._sla_definitions)}"),
                    source=sla_data.get("source", ""),
                    name=sla_data.get("name", ""),
                    description=sla_data.get("description", ""),
                    schedule=sla_data.get("schedule", "0 * * * *"),
                    freshness_threshold=threshold,
                    latency_threshold_seconds=sla_data.get("latency_threshold", 1800),
                    expected_record_count=sla_data.get("expected_record_count"),
                    owner=sla_data.get("owner", ""),
                    enabled=sla_data.get("enabled", True),
                )

                if sla.enabled and sla.source:
                    self._sla_definitions[sla.source] = sla

                    # Initialize freshness state if not exists
                    if sla.source not in self._freshness_state:
                        self._freshness_state[sla.source] = FreshnessState(
                            source=sla.source,
                            sla_id=sla.id,
                        )

        except Exception as e:
            logger.error("sla_file_load_error", file=str(file_path), error=str(e))

    def _load_state(self) -> None:
        """Load persisted freshness state from file."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for source, state_data in data.get("freshness", {}).items():
                # Parse datetime fields
                last_arrival = state_data.get("last_arrival")
                if last_arrival:
                    last_arrival = datetime.fromisoformat(last_arrival)

                expected_at = state_data.get("expected_at")
                if expected_at:
                    expected_at = datetime.fromisoformat(expected_at)

                self._freshness_state[source] = FreshnessState(
                    source=source,
                    sla_id=state_data.get("sla_id", ""),
                    last_arrival=last_arrival,
                    age_seconds=state_data.get("age_seconds", 0),
                    status=FreshnessStatus(state_data.get("status", "UNKNOWN")),
                    expected_at=expected_at,
                    delay_seconds=state_data.get("delay_seconds", 0),
                    record_count=state_data.get("record_count", 0),
                    consecutive_misses=state_data.get("consecutive_misses", 0),
                )

            logger.info("freshness_state_loaded", sources=len(self._freshness_state))

        except Exception as e:
            logger.error("state_load_error", error=str(e))

    def _save_state(self) -> None:
        """Persist freshness state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "freshness": {},
                "last_updated": datetime.utcnow().isoformat(),
            }

            for source, state in self._freshness_state.items():
                data["freshness"][source] = {
                    "sla_id": state.sla_id,
                    "last_arrival": state.last_arrival.isoformat() if state.last_arrival else None,
                    "age_seconds": state.age_seconds,
                    "status": state.status.value,
                    "expected_at": state.expected_at.isoformat() if state.expected_at else None,
                    "delay_seconds": state.delay_seconds,
                    "record_count": state.record_count,
                    "consecutive_misses": state.consecutive_misses,
                }

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error("state_save_error", error=str(e))

    def start(self) -> None:
        """Start background freshness monitoring."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        logger.info("freshness_watcher_started")

    def stop(self) -> None:
        """Stop background freshness monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

        self._save_state()
        logger.info("freshness_watcher_stopped")

    def _run_loop(self) -> None:
        """Background loop for periodic freshness checks."""
        while self._running:
            try:
                self.check_all()
            except Exception as e:
                logger.error("freshness_check_error", error=str(e))

            # Sleep in small increments to allow quick shutdown
            for _ in range(self.check_interval_seconds):
                if not self._running:
                    break
                time.sleep(1)

    def check_all(self) -> list[FreshnessAnomaly]:
        """Check freshness for all monitored sources.

        Returns:
            List of anomalies detected.
        """
        anomalies: list[FreshnessAnomaly] = []

        with self._lock:
            for source, sla in self._sla_definitions.items():
                if not sla.enabled:
                    continue

                source_anomalies = self._check_source(source, sla)
                anomalies.extend(source_anomalies)

            # Check pipelines for stalls and delays
            pipeline_anomalies = self._check_pipelines()
            anomalies.extend(pipeline_anomalies)

            # Check dependency chains
            dependency_anomalies = self._check_dependencies()
            anomalies.extend(dependency_anomalies)

            # Persist state
            self._save_state()

        # Notify callbacks
        for anomaly in anomalies:
            for callback in self._anomaly_callbacks:
                try:
                    callback(anomaly)
                except Exception as e:
                    logger.error("anomaly_callback_error", error=str(e))

        return anomalies

    def _check_source(
        self, source: str, sla: SLADefinition
    ) -> list[FreshnessAnomaly]:
        """Check freshness for a single source.

        Args:
            source: Data source name.
            sla: SLA definition for the source.

        Returns:
            List of anomalies detected.
        """
        anomalies: list[FreshnessAnomaly] = []

        state = self._freshness_state.get(source)
        if state is None:
            state = FreshnessState(source=source, sla_id=sla.id)
            self._freshness_state[source] = state

        # Update expected arrival time
        state.expected_at = sla.get_previous_expected()

        # Refresh state with current thresholds
        state.refresh(sla.freshness_threshold)

        # Check for stale data (FR-001)
        if state.status == FreshnessStatus.CRITICAL:
            anomalies.append(
                self._create_anomaly(
                    failure_code=FailureCode.DATA_STALE,
                    severity=SeverityLevel.CRITICAL,
                    source=source,
                    sla=sla,
                    state=state,
                    explanation=f"Data is stale: {state.age_minutes:.1f} minutes since last arrival (threshold: {sla.freshness_threshold.critical_minutes} min)",
                )
            )
        elif state.status == FreshnessStatus.WARNING:
            anomalies.append(
                self._create_anomaly(
                    failure_code=FailureCode.DATA_STALE,
                    severity=SeverityLevel.WARNING,
                    source=source,
                    sla=sla,
                    state=state,
                    explanation=f"Data freshness warning: {state.age_minutes:.1f} minutes since last arrival (threshold: {sla.freshness_threshold.warning_minutes} min)",
                )
            )

        # Check for SLA breach (FR-002)
        if state.expected_at and state.delay_seconds > 0:
            delay_minutes = state.delay_minutes

            if delay_minutes > 30:  # More than 30 minutes late = breach
                anomalies.append(
                    self._create_anomaly(
                        failure_code=FailureCode.SLA_BREACH,
                        severity=SeverityLevel.CRITICAL,
                        source=source,
                        sla=sla,
                        state=state,
                        explanation=f"SLA breach: data is {delay_minutes:.1f} minutes late",
                    )
                )
            elif delay_minutes > 15:  # 15-30 minutes late = warning
                anomalies.append(
                    self._create_anomaly(
                        failure_code=FailureCode.SLA_WARNING,
                        severity=SeverityLevel.WARNING,
                        source=source,
                        sla=sla,
                        state=state,
                        explanation=f"SLA at risk: data is {delay_minutes:.1f} minutes late",
                    )
                )

        # Check for missing delivery (FR-005)
        if state.consecutive_misses >= 2:
            anomalies.append(
                self._create_anomaly(
                    failure_code=FailureCode.MISSING_DELIVERY,
                    severity=SeverityLevel.CRITICAL,
                    source=source,
                    sla=sla,
                    state=state,
                    explanation=f"Missing delivery: {state.consecutive_misses} consecutive missed arrivals",
                )
            )

        return anomalies

    def _check_pipelines(self) -> list[FreshnessAnomaly]:
        """Check all pipelines for delays and stalls.

        Returns:
            List of pipeline-related anomalies.
        """
        anomalies: list[FreshnessAnomaly] = []

        for pipeline_id, execution in self._pipeline_executions.items():
            # Check for latency spike (FR-008)
            if execution.is_over_threshold:
                anomalies.append(
                    FreshnessAnomaly(
                        id=f"FR-{uuid4().hex[:8]}",
                        failure_code=FailureCode.LATENCY_SPIKE,
                        severity=SeverityLevel.WARNING,
                        source=execution.source,
                        sla_id=pipeline_id,
                        expected_at=execution.started_at,
                        last_arrival=None,
                        delay_seconds=execution.total_duration_seconds - execution.latency_threshold_seconds,
                        explanation=f"Latency spike: pipeline took {execution.total_duration_seconds}s (threshold: {execution.latency_threshold_seconds}s)",
                        details={
                            "pipeline_id": pipeline_id,
                            "duration_seconds": execution.total_duration_seconds,
                            "threshold_seconds": execution.latency_threshold_seconds,
                        },
                    )
                )

            # Check for stalled stage (FR-004)
            stalled = execution.get_stalled_stage()
            if stalled:
                anomalies.append(
                    FreshnessAnomaly(
                        id=f"FR-{uuid4().hex[:8]}",
                        failure_code=FailureCode.PIPELINE_DELAY,
                        severity=SeverityLevel.WARNING,
                        source=execution.source,
                        sla_id=pipeline_id,
                        expected_at=datetime.utcnow(),
                        last_arrival=None,
                        delay_seconds=0,
                        explanation=f"Pipeline stall: stage '{stalled.stage_name}' has not started",
                        pipeline_stage=stalled.stage_name,
                        details={
                            "pipeline_id": pipeline_id,
                            "stalled_stage": stalled.stage_id,
                        },
                    )
                )

            # Check for failed stage (FR-006)
            for stage in execution.stages:
                if stage.status == "FAILED":
                    anomalies.append(
                        FreshnessAnomaly(
                            id=f"FR-{uuid4().hex[:8]}",
                            failure_code=FailureCode.JOB_FAILURE,
                            severity=SeverityLevel.CRITICAL,
                            source=execution.source,
                            sla_id=pipeline_id,
                            expected_at=datetime.utcnow(),
                            last_arrival=None,
                            delay_seconds=0,
                            explanation=f"Pipeline job failed: stage '{stage.stage_name}' - {stage.error_message}",
                            pipeline_stage=stage.stage_name,
                            details={
                                "pipeline_id": pipeline_id,
                                "stage_id": stage.stage_id,
                                "error": stage.error_message,
                            },
                        )
                    )

        return anomalies

    def _check_dependencies(self) -> list[FreshnessAnomaly]:
        """Check dependency chains for delays.

        Returns:
            List of dependency-related anomalies.
        """
        anomalies: list[FreshnessAnomaly] = []

        for source, chain in self._dependency_chains.items():
            chain.check()

            for dep in chain.get_late_dependencies():
                anomalies.append(
                    FreshnessAnomaly(
                        id=f"FR-{uuid4().hex[:8]}",
                        failure_code=FailureCode.DEPENDENCY_DELAY,
                        severity=SeverityLevel.WARNING if not dep.blocking else SeverityLevel.CRITICAL,
                        source=source,
                        sla_id=dep.dependency_id,
                        expected_at=datetime.utcnow(),
                        last_arrival=dep.last_completion,
                        delay_seconds=dep.delay_seconds,
                        explanation=f"Upstream dependency '{dep.dependency_name}' is delayed by {dep.delay_seconds // 60} minutes",
                        details={
                            "dependency_id": dep.dependency_id,
                            "blocking": dep.blocking,
                            "upstream_source": dep.source,
                        },
                    )
                )

        return anomalies

    def _create_anomaly(
        self,
        failure_code: FailureCode,
        severity: SeverityLevel,
        source: str,
        sla: SLADefinition,
        state: FreshnessState,
        explanation: str,
    ) -> FreshnessAnomaly:
        """Create a FreshnessAnomaly instance.

        Args:
            failure_code: FR-xxx code.
            severity: Severity level.
            source: Data source.
            sla: SLA definition.
            state: Freshness state.
            explanation: Human-readable explanation.

        Returns:
            FreshnessAnomaly instance.
        """
        return FreshnessAnomaly(
            id=f"FR-{uuid4().hex[:8]}",
            failure_code=failure_code,
            severity=severity,
            source=source,
            sla_id=sla.id,
            expected_at=state.expected_at or datetime.utcnow(),
            last_arrival=state.last_arrival,
            delay_seconds=state.delay_seconds,
            explanation=explanation,
            details={
                "age_seconds": state.age_seconds,
                "age_minutes": state.age_minutes,
                "consecutive_misses": state.consecutive_misses,
                "sla_owner": sla.owner,
            },
        )

    def record_arrival(
        self, source: str, arrival_time: datetime | None = None, record_count: int = 0
    ) -> None:
        """Record data arrival for a source.

        Args:
            source: Data source name.
            arrival_time: When data arrived (default: now).
            record_count: Number of records in batch.
        """
        with self._lock:
            state = self._freshness_state.get(source)
            if state is None:
                state = FreshnessState(source=source)
                self._freshness_state[source] = state

            state.update(arrival_time or datetime.utcnow(), record_count)

            logger.info(
                "data_arrival_recorded",
                source=source,
                record_count=record_count,
            )

    def record_pipeline_start(
        self, pipeline_id: str, source: str, pipeline_name: str = ""
    ) -> PipelineExecution:
        """Record pipeline execution start.

        Args:
            pipeline_id: Unique pipeline identifier.
            source: Data source being processed.
            pipeline_name: Human-readable name.

        Returns:
            PipelineExecution for tracking stages.
        """
        with self._lock:
            sla = self._sla_definitions.get(source)
            latency_threshold = sla.latency_threshold_seconds if sla else 1800

            execution = PipelineExecution(
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name or pipeline_id,
                source=source,
                latency_threshold_seconds=latency_threshold,
            )
            self._pipeline_executions[pipeline_id] = execution

            logger.info(
                "pipeline_started",
                pipeline_id=pipeline_id,
                source=source,
            )

            return execution

    def record_pipeline_complete(self, pipeline_id: str) -> None:
        """Record pipeline execution completion.

        Args:
            pipeline_id: Pipeline identifier.
        """
        with self._lock:
            execution = self._pipeline_executions.get(pipeline_id)
            if execution:
                execution.completed_at = datetime.utcnow()
                execution.status = "COMPLETED"
                execution.total_duration_seconds = int(
                    (execution.completed_at - execution.started_at).total_seconds()
                )

                logger.info(
                    "pipeline_completed",
                    pipeline_id=pipeline_id,
                    duration_seconds=execution.total_duration_seconds,
                )

    def add_dependency(
        self,
        source: str,
        dependency_id: str,
        dependency_name: str,
        upstream_source: str,
        blocking: bool = True,
    ) -> None:
        """Add a dependency to track for a source.

        Args:
            source: Data source with the dependency.
            dependency_id: Dependency identifier.
            dependency_name: Human-readable name.
            upstream_source: Upstream data source.
            blocking: Whether this dependency blocks downstream.
        """
        with self._lock:
            chain = self._dependency_chains.get(source)
            if chain is None:
                chain = DependencyChain(source=source)
                self._dependency_chains[source] = chain

            chain.dependencies.append(
                DependencyStatus(
                    dependency_id=dependency_id,
                    dependency_name=dependency_name,
                    source=upstream_source,
                    blocking=blocking,
                )
            )

    def on_anomaly(self, callback: Callable[[FreshnessAnomaly], None]) -> None:
        """Register a callback for anomaly notifications.

        Args:
            callback: Function to call when anomaly detected.
        """
        self._anomaly_callbacks.append(callback)

    def get_state(self, source: str) -> FreshnessState | None:
        """Get current freshness state for a source.

        Args:
            source: Data source name.

        Returns:
            FreshnessState or None if not monitored.
        """
        with self._lock:
            return self._freshness_state.get(source)

    def get_all_states(self) -> dict[str, FreshnessState]:
        """Get all freshness states.

        Returns:
            Dictionary of source -> FreshnessState.
        """
        with self._lock:
            return dict(self._freshness_state)

    def get_sla(self, source: str) -> SLADefinition | None:
        """Get SLA definition for a source.

        Args:
            source: Data source name.

        Returns:
            SLADefinition or None if not defined.
        """
        return self._sla_definitions.get(source)

    def check_source(self, source: str) -> tuple[list[FreshnessAnomaly], float]:
        """Check freshness for a single source.

        Args:
            source: Data source name.

        Returns:
            Tuple of (anomalies, health_score).
        """
        sla = self._sla_definitions.get(source)
        if sla is None:
            return [], 100.0

        with self._lock:
            anomalies = self._check_source(source, sla)

        # Calculate health score
        score = 100.0
        for anomaly in anomalies:
            if anomaly.severity == SeverityLevel.CRITICAL:
                score -= 30.0
            elif anomaly.severity == SeverityLevel.WARNING:
                score -= 15.0
        score = max(0.0, min(100.0, score))

        return anomalies, score
