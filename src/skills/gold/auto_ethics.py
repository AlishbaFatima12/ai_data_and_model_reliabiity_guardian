"""Auto-ethics skill for Gold tier - automatic data ethics validation.

This skill automatically detects potential ethics issues in data without
requiring a trained ML model, including:
- PII exposure (emails, phones, SSNs)
- Protected attribute imbalance
- Potential fairness concerns
"""

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel
from src.models.gold_anomaly import EthicsAnomaly


class AutoEthicsResult(BaseModel):
    """Result of automatic ethics validation."""

    passed: bool = True
    anomalies: list[EthicsAnomaly] = Field(default_factory=list)
    pii_fields_detected: list[str] = Field(default_factory=list)
    protected_attributes_found: list[str] = Field(default_factory=list)
    issues_by_type: dict[str, int] = Field(default_factory=dict)


# PII detection patterns
PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
    "ssn": re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "ip_address": re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
}

# Protected attribute field names (case-insensitive matching)
PROTECTED_ATTRIBUTE_NAMES = [
    "gender", "sex", "race", "ethnicity", "religion", "nationality",
    "age", "disability", "marital_status", "sexual_orientation",
]

# Sensitive field names that might contain PII
SENSITIVE_FIELD_NAMES = [
    "email", "phone", "telephone", "mobile", "ssn", "social_security",
    "address", "street", "zip", "postal", "credit_card", "card_number",
    "passport", "driver_license", "ip", "ip_address",
]


