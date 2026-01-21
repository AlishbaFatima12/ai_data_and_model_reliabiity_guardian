"""Model health monitoring skills for Gold Tier Layer 5.

Detects:
- ML-003: Model staleness
- ML-004: Confidence degradation
- ML-005: Model latency spike
- ML-006: Error rate increase
- ML-007: Data-model mismatch
- ML-008: Retraining needed
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.gold_anomaly import ModelHealthAnomaly, DriftType

logger = structlog.get_logger(__name__)


@dataclass
class ModelHealthResult:
    """Result of model health check."""

    anomalies: list[ModelHealthAnomaly]
    passed: bool
    score: float


def check_model_staleness(
    model_id: str,
    model_name: str,
    model_version: str,
    last_trained: datetime,
    max_age_days: int = 90,
    warning_age_days: int = 60,
) -> ModelHealthResult:
    """Check for model staleness (ML-003).

    Models that haven't been retrained within the recommended interval
    may produce degraded predictions.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        last_trained: When the model was last trained.
        max_age_days: Maximum acceptable model age in days.
        warning_age_days: Age threshold for warning.

    Returns:
        ModelHealthResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    now = datetime.utcnow()
    model_age = (now - last_trained).days

    logger.info(
        "model_staleness_check_started",
        model_id=model_id,
        model_age_days=model_age,
        max_age_days=max_age_days,
    )

    if model_age >= max_age_days:
        severity = SeverityLevel.CRITICAL
        blocking = False
        score = 50.0
    elif model_age >= warning_age_days:
        severity = SeverityLevel.WARNING
        blocking = False
        score = 75.0
    else:
        # No anomaly
        logger.info(
            "model_staleness_check_passed",
            model_id=model_id,
            model_age_days=model_age,
        )
        return ModelHealthResult(anomalies=[], passed=True, score=100.0)

    anomaly = ModelHealthAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.MODEL_STALENESS,
        severity=severity,
        model_id=model_id,
        model_version=model_version,
        model_name=model_name,
        timestamp=datetime.utcnow(),
        explanation=(
            f"Model is {model_age} days old, exceeding the "
            f"{'maximum' if model_age >= max_age_days else 'warning'} "
            f"threshold of {max_age_days if model_age >= max_age_days else warning_age_days} days."
        ),
        recommended_action=(
            "Schedule model retraining with recent data to ensure "
            "predictions reflect current patterns."
        ),
        blocking=blocking,
        details={
            "model_age_days": model_age,
            "max_age_days": max_age_days,
            "warning_age_days": warning_age_days,
            "last_trained": last_trained.isoformat(),
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "model_staleness_detected",
        model_id=model_id,
        model_age_days=model_age,
        severity=severity.value,
    )

    return ModelHealthResult(anomalies=anomalies, passed=False, score=score)


