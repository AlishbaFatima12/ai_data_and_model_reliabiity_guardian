"""Utility health skill - Health score aggregation."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.models.anomaly import Anomaly
from src.models.health_score import HealthScore, ComponentScore
from src.lib.constants import FailureCode


class HealthConfig(BaseModel):
    """Configuration for health calculation."""

    state_file: str = Field(
        default="data/state/health.json",
        description="Path to health state file",
    )
    history_size: int = Field(
        default=100,
        ge=1,
        description="Number of historical scores to keep",
    )


class HealthSkill:
    """Utility skill for calculating aggregate health scores (FR-009).

    Aggregates anomaly data into an overall health score.
    """

    name: str = "util.health"

    # Component weights for health calculation
    COMPONENT_WEIGHTS = {
        "completeness": 0.25,  # Null/missing values
        "accuracy": 0.25,      # Type and range issues
        "consistency": 0.20,   # Format and duplicate issues
        "integrity": 0.15,     # Encoding issues
        "timeliness": 0.15,    # Count and general issues
    }

    # Map failure codes to components
    FAILURE_TO_COMPONENT = {
        FailureCode.RECORD_COUNT_MISMATCH: "timeliness",
        FailureCode.NULL_VALUE_DETECTED: "completeness",
        FailureCode.TYPE_MISMATCH: "accuracy",
        FailureCode.RANGE_VIOLATION: "accuracy",
        FailureCode.FORMAT_VIOLATION: "consistency",
        FailureCode.DUPLICATE_DETECTED: "consistency",
        FailureCode.ENCODING_ERROR: "integrity",
        FailureCode.SCHEMA_VIOLATION: "integrity",
    }

    def __init__(self, config: HealthConfig | None = None):
        """Initialize the health skill.

        Args:
            config: Configuration for health calculation.
        """
        self.config = config or HealthConfig()
        self._current_score: HealthScore | None = None

    def calculate(
        self,
        anomalies: list[Anomaly],
        total_records: int,
        previous_score: float | None = None,
    ) -> HealthScore:
        """Calculate health score from anomalies.

        Args:
            anomalies: List of detected anomalies.
            total_records: Total number of records validated.
            previous_score: Previous overall score for trend calculation.

        Returns:
            Calculated HealthScore.
        """
        if not anomalies:
            # Perfect health
            return HealthScore(
                overall_score=100.0,
                component_scores={},
                trend="stable" if previous_score is None else (
                    "improving" if (previous_score or 0) < 100 else "stable"
                ),
                active_anomalies=0,
            )

        # Group anomalies by component
        component_anomalies: dict[str, list[Anomaly]] = {
            comp: [] for comp in self.COMPONENT_WEIGHTS
        }

        for anomaly in anomalies:
            component = self.FAILURE_TO_COMPONENT.get(anomaly.failure_code, "timeliness")
            component_anomalies[component].append(anomaly)

        # Calculate component scores
        component_scores: dict[str, ComponentScore] = {}

        for component, weight in self.COMPONENT_WEIGHTS.items():
            comp_anomalies = component_anomalies.get(component, [])
            if not comp_anomalies:
                score = 100.0
                anomaly_count = 0
            else:
                # Calculate component score based on anomaly severity
                penalty = sum(
                    self._anomaly_penalty(a, total_records)
                    for a in comp_anomalies
                )
                score = max(0.0, 100.0 - penalty)
                anomaly_count = len(comp_anomalies)

            component_scores[component] = ComponentScore(
                name=component,
                score=score,
                weight=weight,
                anomaly_count=anomaly_count,
            )

        # Calculate overall score
        health = HealthScore.calculate(
            component_scores=component_scores,
            active_anomalies=len(anomalies),
            previous_score=previous_score,
        )

        self._current_score = health
        return health

    def _anomaly_penalty(self, anomaly: Anomaly, total_records: int) -> float:
        """Calculate health penalty for an anomaly.

        Args:
            anomaly: The anomaly to calculate penalty for.
            total_records: Total records in the batch.

        Returns:
            Penalty value (0-100).
        """
        # Base penalty on severity
        base_penalty = {
            "CRITICAL": 30.0,
            "WARNING": 15.0,
            "INFO": 5.0,
        }.get(anomaly.severity.value, 10.0)

        # Scale by affected percentage
        if total_records > 0 and anomaly.affected_count > 0:
            affected_pct = anomaly.affected_count / total_records
            # More affected = higher penalty
            scale = min(2.0, 1.0 + affected_pct)
            return base_penalty * scale

        return base_penalty

    def load_state(self) -> HealthScore | None:
        """Load health state from file.

        Returns:
            Loaded HealthScore or None if file doesn't exist.
        """
        state_path = Path(self.config.state_file)
        if not state_path.exists():
            return None

        try:
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct HealthScore
            component_scores = {}
            for name, comp_data in data.get("component_scores", {}).items():
                component_scores[name] = ComponentScore(**comp_data)

            # Convert history
            history = []
            for entry in data.get("history", []):
                if isinstance(entry, dict):
                    ts = datetime.fromisoformat(entry["timestamp"])
                    history.append((ts, entry["score"]))

            score = HealthScore(
                overall_score=data.get("overall_score", 100.0),
                component_scores=component_scores,
                trend=data.get("trend", "stable"),
                active_anomalies=data.get("active_anomalies", 0),
                last_updated=datetime.fromisoformat(data["last_updated"]) if "last_updated" in data else datetime.now(timezone.utc),
                batches_evaluated=data.get("batches_evaluated", 0),
                history=history,
            )

            self._current_score = score
            return score

        except Exception:
            return None

    def save_state(self, health: HealthScore | None = None) -> bool:
        """Save health state to file.

        Args:
            health: HealthScore to save (uses current if not provided).

        Returns:
            True if save was successful.
        """
        score = health or self._current_score
        if score is None:
            return False

        state_path = Path(self.config.state_file)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = score.to_dict()
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception:
            return False

    def get_current_score(self) -> HealthScore:
        """Get the current health score.

        Returns:
            Current HealthScore (loads from file if needed).
        """
        if self._current_score is None:
            loaded = self.load_state()
            if loaded:
                return loaded
            return HealthScore.create_initial()
        return self._current_score

    def update_from_validation(
        self,
        anomalies: list[Anomaly],
        total_records: int,
    ) -> HealthScore:
        """Update health score from a validation result.

        Args:
            anomalies: Anomalies from the latest validation.
            total_records: Total records validated.

        Returns:
            Updated HealthScore.
        """
        # Load previous state
        previous = self.load_state()
        previous_score = previous.overall_score if previous else None
        batches = (previous.batches_evaluated if previous else 0) + 1

        # Calculate new score
        health = self.calculate(
            anomalies=anomalies,
            total_records=total_records,
            previous_score=previous_score,
        )

        # Update history and metadata
        health.batches_evaluated = batches
        health.update_history(max_history=self.config.history_size)

        # Save state
        self.save_state(health)

        return health
