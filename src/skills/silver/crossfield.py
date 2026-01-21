"""Silver Tier crossfield skill for BL-001 detection.

This skill validates cross-field relationships:
- Date comparisons (end_date > start_date)
- Amount calculations (quantity * price == total)
- Status-field consistency (status='shipped' requires ship_date)
"""

import re
import time
from datetime import datetime
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.business_rule import BusinessRule, RuleType, RuleViolation
from src.models.silver_anomaly import BusinessLogicAnomaly

logger = structlog.get_logger(__name__)


class CrossfieldValidationResult:
    """Result of cross-field validation."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[BusinessLogicAnomaly] = []
        self.violations: list[RuleViolation] = []
        self.records_checked: int = 0
        self.records_failed: int = 0
        self.duration_ms: float = 0.0


def validate_crossfield(
    records: list[dict[str, Any]],
    rules: list[BusinessRule | dict[str, Any]],
    batch_id: str,
) -> CrossfieldValidationResult:
    """Validate cross-field relationships in records.

    Args:
        records: List of records to validate.
        rules: Cross-field rules to apply.
        batch_id: Batch identifier for anomalies.

    Returns:
        CrossfieldValidationResult with anomalies and violations.
    """
    start_time = time.perf_counter()
    result = CrossfieldValidationResult()
    result.records_checked = len(records)

    # Convert dict rules to BusinessRule objects if needed
    parsed_rules = _parse_rules(rules)

    # Filter to only crossfield rules
    crossfield_rules = [r for r in parsed_rules if r.type == RuleType.CROSSFIELD]

    if not crossfield_rules:
        logger.debug("no_crossfield_rules_found")
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        return result

    failed_records: set[str] = set()

    for record in records:
        record_id = _get_record_id(record)

        for rule in crossfield_rules:
            if not rule.enabled:
                continue

            violation = _evaluate_crossfield_rule(rule, record)
            if violation:
                violation.record_id = record_id
                result.violations.append(violation)
                failed_records.add(record_id or "unknown")

    result.records_failed = len(failed_records)

    # Convert violations to anomalies grouped by rule
    result.anomalies = _violations_to_anomalies(result.violations, batch_id)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "crossfield_validation_complete",
        batch_id=batch_id,
        records_checked=result.records_checked,
        records_failed=result.records_failed,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def _parse_rules(rules: list[BusinessRule | dict[str, Any]]) -> list[BusinessRule]:
    """Parse rules from mixed list of objects and dicts."""
    parsed: list[BusinessRule] = []

    for rule in rules:
        if isinstance(rule, BusinessRule):
            parsed.append(rule)
        elif isinstance(rule, dict):
            # Convert dict to BusinessRule
            try:
                rule_type = rule.get("type", "crossfield")
                failure_code_str = rule.get("failure_code", "BL-001")

                # Map failure code string
                failure_code = _map_failure_code(failure_code_str)

                # Map severity
                severity_str = rule.get("severity", "critical").upper()
                severity = (
                    SeverityLevel(severity_str)
                    if severity_str in [s.value for s in SeverityLevel]
                    else SeverityLevel.CRITICAL
                )

                parsed.append(
                    BusinessRule(
                        id=rule.get("id", f"rule-{len(parsed)}"),
                        name=rule.get("name", "Unnamed rule"),
                        type=RuleType.CROSSFIELD if rule_type == "crossfield" else RuleType(rule_type),
                        failure_code=failure_code,
                        severity=severity,
                        enabled=rule.get("enabled", True),
                        expression=rule.get("expression", ""),
                        fields=rule.get("fields", []),
                        condition=rule.get("condition"),
                    )
                )
            except Exception as e:
                logger.warning("rule_parse_error", error=str(e))

    return parsed


def _map_failure_code(code_str: str) -> FailureCode:
    """Map failure code string to enum."""
    mapping = {
        "BL-001": FailureCode.CROSS_FIELD_INCONSISTENCY,
        "BL-002": FailureCode.REFERENTIAL_BREAK,
        "BL-003": FailureCode.CALCULATION_ERROR,
        "BL-004": FailureCode.INVALID_STATE_TRANSITION,
        "BL-005": FailureCode.TEMPORAL_ANOMALY,
        "BL-006": FailureCode.DOMAIN_RULE_VIOLATION,
    }
    return mapping.get(code_str, FailureCode.CROSS_FIELD_INCONSISTENCY)


def _get_record_id(record: dict[str, Any]) -> str | None:
    """Extract record ID from common fields."""
    for field in ["id", "order_id", "customer_id", "_id", "record_id"]:
        if field in record and record[field] is not None:
            return str(record[field])
    return None


def _evaluate_crossfield_rule(
    rule: BusinessRule, record: dict[str, Any]
) -> RuleViolation | None:
    """Evaluate a cross-field rule against a record."""
    # Check precondition
    if rule.condition:
        condition_met = _evaluate_expression(rule.condition, record)
        if not condition_met:
            return None

    # Evaluate main expression
    passed = _evaluate_expression(rule.expression, record)

    if passed:
        return None

    # Extract fields involved from expression
    fields = _extract_fields_from_expression(rule.expression, record)

    return RuleViolation(
        rule_id=rule.id,
        rule_name=rule.name,
        failure_code=rule.failure_code,
        severity=rule.severity,
        affected_fields=fields or rule.fields,
        expected_value=rule.expression,
        actual_value=_format_actual_values(fields, record),
        message=f"Cross-field check failed: {rule.expression}",
    )


def _evaluate_expression(expression: str, record: dict[str, Any]) -> bool:
    """Safely evaluate an expression against record values."""
    try:
        # Build evaluation context from record
        context = dict(record)

        # Handle date comparisons
        for key, value in context.items():
            if isinstance(value, str):
                # Try to parse as date
                try:
                    if re.match(r"\d{4}-\d{2}-\d{2}", value):
                        context[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        # Replace field names in expression with values
        eval_expr = expression
        for field, value in context.items():
            if isinstance(value, str) and not isinstance(value, datetime):
                eval_expr = re.sub(
                    rf"\b{re.escape(field)}\b",
                    f"'{value}'",
                    eval_expr
                )
            elif value is None:
                eval_expr = re.sub(
                    rf"\b{re.escape(field)}\b",
                    "None",
                    eval_expr
                )
            elif isinstance(value, datetime):
                # Keep datetime references for comparison
                pass
            else:
                eval_expr = re.sub(
                    rf"\b{re.escape(field)}\b",
                    str(value),
                    eval_expr
                )

        # Safe evaluation
        allowed = {
            "True": True,
            "False": False,
            "None": None,
            **{k: v for k, v in context.items() if isinstance(v, datetime)}
        }

        result = eval(eval_expr, {"__builtins__": {}}, allowed)
        return bool(result)

    except Exception as e:
        logger.debug("expression_eval_error", expression=expression, error=str(e))
        return False


def _extract_fields_from_expression(
    expression: str, record: dict[str, Any]
) -> list[str]:
    """Extract field names mentioned in expression."""
    fields = []
    for field in record.keys():
        if re.search(rf"\b{re.escape(field)}\b", expression):
            fields.append(field)
    return fields


def _format_actual_values(fields: list[str], record: dict[str, Any]) -> str:
    """Format actual values for error message."""
    parts = []
    for field in fields:
        value = record.get(field)
        parts.append(f"{field}={value!r}")
    return ", ".join(parts) if parts else "N/A"


def _violations_to_anomalies(
    violations: list[RuleViolation], batch_id: str
) -> list[BusinessLogicAnomaly]:
    """Convert violations to BusinessLogicAnomaly objects, grouped by rule."""
    # Group by rule_id
    by_rule: dict[str, list[RuleViolation]] = {}
    for v in violations:
        if v.rule_id not in by_rule:
            by_rule[v.rule_id] = []
        by_rule[v.rule_id].append(v)

    anomalies: list[BusinessLogicAnomaly] = []

    for rule_id, rule_violations in by_rule.items():
        first = rule_violations[0]
        affected_records = [v.record_id for v in rule_violations if v.record_id]
        affected_fields = list(set(f for v in rule_violations for f in v.affected_fields))

        # Calculate severity score based on count
        severity_score = min(100, 30 + len(rule_violations) * 10)

        anomalies.append(
            BusinessLogicAnomaly(
                id=f"BL-{uuid4().hex[:8]}",
                failure_code=first.failure_code,
                severity=first.severity,
                severity_score=severity_score,
                rule_id=rule_id,
                rule_name=first.rule_name,
                affected_records=affected_records,
                affected_fields=affected_fields,
                batch_id=batch_id,
                explanation=f"{first.rule_name}: {len(rule_violations)} record(s) failed validation",
                expected_value=first.expected_value,
                actual_value=first.actual_value,
                details={
                    "violation_count": len(rule_violations),
                    "sample_records": affected_records[:5],
                },
            )
        )

    return anomalies
