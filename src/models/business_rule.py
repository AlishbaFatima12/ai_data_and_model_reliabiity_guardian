"""Business Rule Models for Silver Tier Layer 3.

This module defines models for business rule validation:
- BusinessRule: Represents a configurable validation rule
- RuleType: Types of business rules supported
- RuleResult: Result of evaluating a rule
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel


class RuleType(str, Enum):
    """Types of business rules supported."""

    CROSSFIELD = "crossfield"  # Field comparisons (BL-001)
    REFERENTIAL = "referential"  # FK checks (BL-002)
    CALCULATION = "calculation"  # Math validation (BL-003)
    STATE_TRANSITION = "state_transition"  # Lifecycle (BL-004)
    TEMPORAL = "temporal"  # Date/time rules (BL-005)
    DOMAIN = "domain"  # Value constraints (BL-006)
    DISTRIBUTION = "distribution"  # Statistical (BL-007)
    ORPHAN = "orphan"  # Parent check (BL-008)


class ComparisonOperator(str, Enum):
    """Comparison operators for rule expressions."""

    EQ = "=="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    MATCHES = "matches"  # regex


class BusinessRule(BaseModel):
    """Represents a configurable validation rule.

    Attributes:
        id: Unique rule identifier
        name: Human-readable rule name
        description: Detailed description
        type: Rule type (crossfield, referential, etc.)
        failure_code: BL-001 through BL-008
        severity: Default severity level
        enabled: Whether rule is active
        priority: Evaluation order (higher = first)
        expression: Rule expression to evaluate
        fields: Fields involved in the rule
        condition: Optional precondition (IF x THEN check y)
        parameters: Additional rule parameters
        created_at: When rule was created
        updated_at: When rule was last modified
    """

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    description: str = Field(default="", description="Detailed description")
    type: RuleType = Field(..., description="Rule type")
    failure_code: FailureCode = Field(..., description="BL-001 through BL-008")
    severity: SeverityLevel = Field(
        default=SeverityLevel.WARNING, description="Default severity level"
    )
    enabled: bool = Field(default=True, description="Whether rule is active")
    priority: int = Field(default=0, ge=0, description="Evaluation order")
    expression: str = Field(..., description="Rule expression to evaluate")
    fields: list[str] = Field(default_factory=list, description="Fields involved")
    condition: str | None = Field(None, description="Precondition expression")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Additional parameters"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last modification time"
    )

    @property
    def is_crossfield(self) -> bool:
        """Return True if this is a cross-field rule."""
        return self.type == RuleType.CROSSFIELD

    @property
    def is_referential(self) -> bool:
        """Return True if this is a referential integrity rule."""
        return self.type == RuleType.REFERENTIAL

    @property
    def is_stateful(self) -> bool:
        """Return True if rule requires state tracking."""
        return self.type in (RuleType.STATE_TRANSITION, RuleType.DISTRIBUTION)


class StateTransitionRule(BaseModel):
    """Specialized rule for state transition validation.

    Attributes:
        id: Unique rule identifier
        name: Human-readable rule name
        field: Field containing state value
        allowed_states: List of valid states
        allowed_transitions: Map of state -> valid next states
        failure_code: Always BL-004
        severity: Default CRITICAL
    """

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    field: str = Field(..., description="Field containing state value")
    allowed_states: list[str] = Field(..., description="List of valid states")
    allowed_transitions: dict[str, list[str]] = Field(
        ..., description="State transition matrix"
    )
    failure_code: FailureCode = Field(
        default=FailureCode.INVALID_STATE_TRANSITION, description="BL-004"
    )
    severity: SeverityLevel = Field(default=SeverityLevel.CRITICAL)

    def is_valid_transition(self, from_state: str, to_state: str) -> bool:
        """Check if transition is allowed.

        Args:
            from_state: Current state.
            to_state: Target state.

        Returns:
            True if transition is allowed.
        """
        if from_state not in self.allowed_transitions:
            return False
        return to_state in self.allowed_transitions[from_state]


class CalculationRule(BaseModel):
    """Specialized rule for calculation validation.

    Attributes:
        id: Unique rule identifier
        name: Human-readable rule name
        result_field: Field containing calculated result
        expression: Calculation expression
        tolerance: Allowed difference (for float comparisons)
        failure_code: Always BL-003
    """

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    result_field: str = Field(..., description="Field with calculated result")
    expression: str = Field(..., description="Expected calculation expression")
    tolerance: float = Field(default=0.001, description="Allowed difference")
    failure_code: FailureCode = Field(
        default=FailureCode.CALCULATION_ERROR, description="BL-003"
    )
    severity: SeverityLevel = Field(default=SeverityLevel.CRITICAL)


class RuleViolation(BaseModel):
    """Details about a rule violation.

    Attributes:
        rule_id: ID of the violated rule
        rule_name: Name of the violated rule
        failure_code: BL-xxx code
        severity: Severity level
        record_id: ID of affected record (if available)
        affected_fields: Fields involved in violation
        expected_value: What was expected
        actual_value: What was found
        message: Human-readable violation message
    """

    rule_id: str = Field(..., description="ID of violated rule")
    rule_name: str = Field(..., description="Name of violated rule")
    failure_code: FailureCode = Field(..., description="BL-xxx code")
    severity: SeverityLevel = Field(..., description="Severity level")
    record_id: str | None = Field(None, description="Affected record ID")
    affected_fields: list[str] = Field(default_factory=list, description="Fields involved")
    expected_value: str | None = Field(None, description="Expected value")
    actual_value: str | None = Field(None, description="Actual value")
    message: str = Field(..., description="Human-readable message")


class RuleEvaluationResult(BaseModel):
    """Result of evaluating business rules on a batch.

    Attributes:
        rules_evaluated: Number of rules evaluated
        rules_passed: Number of rules that passed
        rules_failed: Number of rules that failed
        rules_skipped: Number of rules skipped (disabled/condition not met)
        violations: List of violations found
        duration_ms: Evaluation time in milliseconds
    """

    rules_evaluated: int = Field(default=0, ge=0, description="Rules evaluated")
    rules_passed: int = Field(default=0, ge=0, description="Rules passed")
    rules_failed: int = Field(default=0, ge=0, description="Rules failed")
    rules_skipped: int = Field(default=0, ge=0, description="Rules skipped")
    violations: list[RuleViolation] = Field(
        default_factory=list, description="Violations found"
    )
    duration_ms: float = Field(default=0.0, ge=0, description="Evaluation time")

    @property
    def has_violations(self) -> bool:
        """Return True if any violations were found."""
        return len(self.violations) > 0

    @property
    def critical_violations(self) -> list[RuleViolation]:
        """Return only CRITICAL violations."""
        return [v for v in self.violations if v.severity == SeverityLevel.CRITICAL]