def check_confidence_degradation(
    model_id: str,
    model_name: str,
    model_version: str,
    baseline_confidence: float,
    current_confidence: float,
    degradation_threshold: float = 0.1,
    critical_threshold: float = 0.2,
) -> ModelHealthResult:
    """Check for confidence score degradation (ML-004).

    When average prediction confidence drops significantly,
    it may indicate model uncertainty or data quality issues.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        baseline_confidence: Historical average confidence (0-1).
        current_confidence: Current average confidence (0-1).
        degradation_threshold: Threshold for warning.
        critical_threshold: Threshold for critical.

    Returns:
        ModelHealthResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    degradation = baseline_confidence - current_confidence

    logger.info(
        "confidence_check_started",
        model_id=model_id,
        baseline=baseline_confidence,
        current=current_confidence,
        degradation=degradation,
    )

    if degradation >= critical_threshold:
        severity = SeverityLevel.CRITICAL
        blocking = True
        score = 40.0
    elif degradation >= degradation_threshold:
        severity = SeverityLevel.WARNING
        blocking = False
        score = 70.0
    else:
        logger.info(
            "confidence_check_passed",
            model_id=model_id,
            degradation=degradation,
        )
        return ModelHealthResult(anomalies=[], passed=True, score=100.0)

    anomaly = ModelHealthAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.CONFIDENCE_DEGRADATION,
        severity=severity,
        model_id=model_id,
        model_version=model_version,
        model_name=model_name,
        confidence_score=current_confidence,
        timestamp=datetime.utcnow(),
        explanation=(
            f"Model confidence has dropped from {baseline_confidence:.1%} to "
            f"{current_confidence:.1%} (degradation: {degradation:.1%})"
        ),
        recommended_action=(
            "Investigate input data quality, check for distribution shifts, "
            "and consider model retraining if degradation persists."
        ),
        blocking=blocking,
        details={
            "baseline_confidence": baseline_confidence,
            "current_confidence": current_confidence,
            "degradation": degradation,
            "threshold": degradation_threshold,
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "confidence_degradation_detected",
        model_id=model_id,
        degradation=degradation,
        severity=severity.value,
    )

    return ModelHealthResult(anomalies=anomalies, passed=False, score=score)


def check_model_latency(
    model_id: str,
    model_name: str,
    model_version: str,
    baseline_latency_ms: float,
    current_latency_ms: float,
    spike_threshold: float = 2.0,
    critical_threshold: float = 5.0,
    absolute_limit_ms: float = 1000.0,
) -> ModelHealthResult:
    """Check for model latency spikes (ML-005).

    Monitors inference latency to detect performance degradation.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        baseline_latency_ms: Historical average latency in ms.
        current_latency_ms: Current average latency in ms.
        spike_threshold: Multiplier threshold for warning.
        critical_threshold: Multiplier threshold for critical.
        absolute_limit_ms: Absolute latency limit in ms.

    Returns:
        ModelHealthResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    latency_ratio = current_latency_ms / baseline_latency_ms if baseline_latency_ms > 0 else 1.0

    logger.info(
        "latency_check_started",
        model_id=model_id,
        baseline_ms=baseline_latency_ms,
        current_ms=current_latency_ms,
        ratio=latency_ratio,
    )

    is_critical = (
        latency_ratio >= critical_threshold or current_latency_ms >= absolute_limit_ms
    )
    is_warning = latency_ratio >= spike_threshold and not is_critical

    if is_critical:
        severity = SeverityLevel.CRITICAL
        blocking = True
        score = 30.0
    elif is_warning:
        severity = SeverityLevel.WARNING
        blocking = False
        score = 65.0
    else:
        logger.info(
            "latency_check_passed",
            model_id=model_id,
            latency_ratio=latency_ratio,
        )
        return ModelHealthResult(anomalies=[], passed=True, score=100.0)

    anomaly = ModelHealthAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.MODEL_LATENCY_SPIKE,
        severity=severity,
        model_id=model_id,
        model_version=model_version,
        model_name=model_name,
        latency_ms=current_latency_ms,
        timestamp=datetime.utcnow(),
        explanation=(
            f"Model inference latency increased from {baseline_latency_ms:.0f}ms to "
            f"{current_latency_ms:.0f}ms ({latency_ratio:.1f}x baseline)"
        ),
        recommended_action=(
            "Check system resources, optimize model serving infrastructure, "
            "or consider model simplification if issue persists."
        ),
        blocking=blocking,
        details={
            "baseline_latency_ms": baseline_latency_ms,
            "current_latency_ms": current_latency_ms,
            "latency_ratio": latency_ratio,
            "absolute_limit_ms": absolute_limit_ms,
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "latency_spike_detected",
        model_id=model_id,
        latency_ratio=latency_ratio,
        current_ms=current_latency_ms,
        severity=severity.value,
    )

    return ModelHealthResult(anomalies=anomalies, passed=False, score=score)


