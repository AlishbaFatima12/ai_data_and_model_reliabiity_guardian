"""HealthCalculator service for computing aggregate health metrics.

Calculates overall health, per-layer health, and historical trends for display.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from src.models.health_score import HealthScore, ComponentScore, SilverTierHealthScore
from src.models.anomaly import Anomaly
from src.models.silver_anomaly import SchemaAnomaly, BusinessLogicAnomaly, FreshnessAnomaly
from src.lib.constants import SeverityLevel


# Color constants per Constitution 6.4
class HealthColors:
    """Health score color coding per Constitution 6.4."""

    EXCELLENT = "#00A67E"  # Green (90-100)
    GOOD = "#FFB020"       # Yellow (70-89)
    FAIR = "#FF8C00"       # Orange (50-69)
    POOR = "#DC3545"       # Red (0-49)

    @classmethod
    def get_color(cls, score: float) -> str:
        """Get color for a health score."""
        if score >= 90:
            return cls.EXCELLENT
        elif score >= 70:
            return cls.GOOD
        elif score >= 50:
            return cls.FAIR
        else:
            return cls.POOR


@dataclass
class OverallHealthInfo:
    """Overall health information for display."""

    score: float
    status: str
    trend: str
    trend_delta: float
    color: str


@dataclass
class LayerHealthInfo:
    """Per-layer health information for display."""

    name: str
    key: str
    tier: str
    score: float
    trend: str
    trend_delta: float
    anomaly_count: int
    color: str


@dataclass
class HealthHistoryPoint:
    """Single point in health history."""

    timestamp: datetime
    score: float


class HealthCalculator:
    """Calculates aggregate health metrics for dashboard display.

    Provides:
    - Overall health with status and trend
    - Per-layer health breakdown
    - Historical health data for sparklines
    """

    # Layer definitions per Constitution
    LAYERS = [
        {"name": "Data Validation", "key": "bronze", "tier": "Bronze"},
        {"name": "Schema Enforcement", "key": "schema", "tier": "Silver"},
        {"name": "Business Logic", "key": "business", "tier": "Silver"},
        {"name": "Freshness & SLA", "key": "freshness", "tier": "Silver"},
        {"name": "Model & Fairness", "key": "model", "tier": "Gold"},
    ]

    def __init__(self):
        """Initialize HealthCalculator."""
        self._history_cache: list[HealthHistoryPoint] = []

    def get_overall_health(self, health_state: HealthScore) -> OverallHealthInfo:
        """Get overall system health with trend.

        Args:
            health_state: Current HealthScore from data loader.

        Returns:
            OverallHealthInfo with score, status, trend, delta, and color.
        """
        score = health_state.overall_score

        # Determine status label
        if score >= 90:
            status = "Excellent"
        elif score >= 70:
            status = "Good"
        elif score >= 50:
            status = "Fair"
        elif score >= 30:
            status = "Poor"
        else:
            status = "Critical"

        # Get trend from health state
        trend = health_state.trend

        # Calculate trend delta from history
        trend_delta = 0.0
        if health_state.history and len(health_state.history) >= 2:
            # Compare current to previous
            prev_score = health_state.history[-2][1] if isinstance(health_state.history[-2], tuple) else health_state.history[-2].get("score", score)
            trend_delta = score - prev_score

        # Get color
        color = HealthColors.get_color(score)

        return OverallHealthInfo(
            score=score,
            status=status,
            trend=trend,
            trend_delta=trend_delta,
            color=color,
        )

    def get_layer_health(
        self,
        health_state: HealthScore,
        anomalies: list[Anomaly] | None = None,
        silver_health: SilverTierHealthScore | None = None,
    ) -> list[LayerHealthInfo]:
        """Get per-layer health breakdown.

        Args:
            health_state: Current HealthScore.
            anomalies: Optional list of anomalies for counts.
            silver_health: Optional Silver tier health state.

        Returns:
            List of LayerHealthInfo for each layer.
        """
        layers: list[LayerHealthInfo] = []

        # Count anomalies by layer
        anomaly_counts: dict[str, int] = {layer["key"]: 0 for layer in self.LAYERS}

        if anomalies:
            for anomaly in anomalies:
                # All current anomalies are Bronze tier
                anomaly_counts["bronze"] += 1

        # Update Silver tier counts if available
        if silver_health:
            anomaly_counts["schema"] = silver_health.schema_layer.anomaly_count
            anomaly_counts["business"] = silver_health.business_logic_layer.anomaly_count
            anomaly_counts["freshness"] = silver_health.freshness_layer.anomaly_count

        for layer_def in self.LAYERS:
            key = layer_def["key"]

            # Get component score if available
            component = health_state.component_scores.get(key)

            if component:
                score = component.score
                # Estimate trend based on anomaly count
                if component.anomaly_count == 0:
                    trend = "stable"
                    trend_delta = 0.0
                elif component.anomaly_count > 2:
                    trend = "degrading"
                    trend_delta = -5.0
                else:
                    trend = "stable"
                    trend_delta = 0.0
            elif silver_health and key == "schema":
                # Use Silver tier schema layer score
                score = silver_health.schema_layer.score
                trend = silver_health.trend if silver_health.schema_layer.anomaly_count > 0 else "stable"
                trend_delta = 0.0
            elif silver_health and key == "business":
                # Use Silver tier business logic layer score
                score = silver_health.business_logic_layer.score
                trend = silver_health.trend if silver_health.business_logic_layer.anomaly_count > 0 else "stable"
                trend_delta = 0.0
            elif silver_health and key == "freshness":
                # Use Silver tier freshness layer score
                score = silver_health.freshness_layer.score
                trend = silver_health.trend if silver_health.freshness_layer.anomaly_count > 0 else "stable"
                trend_delta = 0.0
            else:
                # Default to perfect health for unimplemented layers
                if key == "bronze":
                    # Bronze tier uses overall health
                    score = health_state.overall_score
                    trend = health_state.trend
                    trend_delta = 0.0
                else:
                    # Other layers not implemented yet
                    score = 100.0
                    trend = "stable"
                    trend_delta = 0.0

            layers.append(
                LayerHealthInfo(
                    name=layer_def["name"],
                    key=key,
                    tier=layer_def["tier"],
                    score=score,
                    trend=trend,
                    trend_delta=trend_delta,
                    anomaly_count=anomaly_counts.get(key, 0),
                    color=HealthColors.get_color(score),
                )
            )

        return layers

    def get_health_history(
        self,
        health_state: HealthScore,
        hours: int = 24,
    ) -> tuple[list[datetime], list[float]]:
        """Get health history for sparkline display.

        Args:
            health_state: Current HealthScore with history.
            hours: Number of hours of history (default 24, max 168).

        Returns:
            Tuple of (timestamps, scores) lists.
        """
        hours = min(hours, 168)  # Cap at 7 days

        timestamps: list[datetime] = []
        scores: list[float] = []

        if health_state.history:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=hours)

            for entry in health_state.history:
                # Handle both tuple and dict formats
                if isinstance(entry, tuple):
                    ts, score = entry
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                elif isinstance(entry, dict):
                    ts = entry.get("timestamp")
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    score = entry.get("score", 100.0)
                else:
                    continue

                if ts >= cutoff:
                    timestamps.append(ts)
                    scores.append(score)

        # If no history, generate placeholder with current score
        if not timestamps:
            now = datetime.now(timezone.utc)
            # Create a simple history line
            for i in range(min(hours, 24)):
                ts = now - timedelta(hours=hours - i - 1)
                timestamps.append(ts)
                scores.append(health_state.overall_score)

        return timestamps, scores

    def calculate_overall_from_layers(
        self,
        layer_health: list[LayerHealthInfo],
    ) -> float:
        """Calculate overall health as minimum of all layer scores.

        Per Constitution 6.3: Overall Health = Minimum(All Layer Scores)

        Args:
            layer_health: List of per-layer health info.

        Returns:
            Overall health score (0-100).
        """
        if not layer_health:
            return 100.0

        return min(layer.score for layer in layer_health)

    def get_severity_counts(
        self,
        anomalies: list[Anomaly],
    ) -> dict[str, int]:
        """Get anomaly counts by severity.

        Args:
            anomalies: List of anomalies.

        Returns:
            Dict with counts for CRITICAL, WARNING, INFO.
        """
        counts = {
            "CRITICAL": 0,
            "WARNING": 0,
            "INFO": 0,
        }

        for anomaly in anomalies:
            counts[anomaly.severity.value] += 1

        return counts
