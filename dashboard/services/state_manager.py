"""StateManager service for persisting dashboard state.

Manages acknowledged anomalies and user session state.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateManager:
    """Manages persistent dashboard state.

    Handles:
    - Acknowledged anomalies
    - User view preferences
    - Filter state persistence
    """

    def __init__(self, state_path: Path | None = None):
        """Initialize StateManager.

        Args:
            state_path: Path to state file directory.
        """
        if state_path is None:
            state_path = Path.cwd() / "data" / "dashboard"

        self.state_path = Path(state_path)
        self._acknowledged_file = self.state_path / "acknowledged.json"
        self._ensure_state_dir()

    def _ensure_state_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_path.mkdir(parents=True, exist_ok=True)

    def acknowledge_anomaly(
        self,
        anomaly_id: str,
        user: str = "dashboard_user",
    ) -> tuple[bool, datetime]:
        """Mark anomaly as acknowledged.

        Args:
            anomaly_id: ID of the anomaly to acknowledge.
            user: Optional user identifier.

        Returns:
            Tuple of (success, acknowledged_at).
        """
        acknowledged_at = datetime.now(timezone.utc)

        try:
            acknowledged = self._load_acknowledged()
            acknowledged[anomaly_id] = {
                "user": user,
                "acknowledged_at": acknowledged_at.isoformat(),
            }
            self._save_acknowledged(acknowledged)
            return True, acknowledged_at

        except Exception:
            return False, acknowledged_at

    def unacknowledge_anomaly(self, anomaly_id: str) -> bool:
        """Remove acknowledgment from anomaly.

        Args:
            anomaly_id: ID of the anomaly.

        Returns:
            True if removed, False otherwise.
        """
        try:
            acknowledged = self._load_acknowledged()
            if anomaly_id in acknowledged:
                del acknowledged[anomaly_id]
                self._save_acknowledged(acknowledged)
                return True
            return False

        except Exception:
            return False

    def get_acknowledged_ids(self) -> set[str]:
        """Get set of acknowledged anomaly IDs.

        Returns:
            Set of anomaly ID strings.
        """
        acknowledged = self._load_acknowledged()
        return set(acknowledged.keys())

    def is_acknowledged(self, anomaly_id: str) -> bool:
        """Check if an anomaly is acknowledged.

        Args:
            anomaly_id: ID of the anomaly.

        Returns:
            True if acknowledged, False otherwise.
        """
        return anomaly_id in self.get_acknowledged_ids()

    def get_acknowledgment_details(
        self,
        anomaly_id: str,
    ) -> dict[str, Any] | None:
        """Get acknowledgment details for an anomaly.

        Args:
            anomaly_id: ID of the anomaly.

        Returns:
            Dict with user and acknowledged_at, or None if not acknowledged.
        """
        acknowledged = self._load_acknowledged()
        return acknowledged.get(anomaly_id)

    def clear_acknowledgments(self) -> int:
        """Clear all acknowledgments (for testing).

        Returns:
            Number of acknowledgments cleared.
        """
        acknowledged = self._load_acknowledged()
        count = len(acknowledged)
        self._save_acknowledged({})
        return count

    def _load_acknowledged(self) -> dict[str, Any]:
        """Load acknowledged anomalies from file."""
        if not self._acknowledged_file.exists():
            return {}

        try:
            with open(self._acknowledged_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}

    def _save_acknowledged(self, acknowledged: dict[str, Any]) -> None:
        """Save acknowledged anomalies to file."""
        with open(self._acknowledged_file, "w", encoding="utf-8") as f:
            json.dump(acknowledged, f, indent=2)

    def save_view_preference(self, view: str) -> None:
        """Save user's preferred view.

        Args:
            view: View name (executive, engineer, compliance).
        """
        prefs_file = self.state_path / "preferences.json"
        prefs = self._load_preferences()
        prefs["view"] = view
        prefs["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(prefs_file, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)

    def get_view_preference(self) -> str:
        """Get user's preferred view.

        Returns:
            View name (defaults to 'executive').
        """
        prefs = self._load_preferences()
        return prefs.get("view", "executive")

    def _load_preferences(self) -> dict[str, Any]:
        """Load user preferences from file."""
        prefs_file = self.state_path / "preferences.json"

        if not prefs_file.exists():
            return {}

        try:
            with open(prefs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}