def check_error_rate(
    model_id: str,
    model_name: str,
    model_version: str,
    baseline_error_rate: float,
    current_error_rate: float,
    increase_threshold: float = 0.05,
    critical_threshold: float = 0.1,
    absolute_limit: float = 0.2,
) -> ModelHealthResult:
    """Check for error rate increase (ML-006).

    Monitors prediction error rate to detect model degradation.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        baseline_error_rate: Historical error rate (0-1).
        current_error_rate: Current error rate (0-1).
        increase_threshold: Threshold for warning.
        critical_threshold: Threshold for critical.
        absolute_limit: Absolute error rate limit.

    Returns:
        ModelHealthResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    error_increase = current_error_rate - baseline_error_rate

    logger.info(
        "error_rate_check_started",
        model_id=model_id,
        baseline=baseline_error_rate,
        current=current_error_rate,
        increase=error_increase,
    )

    is_critical = (
        error_increase >= critical_threshold or current_error_rate >= absolute_limit
    )
    is_warning = error_increase >= increase_threshold and not is_critical

    if is_critical:
        severity = SeverityLevel.CRITICAL
        blocking = True
        score = 25.0
    elif is_warning:
        severity = SeverityLevel.WARNING
        blocking = False
        score = 60.0
    else:
        logger.info(
            "error_rate_check_passed",
            model_id=model_id,
            error_increase=error_increase,
        )
        return ModelHealthResult(anomalies=[], passed=True, score=100.0)

    anomaly = ModelHealthAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.ERROR_RATE_INCREASE,
        severity=severity,
        model_id=model_id,
        model_version=model_version,
        model_name=model_name,
        error_rate=current_error_rate,
        timestamp=datetime.utcnow(),
        explanation=(
            f"Model error rate increased from {baseline_error_rate:.1%} to "
            f"{current_error_rate:.1%} (increase: {error_increase:.1%})"
        ),
        recommended_action=(
            "Investigate recent data quality issues, check for distribution shifts, "
            "and consider immediate model retraining."
        ),
        blocking=blocking,
        details={
            "baseline_error_rate": baseline_error_rate,
            "current_error_rate": current_error_rate,
            "error_increase": error_increase,
            "absolute_limit": absolute_limit,
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "error_rate_increase_detected",
        model_id=model_id,
        error_increase=error_increase,
        current_rate=current_error_rate,
        severity=severity.value,
    )

    return ModelHealthResult(anomalies=anomalies, passed=False, score=score)


def check_data_model_compatibility(
    model_id: str,
    model_name: str,
    model_version: str,
    expected_features: list[str],
    actual_features: list[str],
    expected_types: dict[str, str] | None = None,
    actual_types: dict[str, str] | None = None,
) -> ModelHealthResult:
    """Check for data-model mismatch (ML-007).

    Verifies that input data schema matches model expectations.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        expected_features: Features expected by the model.
        actual_features: Features present in the data.
        expected_types: Optional dict of expected feature types.
        actual_types: Optional dict of actual feature types.

    Returns:
        ModelHealthResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    expected_set = set(expected_features)
    actual_set = set(actual_features)

    missing_features = expected_set - actual_set
    extra_features = actual_set - expected_set

    # Check type mismatches
    type_mismatches: dict[str, dict[str, str]] = {}
    if expected_types and actual_types:
        for feature in expected_set & actual_set:
            if feature in expected_types and feature in actual_types:
                if expected_types[feature] != actual_types[feature]:
                    type_mismatches[feature] = {
                        "expected": expected_types[feature],
                        "actual": actual_types[feature],
                    }

    logger.info(
        "data_model_compatibility_check_started",
        model_id=model_id,
        expected_count=len(expected_features),
        actual_count=len(actual_features),
        missing_count=len(missing_features),
    )

    has_issues = missing_features or type_mismatches

    if not has_issues:
        logger.info(
            "data_model_compatibility_check_passed",
            model_id=model_id,
        )
        return ModelHealthResult(anomalies=[], passed=True, score=100.0)

    # Missing features are more critical than type mismatches
    if missing_features:
        severity = SeverityLevel.CRITICAL
        blocking = True
        score = 20.0
    else:
        severity = SeverityLevel.WARNING
        blocking = False
        score = 60.0

    explanation_parts = []
    if missing_features:
        explanation_parts.append(
            f"Missing features: {', '.join(list(missing_features)[:5])}"
            + ("..." if len(missing_features) > 5 else "")
        )
    if type_mismatches:
        explanation_parts.append(
            f"Type mismatches in {len(type_mismatches)} features"
        )

    anomaly = ModelHealthAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.DATA_MODEL_MISMATCH,
        severity=severity,
        model_id=model_id,
        model_version=model_version,
        model_name=model_name,
        affected_features=list(missing_features | set(type_mismatches.keys())),
        timestamp=datetime.utcnow(),
        explanation=". ".join(explanation_parts),
        recommended_action=(
            "Verify data pipeline outputs match model input requirements. "
            "Update feature engineering or model if schema has intentionally changed."
        ),
        blocking=blocking,
        details={
            "missing_features": list(missing_features),
            "extra_features": list(extra_features),
            "type_mismatches": type_mismatches,
            "expected_count": len(expected_features),
            "actual_count": len(actual_features),
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "data_model_mismatch_detected",
        model_id=model_id,
        missing_count=len(missing_features),
        type_mismatch_count=len(type_mismatches),
        severity=severity.value,
    )

    return ModelHealthResult(anomalies=anomalies, passed=False, score=score)


