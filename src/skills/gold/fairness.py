"""Fairness and bias detection skills for Gold Tier Layer 6.

Detects:
- ET-001: Demographic disparity
- ET-002: Fairness violation
- ET-003: Protected class impact
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.gold_anomaly import (
    EthicsAnomaly,
    FairnessViolation,
    FairnessMetric,
    ProtectedAttribute,
)

logger = structlog.get_logger(__name__)


@dataclass
class FairnessResult:
    """Result of fairness check."""

    anomalies: list[EthicsAnomaly]
    passed: bool
    score: float
    violations: list[FairnessViolation]


def calculate_demographic_parity(
    predictions: list[int],
    group_labels: list[str],
) -> dict[str, float]:
    """Calculate positive prediction rate per group.

    Args:
        predictions: Binary predictions (0 or 1).
        group_labels: Group identifier for each prediction.

    Returns:
        Dict mapping group name to positive rate.
    """
    group_counts: dict[str, int] = {}
    group_positives: dict[str, int] = {}

    for pred, group in zip(predictions, group_labels):
        group_counts[group] = group_counts.get(group, 0) + 1
        if pred == 1:
            group_positives[group] = group_positives.get(group, 0) + 1

    rates = {}
    for group in group_counts:
        total = group_counts[group]
        positives = group_positives.get(group, 0)
        rates[group] = positives / total if total > 0 else 0.0

    return rates


def calculate_equalized_odds(
    predictions: list[int],
    actual: list[int],
    group_labels: list[str],
) -> dict[str, dict[str, float]]:
    """Calculate TPR and FPR per group.

    Args:
        predictions: Binary predictions (0 or 1).
        actual: Actual labels (0 or 1).
        group_labels: Group identifier for each prediction.

    Returns:
        Dict mapping group name to {tpr, fpr}.
    """
    group_metrics: dict[str, dict[str, int]] = {}

    for pred, act, group in zip(predictions, actual, group_labels):
        if group not in group_metrics:
            group_metrics[group] = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

        if pred == 1 and act == 1:
            group_metrics[group]["tp"] += 1
        elif pred == 1 and act == 0:
            group_metrics[group]["fp"] += 1
        elif pred == 0 and act == 0:
            group_metrics[group]["tn"] += 1
        else:
            group_metrics[group]["fn"] += 1

    result = {}
    for group, counts in group_metrics.items():
        tp, fp, tn, fn = counts["tp"], counts["fp"], counts["tn"], counts["fn"]
        tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        result[group] = {"tpr": tpr, "fpr": fpr}

    return result


def check_fairness_metrics(
    model_id: str,
    predictions: list[int],
    actual: list[int] | None,
    protected_attribute: ProtectedAttribute,
    group_labels: list[str],
    metric: FairnessMetric = FairnessMetric.DEMOGRAPHIC_PARITY,
    disparity_threshold: float = 0.8,
) -> FairnessResult:
    """Check fairness metrics across groups (ET-002).

    Args:
        model_id: Model identifier.
        predictions: Binary predictions.
        actual: Actual labels (required for some metrics).
        protected_attribute: The protected attribute being checked.
        group_labels: Group identifier for each prediction.
        metric: Fairness metric to evaluate.
        disparity_threshold: Minimum acceptable ratio (0-1).

    Returns:
        FairnessResult with any detected violations.
    """
    anomalies: list[EthicsAnomaly] = []
    violations: list[FairnessViolation] = []

    logger.info(
        "fairness_check_started",
        model_id=model_id,
        metric=metric.value,
        protected_attribute=protected_attribute.value,
        sample_size=len(predictions),
    )

    # Calculate metric values by group
    if metric == FairnessMetric.DEMOGRAPHIC_PARITY:
        group_values = calculate_demographic_parity(predictions, group_labels)
    elif metric in (FairnessMetric.EQUALIZED_ODDS,) and actual is not None:
        odds = calculate_equalized_odds(predictions, actual, group_labels)
        # Use TPR for equalized odds check
        group_values = {g: v["tpr"] for g, v in odds.items()}
    else:
        group_values = calculate_demographic_parity(predictions, group_labels)

    if len(group_values) < 2:
        logger.info("fairness_check_skipped_single_group", model_id=model_id)
        return FairnessResult(
            anomalies=[], passed=True, score=100.0, violations=[]
        )

    # Find disparities between all group pairs
    groups = list(group_values.keys())
    for i, group_a in enumerate(groups):
        for group_b in groups[i + 1 :]:
            val_a = group_values[group_a]
            val_b = group_values[group_b]

            # Calculate disparity ratio (smaller / larger)
            if val_a == 0 and val_b == 0:
                ratio = 1.0
            elif val_a == 0 or val_b == 0:
                ratio = 0.0
            else:
                ratio = min(val_a, val_b) / max(val_a, val_b)

            if ratio < disparity_threshold:
                violation = FairnessViolation(
                    metric=metric,
                    protected_attribute=protected_attribute,
                    group_a=group_a,
                    group_b=group_b,
                    group_a_value=val_a,
                    group_b_value=val_b,
                    disparity_ratio=ratio,
                    threshold=disparity_threshold,
                )
                violations.append(violation)

    passed = len(violations) == 0

    if not passed:
        # Determine severity based on disparity magnitude
        min_ratio = min(v.disparity_ratio for v in violations)

        if min_ratio < 0.5:
            severity = SeverityLevel.CRITICAL
            blocking = True
            score = 30.0
        elif min_ratio < disparity_threshold:
            severity = SeverityLevel.WARNING
            blocking = False
            score = 60.0
        else:
            severity = SeverityLevel.INFO
            blocking = False
            score = 80.0

        affected_groups = list(
            set(
                [v.group_a for v in violations] + [v.group_b for v in violations]
            )
        )

        anomaly = EthicsAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.FAIRNESS_VIOLATION,
            severity=severity,
            model_id=model_id,
            fairness_violations=violations,
            affected_groups=affected_groups,
            protected_attributes=[protected_attribute],
            sample_size=len(predictions),
            timestamp=datetime.utcnow(),
            explanation=(
                f"Fairness violation detected for {protected_attribute.value}. "
                f"{len(violations)} group pair(s) show disparity ratio below "
                f"{disparity_threshold:.0%}. Minimum ratio: {min_ratio:.0%}"
            ),
            remediation_steps=[
                "Review training data for representation bias",
                "Consider bias mitigation techniques (reweighting, resampling)",
                "Implement fairness constraints in model training",
                "Evaluate model predictions across demographic groups",
            ],
            blocking=blocking,
            details={
                "metric": metric.value,
                "threshold": disparity_threshold,
                "min_ratio": min_ratio,
                "group_values": group_values,
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "fairness_violation_detected",
            model_id=model_id,
            violation_count=len(violations),
            min_ratio=min_ratio,
            severity=severity.value,
        )
    else:
        score = 100.0
        logger.info(
            "fairness_check_passed",
            model_id=model_id,
            metric=metric.value,
        )

    return FairnessResult(
        anomalies=anomalies,
        passed=passed,
        score=score,
        violations=violations,
    )


def detect_bias(
    model_id: str,
    predictions: list[int],
    actual: list[int] | None,
    protected_attributes: dict[ProtectedAttribute, list[str]],
    disparity_threshold: float = 0.8,
) -> FairnessResult:
    """Detect bias across multiple protected attributes (ET-001, ET-003).

    Args:
        model_id: Model identifier.
        predictions: Binary predictions.
        actual: Actual labels (optional).
        protected_attributes: Dict mapping attribute to group labels.
        disparity_threshold: Minimum acceptable ratio.

    Returns:
        FairnessResult with all detected violations.
    """
    all_anomalies: list[EthicsAnomaly] = []
    all_violations: list[FairnessViolation] = []
    affected_attributes: list[ProtectedAttribute] = []
    affected_groups: list[str] = []

    logger.info(
        "bias_detection_started",
        model_id=model_id,
        attribute_count=len(protected_attributes),
        sample_size=len(predictions),
    )

    worst_score = 100.0

    for attr, labels in protected_attributes.items():
        result = check_fairness_metrics(
            model_id=model_id,
            predictions=predictions,
            actual=actual,
            protected_attribute=attr,
            group_labels=labels,
            metric=FairnessMetric.DEMOGRAPHIC_PARITY,
            disparity_threshold=disparity_threshold,
        )

        if result.violations:
            affected_attributes.append(attr)
            for v in result.violations:
                affected_groups.extend([v.group_a, v.group_b])

        all_violations.extend(result.violations)
        worst_score = min(worst_score, result.score)

    passed = len(all_violations) == 0

    if not passed and all_violations:
        # Create summary anomaly for demographic disparity (ET-001)
        min_ratio = min(v.disparity_ratio for v in all_violations)

        if min_ratio < 0.5:
            severity = SeverityLevel.CRITICAL
            blocking = True
        elif min_ratio < disparity_threshold:
            severity = SeverityLevel.WARNING
            blocking = False
        else:
            severity = SeverityLevel.INFO
            blocking = False

        # Bias score: 0-100 where 100 is no bias
        bias_score = min_ratio * 100

        anomaly = EthicsAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.DEMOGRAPHIC_DISPARITY,
            severity=severity,
            model_id=model_id,
            fairness_violations=all_violations,
            affected_groups=list(set(affected_groups)),
            protected_attributes=affected_attributes,
            sample_size=len(predictions),
            bias_score=bias_score,
            timestamp=datetime.utcnow(),
            explanation=(
                f"Demographic disparity detected across {len(affected_attributes)} "
                f"protected attribute(s). {len(all_violations)} total violation(s) "
                f"affecting {len(set(affected_groups))} groups."
            ),
            regulatory_references=[
                "EEOC Guidelines",
                "EU AI Act Article 10",
                "CCPA",
            ],
            remediation_steps=[
                "Audit training data for representation",
                "Apply bias mitigation algorithms",
                "Implement ongoing fairness monitoring",
                "Document disparate impact analysis",
            ],
            blocking=blocking,
            details={
                "affected_attributes": [a.value for a in affected_attributes],
                "total_violations": len(all_violations),
                "min_disparity_ratio": min_ratio,
            },
        )
        all_anomalies.append(anomaly)

        # Add protected class impact anomaly if severe (ET-003)
        if severity == SeverityLevel.CRITICAL:
            impact_anomaly = EthicsAnomaly(
                id=str(uuid4()),
                failure_code=FailureCode.PROTECTED_CLASS_IMPACT,
                severity=SeverityLevel.CRITICAL,
                model_id=model_id,
                fairness_violations=all_violations,
                affected_groups=list(set(affected_groups)),
                protected_attributes=affected_attributes,
                sample_size=len(predictions),
                timestamp=datetime.utcnow(),
                explanation=(
                    f"Disproportionate impact on protected class(es) detected. "
                    f"Model shows significant bias affecting "
                    f"{', '.join([a.value for a in affected_attributes])}."
                ),
                regulatory_references=[
                    "Title VII (US)",
                    "Equal Credit Opportunity Act",
                    "Fair Housing Act",
                    "EU AI Act",
                ],
                remediation_steps=[
                    "Immediate review by legal/compliance team",
                    "Consider pausing model deployment",
                    "Implement disparate impact testing",
                    "Document business necessity justification if continuing use",
                ],
                blocking=True,
                details={
                    "impact_severity": "high",
                    "requires_legal_review": True,
                },
            )
            all_anomalies.append(impact_anomaly)

        logger.warning(
            "bias_detected",
            model_id=model_id,
            affected_attributes=[a.value for a in affected_attributes],
            violation_count=len(all_violations),
            min_ratio=min_ratio,
        )
    else:
        logger.info(
            "bias_detection_passed",
            model_id=model_id,
        )

    return FairnessResult(
        anomalies=all_anomalies,
        passed=passed,
        score=worst_score,
        violations=all_violations,
    )
