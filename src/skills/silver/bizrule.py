"""Silver Tier bizrule skill for BL-003, BL-004, BL-005, BL-006 detection.

This skill validates:
- BL-003: Calculation errors (derived values don't match)
- BL-004: Invalid state transitions
- BL-005: Temporal anomalies (date/time violations)
- BL-006: Domain rule violations (value constraints)
"""

import re
import time
from datetime import datetime, date
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import FailureCode, SeverityLevel
from src.models.business_rule import (
    BusinessRule,
    RuleType,
    StateTransitionRule,
    CalculationRule,
    RuleViolation,
)
from src.models.silver_anomaly import BusinessLogicAnomaly

logger = structlog.get_logger(__name__)


class BizruleValidationResult:
    """Result of business rule validation."""

    def __init__(self) -> None:
        """Initialize result."""
        self.anomalies: list[BusinessLogicAnomaly] = []
        self.violations: list[RuleViolation] = []
        self.records_checked: int = 0
        self.records_failed: int = 0
        self.calculation_errors: int = 0
        self.state_violations: int = 0
        self.temporal_violations: int = 0
        self.domain_violations: int = 0
        self.duration_ms: float = 0.0


def evaluate_business_rules(
    records: list[dict[str, Any]],
    rules: list[BusinessRule | StateTransitionRule | CalculationRule | dict[str, Any]],
    batch_id: str = "unknown",
    previous_states: dict[str, str] | None = None,
) -> BizruleValidationResult:
    """Evaluate business rules against records.

    Args:
        records: List of records to validate.
        rules: Business rules to apply.
        batch_id: Batch identifier for anomalies.
        previous_states: Map of record_id -> previous state (for transitions).

    Returns:
        BizruleValidationResult with violations and anomalies.
    """
    start_time = time.perf_counter()
    result = BizruleValidationResult()
    result.records_checked = len(records)

    # Parse rules into appropriate types
    domain_rules, calculation_rules, state_rules, temporal_rules = _categorize_rules(rules)

    failed_records: set[str] = set()

    for record in records:
        record_id = _get_record_id(record)

        # Check domain rules (BL-006)
        for rule in domain_rules:
            violation = _evaluate_domain_rule(rule, record)
            if violation:
                violation.record_id = record_id
                result.violations.append(violation)
                result.domain_violations += 1
                if record_id:
                    failed_records.add(record_id)

        # Check calculation rules (BL-003)
        for rule in calculation_rules:
            violation = _evaluate_calculation_rule(rule, record)
            if violation:
                violation.record_id = record_id
                result.violations.append(violation)
                result.calculation_errors += 1
                if record_id:
                    failed_records.add(record_id)

        # Check temporal rules (BL-005)
        for rule in temporal_rules:
            violation = _evaluate_temporal_rule(rule, record)
            if violation:
                violation.record_id = record_id
                result.violations.append(violation)
                result.temporal_violations += 1
                if record_id:
                    failed_records.add(record_id)

        # Check state transitions (BL-004)
        if previous_states and state_rules:
            for rule in state_rules:
                prev_state = previous_states.get(record_id or "", None)
                if prev_state:
                    current_state = record.get(rule.field)
                    if current_state:
                        violation = _evaluate_state_transition(
                            rule, prev_state, str(current_state), record_id
                        )
                        if violation:
                            result.violations.append(violation)
                            result.state_violations += 1
                            if record_id:
                                failed_records.add(record_id)

    result.records_failed = len(failed_records)

    # Convert violations to anomalies
    result.anomalies = _violations_to_anomalies(result.violations, batch_id)

    result.duration_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        "bizrule_validation_complete",
        batch_id=batch_id,
        records_checked=result.records_checked,
        records_failed=result.records_failed,
        calculation_errors=result.calculation_errors,
        state_violations=result.state_violations,
        temporal_violations=result.temporal_violations,
        domain_violations=result.domain_violations,
        anomalies=len(result.anomalies),
        duration_ms=result.duration_ms,
    )

    return result


def validate_calculation(
    record: dict[str, Any],
    result_field: str,
    expression: str,
    tolerance: float = 0.001,
) -> RuleViolation | None:
    """Validate a calculation in a record.

    Args:
        record: Record to validate.
        result_field: Field containing calculated result.
        expression: Expression that should equal result_field.
        tolerance: Allowed difference for float comparisons.

    Returns:
        RuleViolation if calculation is wrong, None if correct.
    """
    try:
        actual_value = record.get(result_field)
        if actual_value is None:
            return None

        expected_value = _evaluate_math_expression(expression, record)
        if expected_value is None:
            return None

        # Compare with tolerance
        if abs(float(actual_value) - float(expected_value)) <= tolerance:
            return None

        return RuleViolation(
            rule_id=f"calc-{result_field}",
            rule_name=f"Calculation check: {result_field}",
            failure_code=FailureCode.CALCULATION_ERROR,
            severity=SeverityLevel.CRITICAL,
            affected_fields=[result_field],
            expected_value=f"{expression} = {expected_value}",
            actual_value=str(actual_value),
            message=f"Calculation mismatch: {result_field} should be {expected_value}, got {actual_value}",
        )

    except Exception as e:
        logger.debug("calculation_check_error", error=str(e))
        return None