def check_retraining_needed(
    model_id: str,
    model_name: str,
    model_version: str,
    performance_score: float,
    performance_threshold: float = 0.7,
    has_drift: bool = False,
    is_stale: bool = False,
    has_high_error_rate: bool = False,
) -> ModelHealthResult:
    """Check if model retraining is needed (ML-008).

    Aggregates multiple signals to determine if retraining is required.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        performance_score: Overall model performance (0-1).
        performance_threshold: Minimum acceptable performance.
        has_drift: Whether drift has been detected.
        is_stale: Whether model is stale.
        has_high_error_rate: Whether error rate is high.

    Returns:
        ModelHealthResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    logger.info(
        "retraining_check_started",
        model_id=model_id,
        performance_score=performance_score,
        has_drift=has_drift,
        is_stale=is_stale,
        has_high_error_rate=has_high_error_rate,
    )

    # Count signals indicating retraining needed
    signals = []
    if performance_score < performance_threshold:
        signals.append("low_performance")
    if has_drift:
        signals.append("drift_detected")
    if is_stale:
        signals.append("model_stale")
    if has_high_error_rate:
        signals.append("high_error_rate")

    if not signals:
        logger.info(
            "retraining_check_passed",
            model_id=model_id,
        )
        return ModelHealthResult(anomalies=[], passed=True, score=100.0)

    # Severity based on number of signals
    if len(signals) >= 3:
        severity = SeverityLevel.CRITICAL
        blocking = False  # Retraining doesn't block serving
        score = 30.0
    elif len(signals) >= 2:
        severity = SeverityLevel.WARNING
        blocking = False
        score = 55.0
    else:
        severity = SeverityLevel.INFO
        blocking = False
        score = 75.0

    anomaly = ModelHealthAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.RETRAINING_NEEDED,
        severity=severity,
        model_id=model_id,
        model_version=model_version,
        model_name=model_name,
        timestamp=datetime.utcnow(),
        explanation=(
            f"Model retraining recommended based on {len(signals)} signal(s): "
            f"{', '.join(signals)}. Current performance: {performance_score:.1%}"
        ),
        recommended_action=(
            "Schedule model retraining with fresh data. "
            "Consider automated retraining pipeline if not already in place."
        ),
        blocking=blocking,
        details={
            "performance_score": performance_score,
            "performance_threshold": performance_threshold,
            "signals": signals,
            "signal_count": len(signals),
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "retraining_needed_detected",
        model_id=model_id,
        signals=signals,
        severity=severity.value,
    )

    return ModelHealthResult(anomalies=anomalies, passed=False, score=score)
