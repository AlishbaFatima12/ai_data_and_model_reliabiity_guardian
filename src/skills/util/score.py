"""Utility score skill - Severity score calculation."""

from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import SeverityLevel, SEVERITY_THRESHOLDS


class ScoreWeights(BaseModel):
    """Weights for severity score calculation."""

    impact: float = Field(default=0.40, ge=0.0, le=1.0)
    frequency: float = Field(default=0.30, ge=0.0, le=1.0)
    recency: float = Field(default=0.30, ge=0.0, le=1.0)


class ScoreFactors(BaseModel):
    """Input factors for severity calculation."""

    impact: float = Field(ge=0.0, le=100.0, description="Impact score (0-100)")
    frequency: float = Field(ge=0.0, le=100.0, description="Frequency score (0-100)")
    recency: float = Field(ge=0.0, le=100.0, description="Recency score (0-100)")


class ScoreResult(BaseModel):
    """Result of severity score calculation."""

    score: float = Field(ge=0.0, le=100.0)
    severity: SeverityLevel
    factors: ScoreFactors
    weights: ScoreWeights


class ScoreSkill:
    """Utility skill for calculating severity scores (FR-008).

    Calculates severity score using the formula:
    Score = (Impact × 40) + (Frequency × 30) + (Recency × 30)
    """

    name: str = "util.score"

    def __init__(self, weights: ScoreWeights | None = None):
        """Initialize the score skill.

        Args:
            weights: Custom weights for score calculation.
        """
        self.weights = weights or ScoreWeights()

    def calculate(self, factors: ScoreFactors) -> ScoreResult:
        """Calculate severity score from factors.

        Args:
            factors: Input factors (impact, frequency, recency).

        Returns:
            ScoreResult with calculated score and severity.
        """
        score = (
            factors.impact * self.weights.impact +
            factors.frequency * self.weights.frequency +
            factors.recency * self.weights.recency
        )

        # Clamp to 0-100
        score = max(0.0, min(100.0, score))

        severity = self._determine_severity(score)

        return ScoreResult(
            score=score,
            severity=severity,
            factors=factors,
            weights=self.weights,
        )

    def calculate_from_anomaly_data(
        self,
        affected_count: int,
        total_count: int,
        occurrence_count: int = 1,
        hours_since_first: float = 0.0,
    ) -> ScoreResult:
        """Calculate severity score from anomaly statistics.

        Args:
            affected_count: Number of affected records.
            total_count: Total number of records.
            occurrence_count: Number of times this anomaly type occurred.
            hours_since_first: Hours since first occurrence.

        Returns:
            ScoreResult with calculated score and severity.
        """
        # Calculate impact based on affected percentage
        if total_count > 0:
            affected_pct = (affected_count / total_count) * 100
            impact = self._pct_to_impact_score(affected_pct)
        else:
            impact = 50.0  # Default

        # Calculate frequency based on occurrence count
        frequency = self._occurrence_to_frequency_score(occurrence_count)

        # Calculate recency (more recent = higher score)
        recency = self._hours_to_recency_score(hours_since_first)

        factors = ScoreFactors(
            impact=impact,
            frequency=frequency,
            recency=recency,
        )

        return self.calculate(factors)

    def _pct_to_impact_score(self, pct: float) -> float:
        """Convert affected percentage to impact score.

        Args:
            pct: Percentage of records affected.

        Returns:
            Impact score (0-100).
        """
        if pct >= 50:
            return 100.0
        elif pct >= 20:
            return 80.0
        elif pct >= 10:
            return 60.0
        elif pct >= 5:
            return 40.0
        elif pct >= 1:
            return 20.0
        else:
            return 10.0

    def _occurrence_to_frequency_score(self, count: int) -> float:
        """Convert occurrence count to frequency score.

        Args:
            count: Number of occurrences.

        Returns:
            Frequency score (0-100).
        """
        if count >= 100:
            return 100.0
        elif count >= 50:
            return 80.0
        elif count >= 20:
            return 60.0
        elif count >= 10:
            return 40.0
        elif count >= 5:
            return 20.0
        else:
            return 10.0

    def _hours_to_recency_score(self, hours: float) -> float:
        """Convert hours since first occurrence to recency score.

        More recent = higher score.

        Args:
            hours: Hours since first occurrence.

        Returns:
            Recency score (0-100).
        """
        if hours <= 1:
            return 100.0  # Very recent
        elif hours <= 6:
            return 80.0
        elif hours <= 24:
            return 60.0
        elif hours <= 72:
            return 40.0
        elif hours <= 168:  # 1 week
            return 20.0
        else:
            return 10.0

    def _determine_severity(self, score: float) -> SeverityLevel:
        """Determine severity level from score.

        Args:
            score: Severity score (0-100).

        Returns:
            Severity level.
        """
        for severity, (min_score, max_score) in SEVERITY_THRESHOLDS.items():
            if min_score <= score <= max_score:
                return severity

        # Default fallback
        if score >= 70:
            return SeverityLevel.CRITICAL
        elif score >= 40:
            return SeverityLevel.WARNING
        else:
            return SeverityLevel.INFO

    def update_weights(self, weights: ScoreWeights) -> None:
        """Update the scoring weights.

        Args:
            weights: New weights to use.

        Raises:
            ValueError: If weights don't sum to 1.0.
        """
        total = weights.impact + weights.frequency + weights.recency
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        self.weights = weights