def validate_state_transition(
    from_state: str,
    to_state: str,
    allowed_transitions: dict[str, list[str]],
    field: str = "status",
) -> RuleViolation | None:
    """Validate a state transition.

    Args:
        from_state: Current state.
        to_state: Target state.
        allowed_transitions: Map of state -> valid next states.
        field: Field name for error message.

    Returns:
        RuleViolation if transition is invalid, None if valid.
    """
    if from_state not in allowed_transitions:
        return RuleViolation(
            rule_id=f"state-{field}",
            rule_name=f"State transition: {field}",
            failure_code=FailureCode.INVALID_STATE_TRANSITION,
            severity=SeverityLevel.CRITICAL,
            affected_fields=[field],
            expected_value=f"Valid state, got unknown state: {from_state}",
            actual_value=f"{from_state} -> {to_state}",
            message=f"Unknown state: {from_state}",
        )

    valid_next = allowed_transitions[from_state]
    if to_state in valid_next:
        return None

    return RuleViolation(
        rule_id=f"state-{field}",
        rule_name=f"State transition: {field}",
        failure_code=FailureCode.INVALID_STATE_TRANSITION,
        severity=SeverityLevel.CRITICAL,
        affected_fields=[field],
        expected_value=f"Allowed from {from_state}: {valid_next}",
        actual_value=f"{from_state} -> {to_state}",
        message=f"Invalid state transition: {from_state} -> {to_state}",
    )


def validate_temporal(
    record: dict[str, Any],
    check_type: str,
    fields: list[str],
    reference_date: datetime | None = None,
) -> RuleViolation | None:
    """Validate temporal constraints.

    Args:
        record: Record to validate.
        check_type: Type of check ("no_future", "sequence", "not_before").
        fields: Fields to check.
        reference_date: Reference date for comparisons.

    Returns:
        RuleViolation if temporal constraint violated.
    """
    now = reference_date or datetime.utcnow()

    if check_type == "no_future":
        # Check that date fields are not in the future
        for field in fields:
            value = record.get(field)
            if value is None:
                continue

            field_date = _parse_date(value)
            if field_date and field_date > now:
                return RuleViolation(
                    rule_id=f"temporal-{field}",
                    rule_name=f"No future dates: {field}",
                    failure_code=FailureCode.TEMPORAL_ANOMALY,
                    severity=SeverityLevel.WARNING,
                    affected_fields=[field],
                    expected_value=f"Date <= {now.isoformat()}",
                    actual_value=str(value),
                    message=f"Future date not allowed: {field}={value}",
                )

    elif check_type == "sequence" and len(fields) >= 2:
        # Check that dates are in sequence (field1 <= field2 <= field3...)
        prev_date = None
        prev_field = None

        for field in fields:
            value = record.get(field)
            if value is None:
                continue

            current_date = _parse_date(value)
            if current_date is None:
                continue

            if prev_date and current_date < prev_date:
                return RuleViolation(
                    rule_id=f"temporal-sequence",
                    rule_name=f"Date sequence: {' < '.join(fields)}",
                    failure_code=FailureCode.TEMPORAL_ANOMALY,
                    severity=SeverityLevel.CRITICAL,
                    affected_fields=fields,
                    expected_value=f"{prev_field} <= {field}",
                    actual_value=f"{prev_field}={prev_date.isoformat()}, {field}={current_date.isoformat()}",
                    message=f"Date sequence violation: {prev_field} should be before {field}",
                )

            prev_date = current_date
            prev_field = field

    return None


