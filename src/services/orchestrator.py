"""Orchestrator service - Coordinates validation workflows."""

import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty
from threading import Thread, Event
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, Field
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

from src.models.data_batch import DataBatch
from src.models.validation_result import ValidationResult
from src.lib.constants import EventType, BatchStatus
from src.lib.config import get_config, Config
from src.lib.logger import get_logger, bind_correlation_id

from src.services.validator import Validator
from src.services.alerter import Alerter
from src.skills.util.checkpoint import CheckpointSkill


class OrchestratorConfig(BaseModel):
    """Configuration for the orchestrator service."""

    watch_path: str = Field(default="data/incoming")
    file_patterns: list[str] = Field(default_factory=lambda: ["*.csv", "*.json"])
    scheduler_interval: int = Field(default=30, ge=30)
    heartbeat_interval: int = Field(default=60, ge=1)
    max_concurrent: int = Field(default=1, ge=1)


class ValidationEvent(BaseModel):
    """An event in the validation queue."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    file_path: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: int = Field(default=0)  # Higher = more urgent
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileWatcherHandler(FileSystemEventHandler):
    """Watchdog handler for file system events."""

    def __init__(self, orchestrator: "Orchestrator", patterns: list[str]):
        super().__init__()
        self.orchestrator = orchestrator
        self.patterns = patterns
        self._logger = get_logger("file_watcher")

    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation event."""
        if event.is_directory:
            return

        if self._matches_pattern(event.src_path):
            self._logger.debug("file_detected", path=event.src_path)
            self.orchestrator.queue_file_event(event.src_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification event."""
        # For MVP, we only handle new files, not modifications
        pass

    def _matches_pattern(self, path: str) -> bool:
        """Check if path matches any configured pattern."""
        from fnmatch import fnmatch
        filename = Path(path).name
        return any(fnmatch(filename, pattern) for pattern in self.patterns)


class Orchestrator:
    """Orchestrator service that coordinates validation workflows.

    Supports:
    - Event-driven: File watcher for data/incoming/
    - Scheduled: Periodic validation checks
    - Manual: Explicit validation triggers
    - Heartbeat: 60-second health emissions
    """

    def __init__(self, config: OrchestratorConfig | None = None):
        """Initialize the orchestrator service.

        Args:
            config: Configuration for the orchestrator.
        """
        self.config = config or OrchestratorConfig()
        self._logger = get_logger("orchestrator")

        # Core services
        self._validator = Validator()
        self._alerter = Alerter()
        self._checkpoint = CheckpointSkill()

        # Event queue (FIFO with priority)
        self._event_queue: Queue[ValidationEvent] = Queue()
        self._processed_files: set[str] = set()

        # State
        self._running = False
        self._stop_event = Event()
        self._start_time: datetime | None = None
        self._batches_processed = 0
        self._last_heartbeat: datetime | None = None

        # Threads
        self._watcher_observer: Observer | None = None
        self._processor_thread: Thread | None = None
        self._heartbeat_thread: Thread | None = None
        self._scheduler_thread: Thread | None = None

        # Callbacks
        self._on_validation_complete: list[Callable[[ValidationResult], None]] = []

    @property
    def is_running(self) -> bool:
        """Check if orchestrator is running."""
        return self._running

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        if self._start_time is None:
            return 0.0
        return (datetime.now(timezone.utc) - self._start_time).total_seconds()

    def start(self) -> None:
        """Start the orchestrator service."""
        if self._running:
            self._logger.warning("orchestrator_already_running")
            return

        self._logger.info("orchestrator_starting")
        self._running = True
        self._stop_event.clear()
        self._start_time = datetime.now(timezone.utc)

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

        # Ensure watch directory exists
        watch_path = Path(self.config.watch_path)
        watch_path.mkdir(parents=True, exist_ok=True)

        # Start alerter
        self._alerter.start()

        # Start file watcher
        self._start_file_watcher()

        # Start event processor
        self._processor_thread = Thread(target=self._process_loop, daemon=True)
        self._processor_thread.start()

        # Start heartbeat
        self._heartbeat_thread = Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        # Start scheduler
        self._scheduler_thread = Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()

        self._logger.info(
            "orchestrator_started",
            watch_path=self.config.watch_path,
            patterns=self.config.file_patterns,
        )

    def stop(self) -> None:
        """Stop the orchestrator service."""
        if not self._running:
            return

        self._logger.info("orchestrator_stopping")
        self._running = False
        self._stop_event.set()

        # Stop file watcher
        if self._watcher_observer:
            self._watcher_observer.stop()
            self._watcher_observer.join(timeout=5)

        # Stop alerter
        self._alerter.stop()

        # Wait for threads
        for thread in [self._processor_thread, self._heartbeat_thread, self._scheduler_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=5)

        self._logger.info(
            "orchestrator_stopped",
            uptime_seconds=self.uptime_seconds,
            batches_processed=self._batches_processed,
        )

    def run(self) -> None:
        """Run the orchestrator (blocking)."""
        self.start()
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self._logger.info("keyboard_interrupt")
        finally:
            self.stop()

    def queue_file_event(self, file_path: str) -> None:
        """Queue a file arrival event.

        Args:
            file_path: Path to the arrived file.
        """
        # Skip if already processed
        abs_path = str(Path(file_path).resolve())
        if abs_path in self._processed_files:
            return

        event = ValidationEvent(
            event_type=EventType.FILE_ARRIVED,
            file_path=abs_path,
            priority=1,  # File events have higher priority
        )
        self._event_queue.put(event)
        self._logger.debug("event_queued", event_type="FILE_ARRIVED", path=file_path)

    def trigger_manual_validation(self, file_path: str) -> ValidationResult | None:
        """Trigger validation manually.

        Args:
            file_path: Path to file to validate.

        Returns:
            ValidationResult or None if file doesn't exist.
        """
        path = Path(file_path)
        if not path.exists():
            self._logger.error("file_not_found", path=file_path)
            return None

        self._logger.info("manual_validation_triggered", path=file_path)

        try:
            result = self._validator.validate_file(path)
            self._batches_processed += 1

            # Notify callbacks
            for callback in self._on_validation_complete:
                try:
                    callback(result)
                except Exception as e:
                    self._logger.error("callback_error", error=str(e))

            return result
        except Exception as e:
            self._logger.error("manual_validation_error", path=file_path, error=str(e))
            return None

    def get_status(self) -> dict[str, Any]:
        """Get orchestrator status.

        Returns:
            Status dictionary.
        """
        return {
            "running": self._running,
            "uptime_seconds": self.uptime_seconds,
            "batches_processed": self._batches_processed,
            "queue_size": self._event_queue.qsize(),
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "watch_path": self.config.watch_path,
            "patterns": self.config.file_patterns,
        }

    def on_validation_complete(self, callback: Callable[[ValidationResult], None]) -> None:
        """Register a callback for validation completion.

        Args:
            callback: Function to call with ValidationResult.
        """
        self._on_validation_complete.append(callback)

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def handle_signal(signum: int, frame: Any) -> None:
            self._logger.info("signal_received", signal=signum)
            self.stop()

        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

    def _start_file_watcher(self) -> None:
        """Start the file system watcher."""
        watch_path = Path(self.config.watch_path)
        handler = FileWatcherHandler(self, self.config.file_patterns)

        self._watcher_observer = Observer()
        self._watcher_observer.schedule(handler, str(watch_path), recursive=False)
        self._watcher_observer.start()

        self._logger.info("file_watcher_started", path=str(watch_path))

    def _process_loop(self) -> None:
        """Main event processing loop."""
        while not self._stop_event.is_set():
            try:
                # Get next event from queue with timeout
                try:
                    event = self._event_queue.get(timeout=1.0)
                except Empty:
                    continue

                self._process_event(event)

            except Exception as e:
                self._logger.error("process_loop_error", error=str(e))

    def _process_event(self, event: ValidationEvent) -> None:
        """Process a single validation event.

        Args:
            event: The event to process.
        """
        bind_correlation_id(event.id)

        self._logger.debug(
            "processing_event",
            event_id=event.id,
            event_type=event.event_type.value,
        )

        try:
            if event.event_type == EventType.FILE_ARRIVED:
                self._handle_file_event(event)
            elif event.event_type == EventType.SCHEDULED_CHECK:
                self._handle_scheduled_event(event)
            elif event.event_type == EventType.MANUAL_TRIGGER:
                self._handle_manual_event(event)
            elif event.event_type == EventType.SHUTDOWN:
                self.stop()

        except Exception as e:
            self._logger.error(
                "event_processing_error",
                event_id=event.id,
                error=str(e),
            )
            # Continue processing (don't stop on individual failures)

    def _handle_file_event(self, event: ValidationEvent) -> None:
        """Handle a file arrival event.

        Args:
            event: The file event.
        """
        if not event.file_path:
            return

        path = Path(event.file_path)
        if not path.exists():
            self._logger.warning("file_not_found", path=event.file_path)
            return

        # Mark as processed
        self._processed_files.add(str(path.resolve()))

        # Save start checkpoint
        batch_id = str(uuid4())
        self._checkpoint.create_start_checkpoint(
            batch_id=batch_id,
            metadata={"source": event.file_path},
        )

        try:
            # Validate
            result = self._validator.validate_file(path)
            self._batches_processed += 1

            # Clean up checkpoint on success
            self._checkpoint.delete_for_batch(batch_id)

            # Notify callbacks
            for callback in self._on_validation_complete:
                try:
                    callback(result)
                except Exception as e:
                    self._logger.error("callback_error", error=str(e))

            self._logger.info(
                "file_validation_complete",
                path=event.file_path,
                passed=result.passed,
                anomalies=result.anomaly_count,
            )

        except Exception as e:
            self._logger.error(
                "file_validation_error",
                path=event.file_path,
                error=str(e),
            )
            # Checkpoint remains for recovery

    def _handle_scheduled_event(self, event: ValidationEvent) -> None:
        """Handle a scheduled check event.

        Args:
            event: The scheduled event.
        """
        # Check for any unprocessed files in watch directory
        watch_path = Path(self.config.watch_path)
        if not watch_path.exists():
            return

        from fnmatch import fnmatch
        for path in watch_path.iterdir():
            if path.is_file():
                for pattern in self.config.file_patterns:
                    if fnmatch(path.name, pattern):
                        abs_path = str(path.resolve())
                        if abs_path not in self._processed_files:
                            self.queue_file_event(abs_path)

    def _handle_manual_event(self, event: ValidationEvent) -> None:
        """Handle a manual trigger event.

        Args:
            event: The manual event.
        """
        if event.file_path:
            self.trigger_manual_validation(event.file_path)

    def _heartbeat_loop(self) -> None:
        """Heartbeat emission loop (FR-014)."""
        while not self._stop_event.is_set():
            self._emit_heartbeat()
            self._stop_event.wait(timeout=self.config.heartbeat_interval)

    def _emit_heartbeat(self) -> None:
        """Emit a heartbeat event."""
        self._last_heartbeat = datetime.now(timezone.utc)
        status = "healthy" if self._running else "stopped"

        self._logger.debug(
            "heartbeat",
            status=status,
            uptime_seconds=self.uptime_seconds,
            batches_processed=self._batches_processed,
            queue_size=self._event_queue.qsize(),
        )

    def _scheduler_loop(self) -> None:
        """Scheduled task loop."""
        while not self._stop_event.is_set():
            # Queue a scheduled check
            event = ValidationEvent(
                event_type=EventType.SCHEDULED_CHECK,
                priority=0,  # Lower priority than file events
            )
            self._event_queue.put(event)

            self._stop_event.wait(timeout=self.config.scheduler_interval)

    def recover_from_checkpoint(self) -> int:
        """Attempt to recover from any pending checkpoints.

        Returns:
            Number of batches recovered.
        """
        checkpoints = self._checkpoint.list_checkpoints()
        recovered = 0

        for cp_summary in checkpoints:
            cp = self._checkpoint.load(cp_summary["id"])
            if cp and cp.is_start:
                # Incomplete validation - could retry
                self._logger.info(
                    "checkpoint_found",
                    batch_id=cp.batch_id,
                    checkpoint_id=cp.id,
                )
                # For MVP, just clean up old checkpoints
                self._checkpoint.delete(cp.id)
                recovered += 1

        return recovered
