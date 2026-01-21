"""Ethics and compliance monitoring skills for Gold Tier Layer 6.

Detects:
- ET-004: Explainability gap
- ET-005: Consent violation
- ET-006: PII exposure risk
- ET-007: Audit trail gap
- ET-008: Compliance breach
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.gold_anomaly import EthicsAnomaly, ProtectedAttribute

logger = structlog.get_logger(__name__)


# Common PII field patterns
PII_FIELD_PATTERNS = [
    "ssn", "social_security", "national_id",
    "email", "phone", "telephone", "mobile",
    "address", "street", "zip", "postal",
    "birth", "dob", "date_of_birth",
    "name", "first_name", "last_name", "full_name",
    "driver_license", "passport",
    "credit_card", "account_number", "bank",
    "ip_address", "mac_address",
    "biometric", "fingerprint", "face_id",
    "medical", "health", "diagnosis",
    "salary", "income", "wage",
    "race", "ethnicity", "religion", "gender", "sexual_orientation",
]


@dataclass
class EthicsResult:
    """Result of ethics check."""

    anomalies: list[EthicsAnomaly]
    passed: bool
    score: float


def check_explainability(
    model_id: str,
    model_name: str,
    model_type: str,
    has_feature_importance: bool = False,
    has_shap_values: bool = False,
    has_local_explanations: bool = False,
    has_model_card: bool = False,
    min_explainability_score: float = 50.0,
) -> EthicsResult:
    """Check model explainability (ET-004).

    Verifies that model decisions can be explained to stakeholders.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        model_type: Type of model (e.g., "neural_network", "random_forest").
        has_feature_importance: Whether feature importance is available.
        has_shap_values: Whether SHAP values are computed.
        has_local_explanations: Whether local explanations are available.
        has_model_card: Whether model card documentation exists.
        min_explainability_score: Minimum acceptable score.

    Returns:
        EthicsResult with any detected anomalies.
    """
    anomalies: list[EthicsAnomaly] = []

    # Calculate explainability score
    score_components = {
        "feature_importance": 25 if has_feature_importance else 0,
        "shap_values": 30 if has_shap_values else 0,
        "local_explanations": 25 if has_local_explanations else 0,
        "model_card": 20 if has_model_card else 0,
    }
    explainability_score = sum(score_components.values())

    # Inherently interpretable models get a bonus
    interpretable_models = ["logistic_regression", "decision_tree", "linear_regression"]
    if model_type.lower() in interpretable_models:
        explainability_score = min(100, explainability_score + 20)

    logger.info(
        "explainability_check_started",
        model_id=model_id,
        model_type=model_type,
        score=explainability_score,
    )

    if explainability_score >= min_explainability_score:
        logger.info(
            "explainability_check_passed",
            model_id=model_id,
            score=explainability_score,
        )
        return EthicsResult(anomalies=[], passed=True, score=explainability_score)

    # Determine severity
    if explainability_score < 25:
        severity = SeverityLevel.CRITICAL
        blocking = True
    elif explainability_score < min_explainability_score:
        severity = SeverityLevel.WARNING
        blocking = False
    else:
        severity = SeverityLevel.INFO
        blocking = False

    missing_components = [k for k, v in score_components.items() if v == 0]

    anomaly = EthicsAnomaly(
        id=str(uuid4()),
        failure_code=FailureCode.EXPLAINABILITY_GAP,
        severity=severity,
        model_id=model_id,
        explainability_score=explainability_score,
        timestamp=datetime.utcnow(),
        explanation=(
            f"Model explainability score ({explainability_score}/100) is below "
            f"the minimum threshold ({min_explainability_score}/100). "
            f"Missing: {', '.join(missing_components)}."
        ),
        regulatory_references=[
            "EU AI Act Article 13 (Transparency)",
            "GDPR Article 22 (Right to explanation)",
        ],
        remediation_steps=[
            "Implement SHAP or LIME for local explanations",
            "Generate feature importance rankings",
            "Create model card with performance documentation",
            "Consider using more interpretable model architectures",
        ],
        blocking=blocking,
        details={
            "model_type": model_type,
            "score_components": score_components,
            "missing_components": missing_components,
        },
    )
    anomalies.append(anomaly)

    logger.warning(
        "explainability_gap_detected",
        model_id=model_id,
        score=explainability_score,
        missing=missing_components,
        severity=severity.value,
    )

    return EthicsResult(anomalies=anomalies, passed=False, score=explainability_score)


def check_consent_compliance(
    model_id: str | None,
    dataset_id: str,
    data_sources: list[str],
    consent_purposes: dict[str, list[str]],
    intended_use: str,
    has_explicit_consent: bool = True,
    consent_timestamp: datetime | None = None,
    retention_period_days: int | None = None,
) -> EthicsResult:
    """Check consent compliance (ET-005).

    Verifies data usage aligns with consent scope.

    Args:
        model_id: Model identifier (if applicable).
        dataset_id: Dataset identifier.
        data_sources: List of data source names.
        consent_purposes: Dict mapping source to consented purposes.
        intended_use: Intended use of the data.
        has_explicit_consent: Whether explicit consent was obtained.
        consent_timestamp: When consent was given.
        retention_period_days: Data retention period in days.

    Returns:
        EthicsResult with any detected anomalies.
    """
    anomalies: list[EthicsAnomaly] = []
    violations: list[str] = []

    logger.info(
        "consent_check_started",
        dataset_id=dataset_id,
        source_count=len(data_sources),
        intended_use=intended_use,
    )

    # Check if intended use is covered by consent
    for source in data_sources:
        if source in consent_purposes:
            consented = consent_purposes[source]
            if intended_use not in consented and "all" not in consented:
                violations.append(
                    f"Source '{source}' not consented for '{intended_use}'"
                )
        else:
            violations.append(f"No consent record for source '{source}'")

    # Check consent freshness
    if consent_timestamp:
        age_days = (datetime.utcnow() - consent_timestamp).days
        if age_days > 365:
            violations.append(f"Consent is {age_days} days old (may need renewal)")

    # Check explicit consent requirement
    if not has_explicit_consent:
        violations.append("Explicit consent not obtained (implied consent only)")

    passed = len(violations) == 0

    if not passed:
        if len(violations) >= 3 or not has_explicit_consent:
            severity = SeverityLevel.CRITICAL
            blocking = True
            score = 20.0
        else:
            severity = SeverityLevel.WARNING
            blocking = False
            score = 60.0

        anomaly = EthicsAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.CONSENT_VIOLATION,
            severity=severity,
            model_id=model_id,
            dataset_id=dataset_id,
            consent_scope=intended_use,
            timestamp=datetime.utcnow(),
            explanation=(
                f"Potential consent violation detected. "
                f"{len(violations)} issue(s) found: "
                + "; ".join(violations[:3])
                + ("..." if len(violations) > 3 else "")
            ),
            regulatory_references=[
                "GDPR Article 6 (Lawfulness of processing)",
                "GDPR Article 7 (Conditions for consent)",
                "CCPA Section 1798.100",
            ],
            remediation_steps=[
                "Review consent records for all data sources",
                "Obtain explicit consent for intended use",
                "Implement consent management system",
                "Document legal basis for data processing",
            ],
            blocking=blocking,
            details={
                "violations": violations,
                "data_sources": data_sources,
                "intended_use": intended_use,
                "has_explicit_consent": has_explicit_consent,
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "consent_violation_detected",
            dataset_id=dataset_id,
            violation_count=len(violations),
            severity=severity.value,
        )
    else:
        score = 100.0
        logger.info(
            "consent_check_passed",
            dataset_id=dataset_id,
        )

    return EthicsResult(anomalies=anomalies, passed=passed, score=score)


def check_pii_exposure(
    model_id: str | None,
    dataset_id: str,
    field_names: list[str],
    has_encryption: bool = False,
    has_masking: bool = False,
    has_access_controls: bool = True,
) -> EthicsResult:
    """Check for PII exposure risk (ET-006).

    Identifies potentially exposed personally identifiable information.

    Args:
        model_id: Model identifier (if applicable).
        dataset_id: Dataset identifier.
        field_names: List of field names in the dataset.
        has_encryption: Whether data is encrypted at rest.
        has_masking: Whether PII fields are masked.
        has_access_controls: Whether access controls are in place.

    Returns:
        EthicsResult with any detected anomalies.
    """
    anomalies: list[EthicsAnomaly] = []

    logger.info(
        "pii_exposure_check_started",
        dataset_id=dataset_id,
        field_count=len(field_names),
    )

    # Detect potential PII fields
    pii_fields: list[str] = []
    for field in field_names:
        field_lower = field.lower()
        for pattern in PII_FIELD_PATTERNS:
            if pattern in field_lower:
                pii_fields.append(field)
                break

    # Calculate risk score
    risk_factors = []
    if pii_fields:
        risk_factors.append(f"{len(pii_fields)} potential PII fields")
    if not has_encryption:
        risk_factors.append("no encryption")
    if not has_masking and pii_fields:
        risk_factors.append("no masking")
    if not has_access_controls:
        risk_factors.append("no access controls")

    # Score: 100 (safe) - penalties
    score = 100.0
    if pii_fields:
        score -= min(30, len(pii_fields) * 5)
    if not has_encryption:
        score -= 25
    if not has_masking and pii_fields:
        score -= 20
    if not has_access_controls:
        score -= 25
    score = max(0, score)

    passed = score >= 70 and not (pii_fields and not has_masking)

    if not passed:
        if score < 40 or (pii_fields and not has_encryption):
            severity = SeverityLevel.CRITICAL
            blocking = True
        else:
            severity = SeverityLevel.WARNING
            blocking = False

        anomaly = EthicsAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.PII_EXPOSURE_RISK,
            severity=severity,
            model_id=model_id,
            dataset_id=dataset_id,
            pii_fields_exposed=pii_fields,
            timestamp=datetime.utcnow(),
            explanation=(
                f"PII exposure risk detected. {len(pii_fields)} potential PII "
                f"field(s) identified. Risk factors: {', '.join(risk_factors)}."
            ),
            regulatory_references=[
                "GDPR Article 32 (Security of processing)",
                "CCPA Section 1798.150",
                "HIPAA Security Rule",
            ],
            remediation_steps=[
                "Implement data encryption at rest and in transit",
                "Apply PII masking or tokenization",
                "Review and strengthen access controls",
                "Conduct data minimization assessment",
                "Implement data loss prevention (DLP) tools",
            ],
            blocking=blocking,
            details={
                "pii_fields": pii_fields,
                "has_encryption": has_encryption,
                "has_masking": has_masking,
                "has_access_controls": has_access_controls,
                "risk_factors": risk_factors,
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "pii_exposure_risk_detected",
            dataset_id=dataset_id,
            pii_field_count=len(pii_fields),
            score=score,
            severity=severity.value,
        )
    else:
        logger.info(
            "pii_exposure_check_passed",
            dataset_id=dataset_id,
            pii_field_count=len(pii_fields),
        )

    return EthicsResult(anomalies=anomalies, passed=passed, score=score)


def check_audit_trail(
    model_id: str,
    has_prediction_logs: bool = False,
    has_input_logs: bool = False,
    has_decision_logs: bool = False,
    has_access_logs: bool = False,
    log_retention_days: int = 0,
    min_retention_days: int = 365,
) -> EthicsResult:
    """Check audit trail completeness (ET-007).

    Verifies that decision audit trail is complete and retained.

    Args:
        model_id: Model identifier.
        has_prediction_logs: Whether predictions are logged.
        has_input_logs: Whether inputs are logged.
        has_decision_logs: Whether decisions are logged.
        has_access_logs: Whether access is logged.
        log_retention_days: How long logs are retained.
        min_retention_days: Minimum required retention.

    Returns:
        EthicsResult with any detected anomalies.
    """
    anomalies: list[EthicsAnomaly] = []

    logger.info(
        "audit_trail_check_started",
        model_id=model_id,
        retention_days=log_retention_days,
    )

    # Calculate completeness score
    components = {
        "prediction_logs": has_prediction_logs,
        "input_logs": has_input_logs,
        "decision_logs": has_decision_logs,
        "access_logs": has_access_logs,
    }
    present_count = sum(1 for v in components.values() if v)
    completeness = (present_count / len(components)) * 100

    # Check retention
    retention_ok = log_retention_days >= min_retention_days

    # Overall score
    score = completeness * 0.7 + (30 if retention_ok else 0)

    missing = [k for k, v in components.items() if not v]
    passed = completeness >= 75 and retention_ok

    if not passed:
        if completeness < 50 or not has_prediction_logs:
            severity = SeverityLevel.CRITICAL
            blocking = False
        else:
            severity = SeverityLevel.WARNING
            blocking = False

        issues = []
        if missing:
            issues.append(f"Missing: {', '.join(missing)}")
        if not retention_ok:
            issues.append(
                f"Retention ({log_retention_days}d) below minimum ({min_retention_days}d)"
            )

        anomaly = EthicsAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.AUDIT_TRAIL_GAP,
            severity=severity,
            model_id=model_id,
            timestamp=datetime.utcnow(),
            explanation=(
                f"Audit trail incomplete. Completeness: {completeness:.0f}%. "
                + "; ".join(issues)
            ),
            regulatory_references=[
                "EU AI Act Article 12 (Record-keeping)",
                "SOX Section 302",
                "GDPR Article 30 (Records of processing)",
            ],
            remediation_steps=[
                "Implement comprehensive prediction logging",
                "Log all inputs used for model decisions",
                "Implement tamper-proof audit log storage",
                f"Extend log retention to {min_retention_days} days minimum",
            ],
            blocking=blocking,
            details={
                "components": components,
                "missing": missing,
                "completeness": completeness,
                "retention_days": log_retention_days,
                "min_retention_days": min_retention_days,
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "audit_trail_gap_detected",
            model_id=model_id,
            completeness=completeness,
            missing=missing,
            severity=severity.value,
        )
    else:
        logger.info(
            "audit_trail_check_passed",
            model_id=model_id,
            completeness=completeness,
        )

    return EthicsResult(anomalies=anomalies, passed=passed, score=score)


def check_regulatory_compliance(
    model_id: str,
    model_name: str,
    risk_level: str,
    applicable_regulations: list[str],
    compliance_checks: dict[str, bool],
) -> EthicsResult:
    """Check regulatory compliance (ET-008).

    Verifies model meets applicable regulatory requirements.

    Args:
        model_id: Model identifier.
        model_name: Human-readable model name.
        risk_level: Risk level (low, medium, high, unacceptable).
        applicable_regulations: List of applicable regulations.
        compliance_checks: Dict of check_name -> passed.

    Returns:
        EthicsResult with any detected anomalies.
    """
    anomalies: list[EthicsAnomaly] = []

    logger.info(
        "compliance_check_started",
        model_id=model_id,
        risk_level=risk_level,
        regulation_count=len(applicable_regulations),
    )

    # Calculate compliance score
    if compliance_checks:
        passed_checks = sum(1 for v in compliance_checks.values() if v)
        compliance_rate = passed_checks / len(compliance_checks)
        score = compliance_rate * 100
    else:
        compliance_rate = 1.0
        score = 100.0

    failed_checks = [k for k, v in compliance_checks.items() if not v]

    # Risk level multiplier
    risk_multipliers = {"low": 1.0, "medium": 1.5, "high": 2.0, "unacceptable": 3.0}
    risk_mult = risk_multipliers.get(risk_level.lower(), 1.0)

    # Adjust threshold based on risk
    min_compliance = 1.0 - (0.1 / risk_mult)  # Higher risk = stricter threshold

    passed = compliance_rate >= min_compliance and risk_level.lower() != "unacceptable"

    if not passed:
        if risk_level.lower() == "unacceptable" or compliance_rate < 0.5:
            severity = SeverityLevel.CRITICAL
            blocking = True
        elif compliance_rate < min_compliance:
            severity = SeverityLevel.WARNING
            blocking = False
        else:
            severity = SeverityLevel.INFO
            blocking = False

        anomaly = EthicsAnomaly(
            id=str(uuid4()),
            failure_code=FailureCode.COMPLIANCE_BREACH,
            severity=severity,
            model_id=model_id,
            timestamp=datetime.utcnow(),
            explanation=(
                f"Compliance issues detected for {model_name}. "
                f"Risk level: {risk_level}. "
                f"Compliance rate: {compliance_rate:.0%}. "
                f"Failed checks: {', '.join(failed_checks) if failed_checks else 'None'}."
            ),
            regulatory_references=applicable_regulations,
            remediation_steps=[
                "Address failed compliance checks immediately",
                "Conduct full compliance audit",
                "Engage legal/compliance team for guidance",
                "Document remediation actions taken",
                "Consider model redesign for high-risk applications",
            ],
            blocking=blocking,
            details={
                "risk_level": risk_level,
                "compliance_checks": compliance_checks,
                "failed_checks": failed_checks,
                "compliance_rate": compliance_rate,
                "applicable_regulations": applicable_regulations,
            },
        )
        anomalies.append(anomaly)

        logger.warning(
            "compliance_breach_detected",
            model_id=model_id,
            risk_level=risk_level,
            compliance_rate=compliance_rate,
            severity=severity.value,
        )
    else:
        logger.info(
            "compliance_check_passed",
            model_id=model_id,
            compliance_rate=compliance_rate,
        )

    return EthicsResult(anomalies=anomalies, passed=passed, score=score)