def _categorize_rules(
    rules: list[BusinessRule | StateTransitionRule | CalculationRule | dict[str, Any]],
) -> tuple[
    list[BusinessRule],
    list[CalculationRule],
    list[StateTransitionRule],
    list[BusinessRule],
]:
    """Categorize rules by type."""
    domain_rules: list[BusinessRule] = []
    calculation_rules: list[CalculationRule] = []
    state_rules: list[StateTransitionRule] = []
    temporal_rules: list[BusinessRule] = []

    for rule in rules:
        if isinstance(rule, StateTransitionRule):
            state_rules.append(rule)
        elif isinstance(rule, CalculationRule):
            calculation_rules.append(rule)
        elif isinstance(rule, BusinessRule):
            if rule.type == RuleType.TEMPORAL:
                temporal_rules.append(rule)
            elif rule.type == RuleType.CALCULATION:
                calculation_rules.append(
                    CalculationRule(
                        id=rule.id,
                        name=rule.name,
                        result_field=rule.parameters.get("result_field", ""),
                        expression=rule.expression,
                        tolerance=rule.parameters.get("tolerance", 0.001),
                        severity=rule.severity,
                    )
                )
            elif rule.type == RuleType.STATE_TRANSITION:
                state_rules.append(
                    StateTransitionRule(
                        id=rule.id,
                        name=rule.name,
                        field=rule.parameters.get("field", "status"),
                        allowed_states=rule.parameters.get("allowed_states", []),
                        allowed_transitions=rule.parameters.get("transitions", {}),
                        severity=rule.severity,
                    )
                )
            else:
                domain_rules.append(rule)
        elif isinstance(rule, dict):
            # Parse dict to appropriate rule type
            rule_type = rule.get("type", "domain")
            if rule_type == "state_transition":
                state_rules.append(
                    StateTransitionRule(
                        id=rule.get("id", f"rule-{len(state_rules)}"),
                        name=rule.get("name", "State transition"),
                        field=rule.get("field", "status"),
                        allowed_states=rule.get("allowed_values", []),
                        allowed_transitions=rule.get("transitions", {}),
                    )
                )
            elif rule_type == "calculation":
                calculation_rules.append(
                    CalculationRule(
                        id=rule.get("id", f"rule-{len(calculation_rules)}"),
                        name=rule.get("name", "Calculation"),
                        result_field=rule.get("result_field", ""),
                        expression=rule.get("expression", ""),
                        tolerance=rule.get("tolerance", 0.001),
                    )
                )
            elif rule_type == "temporal":
                temporal_rules.append(
                    BusinessRule(
                        id=rule.get("id", f"rule-{len(temporal_rules)}"),
                        name=rule.get("name", "Temporal check"),
                        type=RuleType.TEMPORAL,
                        failure_code=FailureCode.TEMPORAL_ANOMALY,
                        expression=rule.get("expression", ""),
                        fields=rule.get("fields", []),
                        parameters=rule,
                    )
                )
            else:
                # Domain rule
                failure_code = _map_failure_code(rule.get("failure_code", "BL-006"))
                severity_str = rule.get("severity", "warning").upper()
                severity = (
                    SeverityLevel(severity_str)
                    if severity_str in [s.value for s in SeverityLevel]
                    else SeverityLevel.WARNING
                )
                domain_rules.append(
                    BusinessRule(
                        id=rule.get("id", f"rule-{len(domain_rules)}"),
                        name=rule.get("name", "Domain rule"),
                        type=RuleType.DOMAIN,
                        failure_code=failure_code,
                        severity=severity,
                        expression=rule.get("expression", ""),
                        fields=rule.get("fields", []),
                        enabled=rule.get("enabled", True),
                    )
                )

    return domain_rules, calculation_rules, state_rules, temporal_rules


def _evaluate_domain_rule(
    rule: BusinessRule, record: dict[str, Any]
) -> RuleViolation | None:
    """Evaluate a domain rule against a record."""
    if not rule.enabled:
        return None

    # Check condition
    if rule.condition:
        condition_met = _evaluate_expression(rule.condition, record)
        if not condition_met:
            return None

    passed = _evaluate_expression(rule.expression, record)
    if passed:
        return None

    fields = rule.fields or _extract_fields(rule.expression, record)

    return RuleViolation(
        rule_id=rule.id,
        rule_name=rule.name,
        failure_code=rule.failure_code,
        severity=rule.severity,
        affected_fields=fields,
        expected_value=rule.expression,
        actual_value=_format_values(fields, record),
        message=f"Domain rule violation: {rule.name}",
    )


def _evaluate_calculation_rule(
    rule: CalculationRule, record: dict[str, Any]
) -> RuleViolation | None:
    """Evaluate a calculation rule."""
    return validate_calculation(
        record,
        rule.result_field,
        rule.expression,
        rule.tolerance,
    )


def _evaluate_temporal_rule(
    rule: BusinessRule, record: dict[str, Any]
) -> RuleViolation | None:
    """Evaluate a temporal rule."""
    check_type = rule.parameters.get("check_type", "no_future")
    fields = rule.fields or []

    return validate_temporal(record, check_type, fields)


