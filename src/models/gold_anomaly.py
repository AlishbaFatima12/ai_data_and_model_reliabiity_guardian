"""Gold Tier Anomaly Models.

This module defines anomaly types for Gold Tier validation:
- ModelHealthAnomaly: Model health issues (ML-001 to ML-008)
- EthicsAnomaly: Ethics and bias violations (ET-001 to ET-008)
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel


class DriftType(str, Enum):
    """Type of drift detected in model monitoring."""

    PREDICTION = "prediction"  # Output distribution shift
    FEATURE = "feature"  # Input feature distribution shift
    CONCEPT = "concept"  # Underlying relationship change
    LABEL = "label"  # Target variable distribution shift


class FairnessMetric(str, Enum):
    """Fairness metrics for bias detection."""

    DEMOGRAPHIC_PARITY = "demographic_parity"  # Equal positive rates across groups
    EQUALIZED_ODDS = "equalized_odds"  # Equal TPR/FPR across groups
    PREDICTIVE_PARITY = "predictive_parity"  # Equal precision across groups
    CALIBRATION = "calibration"  # Equal calibration across groups
    INDIVIDUAL_FAIRNESS = "individual_fairness"  # Similar individuals treated similarly


class ProtectedAttribute(str, Enum):
    """Protected attributes for bias monitoring."""

    AGE = "age"
    GENDER = "gender"
    RACE = "race"
    ETHNICITY = "ethnicity"
    DISABILITY = "disability"
    RELIGION = "religion"
    NATIONALITY = "nationality"
    MARITAL_STATUS = "marital_status"


class DriftMetrics(BaseModel):
    """Metrics for drift detection."""

    psi: float | None = Field(None, ge=0, description="Population Stability Index")
    kl_divergence: float | None = Field(None, ge=0, description="KL Divergence")
    js_divergence: float | None = Field(None, ge=0, le=1, description="Jensen-Shannon Divergence")
    wasserstein_distance: float | None = Field(None, ge=0, description="Wasserstein Distance")
    chi_squared: float | None = Field(None, ge=0, description="Chi-squared statistic")
    ks_statistic: float | None = Field(None, ge=0, le=1, description="Kolmogorov-Smirnov statistic")


class ModelHealthAnomaly(BaseModel):
    """Records model health issues (ML-001 through ML-008).

    Layer 5: Model Health Monitoring

    Attributes:
        id: Unique anomaly identifier
        failure_code: ML-001 through ML-008
        severity: Based on impact assessment
        model_id: Model identifier
        model_version: Model version string
        model_name: Human-readable model name
        drift_type: Type of drift if applicable
        drift_metrics: Quantitative drift measurements
        baseline_period: Reference period for comparison
        current_period: Current evaluation period
        affected_features: Features exhibiting drift
        timestamp: Detection time
        explanation: Human-readable description
        recommended_action: Suggested remediation
        details: Additional context
    """

    id: str = Field(..., description="Unique anomaly identifier")
    failure_code: FailureCode = Field(..., description="ML-001 through ML-008")
    severity: SeverityLevel = Field(..., description="Based on impact assessment")
    model_id: str = Field(..., description="Model identifier")
    model_version: str = Field(..., description="Model version string")
    model_name: str = Field(..., description="Human-readable model name")
    drift_type: DriftType | None = Field(None, description="Type of drift if applicable")
    drift_metrics: DriftMetrics | None = Field(None, description="Quantitative drift measurements")
    baseline_period: str | None = Field(None, description="Reference period for comparison")
    current_period: str | None = Field(None, description="Current evaluation period")
    affected_features: list[str] = Field(default_factory=list, description="Features exhibiting drift")
    confidence_score: float | None = Field(None, ge=0, le=1, description="Current model confidence")
    error_rate: float | None = Field(None, ge=0, le=1, description="Current error rate")
    latency_ms: float | None = Field(None, ge=0, description="Inference latency in ms")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection time")
    explanation: str = Field(..., description="Human-readable description")
    recommended_action: str | None = Field(None, description="Suggested remediation")
    blocking: bool = Field(default=False, description="Blocks model serving")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @property
    def is_model_health_anomaly(self) -> bool:
        """Return True if this is a model health anomaly."""
        return self.failure_code.value.startswith("ML-")

    @property
    def requires_retraining(self) -> bool:
        """Check if this anomaly indicates retraining is needed."""
        retraining_codes = [
            FailureCode.PREDICTION_DRIFT,
            FailureCode.FEATURE_DRIFT,
            FailureCode.MODEL_STALENESS,
            FailureCode.RETRAINING_NEEDED,
        ]
        return self.failure_code in retraining_codes and self.severity == SeverityLevel.CRITICAL


class FairnessViolation(BaseModel):
    """Details about a fairness metric violation."""

    metric: FairnessMetric = Field(..., description="Fairness metric")
    protected_attribute: ProtectedAttribute = Field(..., description="Protected attribute")
    group_a: str = Field(..., description="First comparison group")
    group_b: str = Field(..., description="Second comparison group")
    group_a_value: float = Field(..., description="Metric value for group A")
    group_b_value: float = Field(..., description="Metric value for group B")
    disparity_ratio: float = Field(..., description="Ratio of group values")
    threshold: float = Field(..., description="Acceptable threshold")


class EthicsAnomaly(BaseModel):
    """Records ethics and bias violations (ET-001 through ET-008).

    Layer 6: Ethics & Bias Monitoring

    Attributes:
        id: Unique anomaly identifier
        failure_code: ET-001 through ET-008
        severity: Based on impact and regulatory risk
        model_id: Model identifier (if model-related)
        dataset_id: Dataset identifier (if data-related)
        fairness_violations: Specific fairness metric violations
        affected_groups: Demographic groups impacted
        protected_attributes: Protected attributes involved
        sample_size: Number of records analyzed
        bias_score: Overall bias score (0-100)
        timestamp: Detection time
        explanation: Human-readable description
        regulatory_references: Relevant regulations
        remediation_steps: Suggested actions
        details: Additional context
    """

    id: str = Field(..., description="Unique anomaly identifier")
    failure_code: FailureCode = Field(..., description="ET-001 through ET-008")
    severity: SeverityLevel = Field(..., description="Based on impact and regulatory risk")
    model_id: str | None = Field(None, description="Model identifier if model-related")
    dataset_id: str | None = Field(None, description="Dataset identifier if data-related")
    fairness_violations: list[FairnessViolation] = Field(
        default_factory=list, description="Specific fairness metric violations"
    )
    affected_groups: list[str] = Field(default_factory=list, description="Demographic groups impacted")
    protected_attributes: list[ProtectedAttribute] = Field(
        default_factory=list, description="Protected attributes involved"
    )
    sample_size: int | None = Field(None, ge=0, description="Number of records analyzed")
    bias_score: float | None = Field(None, ge=0, le=100, description="Overall bias score")
    explainability_score: float | None = Field(None, ge=0, le=100, description="Explainability score")
    pii_fields_exposed: list[str] = Field(default_factory=list, description="PII fields at risk")
    consent_scope: str | None = Field(None, description="Consent scope that may be violated")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection time")
    explanation: str = Field(..., description="Human-readable description")
    regulatory_references: list[str] = Field(
        default_factory=list, description="Relevant regulations (GDPR, CCPA, etc.)"
    )
    remediation_steps: list[str] = Field(default_factory=list, description="Suggested actions")
    blocking: bool = Field(default=False, description="Blocks deployment/usage")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @property
    def is_ethics_anomaly(self) -> bool:
        """Return True if this is an ethics anomaly."""
        return self.failure_code.value.startswith("ET-")

    @property
    def is_regulatory_risk(self) -> bool:
        """Check if this anomaly poses regulatory risk."""
        regulatory_codes = [
            FailureCode.CONSENT_VIOLATION,
            FailureCode.PII_EXPOSURE_RISK,
            FailureCode.COMPLIANCE_BREACH,
        ]
        return self.failure_code in regulatory_codes

    @property
    def requires_immediate_action(self) -> bool:
        """Check if immediate action is required."""
        return self.severity == SeverityLevel.CRITICAL and self.is_regulatory_risk


# Type alias for any Gold tier anomaly
GoldAnomaly = ModelHealthAnomaly | EthicsAnomaly


class GoldAnomalyCount(BaseModel):
    """Counts of anomalies by layer."""

    model_health: int = Field(default=0, ge=0, description="Active model health anomalies")
    ethics: int = Field(default=0, ge=0, description="Active ethics anomalies")

    @property
    def total(self) -> int:
        """Return total anomaly count."""
        return self.model_health + self.ethics
