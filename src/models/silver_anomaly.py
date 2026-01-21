"""Silver Tier Anomaly Models.

This module defines anomaly types for Silver Tier validation:
- SchemaAnomaly: Schema and contract violations (SC-001 to SC-008)
- BusinessLogicAnomaly: Business rule violations (BL-001 to BL-008)
- FreshnessAnomaly: Freshness and SLA violations (FR-001 to FR-008)
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.lib.constants import FailureCode, SeverityLevel


class ColumnCriticality(str, Enum):
    """Column criticality determines severity of missing/invalid column."""

    REQUIRED = "required"  # Missing/invalid → CRITICAL severity
    OPTIONAL = "optional"  # Missing/invalid → WARNING severity


class ViolationDetail(BaseModel):
    """Details about a specific schema violation."""

    column: str = Field(..., description="Column name")
    issue: str = Field(..., description="What's wrong")
    expected: str | None = Field(None, description="Expected value/type")
    actual: str | None = Field(None, description="Actual value/type")


class SchemaAnomaly(BaseModel):
    """Records schema/contract violations (SC-001 through SC-008).

    Attributes:
        id: Unique anomaly identifier
        failure_code: SC-001 through SC-008
        severity: Based on column criticality
        contract_id: Schema contract reference
        contract_version: Contract version
        affected_columns: Columns with violations
        violation_details: Specific issues
        batch_id: Data batch reference
        timestamp: Detection time
        explanation: Human-readable description
        blocking: Prevents downstream processing
    """

    id: str = Field(..., description="Unique anomaly identifier")
    failure_code: FailureCode = Field(..., description="SC-001 through SC-008")
    severity: SeverityLevel = Field(..., description="Based on column criticality")
    contract_id: str = Field(..., description="Schema contract reference")
    contract_version: str = Field(..., description="Contract version")
    affected_columns: list[str] = Field(default_factory=list, description="Columns with violations")
    violation_details: list[ViolationDetail] = Field(
        default_factory=list, description="Specific issues"
    )
    batch_id: str = Field(..., description="Data batch reference")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection time")
    explanation: str = Field(..., description="Human-readable description")
    blocking: bool = Field(default=False, description="Prevents downstream processing")

    @property
    def is_schema_anomaly(self) -> bool:
        """Return True if this is a schema anomaly."""
        return self.failure_code.value.startswith("SC-")


class BusinessLogicAnomaly(BaseModel):
    """Records business rule violations (BL-001 through BL-008).

    Attributes:
        id: Unique anomaly identifier
        failure_code: BL-001 through BL-008
        severity: From rule definition
        severity_score: Calculated 0-100
        rule_id: Business rule reference
        rule_name: Human-readable rule name
        affected_records: Record IDs
        affected_fields: Fields involved
        batch_id: Data batch reference
        timestamp: Detection time
        explanation: Human-readable description
        expected_value: What was expected
        actual_value: What was found
        details: Additional context
    """

    id: str = Field(..., description="Unique anomaly identifier")
    failure_code: FailureCode = Field(..., description="BL-001 through BL-008")
    severity: SeverityLevel = Field(..., description="From rule definition")
    severity_score: int = Field(..., ge=0, le=100, description="Calculated severity score")
    rule_id: str = Field(..., description="Business rule reference")
    rule_name: str = Field(..., description="Human-readable rule name")
    affected_records: list[str] = Field(default_factory=list, description="Record IDs")
    affected_fields: list[str] = Field(default_factory=list, description="Fields involved")
    batch_id: str = Field(..., description="Data batch reference")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection time")
    explanation: str = Field(..., description="Human-readable description")
    expected_value: str | None = Field(None, description="What was expected")
    actual_value: str | None = Field(None, description="What was found")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @property
    def is_business_logic_anomaly(self) -> bool:
        """Return True if this is a business logic anomaly."""
        return self.failure_code.value.startswith("BL-")


class FreshnessAnomaly(BaseModel):
    """Records timeliness violations (FR-001 through FR-008).

    Attributes:
        id: Unique anomaly identifier
        failure_code: FR-001 through FR-008
        severity: Based on threshold
        source: Data source name
        sla_id: SLA definition reference
        expected_at: When data was expected
        last_arrival: When data last arrived
        delay_seconds: Delay duration
        timestamp: Detection time
        explanation: Human-readable description
        pipeline_stage: For pipeline stalls
        details: Additional context
    """

    id: str = Field(..., description="Unique anomaly identifier")
    failure_code: FailureCode = Field(..., description="FR-001 through FR-008")
    severity: SeverityLevel = Field(..., description="Based on threshold")
    source: str = Field(..., description="Data source name")
    sla_id: str = Field(..., description="SLA definition reference")
    expected_at: datetime = Field(..., description="When data was expected")
    last_arrival: datetime | None = Field(None, description="When data last arrived")
    delay_seconds: int = Field(..., ge=0, description="Delay duration in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Detection time")
    explanation: str = Field(..., description="Human-readable description")
    pipeline_stage: str | None = Field(None, description="For pipeline stall issues")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    @property
    def is_freshness_anomaly(self) -> bool:
        """Return True if this is a freshness anomaly."""
        return self.failure_code.value.startswith("FR-")

    @property
    def delay_minutes(self) -> float:
        """Return delay in minutes."""
        return self.delay_seconds / 60.0


# Type alias for any Silver tier anomaly
SilverAnomaly = SchemaAnomaly | BusinessLogicAnomaly | FreshnessAnomaly


class AnomalyCount(BaseModel):
    """Counts of anomalies by layer."""

    schema_count: int = Field(default=0, ge=0, description="Active schema anomalies")
    business_logic: int = Field(default=0, ge=0, description="Active BL anomalies")
    freshness: int = Field(default=0, ge=0, description="Active freshness anomalies")

    @property
    def total(self) -> int:
        """Return total anomaly count."""
        return self.schema_count + self.business_logic + self.freshness
