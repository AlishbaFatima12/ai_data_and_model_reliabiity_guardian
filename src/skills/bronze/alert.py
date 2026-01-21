"""Bronze alert skill - Alert formatting and dispatch."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.anomaly import Anomaly
from src.models.alert import Alert
from src.lib.constants import AlertChannel, SeverityLevel


class AlertConfig(BaseModel):
    """Configuration for alert skill."""

    alert_log_dir: str = Field(
        default="logs/alerts",
        description="Directory for alert log files",
    )
    console_enabled: bool = Field(
        default=True,
        description="Whether to output alerts to console",
    )
    log_enabled: bool = Field(
        default=True,
        description="Whether to log alerts to file",
    )


class AlertSkill:
    """Bronze skill for formatting and dispatching alerts (FR-011, FR-012).

    Creates and dispatches alerts for WARNING and CRITICAL anomalies.
    """

    name: str = "bronze.alert"

    def __init__(self, config: AlertConfig | None = None):
        """Initialize the alert skill.

        Args:
            config: Configuration for alert handling.
        """
        self.config = config or AlertConfig()

    def create_alert(
        self,
        anomaly: Anomaly,
        channel: AlertChannel = AlertChannel.CONSOLE,
    ) -> Alert:
        """Create an alert from an anomaly.

        Args:
            anomaly: The anomaly to create an alert for.
            channel: Output channel for the alert.

        Returns:
            Created Alert instance.
        """
        return Alert.from_anomaly(
            anomaly_id=anomaly.id,
            batch_id=anomaly.batch_id,
            severity=anomaly.severity,
            failure_code=anomaly.failure_code.value,
            root_cause=anomaly.root_cause,
            affected_count=anomaly.affected_count,
            channel=channel,
        )

    def dispatch(self, alert: Alert) -> bool:
        """Dispatch an alert to its channel.

        Args:
            alert: Alert to dispatch.

        Returns:
            True if dispatch was successful.
        """
        success = True

        if self.config.console_enabled:
            if not self._dispatch_console(alert):
                success = False

        if self.config.log_enabled:
            if not self._dispatch_log(alert):
                success = False

        if success:
            alert.mark_sent()

        return success

    def dispatch_for_anomalies(
        self,
        anomalies: list[Anomaly],
    ) -> list[Alert]:
        """Create and dispatch alerts for a list of anomalies.

        Only creates alerts for WARNING and CRITICAL severity.

        Args:
            anomalies: List of anomalies to process.

        Returns:
            List of dispatched alerts.
        """
        alerts: list[Alert] = []

        for anomaly in anomalies:
            if not anomaly.requires_alert:
                continue

            # Create and dispatch to both channels if enabled
            if self.config.console_enabled:
                console_alert = self.create_alert(anomaly, AlertChannel.CONSOLE)
                self._dispatch_console(console_alert)
                console_alert.mark_sent()
                alerts.append(console_alert)

            if self.config.log_enabled:
                log_alert = self.create_alert(anomaly, AlertChannel.LOG_FILE)
                self._dispatch_log(log_alert)
                log_alert.mark_sent()
                if not self.config.console_enabled:
                    alerts.append(log_alert)

        return alerts

    def _dispatch_console(self, alert: Alert) -> bool:
        """Dispatch alert to console.

        Args:
            alert: Alert to dispatch.

        Returns:
            True if successful.
        """
        try:
            output = alert.format_console()
            print(output)
            return True
        except Exception:
            return False

    def _dispatch_log(self, alert: Alert) -> bool:
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
            }

            with open(filepath, "a", encoding="utf-8") as f:
                json.dump(entry, f, default=str)
                f.write("\n")

            return True
        except Exception:
            return False

    def format_summary(
        self,
        anomalies: list[Anomaly],
        batch_id: str,
    ) -> str:
        """Format a summary alert for multiple anomalies.

        Args:
            anomalies: List of anomalies.
            batch_id: Batch ID.

        Returns:
            Formatted summary string.
        """
        critical = [a for a in anomalies if a.severity == SeverityLevel.CRITICAL]
        warning = [a for a in anomalies if a.severity == SeverityLevel.WARNING]

        lines = [
            f"=== Validation Alert Summary for Batch {batch_id} ===",
            "",
        ]

        if critical:
            lines.append(f"🚨 CRITICAL Issues ({len(critical)}):")
            for a in critical:
                lines.append(f"  - {a.failure_code.value}: {a.root_cause}")
            lines.append("")

        if warning:
            lines.append(f"⚠️ WARNING Issues ({len(warning)}):")
            for a in warning:
                lines.append(f"  - {a.failure_code.value}: {a.root_cause}")
            lines.append("")

        total_affected = sum(a.affected_count for a in anomalies if a.requires_alert)
        lines.append(f"Total affected records: {total_affected}")
        lines.append("=" * 50)

        return "\n".join(lines)

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

        return alerts
