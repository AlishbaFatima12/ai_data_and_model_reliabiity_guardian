"""HealthScore model for DMRG-FTE."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ComponentScore(BaseModel):
    """Score for a single component/dimension of health."""

    name: str = Field(..., description="Component name (e.g., 'completeness', 'accuracy')")
    score: float = Field(ge=0.0, le=100.0, description="Component score (0-100)")
    weight: float = Field(ge=0.0, le=1.0, default=1.0, description="Weight in overall calculation")
    anomaly_count: int = Field(ge=0, default=0, description="Number of anomalies affecting this component")


class HealthScore(BaseModel):
    """Overall health score for data quality.

    Per spec: Health score is 0-100, aggregated from component scores,
    with trend tracking over time.
    """

    overall_score: float = Field(
        ge=0.0, le=100.0,
        description="Overall health score (0-100, higher is better)",
    )
    component_scores: dict[str, ComponentScore] = Field(
        default_factory=dict,
        description="Breakdown by component/dimension",
    )
    trend: str = Field(
        default="stable",
        description="Trend direction (improving, stable, degrading)",
    )
    active_anomalies: int = Field(
        ge=0, default=0,
        description="Number of currently active anomalies",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the health score was last calculated",
    )
    batches_evaluated: int = Field(
        ge=0, default=0,
        description="Number of batches evaluated for this score",
    )
    history: list[tuple[datetime, float]] = Field(
        default_factory=list,
        description="Recent history of scores for trend calculation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def create_initial(cls) -> "HealthScore":
        """Create an initial health score (100% healthy).

        Returns:
            New HealthScore with perfect score.
        """
        return cls(
            overall_score=100.0,
            trend="stable",
            active_anomalies=0,
        )

    @classmethod
    def calculate(
        cls,
        component_scores: dict[str, ComponentScore],
        active_anomalies: int,
        previous_score: float | None = None,
    ) -> "HealthScore":
        """Calculate health score from component scores.

        Args:
            component_scores: Dictionary of component scores.
            active_anomalies: Count of active anomalies.
            previous_score: Previous overall score for trend calculation.

        Returns:
            New HealthScore instance.
        """
        if not component_scores:
            overall = 100.0
        else:
            # Weighted average of component scores
            total_weight = sum(c.weight for c in component_scores.values())
            if total_weight > 0:
                overall = sum(
                    c.score * c.weight for c in component_scores.values()
                ) / total_weight
            else:
                overall = 100.0

        # Determine trend
        if previous_score is not None:
            diff = overall - previous_score
            if diff > 1.0:
                trend = "improving"
            elif diff < -1.0:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return cls(
            overall_score=overall,
            component_scores=component_scores,
            trend=trend,
            active_anomalies=active_anomalies,
        )

    def update_history(self, max_history: int = 100) -> None:
        """Add current score to history.

        Args:
            max_history: Maximum history entries to keep.
        """
        self.history.append((self.last_updated, self.overall_score))
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]

    @property
    def is_healthy(self) -> bool:
        """Check if overall health is good (>=70)."""
        return self.overall_score >= 70.0

    @property
    def is_critical(self) -> bool:
        """Check if health is critical (<40)."""
        return self.overall_score < 40.0

    @property
    def status_label(self) -> str:
        """Get human-readable status label."""
        if self.overall_score >= 90:
            return "Excellent"
        elif self.overall_score >= 70:
            return "Good"
        elif self.overall_score >= 50:
            return "Fair"
        elif self.overall_score >= 30:
            return "Poor"
        else:
            return "Critical"

    def format_summary(self) -> str:
        """Format a human-readable summary.

        Returns:
            Summary string.
        """
        return (
            f"Health: {self.overall_score:.1f}/100 ({self.status_label}) | "
            f"Trend: {self.trend} | Active anomalies: {self.active_anomalies}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = self.model_dump(mode="json")
        # Convert history tuples
        data["history"] = [
            {"timestamp": ts.isoformat() if isinstance(ts, datetime) else ts, "score": score}
            for ts, score in self.history
        ]
        return data


class SilverLayerScore(BaseModel):
    """Score for a single Silver tier layer (Schema, Business Logic, Freshness)."""

    layer_name: str = Field(..., description="Layer name (schema, business_logic, freshness)")
    layer_number: int = Field(..., ge=2, le=4, description="Constitution layer number (2, 3, or 4)")
    score: float = Field(ge=0.0, le=100.0, description="Layer score (0-100)")
    weight: float = Field(ge=0.0, le=1.0, default=1.0, description="Weight in overall calculation")
    anomaly_count: int = Field(ge=0, default=0, description="Number of anomalies in this layer")
    critical_count: int = Field(ge=0, default=0, description="Number of CRITICAL anomalies")
    warning_count: int = Field(ge=0, default=0, description="Number of WARNING anomalies")
    last_check: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this layer was last checked",
    )

    @property
    def is_healthy(self) -> bool:
        """Check if layer is healthy (no critical anomalies and score >= 70)."""
        return self.critical_count == 0 and self.score >= 70.0


class SilverTierHealthScore(BaseModel):
    """Aggregated health score for all Silver tier layers.

    Per spec: Combines Layer 2 (Schema), Layer 3 (Business Logic),
    and Layer 4 (Freshness) into a unified health view.
    """

    overall_score: float = Field(
        ge=0.0, le=100.0,
        description="Overall Silver tier health score (0-100)",
    )
    schema_layer: SilverLayerScore = Field(
        ..., description="Layer 2: Schema & Contract Enforcement"
    )
    business_logic_layer: SilverLayerScore = Field(
        ..., description="Layer 3: Business Logic Validation"
    )
    freshness_layer: SilverLayerScore = Field(
        ..., description="Layer 4: Freshness & SLA Monitoring"
    )
    trend: str = Field(
        default="stable",
        description="Trend direction (improving, stable, degrading)",
    )
    total_anomalies: int = Field(ge=0, default=0, description="Total anomalies across all layers")
    blocking_issues: int = Field(ge=0, default=0, description="Number of blocking issues")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the health score was last calculated",
    )
    history: list[tuple[datetime, float]] = Field(
        default_factory=list,
        description="Recent history of scores for trend calculation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def create_initial(cls) -> "SilverTierHealthScore":
        """Create an initial Silver tier health score (100% healthy).

        Returns:
            New SilverTierHealthScore with perfect scores.
        """
        now = datetime.now(timezone.utc)
        return cls(
            overall_score=100.0,
            schema_layer=SilverLayerScore(
                layer_name="schema", layer_number=2, score=100.0, last_check=now
            ),
            business_logic_layer=SilverLayerScore(
                layer_name="business_logic", layer_number=3, score=100.0, last_check=now
            ),
            freshness_layer=SilverLayerScore(
                layer_name="freshness", layer_number=4, score=100.0, last_check=now
            ),
            trend="stable",
            total_anomalies=0,
            blocking_issues=0,
        )

    @classmethod
    def calculate(
        cls,
        schema_layer: SilverLayerScore,
        business_logic_layer: SilverLayerScore,
        freshness_layer: SilverLayerScore,
        previous_score: float | None = None,
    ) -> "SilverTierHealthScore":
        """Calculate Silver tier health from layer scores.

        Per Constitution 6.3: Overall Health = Minimum(All Layer Scores)

        Args:
            schema_layer: Layer 2 score.
            business_logic_layer: Layer 3 score.
            freshness_layer: Layer 4 score.
            previous_score: Previous overall score for trend calculation.

        Returns:
            New SilverTierHealthScore instance.
        """
        layers = [schema_layer, business_logic_layer, freshness_layer]

        # Per Constitution 6.3: Overall Health = Minimum(All Layer Scores)
        overall = min(layer.score for layer in layers)

        # Aggregate anomaly counts
        total_anomalies = sum(layer.anomaly_count for layer in layers)
        blocking_issues = sum(layer.critical_count for layer in layers)

        # Determine trend
        if previous_score is not None:
            diff = overall - previous_score
            if diff > 1.0:
                trend = "improving"
            elif diff < -1.0:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return cls(
            overall_score=overall,
            schema_layer=schema_layer,
            business_logic_layer=business_logic_layer,
            freshness_layer=freshness_layer,
            trend=trend,
            total_anomalies=total_anomalies,
            blocking_issues=blocking_issues,
        )

    @property
    def is_healthy(self) -> bool:
        """Check if all Silver layers are healthy."""
        return (
            self.schema_layer.is_healthy
            and self.business_logic_layer.is_healthy
            and self.freshness_layer.is_healthy
        )

    @property
    def is_critical(self) -> bool:
        """Check if any layer is in critical state."""
        return self.blocking_issues > 0 or self.overall_score < 40.0

    @property
    def status_label(self) -> str:
        """Get human-readable status label."""
        if self.overall_score >= 90:
            return "Excellent"
        elif self.overall_score >= 70:
            return "Good"
        elif self.overall_score >= 50:
            return "Fair"
        elif self.overall_score >= 30:
            return "Poor"
        else:
            return "Critical"

    def get_layer_by_number(self, layer_number: int) -> SilverLayerScore | None:
        """Get layer score by Constitution layer number."""
        layer_map = {
            2: self.schema_layer,
            3: self.business_logic_layer,
            4: self.freshness_layer,
        }
        return layer_map.get(layer_number)

    def format_summary(self) -> str:
        """Format a human-readable summary.

        Returns:
            Summary string.
        """
        return (
            f"Silver Health: {self.overall_score:.1f}/100 ({self.status_label}) | "
            f"Schema: {self.schema_layer.score:.1f} | "
            f"BizLogic: {self.business_logic_layer.score:.1f} | "
            f"Freshness: {self.freshness_layer.score:.1f} | "
            f"Blocking: {self.blocking_issues}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = self.model_dump(mode="json")
        data["history"] = [
            {"timestamp": ts.isoformat() if isinstance(ts, datetime) else ts, "score": score}
            for ts, score in self.history
        ]
        return data


class GoldLayerScore(BaseModel):
    """Score for a single Gold tier layer (Model Health, Ethics)."""

    layer_name: str = Field(..., description="Layer name (model_health, ethics)")
    layer_number: int = Field(..., ge=5, le=6, description="Constitution layer number (5 or 6)")
    score: float = Field(ge=0.0, le=100.0, description="Layer score (0-100)")
    weight: float = Field(ge=0.0, le=1.0, default=1.0, description="Weight in overall calculation")
    anomaly_count: int = Field(ge=0, default=0, description="Number of anomalies in this layer")
    critical_count: int = Field(ge=0, default=0, description="Number of CRITICAL anomalies")
    warning_count: int = Field(ge=0, default=0, description="Number of WARNING anomalies")
    models_monitored: int = Field(ge=0, default=0, description="Number of models being monitored")
    last_check: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this layer was last checked",
    )

    @property
    def is_healthy(self) -> bool:
        """Check if layer is healthy (no critical anomalies and score >= 70)."""
        return self.critical_count == 0 and self.score >= 70.0


class GoldTierHealthScore(BaseModel):
    """Aggregated health score for all Gold tier layers.

    Per spec: Combines Layer 5 (Model Health) and Layer 6 (Ethics & Bias)
    into a unified health view.
    """

    overall_score: float = Field(
        ge=0.0, le=100.0,
        description="Overall Gold tier health score (0-100)",
    )
    model_health_layer: GoldLayerScore = Field(
        ..., description="Layer 5: Model Health Monitoring"
    )
    ethics_layer: GoldLayerScore = Field(
        ..., description="Layer 6: Ethics & Bias Monitoring"
    )
    trend: str = Field(
        default="stable",
        description="Trend direction (improving, stable, degrading)",
    )
    total_anomalies: int = Field(ge=0, default=0, description="Total anomalies across all layers")
    blocking_issues: int = Field(ge=0, default=0, description="Number of blocking issues")
    models_at_risk: int = Field(ge=0, default=0, description="Models requiring attention")
    regulatory_alerts: int = Field(ge=0, default=0, description="Ethics issues with regulatory risk")
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the health score was last calculated",
    )
    history: list[tuple[datetime, float]] = Field(
        default_factory=list,
        description="Recent history of scores for trend calculation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @classmethod
    def create_initial(cls) -> "GoldTierHealthScore":
        """Create an initial Gold tier health score (100% healthy).

        Returns:
            New GoldTierHealthScore with perfect scores.
        """
        now = datetime.now(timezone.utc)
        return cls(
            overall_score=100.0,
            model_health_layer=GoldLayerScore(
                layer_name="model_health", layer_number=5, score=100.0, last_check=now
            ),
            ethics_layer=GoldLayerScore(
                layer_name="ethics", layer_number=6, score=100.0, last_check=now
            ),
            trend="stable",
            total_anomalies=0,
            blocking_issues=0,
            models_at_risk=0,
            regulatory_alerts=0,
        )

    @classmethod
    def calculate(
        cls,
        model_health_layer: GoldLayerScore,
        ethics_layer: GoldLayerScore,
        previous_score: float | None = None,
    ) -> "GoldTierHealthScore":
        """Calculate Gold tier health from layer scores.

        Per Constitution 6.3: Overall Health = Minimum(All Layer Scores)

        Args:
            model_health_layer: Layer 5 score.
            ethics_layer: Layer 6 score.
            previous_score: Previous overall score for trend calculation.

        Returns:
            New GoldTierHealthScore instance.
        """
        layers = [model_health_layer, ethics_layer]

        # Per Constitution 6.3: Overall Health = Minimum(All Layer Scores)
        overall = min(layer.score for layer in layers)

        # Aggregate anomaly counts
        total_anomalies = sum(layer.anomaly_count for layer in layers)
        blocking_issues = sum(layer.critical_count for layer in layers)

        # Determine trend
        if previous_score is not None:
            diff = overall - previous_score
            if diff > 1.0:
                trend = "improving"
            elif diff < -1.0:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return cls(
            overall_score=overall,
            model_health_layer=model_health_layer,
            ethics_layer=ethics_layer,
            trend=trend,
            total_anomalies=total_anomalies,
            blocking_issues=blocking_issues,
            models_at_risk=model_health_layer.critical_count,
            regulatory_alerts=ethics_layer.critical_count,
        )

    @property
    def is_healthy(self) -> bool:
        """Check if all Gold layers are healthy."""
        return self.model_health_layer.is_healthy and self.ethics_layer.is_healthy

    @property
    def is_critical(self) -> bool:
        """Check if any layer is in critical state."""
        return self.blocking_issues > 0 or self.overall_score < 40.0

    @property
    def has_regulatory_risk(self) -> bool:
        """Check if there are regulatory compliance risks."""
        return self.regulatory_alerts > 0

    @property
    def status_label(self) -> str:
        """Get human-readable status label."""
        if self.overall_score >= 90:
            return "Excellent"
        elif self.overall_score >= 70:
            return "Good"
        elif self.overall_score >= 50:
            return "Fair"
        elif self.overall_score >= 30:
            return "Poor"
        else:
            return "Critical"

    def get_layer_by_number(self, layer_number: int) -> GoldLayerScore | None:
        """Get layer score by Constitution layer number."""
        layer_map = {
            5: self.model_health_layer,
            6: self.ethics_layer,
        }
        return layer_map.get(layer_number)

    def format_summary(self) -> str:
        """Format a human-readable summary.

        Returns:
            Summary string.
        """
        return (
            f"Gold Health: {self.overall_score:.1f}/100 ({self.status_label}) | "
            f"Model Health: {self.model_health_layer.score:.1f} | "
            f"Ethics: {self.ethics_layer.score:.1f} | "
            f"Regulatory Alerts: {self.regulatory_alerts}"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = self.model_dump(mode="json")
        data["history"] = [
            {"timestamp": ts.isoformat() if isinstance(ts, datetime) else ts, "score": score}
            for ts, score in self.history
        ]
        return data