def validate_auto_ethics(
    records: list[dict[str, Any]],
    batch_id: str,
    model_id: str = "data_ethics_check",
) -> AutoEthicsResult:
    """Automatically detect ethics issues in data.

    Args:
        records: Data records to validate.
        batch_id: Batch ID for anomaly tracking.
        model_id: Model ID for anomaly attribution.

    Returns:
        AutoEthicsResult with detected issues.
    """
    if not records:
        return AutoEthicsResult(passed=True)

    anomalies: list[EthicsAnomaly] = []
    pii_fields: list[str] = []
    protected_attrs: list[str] = []
    issues_by_type: dict[str, int] = {}

    # Get all field names from first record
    field_names = list(records[0].keys()) if records else []

    # Step 1: Detect PII fields by name
    for field in field_names:
        field_lower = field.lower()
        for sensitive in SENSITIVE_FIELD_NAMES:
            if sensitive in field_lower:
                pii_fields.append(field)
                break

    # Step 2: Detect PII by content patterns
    pii_by_pattern: dict[str, list[tuple[str, int]]] = {}  # pattern -> [(field, row_idx)]

    for idx, record in enumerate(records[:1000]):  # Sample first 1000 rows
        for field, value in record.items():
            if value is None or field in pii_fields:
                continue
            str_value = str(value)
            for pattern_name, pattern in PII_PATTERNS.items():
                if pattern.search(str_value):
                    if pattern_name not in pii_by_pattern:
                        pii_by_pattern[pattern_name] = []
                    pii_by_pattern[pattern_name].append((field, idx))
                    if field not in pii_fields:
                        pii_fields.append(field)
                    break

    # Create PII exposure anomalies
    if pii_fields:
        issues_by_type["pii_exposure"] = len(pii_fields)

        anomaly = EthicsAnomaly(
            id=f"ET-PII-{uuid4().hex[:8]}",
            failure_code=FailureCode.PII_EXPOSURE_RISK,
            severity=SeverityLevel.CRITICAL,
            severity_score=85.0,
            model_id=model_id,
            timestamp=datetime.utcnow(),
            explanation=f"Detected {len(pii_fields)} fields with potential PII: {', '.join(pii_fields[:5])}{'...' if len(pii_fields) > 5 else ''}",
            affected_fields=pii_fields[:10],
            affected_groups=["all_users"],
            metric_name="pii_field_count",
            metric_value=float(len(pii_fields)),
            threshold=0.0,
            is_regulatory_risk=True,
            regulatory_references=["GDPR Article 4", "CCPA §1798.140"],
            remediation_suggestion="Apply data masking or encryption to PII fields before processing",
        )
        anomalies.append(anomaly)

    # Step 3: Detect protected attributes
    for field in field_names:
        field_lower = field.lower().replace("_", "").replace("-", "")
        for protected in PROTECTED_ATTRIBUTE_NAMES:
            if protected.replace("_", "") in field_lower:
                protected_attrs.append(field)
                break

    # Step 4: Check for imbalanced protected attributes
    for attr in protected_attrs:
        values = [r.get(attr) for r in records if r.get(attr) is not None]
        if not values:
            continue

        # Count distribution
        value_counts: dict[str, int] = {}
        for v in values:
            str_v = str(v)
            value_counts[str_v] = value_counts.get(str_v, 0) + 1

        # Check for severe imbalance (any group < 10% or > 90%)
        total = sum(value_counts.values())
        if total > 0:
            for group, count in value_counts.items():
                ratio = count / total
                if ratio < 0.05 or ratio > 0.95:  # Severe imbalance
                    issues_by_type["protected_attribute_imbalance"] = issues_by_type.get("protected_attribute_imbalance", 0) + 1

                    anomaly = EthicsAnomaly(
                        id=f"ET-BIAS-{uuid4().hex[:8]}",
                        failure_code=FailureCode.DEMOGRAPHIC_DISPARITY,
                        severity=SeverityLevel.WARNING,
                        severity_score=60.0,
                        model_id=model_id,
                        timestamp=datetime.utcnow(),
                        explanation=f"Protected attribute '{attr}' has imbalanced distribution: group '{group}' is {ratio*100:.1f}% of data",
                        affected_fields=[attr],
                        affected_groups=[group],
                        metric_name="group_ratio",
                        metric_value=ratio,
                        threshold=0.05,
                        is_regulatory_risk=True,
                        regulatory_references=["EEOC Guidelines", "Fair Lending Act"],
                        remediation_suggestion=f"Review data collection practices for '{attr}' to ensure representative sampling",
                    )
                    anomalies.append(anomaly)
                    break  # Only one anomaly per attribute

    # Step 5: Check for age-based concerns (minors in dataset)
    age_field = None
    for field in field_names:
        if "age" in field.lower():
            age_field = field
            break

    if age_field:
        minor_count = 0
        minor_rows = []
        for idx, record in enumerate(records):
            age = record.get(age_field)
            if age is not None:
                try:
                    age_val = float(age)
                    if 0 < age_val < 18:
                        minor_count += 1
                        if len(minor_rows) < 100:
                            minor_rows.append(idx)
                except (ValueError, TypeError):
                    pass

        if minor_count > 0:
            issues_by_type["minor_data"] = minor_count

            anomaly = EthicsAnomaly(
                id=f"ET-MINOR-{uuid4().hex[:8]}",
                failure_code=FailureCode.CONSENT_VIOLATION,
                severity=SeverityLevel.WARNING if minor_count < 100 else SeverityLevel.CRITICAL,
                severity_score=70.0 if minor_count < 100 else 85.0,
                model_id=model_id,
                timestamp=datetime.utcnow(),
                explanation=f"Dataset contains {minor_count} records of minors (age < 18). Special consent requirements may apply.",
                affected_fields=[age_field],
                affected_groups=["minors"],
                affected_records=minor_rows,
                metric_name="minor_count",
                metric_value=float(minor_count),
                threshold=0.0,
                is_regulatory_risk=True,
                regulatory_references=["COPPA", "GDPR Article 8"],
                remediation_suggestion="Verify parental consent for minor data processing",
            )
            anomalies.append(anomaly)

    passed = len(anomalies) == 0

    return AutoEthicsResult(
        passed=passed,
        anomalies=anomalies,
        pii_fields_detected=pii_fields,
        protected_attributes_found=protected_attrs,
        issues_by_type=issues_by_type,
    )
