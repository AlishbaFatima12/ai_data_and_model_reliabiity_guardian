"""Drift detection skills for Gold Tier Layer 5.

Detects:
- ML-001: Prediction drift
- ML-002: Feature drift
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import numpy as np
import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.gold_anomaly import (
    ModelHealthAnomaly,
    DriftType,
    DriftMetrics,
)

logger = structlog.get_logger(__name__)


@dataclass
class DriftResult:
    """Result of drift detection."""

    anomalies: list[ModelHealthAnomaly]
    drift_detected: bool
    metrics: DriftMetrics | None


def calculate_psi(
    baseline: list[float], current: list[float], bins: int = 10
) -> float:
    """Calculate Population Stability Index.

    PSI measures how much a distribution has shifted.
    PSI < 0.1: No significant change
    0.1 <= PSI < 0.25: Moderate change
    PSI >= 0.25: Significant change

    Args:
        baseline: Baseline distribution values.
        current: Current distribution values.
        bins: Number of bins for histogram.

    Returns:
        PSI value.
    """
    if not baseline or not current:
        return 0.0

    # Create bins from baseline
    baseline_arr = np.array(baseline)
    current_arr = np.array(current)

    # Handle edge cases
    if len(baseline_arr) < bins or len(current_arr) < bins:
        bins = min(len(baseline_arr), len(current_arr), bins)
        if bins < 2:
            return 0.0

    # Create histogram bins from baseline
    _, bin_edges = np.histogram(baseline_arr, bins=bins)

    # Calculate proportions for each bin
    baseline_counts, _ = np.histogram(baseline_arr, bins=bin_edges)
    current_counts, _ = np.histogram(current_arr, bins=bin_edges)

    # Normalize to proportions
    baseline_props = baseline_counts / len(baseline_arr)
    current_props = current_counts / len(current_arr)

    # Add small epsilon to avoid division by zero
    epsilon = 1e-10
    baseline_props = np.clip(baseline_props, epsilon, 1 - epsilon)
    current_props = np.clip(current_props, epsilon, 1 - epsilon)

    # Calculate PSI
    psi = np.sum((current_props - baseline_props) * np.log(current_props / baseline_props))

    return float(psi)


def calculate_ks_statistic(
    baseline: list[float], current: list[float]
) -> float:
    """Calculate Kolmogorov-Smirnov statistic.

    KS statistic measures the maximum distance between two CDFs.

    Args:
        baseline: Baseline distribution values.
        current: Current distribution values.

    Returns:
        KS statistic (0-1).
    """
    if not baseline or not current:
        return 0.0

    baseline_sorted = np.sort(baseline)
    current_sorted = np.sort(current)

    # Create combined sorted array
    all_values = np.sort(np.concatenate([baseline_sorted, current_sorted]))

    # Calculate CDF for each distribution at each point
    baseline_cdf = np.searchsorted(baseline_sorted, all_values, side="right") / len(baseline)
    current_cdf = np.searchsorted(current_sorted, all_values, side="right") / len(current)

    # KS statistic is maximum absolute difference
    ks_stat = np.max(np.abs(baseline_cdf - current_cdf))

    return float(ks_stat)


def calculate_js_divergence(
    baseline: list[float], current: list[float], bins: int = 10
) -> float:
    """Calculate Jensen-Shannon Divergence.

    JS divergence is symmetric and bounded [0, 1].

    Args:
        baseline: Baseline distribution values.
        current: Current distribution values.
        bins: Number of bins for histogram.

    Returns:
        JS divergence (0-1).
    """
    if not baseline or not current:
        return 0.0

    baseline_arr = np.array(baseline)
    current_arr = np.array(current)

    if len(baseline_arr) < bins or len(current_arr) < bins:
        bins = min(len(baseline_arr), len(current_arr), bins)
        if bins < 2:
            return 0.0

    # Create histogram bins from combined data
    combined = np.concatenate([baseline_arr, current_arr])
    _, bin_edges = np.histogram(combined, bins=bins)

    baseline_counts, _ = np.histogram(baseline_arr, bins=bin_edges)
    current_counts, _ = np.histogram(current_arr, bins=bin_edges)

    # Normalize to probabilities
    epsilon = 1e-10
    p = baseline_counts / len(baseline_arr) + epsilon
    q = current_counts / len(current_arr) + epsilon
    p = p / p.sum()
    q = q / q.sum()

    # Average distribution
    m = (p + q) / 2

    # KL divergences
    kl_pm = np.sum(p * np.log(p / m))
    kl_qm = np.sum(q * np.log(q / m))

    # JS divergence
    js = (kl_pm + kl_qm) / 2

    return float(min(js, 1.0))


def detect_prediction_drift(
    model_id: str,
    model_name: str,
    model_version: str,
    baseline_predictions: list[float],
    current_predictions: list[float],
    psi_threshold: float = 0.25,
    ks_threshold: float = 0.2,
    baseline_period: str = "last_30_days",
    current_period: str = "last_24_hours",
) -> DriftResult:
    """Detect prediction drift (ML-001).

    Compares current model predictions against baseline distribution.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        baseline_predictions: Baseline prediction values.
        current_predictions: Current prediction values.
        psi_threshold: PSI threshold for drift detection.
        ks_threshold: KS statistic threshold.
        baseline_period: Description of baseline period.
        current_period: Description of current period.

    Returns:
        DriftResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []

    logger.info(
        "prediction_drift_check_started",
        model_id=model_id,
        baseline_count=len(baseline_predictions),
        current_count=len(current_predictions),
    )

    # Calculate drift metrics
    psi = calculate_psi(baseline_predictions, current_predictions)
    ks_stat = calculate_ks_statistic(baseline_predictions, current_predictions)
    js_div = calculate_js_divergence(baseline_predictions, current_predictions)

    drift_metrics = DriftMetrics(
        psi=psi,
        ks_statistic=ks_stat,
        js_divergence=js_div,
    )

    drift_detected = psi >= psi_threshold or ks_stat >= ks_threshold

    if drift_detected:
        # Determine severity based on magnitude
        if psi >= 0.5 or ks_stat >= 0.4:
            severity = SeverityLevel.CRITICAL
            blocking = True
        elif psi >= 0.25 or ks_stat >= 0.2:
            severity = SeverityLevel.WARNING
            blocking = False
        else:
            severity = SeverityLevel.INFO
            blocking = False

        anomaly = ModelHealthAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.PREDICTION_DRIFT,
            severity=severity,
            model_id=model_id,
            model_version=model_version,
            model_name=model_name,
            drift_type=DriftType.PREDICTION,
            drift_metrics=drift_metrics,
            baseline_period=baseline_period,
            current_period=current_period,
            timestamp=datetime.utcnow(),
            explanation=(
                f"Prediction distribution has shifted significantly. "
                f"PSI={psi:.3f} (threshold={psi_threshold}), "
                f"KS={ks_stat:.3f} (threshold={ks_threshold})"
            ),
            recommended_action=(
                "Review recent data changes, consider model retraining, "
                "or investigate potential concept drift."
            ),
            blocking=blocking,
            details={
                "psi": psi,
                "ks_statistic": ks_stat,
                "js_divergence": js_div,
                "baseline_count": len(baseline_predictions),
                "current_count": len(current_predictions),
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "prediction_drift_detected",
            model_id=model_id,
            psi=psi,
            ks_stat=ks_stat,
            severity=severity.value,
        )
    else:
        logger.info(
            "prediction_drift_check_passed",
            model_id=model_id,
            psi=psi,
            ks_stat=ks_stat,
        )

    return DriftResult(
        anomalies=anomalies,
        drift_detected=drift_detected,
        metrics=drift_metrics,
    )