def _evaluate_state_transition(
    rule: StateTransitionRule,
    from_state: str,
    to_state: str,
    record_id: str | None,
) -> RuleViolation | None:
    """Evaluate a state transition rule."""
    if rule.is_valid_transition(from_state, to_state):
        return None

    return RuleViolation(
        rule_id=rule.id,
        rule_name=rule.name,
        failure_code=rule.failure_code,
        severity=rule.severity,
        record_id=record_id,
        affected_fields=[rule.field],
        expected_value=f"Valid transitions from {from_state}: {rule.allowed_transitions.get(from_state, [])}",
        actual_value=f"{from_state} -> {to_state}",
        message=f"Invalid state transition: {from_state} -> {to_state}",
    )


def _evaluate_expression(expression: str, record: dict[str, Any]) -> bool:
    """Safely evaluate an expression."""
    try:
        # Build context
        context = dict(record)

        # Replace field names
        eval_expr = expression
        for field, value in context.items():
            if isinstance(value, str):
                eval_expr = re.sub(rf"\b{re.escape(field)}\b", f"'{value}'", eval_expr)
            elif value is None:
                eval_expr = re.sub(rf"\b{re.escape(field)}\b", "None", eval_expr)
            else:
                eval_expr = re.sub(rf"\b{re.escape(field)}\b", str(value), eval_expr)

        result = eval(eval_expr, {"__builtins__": {}}, {"True": True, "False": False, "None": None})
        return bool(result)
    except Exception:
        return False


def _evaluate_math_expression(expression: str, record: dict[str, Any]) -> float | None:
    """Evaluate a math expression and return numeric result."""
    try:
        context = dict(record)
        eval_expr = expression

        for field, value in context.items():
            if isinstance(value, (int, float)):
                eval_expr = re.sub(rf"\b{re.escape(field)}\b", str(value), eval_expr)

        result = eval(
            eval_expr,
            {"__builtins__": {}},
            {"sum": sum, "abs": abs, "min": min, "max": max}
        )
        return float(result)
    except Exception:
        return None


def _parse_date(value: Any) -> datetime | None:
    """Parse a value to datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            pass
    return None


def _map_failure_code(code_str: str) -> FailureCode:
    """Map failure code string to enum."""
    mapping = {
        "BL-003": FailureCode.CALCULATION_ERROR,
        "BL-004": FailureCode.INVALID_STATE_TRANSITION,
        "BL-005": FailureCode.TEMPORAL_ANOMALY,
        "BL-006": FailureCode.DOMAIN_RULE_VIOLATION,
    }
    return mapping.get(code_str, FailureCode.DOMAIN_RULE_VIOLATION)


def _extract_fields(expression: str, record: dict[str, Any]) -> list[str]:
    """Extract field names from expression."""
    fields = []
    for field in record.keys():
        if re.search(rf"\b{re.escape(field)}\b", expression):
            fields.append(field)
    return fields


def _format_values(fields: list[str], record: dict[str, Any]) -> str:
    """Format field values for error message."""
    parts = [f"{f}={record.get(f)!r}" for f in fields]
    return ", ".join(parts) if parts else "N/A"


def _get_record_id(record: dict[str, Any]) -> str | None:
    """Extract record ID."""
    for field in ["id", "order_id", "customer_id", "_id", "record_id"]:
        if field in record and record[field] is not None:
            return str(record[field])
    return None


def _violations_to_anomalies(
    violations: list[RuleViolation], batch_id: str
) -> list[BusinessLogicAnomaly]:
    """Convert violations to anomalies grouped by failure code."""
    by_code: dict[str, list[RuleViolation]] = {}
    for v in violations:
        code = v.failure_code.value
        if code not in by_code:
            by_code[code] = []
        by_code[code].append(v)

    anomalies: list[BusinessLogicAnomaly] = []

    for code, code_violations in by_code.items():
        first = code_violations[0]
        affected_records = [v.record_id for v in code_violations if v.record_id]
        affected_fields = list(set(f for v in code_violations for f in v.affected_fields))

        severity_score = min(100, 30 + len(code_violations) * 10)

        anomalies.append(
            BusinessLogicAnomaly(
                id=f"BL-{uuid4().hex[:8]}",
                failure_code=first.failure_code,
                severity=first.severity,
                severity_score=severity_score,
                rule_id=first.rule_id,
                rule_name=first.rule_name,
                affected_records=affected_records,
                affected_fields=affected_fields,
                batch_id=batch_id,
                explanation=f"{first.failure_code.description}: {len(code_violations)} violation(s)",
                expected_value=first.expected_value,
                actual_value=first.actual_value,
                details={
                    "violation_count": len(code_violations),
                    "failure_code": code,
                },
            )
        )

    return anomalies
