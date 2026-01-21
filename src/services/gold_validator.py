"""GoldValidator service for Gold tier validation.

This service orchestrates validation across Gold tier layers:
- Layer 5: Model Health Monitoring (ML-001 to ML-008)
- Layer 6: Ethics & Bias Monitoring (ET-001 to ET-008)
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import SeverityLevel
from src.models.gold_anomaly import (
    ModelHealthAnomaly,
    EthicsAnomaly,
    DriftMetrics,
    ProtectedAttribute,
)
from src.models.validation_result import GoldValidationResult
from src.models.health_score import GoldTierHealthScore, GoldLayerScore
from src.skills.gold.drift import detect_prediction_drift, detect_feature_drift
from src.skills.gold.model_health import (
    check_model_staleness,
    check_confidence_degradation,
    check_model_latency,
    check_error_rate,
    check_data_model_compatibility,
    check_retraining_needed,
)
from src.skills.gold.fairness import check_fairness_metrics, detect_bias
from src.skills.gold.ethics import (
    check_explainability,
    check_consent_compliance,
    check_pii_exposure,
    check_audit_trail,
    check_regulatory_compliance,
)

logger = structlog.get_logger(__name__)


class ModelMetrics:
    """Container for model metrics used in validation."""

    def __init__(
        self,
        model_id: str,
        model_name: str,
        model_version: str,
        model_type: str = "unknown",
        last_trained: datetime | None = None,
        baseline_predictions: list[float] | None = None,
        current_predictions: list[float] | None = None,
        baseline_features: dict[str, list[float]] | None = None,
        current_features: dict[str, list[float]] | None = None,
        baseline_confidence: float = 0.9,
        current_confidence: float = 0.9,
        baseline_latency_ms: float = 100.0,
        current_latency_ms: float = 100.0,
        baseline_error_rate: float = 0.05,
        current_error_rate: float = 0.05,
        expected_features: list[str] | None = None,
        actual_features: list[str] | None = None,
    ) -> None:
        """Initialize model metrics.

        Args:
            model_id: Unique model identifier.
            model_name: Human-readable model name.
            model_version: Model version string.
            model_type: Type of model (e.g., neural_network, random_forest).
            last_trained: When the model was last trained.
            baseline_predictions: Historical prediction values.
            current_predictions: Recent prediction values.
            baseline_features: Historical feature distributions.
            current_features: Current feature distributions.
            baseline_confidence: Historical average confidence.
            current_confidence: Current average confidence.
            baseline_latency_ms: Historical average latency.
            current_latency_ms: Current average latency.
            baseline_error_rate: Historical error rate.
            current_error_rate: Current error rate.
            expected_features: Features expected by the model.
            actual_features: Features present in the data.
        """
        self.model_id = model_id
        self.model_name = model_name
        self.model_version = model_version
        self.model_type = model_type
        self.last_trained = last_trained or datetime.utcnow()
        self.baseline_predictions = baseline_predictions or []
        self.current_predictions = current_predictions or []
        self.baseline_features = baseline_features or {}
        self.current_features = current_features or {}
        self.baseline_confidence = baseline_confidence
        self.current_confidence = current_confidence
        self.baseline_latency_ms = baseline_latency_ms
        self.current_latency_ms = current_latency_ms
        self.baseline_error_rate = baseline_error_rate
        self.current_error_rate = current_error_rate
        self.expected_features = expected_features or []
        self.actual_features = actual_features or []


class EthicsConfig:
    """Configuration for ethics validation."""

    def __init__(
        self,
        predictions: list[int] | None = None,
        actual_labels: list[int] | None = None,
        protected_attributes: dict[ProtectedAttribute, list[str]] | None = None,
        dataset_id: str | None = None,
        field_names: list[str] | None = None,
        data_sources: list[str] | None = None,
        consent_purposes: dict[str, list[str]] | None = None,
        intended_use: str = "model_training",
        has_encryption: bool = True,
        has_masking: bool = True,
        has_access_controls: bool = True,
        has_feature_importance: bool = False,
        has_shap_values: bool = False,
        has_local_explanations: bool = False,
        has_model_card: bool = False,
        has_prediction_logs: bool = True,
        has_input_logs: bool = True,
        has_decision_logs: bool = True,
        has_access_logs: bool = True,
        log_retention_days: int = 365,
        risk_level: str = "medium",
        applicable_regulations: list[str] | None = None,
        compliance_checks: dict[str, bool] | None = None,
    ) -> None:
        """Initialize ethics configuration.

        Args:
            predictions: Binary predictions for fairness checks.
            actual_labels: Actual labels for fairness metrics.
            protected_attributes: Dict mapping attribute to group labels.
            dataset_id: Dataset identifier.
            field_names: List of field names for PII detection.
            data_sources: List of data source names.
            consent_purposes: Dict mapping source to consented purposes.
            intended_use: Intended use of the data.
            has_encryption: Whether data is encrypted.
            has_masking: Whether PII is masked.
            has_access_controls: Whether access controls are in place.
            has_feature_importance: Whether feature importance is available.
            has_shap_values: Whether SHAP values are computed.
            has_local_explanations: Whether local explanations exist.
            has_model_card: Whether model card exists.
            has_prediction_logs: Whether predictions are logged.
            has_input_logs: Whether inputs are logged.
            has_decision_logs: Whether decisions are logged.
            has_access_logs: Whether access is logged.
            log_retention_days: Log retention period.
            risk_level: Model risk level.
            applicable_regulations: List of applicable regulations.
            compliance_checks: Dict of compliance checks.
        """
        self.predictions = predictions or []
        self.actual_labels = actual_labels
        self.protected_attributes = protected_attributes or {}
        self.dataset_id = dataset_id or "unknown"
        self.field_names = field_names or []
        self.data_sources = data_sources or []
        self.consent_purposes = consent_purposes or {}
        self.intended_use = intended_use
        self.has_encryption = has_encryption
        self.has_masking = has_masking
        self.has_access_controls = has_access_controls
        self.has_feature_importance = has_feature_importance
        self.has_shap_values = has_shap_values
        self.has_local_explanations = has_local_explanations
        self.has_model_card = has_model_card
        self.has_prediction_logs = has_prediction_logs
        self.has_input_logs = has_input_logs
        self.has_decision_logs = has_decision_logs
        self.has_access_logs = has_access_logs
        self.log_retention_days = log_retention_days
        self.risk_level = risk_level
        self.applicable_regulations = applicable_regulations or []
        self.compliance_checks = compliance_checks or {}


class GoldValidator:
    """Orchestrates Gold tier validation across all layers.

    Per spec: Validates models for health (Layer 5) and
    ethics/bias compliance (Layer 6).
    """

    def __init__(
        self,
        config_dir: Path | None = None,
    ) -> None:
        """Initialize the Gold validator.

        Args:
            config_dir: Directory containing configuration files.
        """
        self.config_dir = config_dir or Path("config/gold")

        # Health score tracking
        self._current_health: GoldTierHealthScore | None = None

        # Thresholds (can be loaded from config)
        self.psi_threshold = 0.25
        self.ks_threshold = 0.2
        self.staleness_warning_days = 60
        self.staleness_critical_days = 90
        self.confidence_threshold = 0.1
        self.latency_threshold = 2.0
        self.error_rate_threshold = 0.05
        self.fairness_threshold = 0.8

        logger.info(
            "gold_validator_initialized",
            config_dir=str(self.config_dir),
        )

    def validate(
        self,
        model_metrics: ModelMetrics,
        ethics_config: EthicsConfig | None = None,
    ) -> GoldValidationResult:
        """Run full Gold tier validation on a model.

        Executes both layers:
        1. Model Health validation (Layer 5)
        2. Ethics & Bias validation (Layer 6)

        Args:
            model_metrics: Model metrics for health checks.
            ethics_config: Ethics configuration (optional).

        Returns:
            GoldValidationResult with all anomalies and scores.
        """
        start_time = time.perf_counter()
        skills_executed: list[str] = []

        logger.info("gold_validation_started", model_id=model_metrics.model_id)

        # Layer 5: Model Health validation
        health_anomalies, health_score = self.validate_model_health(model_metrics)
        skills_executed.extend([
            "drift", "staleness", "confidence", "latency",
            "error_rate", "compatibility", "retraining"
        ])

        # Check for blocking health issues
        blocking_health = any(a.blocking for a in health_anomalies)

        # Layer 6: Ethics validation
        ethics_anomalies: list[EthicsAnomaly] = []
        ethics_score = 100.0

        if ethics_config is not None:
            ethics_anomalies, ethics_score = self.validate_ethics(
                model_metrics, ethics_config
            )
            skills_executed.extend([
                "fairness", "bias", "explainability",
                "consent", "pii", "audit", "compliance"
            ])

        duration_ms = (time.perf_counter() - start_time) * 1000

        result = GoldValidationResult.create(
            model_id=model_metrics.model_id,
            model_health_anomalies=health_anomalies,
            ethics_anomalies=ethics_anomalies,
            model_health_score=health_score,
            ethics_score=ethics_score,
            duration_ms=duration_ms,
            skills_executed=skills_executed,
            metadata={
                "model_name": model_metrics.model_name,
                "model_version": model_metrics.model_version,
                "blocked_by_health": blocking_health,
            },
        )

        # Update health score
        self._update_health_score(result)

        logger.info(
            "gold_validation_completed",
            model_id=model_metrics.model_id,
            passed=result.passed,
            blocked=result.blocked,
            total_anomalies=result.total_anomalies,
            duration_ms=duration_ms,
        )

        return result

    def validate_model_health(
        self, metrics: ModelMetrics
    ) -> tuple[list[ModelHealthAnomaly], float]:
        """Validate model health (Layer 5).

        Detects ML-001 through ML-008 issues.

        Args:
            metrics: Model metrics for validation.

        Returns:
            Tuple of (anomalies, health_score).
        """
        all_anomalies: list[ModelHealthAnomaly] = []

        logger.info("model_health_validation_started", model_id=metrics.model_id)

        # ML-001: Prediction drift
        if metrics.baseline_predictions and metrics.current_predictions:
            drift_result = detect_prediction_drift(
                model_id=metrics.model_id,
                model_name=metrics.model_name,
                model_version=metrics.model_version,
                baseline_predictions=metrics.baseline_predictions,
                current_predictions=metrics.current_predictions,
                psi_threshold=self.psi_threshold,
                ks_threshold=self.ks_threshold,
            )
            all_anomalies.extend(drift_result.anomalies)

        # ML-002: Feature drift
        if metrics.baseline_features and metrics.current_features:
            feature_drift_result = detect_feature_drift(
                model_id=metrics.model_id,
                model_name=metrics.model_name,
                model_version=metrics.model_version,
                baseline_features=metrics.baseline_features,
                current_features=metrics.current_features,
                psi_threshold=self.psi_threshold,
            )
            all_anomalies.extend(feature_drift_result.anomalies)

        # ML-003: Model staleness
        staleness_result = check_model_staleness(
            model_id=metrics.model_id,
            model_name=metrics.model_name,
            model_version=metrics.model_version,
            last_trained=metrics.last_trained,
            max_age_days=self.staleness_critical_days,
            warning_age_days=self.staleness_warning_days,
        )
        all_anomalies.extend(staleness_result.anomalies)

        # ML-004: Confidence degradation
        confidence_result = check_confidence_degradation(
            model_id=metrics.model_id,
            model_name=metrics.model_name,
            model_version=metrics.model_version,
            baseline_confidence=metrics.baseline_confidence,
            current_confidence=metrics.current_confidence,
            degradation_threshold=self.confidence_threshold,
        )
        all_anomalies.extend(confidence_result.anomalies)

        # ML-005: Latency spike
        latency_result = check_model_latency(
            model_id=metrics.model_id,
            model_name=metrics.model_name,
            model_version=metrics.model_version,
            baseline_latency_ms=metrics.baseline_latency_ms,
            current_latency_ms=metrics.current_latency_ms,
            spike_threshold=self.latency_threshold,
        )
        all_anomalies.extend(latency_result.anomalies)

        # ML-006: Error rate increase
        error_result = check_error_rate(
            model_id=metrics.model_id,
            model_name=metrics.model_name,
            model_version=metrics.model_version,
            baseline_error_rate=metrics.baseline_error_rate,
            current_error_rate=metrics.current_error_rate,
            increase_threshold=self.error_rate_threshold,
        )
        all_anomalies.extend(error_result.anomalies)

        # ML-007: Data-model compatibility
        if metrics.expected_features and metrics.actual_features:
            compat_result = check_data_model_compatibility(
                model_id=metrics.model_id,
                model_name=metrics.model_name,
                model_version=metrics.model_version,
                expected_features=metrics.expected_features,
                actual_features=metrics.actual_features,
            )
            all_anomalies.extend(compat_result.anomalies)

        # ML-008: Retraining needed (aggregates signals)
        has_drift = any(
            a.failure_code.value in ("ML-001", "ML-002")
            for a in all_anomalies
        )
        is_stale = any(
            a.failure_code.value == "ML-003"
            for a in all_anomalies
        )
        has_high_error = any(
            a.failure_code.value == "ML-006" and a.severity == SeverityLevel.CRITICAL
            for a in all_anomalies
        )

        # Calculate performance score from other metrics
        performance_score = 1.0 - metrics.current_error_rate

        retraining_result = check_retraining_needed(
            model_id=metrics.model_id,
            model_name=metrics.model_name,
            model_version=metrics.model_version,
            performance_score=performance_score,
            has_drift=has_drift,
            is_stale=is_stale,
            has_high_error_rate=has_high_error,
        )
        all_anomalies.extend(retraining_result.anomalies)

        # Calculate health score
        score = 100.0
        for anomaly in all_anomalies:
            if anomaly.severity == SeverityLevel.CRITICAL:
                score -= 25.0
            elif anomaly.severity == SeverityLevel.WARNING:
                score -= 10.0
            else:
                score -= 2.0
        score = max(0.0, min(100.0, score))

        logger.info(
            "model_health_validation_complete",
            model_id=metrics.model_id,
            anomaly_count=len(all_anomalies),
            score=score,
        )

        return all_anomalies, score

    def validate_ethics(
        self, metrics: ModelMetrics, config: EthicsConfig
    ) -> tuple[list[EthicsAnomaly], float]:
        """Validate ethics and bias (Layer 6).

        Detects ET-001 through ET-008 issues.

        Args:
            metrics: Model metrics.
            config: Ethics configuration.

        Returns:
            Tuple of (anomalies, ethics_score).
        """
        all_anomalies: list[EthicsAnomaly] = []

        logger.info("ethics_validation_started", model_id=metrics.model_id)

        # ET-001, ET-002, ET-003: Fairness and bias
        if config.predictions and config.protected_attributes:
            bias_result = detect_bias(
                model_id=metrics.model_id,
                predictions=config.predictions,
                actual=config.actual_labels,
                protected_attributes=config.protected_attributes,
                disparity_threshold=self.fairness_threshold,
            )
            all_anomalies.extend(bias_result.anomalies)

        # ET-004: Explainability
        explain_result = check_explainability(
            model_id=metrics.model_id,
            model_name=metrics.model_name,
            model_type=metrics.model_type,
            has_feature_importance=config.has_feature_importance,
            has_shap_values=config.has_shap_values,
            has_local_explanations=config.has_local_explanations,
            has_model_card=config.has_model_card,
        )
        all_anomalies.extend(explain_result.anomalies)

        # ET-005: Consent compliance
        if config.data_sources:
            consent_result = check_consent_compliance(
                model_id=metrics.model_id,
                dataset_id=config.dataset_id,
                data_sources=config.data_sources,
                consent_purposes=config.consent_purposes,
                intended_use=config.intended_use,
            )
            all_anomalies.extend(consent_result.anomalies)

        # ET-006: PII exposure
        if config.field_names:
            pii_result = check_pii_exposure(
                model_id=metrics.model_id,
                dataset_id=config.dataset_id,
                field_names=config.field_names,
                has_encryption=config.has_encryption,
                has_masking=config.has_masking,
                has_access_controls=config.has_access_controls,
            )
            all_anomalies.extend(pii_result.anomalies)

        # ET-007: Audit trail
        audit_result = check_audit_trail(
            model_id=metrics.model_id,
            has_prediction_logs=config.has_prediction_logs,
            has_input_logs=config.has_input_logs,
            has_decision_logs=config.has_decision_logs,
            has_access_logs=config.has_access_logs,
            log_retention_days=config.log_retention_days,
        )
        all_anomalies.extend(audit_result.anomalies)

        # ET-008: Regulatory compliance
        if config.applicable_regulations:
            compliance_result = check_regulatory_compliance(
                model_id=metrics.model_id,
                model_name=metrics.model_name,
                risk_level=config.risk_level,
                applicable_regulations=config.applicable_regulations,
                compliance_checks=config.compliance_checks,
            )
            all_anomalies.extend(compliance_result.anomalies)

        # Calculate ethics score
        score = 100.0
        for anomaly in all_anomalies:
            if anomaly.severity == SeverityLevel.CRITICAL:
                score -= 30.0
            elif anomaly.severity == SeverityLevel.WARNING:
                score -= 12.0
            else:
                score -= 3.0
        score = max(0.0, min(100.0, score))

        logger.info(
            "ethics_validation_complete",
            model_id=metrics.model_id,
            anomaly_count=len(all_anomalies),
            score=score,
        )

        return all_anomalies, score

    def get_health_score(self) -> GoldTierHealthScore:
        """Get current Gold tier health score.

        Returns:
            Current aggregated health score across all layers.
        """
        if self._current_health is None:
            self._current_health = GoldTierHealthScore.create_initial()
        return self._current_health

    def _update_health_score(self, result: GoldValidationResult) -> None:
        """Update health score based on validation result.

        Args:
            result: The validation result to incorporate.
        """
        now = datetime.now(timezone.utc)
        previous_score = (
            self._current_health.overall_score if self._current_health else None
        )

        # Create layer scores from result
        model_health_layer = GoldLayerScore(
            layer_name="model_health",
            layer_number=5,
            score=result.model_health_score,
            anomaly_count=len(result.model_health_anomalies),
            critical_count=len(result.critical_model_health_anomalies),
            warning_count=len([
                a for a in result.model_health_anomalies
                if a.severity == SeverityLevel.WARNING
            ]),
            last_check=now,
        )

        ethics_layer = GoldLayerScore(
            layer_name="ethics",
            layer_number=6,
            score=result.ethics_score,
            anomaly_count=len(result.ethics_anomalies),
            critical_count=len(result.critical_ethics_anomalies),
            warning_count=len([
                a for a in result.ethics_anomalies
                if a.severity == SeverityLevel.WARNING
            ]),
            last_check=now,
        )

        self._current_health = GoldTierHealthScore.calculate(
            model_health_layer=model_health_layer,
            ethics_layer=ethics_layer,
            previous_score=previous_score,
        )

        logger.debug(
            "health_score_updated",
            overall=self._current_health.overall_score,
            trend=self._current_health.trend,
        )

    def reset_health(self) -> None:
        """Reset health score to initial state."""
        self._current_health = GoldTierHealthScore.create_initial()
        logger.info("health_score_reset")