def detect_feature_drift(
    model_id: str,
    model_name: str,
    model_version: str,
    baseline_features: dict[str, list[float]],
    current_features: dict[str, list[float]],
    psi_threshold: float = 0.25,
    baseline_period: str = "last_30_days",
    current_period: str = "last_24_hours",
) -> DriftResult:
    """Detect feature drift (ML-002).

    Compares current feature distributions against baseline.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_version: Model version string.
        baseline_features: Dict of feature_name -> baseline values.
        current_features: Dict of feature_name -> current values.
        psi_threshold: PSI threshold for drift detection.
        baseline_period: Description of baseline period.
        current_period: Description of current period.

    Returns:
        DriftResult with any detected anomalies.
    """
    anomalies: list[ModelHealthAnomaly] = []
    affected_features: list[str] = []
    feature_psis: dict[str, float] = {}

    logger.info(
        "feature_drift_check_started",
        model_id=model_id,
        feature_count=len(baseline_features),
    )

    # Check each feature
    for feature_name in baseline_features:
        if feature_name not in current_features:
            continue

        baseline = baseline_features[feature_name]
        current = current_features[feature_name]

        psi = calculate_psi(baseline, current)
        feature_psis[feature_name] = psi

        if psi >= psi_threshold:
            affected_features.append(feature_name)

    drift_detected = len(affected_features) > 0

    if drift_detected:
        # Calculate aggregate metrics
        max_psi = max(feature_psis.values()) if feature_psis else 0
        avg_psi = sum(feature_psis.values()) / len(feature_psis) if feature_psis else 0

        # Determine severity based on number and magnitude of drifted features
        drift_ratio = len(affected_features) / len(baseline_features)
        if drift_ratio >= 0.5 or max_psi >= 0.5:
            severity = SeverityLevel.CRITICAL
            blocking = True
        elif drift_ratio >= 0.2 or max_psi >= 0.25:
            severity = SeverityLevel.WARNING
            blocking = False
        else:
            severity = SeverityLevel.INFO
            blocking = False

        drift_metrics = DriftMetrics(
            psi=avg_psi,
            ks_statistic=None,
            js_divergence=None,
        )

        anomaly = ModelHealthAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.FEATURE_DRIFT,
            severity=severity,
            model_id=model_id,
            model_version=model_version,
            model_name=model_name,
            drift_type=DriftType.FEATURE,
            drift_metrics=drift_metrics,
            baseline_period=baseline_period,
            current_period=current_period,
            affected_features=affected_features,
            timestamp=datetime.utcnow(),
            explanation=(
                f"{len(affected_features)} of {len(baseline_features)} features "
                f"show significant distribution shift. "
                f"Max PSI={max_psi:.3f}, affected: {', '.join(affected_features[:3])}"
                + ("..." if len(affected_features) > 3 else "")
            ),
            recommended_action=(
                "Investigate data pipeline changes, check for data quality issues, "
                "consider feature engineering updates or model retraining."
            ),
            blocking=blocking,
            details={
                "feature_psis": feature_psis,
                "affected_features": affected_features,
                "total_features": len(baseline_features),
                "drift_ratio": drift_ratio,
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "feature_drift_detected",
            model_id=model_id,
            affected_count=len(affected_features),
            max_psi=max_psi,
            severity=severity.value,
        )
    else:
        logger.info(
            "feature_drift_check_passed",
            model_id=model_id,
            max_psi=max(feature_psis.values()) if feature_psis else 0,
        )

    return DriftResult(
        anomalies=anomalies,
        drift_detected=drift_detected,
        metrics=DriftMetrics(psi=max(feature_psis.values()) if feature_psis else 0) if feature_psis else None,
    )
