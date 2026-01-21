"""ValidationResult model for DMRG-FTE."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.anomaly import Anomaly
from src.models.silver_anomaly import (
    SchemaAnomaly,
    BusinessLogicAnomaly,
    FreshnessAnomaly,
    SilverAnomaly,
    AnomalyCount,
)
from src.models.gold_anomaly import (
    ModelHealthAnomaly,
    EthicsAnomaly,
    GoldAnomaly,
    GoldAnomalyCount,
)
from src.lib.constants import SeverityLevel


class ValidationResult(BaseModel):
    """Result of validating a data batch.

    Per spec: Contains pass/fail status, list of anomalies with failure codes,
    health score, and execution metadata.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str = Field(..., description="ID of the validated batch")
    passed: bool = Field(..., description="Whether validation passed (no CRITICAL anomalies)")
    anomalies: list[Anomaly] = Field(
        default_factory=list,
        description="List of detected anomalies",
    )
    health_score: float = Field(
        ge=0.0, le=100.0,
        description="Overall health score (0-100, higher is better)",
    )
    duration_ms: float = Field(
        ge=0.0,
        description="Validation duration in milliseconds",
    )
    skills_executed: list[str] = Field(
        default_factory=list,
        description="List of skill names that were executed",
    )
    validated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When validation completed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the validation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @property
    def anomaly_count(self) -> int:
        """Get total count of anomalies."""
        return len(self.anomalies)

    @property
    def critical_anomalies(self) -> list[Anomaly]:
        """Get list of CRITICAL severity anomalies."""
        return [a for a in self.anomalies if a.severity == SeverityLevel.CRITICAL]

    @property
    def warning_anomalies(self) -> list[Anomaly]:
        """Get list of WARNING severity anomalies."""
        return [a for a in self.anomalies if a.severity == SeverityLevel.WARNING]

    @property
    def info_anomalies(self) -> list[Anomaly]:
        """Get list of INFO severity anomalies."""
        return [a for a in self.anomalies if a.severity == SeverityLevel.INFO]

    @property
    def has_critical(self) -> bool:
        """Check if there are any CRITICAL anomalies."""
        return len(self.critical_anomalies) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any WARNING anomalies."""
        return len(self.warning_anomalies) > 0

    @property
    def requires_alerts(self) -> bool:
        """Check if any anomalies require alerts."""
        return any(a.requires_alert for a in self.anomalies)

    @property
    def requires_quarantine(self) -> bool:
        """Check if any records require quarantine."""
        return any(a.requires_quarantine for a in self.anomalies)

    @property
    def records_to_quarantine(self) -> set[int]:
        """Get set of record indices that need quarantine."""
        records: set[int] = set()
        for anomaly in self.anomalies:
            if anomaly.requires_quarantine:
                records.update(anomaly.affected_records)
        return records

    @classmethod
    def create(
        cls,
        batch_id: str,
        anomalies: list[Anomaly],
        health_score: float,
        duration_ms: float,
        skills_executed: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> "ValidationResult":
        """Create a validation result.

        Automatically determines passed status based on anomaly severities.

        Args:
            batch_id: ID of the validated batch.
            anomalies: List of detected anomalies.
            health_score: Calculated health score.
            duration_ms: Validation duration.
            skills_executed: List of executed skill names.
            metadata: Additional metadata.

        Returns:
            New ValidationResult instance.
        """
        # Validation passes if no CRITICAL anomalies
        passed = not any(a.severity == SeverityLevel.CRITICAL for a in anomalies)

        return cls(
            batch_id=batch_id,
            passed=passed,
            anomalies=anomalies,
            health_score=health_score,
            duration_ms=duration_ms,
            skills_executed=skills_executed,
            metadata=metadata or {},
        )

    def format_summary(self) -> str:
        """Format a human-readable summary of the result.

        Returns:
            Summary string.
        """
        status = "PASSED" if self.passed else "FAILED"
        critical = len(self.critical_anomalies)
        warning = len(self.warning_anomalies)
        info = len(self.info_anomalies)

        return (
            f"Validation {status} | Health: {self.health_score:.1f}/100 | "
            f"Anomalies: {critical} CRITICAL, {warning} WARNING, {info} INFO | "
            f"Duration: {self.duration_ms:.1f}ms"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")


class SilverValidationResult(BaseModel):
    """Result of Silver tier validation.

    Per spec: Contains results from all three Silver layers:
    - Layer 2: Schema & Contract Enforcement
    - Layer 3: Business Logic Validation
    - Layer 4: Freshness & SLA Monitoring
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str = Field(..., description="ID of the validated batch")
    passed: bool = Field(..., description="Whether validation passed (no blocking issues)")
    blocked: bool = Field(default=False, description="Whether data is blocked from downstream")

    # Layer-specific anomalies
    schema_anomalies: list[SchemaAnomaly] = Field(
        default_factory=list,
        description="Layer 2: Schema/contract violations",
    )
    business_logic_anomalies: list[BusinessLogicAnomaly] = Field(
        default_factory=list,
        description="Layer 3: Business rule violations",
    )
    freshness_anomalies: list[FreshnessAnomaly] = Field(
        default_factory=list,
        description="Layer 4: Freshness/SLA violations",
    )

    # Aggregate scores
    schema_score: float = Field(ge=0.0, le=100.0, description="Layer 2 health score")
    business_logic_score: float = Field(ge=0.0, le=100.0, description="Layer 3 health score")
    freshness_score: float = Field(ge=0.0, le=100.0, description="Layer 4 health score")
    overall_score: float = Field(ge=0.0, le=100.0, description="Combined Silver tier score")

    # Execution metadata
    duration_ms: float = Field(ge=0.0, description="Total validation duration in milliseconds")
    skills_executed: list[str] = Field(
        default_factory=list,
        description="List of Silver skill names that were executed",
    )
    validated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When validation completed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the validation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @property
    def anomaly_counts(self) -> AnomalyCount:
        """Get counts of anomalies by layer."""
        return AnomalyCount(
            schema=len(self.schema_anomalies),
            business_logic=len(self.business_logic_anomalies),
            freshness=len(self.freshness_anomalies),
        )

    @property
    def total_anomalies(self) -> int:
        """Get total count of all anomalies."""
        return self.anomaly_counts.total

    @property
    def all_anomalies(self) -> list[SilverAnomaly]:
        """Get all anomalies across all layers."""
        return self.schema_anomalies + self.business_logic_anomalies + self.freshness_anomalies

    @property
    def critical_schema_anomalies(self) -> list[SchemaAnomaly]:
        """Get CRITICAL schema anomalies."""
        return [a for a in self.schema_anomalies if a.severity == SeverityLevel.CRITICAL]

    @property
    def critical_business_logic_anomalies(self) -> list[BusinessLogicAnomaly]:
        """Get CRITICAL business logic anomalies."""
        return [a for a in self.business_logic_anomalies if a.severity == SeverityLevel.CRITICAL]

    @property
    def critical_freshness_anomalies(self) -> list[FreshnessAnomaly]:
        """Get CRITICAL freshness anomalies."""
        return [a for a in self.freshness_anomalies if a.severity == SeverityLevel.CRITICAL]

    @property
    def blocking_anomalies(self) -> list[SchemaAnomaly]:
        """Get anomalies that block downstream processing."""
        return [a for a in self.schema_anomalies if a.blocking]

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are any blocking schema issues."""
        return len(self.blocking_anomalies) > 0

    @property
    def requires_alerts(self) -> bool:
        """Check if any anomalies require alerts (WARNING or CRITICAL)."""
        return any(
            a.severity in (SeverityLevel.WARNING, SeverityLevel.CRITICAL)
            for a in self.all_anomalies
        )

    @classmethod
    def create(
        cls,
        batch_id: str,
        schema_anomalies: list[SchemaAnomaly],
        business_logic_anomalies: list[BusinessLogicAnomaly],
        freshness_anomalies: list[FreshnessAnomaly],
        schema_score: float,
        business_logic_score: float,
        freshness_score: float,
        duration_ms: float,
        skills_executed: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> "SilverValidationResult":
        """Create a Silver validation result.

        Automatically determines passed/blocked status based on anomalies.

        Args:
            batch_id: ID of the validated batch.
            schema_anomalies: Layer 2 anomalies.
            business_logic_anomalies: Layer 3 anomalies.
            freshness_anomalies: Layer 4 anomalies.
            schema_score: Layer 2 health score.
            business_logic_score: Layer 3 health score.
            freshness_score: Layer 4 health score.
            duration_ms: Validation duration.
            skills_executed: List of executed skill names.
            metadata: Additional metadata.

        Returns:
            New SilverValidationResult instance.
        """
        # Check for blocking schema anomalies
        blocking_schema = [a for a in schema_anomalies if a.blocking]
        blocked = len(blocking_schema) > 0

        # Validation passes if no CRITICAL anomalies across any layer
        has_critical = (
            any(a.severity == SeverityLevel.CRITICAL for a in schema_anomalies)
            or any(a.severity == SeverityLevel.CRITICAL for a in business_logic_anomalies)
            or any(a.severity == SeverityLevel.CRITICAL for a in freshness_anomalies)
        )
        passed = not has_critical

        # Calculate overall score (weighted average of layers)
        overall_score = (schema_score + business_logic_score + freshness_score) / 3.0

        return cls(
            batch_id=batch_id,
            passed=passed,
            blocked=blocked,
            schema_anomalies=schema_anomalies,
            business_logic_anomalies=business_logic_anomalies,
            freshness_anomalies=freshness_anomalies,
            schema_score=schema_score,
            business_logic_score=business_logic_score,
            freshness_score=freshness_score,
            overall_score=overall_score,
            duration_ms=duration_ms,
            skills_executed=skills_executed,
            metadata=metadata or {},
        )

    def format_summary(self) -> str:
        """Format a human-readable summary of the result.

        Returns:
            Summary string.
        """
        status = "PASSED" if self.passed else "FAILED"
        blocked_str = " [BLOCKED]" if self.blocked else ""
        counts = self.anomaly_counts

        return (
            f"Silver Validation {status}{blocked_str} | "
            f"Overall: {self.overall_score:.1f}/100 | "
            f"Schema: {counts.schema} | BizLogic: {counts.business_logic} | "
            f"Freshness: {counts.freshness} | Duration: {self.duration_ms:.1f}ms"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")


class GoldValidationResult(BaseModel):
    """Result of Gold tier validation.

    Per spec: Contains results from Gold tier layers:
    - Layer 5: Model Health Monitoring (ML-001 to ML-008)
    - Layer 6: Ethics & Bias Monitoring (ET-001 to ET-008)
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    model_id: str = Field(..., description="ID of the model being validated")
    passed: bool = Field(..., description="Whether validation passed (no blocking issues)")
    blocked: bool = Field(default=False, description="Whether model serving is blocked")

    # Layer-specific anomalies
    model_health_anomalies: list[ModelHealthAnomaly] = Field(
        default_factory=list,
        description="Layer 5: Model health issues",
    )
    ethics_anomalies: list[EthicsAnomaly] = Field(
        default_factory=list,
        description="Layer 6: Ethics/bias violations",
    )

    # Aggregate scores
    model_health_score: float = Field(ge=0.0, le=100.0, description="Layer 5 health score")
    ethics_score: float = Field(ge=0.0, le=100.0, description="Layer 6 health score")
    overall_score: float = Field(ge=0.0, le=100.0, description="Combined Gold tier score")

    # Execution metadata
    duration_ms: float = Field(ge=0.0, description="Total validation duration in milliseconds")
    skills_executed: list[str] = Field(
        default_factory=list,
        description="List of Gold skill names that were executed",
    )
    validated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When validation completed",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the validation",
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }

    @property
    def anomaly_counts(self) -> GoldAnomalyCount:
        """Get counts of anomalies by layer."""
        return GoldAnomalyCount(
            model_health=len(self.model_health_anomalies),
            ethics=len(self.ethics_anomalies),
        )

    @property
    def total_anomalies(self) -> int:
        """Get total count of all anomalies."""
        return self.anomaly_counts.total

    @property
    def all_anomalies(self) -> list[GoldAnomaly]:
        """Get all anomalies across all layers."""
        return self.model_health_anomalies + self.ethics_anomalies

    @property
    def critical_model_health_anomalies(self) -> list[ModelHealthAnomaly]:
        """Get CRITICAL model health anomalies."""
        return [a for a in self.model_health_anomalies if a.severity == SeverityLevel.CRITICAL]

    @property
    def critical_ethics_anomalies(self) -> list[EthicsAnomaly]:
        """Get CRITICAL ethics anomalies."""
        return [a for a in self.ethics_anomalies if a.severity == SeverityLevel.CRITICAL]

    @property
    def blocking_anomalies(self) -> list[GoldAnomaly]:
        """Get anomalies that block model serving."""
        blocking: list[GoldAnomaly] = []
        blocking.extend([a for a in self.model_health_anomalies if a.blocking])
        blocking.extend([a for a in self.ethics_anomalies if a.blocking])
        return blocking

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are any blocking issues."""
        return len(self.blocking_anomalies) > 0

    @property
    def has_regulatory_risk(self) -> bool:
        """Check if there are any regulatory risk anomalies."""
        return any(a.is_regulatory_risk for a in self.ethics_anomalies)

    @property
    def requires_alerts(self) -> bool:
        """Check if any anomalies require alerts (WARNING or CRITICAL)."""
        return any(
            a.severity in (SeverityLevel.WARNING, SeverityLevel.CRITICAL)
            for a in self.all_anomalies
        )

    @property
    def requires_retraining(self) -> bool:
        """Check if any model health anomalies indicate retraining is needed."""
        return any(a.requires_retraining for a in self.model_health_anomalies)

    @classmethod
    def create(
        cls,
        model_id: str,
        model_health_anomalies: list[ModelHealthAnomaly],
        ethics_anomalies: list[EthicsAnomaly],
        model_health_score: float,
        ethics_score: float,
        duration_ms: float,
        skills_executed: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> "GoldValidationResult":
        """Create a Gold validation result.

        Automatically determines passed/blocked status based on anomalies.

        Args:
            model_id: ID of the validated model.
            model_health_anomalies: Layer 5 anomalies.
            ethics_anomalies: Layer 6 anomalies.
            model_health_score: Layer 5 health score.
            ethics_score: Layer 6 health score.
            duration_ms: Validation duration.
            skills_executed: List of executed skill names.
            metadata: Additional metadata.

        Returns:
            New GoldValidationResult instance.
        """
        # Check for blocking anomalies
        blocking_health = [a for a in model_health_anomalies if a.blocking]
        blocking_ethics = [a for a in ethics_anomalies if a.blocking]
        blocked = len(blocking_health) > 0 or len(blocking_ethics) > 0

        # Validation passes if no CRITICAL anomalies across any layer
        has_critical = (
            any(a.severity == SeverityLevel.CRITICAL for a in model_health_anomalies)
            or any(a.severity == SeverityLevel.CRITICAL for a in ethics_anomalies)
        )
        passed = not has_critical

        # Calculate overall score (minimum of layer scores per Constitution 6.3)
        overall_score = min(model_health_score, ethics_score)

        return cls(
            model_id=model_id,
            passed=passed,
            blocked=blocked,
            model_health_anomalies=model_health_anomalies,
            ethics_anomalies=ethics_anomalies,
            model_health_score=model_health_score,
            ethics_score=ethics_score,
            overall_score=overall_score,
            duration_ms=duration_ms,
            skills_executed=skills_executed,
            metadata=metadata or {},
        )

    def format_summary(self) -> str:
        """Format a human-readable summary of the result.

        Returns:
            Summary string.
        """
        status = "PASSED" if self.passed else "FAILED"
        blocked_str = " [BLOCKED]" if self.blocked else ""
        counts = self.anomaly_counts

        return (
            f"Gold Validation {status}{blocked_str} | "
            f"Overall: {self.overall_score:.1f}/100 | "
            f"Model Health: {counts.model_health} | Ethics: {counts.ethics} | "
            f"Duration: {self.duration_ms:.1f}ms"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode="json")
