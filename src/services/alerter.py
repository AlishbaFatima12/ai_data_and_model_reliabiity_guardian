"""Alerter service - Alert generation and dispatch with timing."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread, Event
from typing import Any
from collections import deque

from pydantic import BaseModel, Field

from src.models.anomaly import Anomaly
from src.models.alert import Alert
from src.lib.constants import AlertChannel, SeverityLevel, ALERT_DISPATCH_SECONDS
from src.lib.logger import get_logger


class AlerterConfig(BaseModel):
    """Configuration for the alerter service."""

    critical_dispatch_seconds: int = Field(
        default=60,
        ge=1,
        description="Time to dispatch CRITICAL alerts (per SC-002)",
    )
    warning_dispatch_seconds: int = Field(
        default=300,
        ge=1,
        description="Time to dispatch WARNING alerts (per SC-002)",
    )
    console_enabled: bool = Field(
        default=True,
        description="Whether to output alerts to console",
    )
    log_enabled: bool = Field(
        default=True,
        description="Whether to log alerts to file",
    )
    alert_log_dir: str = Field(
        default="logs/alerts",
        description="Directory for alert log files",
    )


class PendingAlert:
    """Represents an alert pending dispatch with timing."""

    def __init__(self, alert: Alert, dispatch_at: datetime):
        self.alert = alert
        self.dispatch_at = dispatch_at
        self.dispatched = False


class Alerter:
    """Alerter service with severity-based timing (FR-011, FR-012, FR-013).

    Generates alerts within specified timeframes:
    - CRITICAL: within 1 minute (60 seconds)
    - WARNING: within 5 minutes (300 seconds)
    """

    def __init__(self, config: AlerterConfig | None = None):
        """Initialize the alerter service.

        Args:
            config: Configuration for the alerter.
        """
        self.config = config or AlerterConfig()
        self._logger = get_logger("alerter")

        # Alert queues
        self._critical_queue: deque[PendingAlert] = deque()
        self._warning_queue: deque[PendingAlert] = deque()

        # Background processing
        self._stop_event = Event()
        self._processor_thread: Thread | None = None

    def start(self) -> None:
        """Start the background alert processor."""
        if self._processor_thread and self._processor_thread.is_alive():
            return

        self._stop_event.clear()
        self._processor_thread = Thread(target=self._process_loop, daemon=True)
        self._processor_thread.start()
        self._logger.info("alerter_started")

    def stop(self) -> None:
        """Stop the background alert processor."""
        self._stop_event.set()
        if self._processor_thread:
            self._processor_thread.join(timeout=5)
        self._logger.info("alerter_stopped")

    def queue_alert(self, anomaly: Anomaly) -> Alert | None:
        """Queue an alert for dispatch based on severity.

        Args:
            anomaly: The anomaly to create an alert for.

        Returns:
            Created Alert if anomaly requires alerting, None otherwise.
        """
        if not anomaly.requires_alert:
            return None

        alert = self._create_alert(anomaly)
        dispatch_delay = self._get_dispatch_delay(anomaly.severity)
        dispatch_at = datetime.now(timezone.utc)

        pending = PendingAlert(alert, dispatch_at)

        if anomaly.severity == SeverityLevel.CRITICAL:
            self._critical_queue.append(pending)
            self._logger.debug(
                "alert_queued",
                alert_id=alert.id,
                severity="CRITICAL",
                queue_size=len(self._critical_queue),
            )
        else:
            self._warning_queue.append(pending)
            self._logger.debug(
                "alert_queued",
                alert_id=alert.id,
                severity="WARNING",
                queue_size=len(self._warning_queue),
            )

        return alert

    def queue_alerts_for_anomalies(
        self,
        anomalies: list[Anomaly],
    ) -> list[Alert]:
        """Queue alerts for multiple anomalies.

        Args:
            anomalies: List of anomalies to process.

        Returns:
            List of created alerts.
        """
        alerts = []
        for anomaly in anomalies:
            alert = self.queue_alert(anomaly)
            if alert:
                alerts.append(alert)
        return alerts

    def dispatch_immediate(self, anomaly: Anomaly) -> Alert | None:
        """Dispatch an alert immediately without queueing.

        Args:
            anomaly: The anomaly to alert on.

        Returns:
            Dispatched Alert or None.
        """
        if not anomaly.requires_alert:
            return None

        alert = self._create_alert(anomaly)
        self._dispatch_alert(alert)
        return alert

    def dispatch_all_pending(self) -> int:
        """Dispatch all pending alerts immediately.

        Returns:
            Number of alerts dispatched.
        """
        count = 0

        # Dispatch critical alerts
        while self._critical_queue:
            pending = self._critical_queue.popleft()
            if not pending.dispatched:
                self._dispatch_alert(pending.alert)
                count += 1

        # Dispatch warning alerts
        while self._warning_queue:
            pending = self._warning_queue.popleft()
            if not pending.dispatched:
                self._dispatch_alert(pending.alert)
                count += 1

        return count

    def _process_loop(self) -> None:
        """Background loop for processing alert queues."""
        while not self._stop_event.is_set():
            try:
                self._process_queues()
            except Exception as e:
                self._logger.error("alert_process_error", error=str(e))

            # Sleep briefly between checks
            self._stop_event.wait(timeout=1.0)

    def _process_queues(self) -> None:
        """Process pending alerts in both queues."""
        now = datetime.now(timezone.utc)

        # Process critical queue (immediate dispatch)
        while self._critical_queue:
            pending = self._critical_queue[0]
            if pending.dispatched:
                self._critical_queue.popleft()
                continue

            # Critical alerts dispatch immediately
            self._dispatch_alert(pending.alert)
            pending.dispatched = True
            self._critical_queue.popleft()

        # Process warning queue (delayed dispatch)
        processed = []
        for i, pending in enumerate(self._warning_queue):
            if pending.dispatched:
                processed.append(i)
                continue

            # Check if it's time to dispatch
            elapsed = (now - pending.dispatch_at).total_seconds()
            if elapsed >= 0:  # Ready to dispatch
                self._dispatch_alert(pending.alert)
                pending.dispatched = True
                processed.append(i)

        # Remove processed alerts (in reverse order to maintain indices)
        for i in reversed(processed):
            if i < len(self._warning_queue):
                del self._warning_queue[i]

    def _create_alert(self, anomaly: Anomaly) -> Alert:
        """Create an alert from an anomaly.

        Args:
            anomaly: The source anomaly.

        Returns:
            Created Alert instance.
        """
        channel = AlertChannel.CONSOLE if self.config.console_enabled else AlertChannel.LOG_FILE

        return Alert.from_anomaly(
            anomaly_id=anomaly.id,
            batch_id=anomaly.batch_id,
            severity=anomaly.severity,
            failure_code=anomaly.failure_code.value,
            root_cause=anomaly.root_cause,
            affected_count=anomaly.affected_count,
            channel=channel,
        )

    def _dispatch_alert(self, alert: Alert) -> bool:
        """Dispatch an alert to configured channels.

        Args:
            alert: Alert to dispatch.

        Returns:
            True if dispatch was successful.
        """
        success = True

        if self.config.console_enabled:
            if not self._dispatch_to_console(alert):
                success = False

        if self.config.log_enabled:
            if not self._dispatch_to_log(alert):
                success = False

        if success:
            alert.mark_sent()
            self._logger.info(
                "alert_dispatched",
                alert_id=alert.id,
                severity=alert.severity.value,
                batch_id=alert.batch_id,
            )

        return success

    def _dispatch_to_console(self, alert: Alert) -> bool:
        """Dispatch alert to console output.

        Args:
            alert: Alert to dispatch.

        Returns:
            True if successful.
        """
        try:
            output = alert.format_console()
            print(output)
            return True
        except Exception as e:
            self._logger.error("console_dispatch_failed", error=str(e))
            return False

    def _dispatch_to_log(self, alert: Alert) -> bool:
        """Dispatch alert to log file.

        Args:
            alert: Alert to dispatch.

        Returns:
            True if successful.
        """
        log_dir = Path(self.config.alert_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{date_str}.jsonl"
        filepath = log_dir / filename

        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "alert_id": alert.id,
                "anomaly_id": alert.anomaly_id,
                "batch_id": alert.batch_id,
                "severity": alert.severity.value,
                "message": alert.message,
                "failure_code": alert.failure_code,
                "sent_timestamp": alert.sent_timestamp.isoformat() if alert.sent_timestamp else None,
            }

            with open(filepath, "a", encoding="utf-8") as f:
                json.dump(entry, f, default=str)
                f.write("\n")

            return True
        except Exception as e:
            self._logger.error("log_dispatch_failed", error=str(e))
            return False

    def _get_dispatch_delay(self, severity: SeverityLevel) -> int:
        """Get dispatch delay in seconds for a severity level.

        Args:
            severity: Severity level.

        Returns:
            Delay in seconds (0 for immediate).
        """
        if severity == SeverityLevel.CRITICAL:
            return 0  # Immediate
        elif severity == SeverityLevel.WARNING:
            return 0  # For MVP, dispatch warnings immediately too
        else:
            return 0

    def get_pending_count(self) -> dict[str, int]:
        """Get count of pending alerts by severity.

        Returns:
            Dictionary with counts.
        """
        return {
            "critical": len(self._critical_queue),
            "warning": len(self._warning_queue),
            "total": len(self._critical_queue) + len(self._warning_queue),
        }

    def read_alerts(
        self,
        date: datetime | None = None,
        severity: SeverityLevel | None = None,
        batch_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read alerts from log file.

        Args:
            date: Date to read alerts from (default: today).
            severity: Filter by severity.
            batch_id: Filter by batch ID.
            limit: Maximum alerts to return.

        Returns:
            List of matching alerts.
        """
        log_dir = Path(self.config.alert_log_dir)
        if not log_dir.exists():
            return []

        if date is None:
            date = datetime.now(timezone.utc)

        date_str = date.strftime("%Y-%m-%d")
        filename = f"{date_str}.jsonl"
        filepath = log_dir / filename

        if not filepath.exists():
            return []

        alerts = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    entry = json.loads(line)

                    # Apply filters
                    if severity and entry.get("severity") != severity.value:
                        continue
                    if batch_id and entry.get("batch_id") != batch_id:
                        continue

                    alerts.append(entry)

                    if len(alerts) >= limit:
                        break

        except Exception:
            pass

        # Sort by timestamp (newest first)
        alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return alerts

    def get_alert_stats(self, date: datetime | None = None) -> dict[str, Any]:
        """Get alert statistics for a date.

        Args:
            date: Date to get stats for (default: today).

        Returns:
            Statistics dictionary.
        """
        alerts = self.read_alerts(date=date, limit=10000)

        stats: dict[str, Any] = {
            "total": len(alerts),
            "by_severity": {},
            "by_batch": {},
            "by_failure_code": {},
        }

        for alert in alerts:
            # By severity
            severity = alert.get("severity", "UNKNOWN")
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

            # By batch
            batch = alert.get("batch_id", "unknown")
            stats["by_batch"][batch] = stats["by_batch"].get(batch, 0) + 1

            # By failure code
            code = alert.get("failure_code", "unknown")
            stats["by_failure_code"][code] = stats["by_failure_code"].get(code, 0) + 1

        return stats
