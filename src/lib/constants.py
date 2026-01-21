"""Constants and enumerations for DMRG-FTE."""

from enum import Enum


class FailureCode(str, Enum):
    """Failure codes for all tiers (DV-xxx Bronze, SC-xxx Schema, BL-xxx Business, FR-xxx Freshness)."""

    # Bronze Tier - Data Validation (DV-001 through DV-008)
    RECORD_COUNT_MISMATCH = "DV-001"
    NULL_VALUE_DETECTED = "DV-002"
    TYPE_MISMATCH = "DV-003"
    RANGE_VIOLATION = "DV-004"
    FORMAT_VIOLATION = "DV-005"
    DUPLICATE_DETECTED = "DV-006"
    ENCODING_ERROR = "DV-007"
    SCHEMA_VIOLATION = "DV-008"

    # Silver Tier - Schema & Contract Enforcement (SC-001 through SC-008)
    MISSING_COLUMN = "SC-001"
    EXTRA_COLUMN = "SC-002"
    COLUMN_TYPE_CHANGE = "SC-003"
    PRECISION_LOSS = "SC-004"
    CONSTRAINT_VIOLATION = "SC-005"
    VERSION_MISMATCH = "SC-006"
    BREAKING_CHANGE = "SC-007"
    CONTRACT_HASH_MISMATCH = "SC-008"

    # Silver Tier - Business Logic Validation (BL-001 through BL-008)
    CROSS_FIELD_INCONSISTENCY = "BL-001"
    REFERENTIAL_BREAK = "BL-002"
    CALCULATION_ERROR = "BL-003"
    INVALID_STATE_TRANSITION = "BL-004"
    TEMPORAL_ANOMALY = "BL-005"
    DOMAIN_RULE_VIOLATION = "BL-006"
    DISTRIBUTION_SHIFT = "BL-007"
    ORPHAN_RECORD = "BL-008"

    # Silver Tier - Freshness & SLA Monitoring (FR-001 through FR-008)
    DATA_STALE = "FR-001"
    SLA_BREACH = "FR-002"
    SLA_WARNING = "FR-003"
    PIPELINE_DELAY = "FR-004"
    MISSING_DELIVERY = "FR-005"
    JOB_FAILURE = "FR-006"
    DEPENDENCY_DELAY = "FR-007"
    LATENCY_SPIKE = "FR-008"

    # Gold Tier - Model Health (ML-001 through ML-008)
    PREDICTION_DRIFT = "ML-001"
    FEATURE_DRIFT = "ML-002"
    MODEL_STALENESS = "ML-003"
    CONFIDENCE_DEGRADATION = "ML-004"
    MODEL_LATENCY_SPIKE = "ML-005"
    ERROR_RATE_INCREASE = "ML-006"
    DATA_MODEL_MISMATCH = "ML-007"
    RETRAINING_NEEDED = "ML-008"

    # Gold Tier - Ethics & Bias (ET-001 through ET-008)
    DEMOGRAPHIC_DISPARITY = "ET-001"
    FAIRNESS_VIOLATION = "ET-002"
    PROTECTED_CLASS_IMPACT = "ET-003"
    EXPLAINABILITY_GAP = "ET-004"
    CONSENT_VIOLATION = "ET-005"
    PII_EXPOSURE_RISK = "ET-006"
    AUDIT_TRAIL_GAP = "ET-007"
    COMPLIANCE_BREACH = "ET-008"

    @property
    def description(self) -> str:
        """Return human-readable description for the failure code."""
        descriptions = {
            # Bronze Tier
            "DV-001": "Actual record count differs from expected",
            "DV-002": "Unexpected null or missing values in required field",
            "DV-003": "Field value does not match expected data type",
            "DV-004": "Numeric value outside allowed range",
            "DV-005": "Value does not match expected pattern/format",
            "DV-006": "Exact duplicate record found",
            "DV-007": "Invalid character encoding detected",
            "DV-008": "Record structure does not match expected schema",
            # Silver - Schema
            "SC-001": "Required column absent from data",
            "SC-002": "Unexpected column present in data",
            "SC-003": "Column data type differs from contract",
            "SC-004": "Numeric precision insufficient for declared contract",
            "SC-005": "Primary/foreign key or uniqueness violated",
            "SC-006": "Schema version incompatible with consumer expectation",
            "SC-007": "Non-backward-compatible schema modification detected",
            "SC-008": "API/data contract signature differs from registered version",
            # Silver - Business Logic
            "BL-001": "Related fields have logically incompatible values",
            "BL-002": "Referenced entity does not exist",
            "BL-003": "Derived/aggregated value does not match inputs",
            "BL-004": "Entity moved to impossible state",
            "BL-005": "Date/time value violates business time rules",
            "BL-006": "Value breaks explicit business constraint",
            "BL-007": "Statistical profile significantly different from baseline",
            "BL-008": "Record has no valid parent/owner",
            # Silver - Freshness
            "FR-001": "Time since last update exceeds freshness threshold",
            "FR-002": "Delivery deadline missed",
            "FR-003": "Delivery at risk (threshold proximity exceeded)",
            "FR-004": "Processing duration exceeds expected window",
            "FR-005": "Expected data arrival did not occur",
            "FR-006": "Scheduled pipeline execution failed",
            "FR-007": "Upstream dependency late, blocking downstream",
            "FR-008": "End-to-end time significantly above baseline",
            # Gold - Model Health
            "ML-001": "Model predictions drifting from expected distribution",
            "ML-002": "Input feature distribution shift detected",
            "ML-003": "Model age exceeds recommended retraining interval",
            "ML-004": "Prediction confidence scores degrading over time",
            "ML-005": "Model inference latency exceeds threshold",
            "ML-006": "Model error rate increased significantly",
            "ML-007": "Input data schema incompatible with model expectations",
            "ML-008": "Model performance indicates retraining required",
            # Gold - Ethics & Bias
            "ET-001": "Outcome disparity across demographic groups detected",
            "ET-002": "Fairness metric threshold violated",
            "ET-003": "Disproportionate impact on protected class identified",
            "ET-004": "Model decision lacks sufficient explainability",
            "ET-005": "Data usage may violate consent constraints",
            "ET-006": "Personally identifiable information exposure risk",
            "ET-007": "Decision audit trail incomplete or missing",
            "ET-008": "Regulatory compliance requirement not met",
        }
        return descriptions.get(self.value, "Unknown failure")

    @property
    def tier(self) -> str:
        """Return the tier this failure code belongs to."""
        if self.value.startswith("DV-"):
            return "bronze"
        elif self.value.startswith("SC-"):
            return "silver_schema"
        elif self.value.startswith("BL-"):
            return "silver_business"
        elif self.value.startswith("FR-"):
            return "silver_freshness"
        elif self.value.startswith("ML-"):
            return "gold_model_health"
        elif self.value.startswith("ET-"):
            return "gold_ethics"
        return "unknown"

    @property
    def layer(self) -> int:
        """Return the Constitution layer number."""
        tier_layers = {
            "bronze": 1,
            "silver_schema": 2,
            "silver_business": 3,
            "silver_freshness": 4,
            "gold_model_health": 5,
            "gold_ethics": 6,
        }
        return tier_layers.get(self.tier, 0)


class SeverityLevel(str, Enum):
    """Severity levels for anomalies."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

    @property
    def alert_priority(self) -> int:
        """Return numeric priority for sorting (higher = more urgent)."""
        priorities = {
            "INFO": 0,
            "WARNING": 1,
            "CRITICAL": 2,
        }
        return priorities.get(self.value, 0)

    @property
    def requires_alert(self) -> bool:
        """Return whether this severity level requires an alert."""
        return self in (SeverityLevel.WARNING, SeverityLevel.CRITICAL)

    @property
    def requires_quarantine(self) -> bool:
        """Return whether this severity level requires quarantine."""
        return self == SeverityLevel.CRITICAL


class BatchStatus(str, Enum):
    """Status of a data batch in the validation pipeline."""

    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"

    @property
    def is_terminal(self) -> bool:
        """Return whether this is a terminal (final) status."""
        return self in (BatchStatus.PASSED, BatchStatus.FAILED, BatchStatus.ERROR)

    @property
    def is_success(self) -> bool:
        """Return whether this status indicates successful validation."""
        return self == BatchStatus.PASSED


class EventType(str, Enum):
    """Event types for orchestrator event queue."""

    FILE_ARRIVED = "FILE_ARRIVED"
    SCHEDULED_CHECK = "SCHEDULED_CHECK"
    MANUAL_TRIGGER = "MANUAL_TRIGGER"
    HEARTBEAT = "HEARTBEAT"
    SHUTDOWN = "SHUTDOWN"


class AlertChannel(str, Enum):
    """Alert output channels."""

    CONSOLE = "CONSOLE"
    LOG_FILE = "LOG_FILE"


# Severity score thresholds
SEVERITY_THRESHOLDS = {
    SeverityLevel.CRITICAL: (70, 100),
    SeverityLevel.WARNING: (40, 69),
    SeverityLevel.INFO: (0, 39),
}

# Alert dispatch timeframes (seconds) - per SC-002
ALERT_DISPATCH_SECONDS = {
    SeverityLevel.CRITICAL: 60,  # 1 minute
    SeverityLevel.WARNING: 300,  # 5 minutes
    SeverityLevel.INFO: None,  # No alert for INFO
}

# Performance constraints
MAX_RECORD_VALIDATION_MS = 100  # Per Constitution 9.1
TARGET_10K_VALIDATION_SECONDS = 5  # Per SC-001
MAX_BATCH_SIZE = 100000  # Per Assumption 5
MAX_RECOVERY_SECONDS = 60  # Per SC-006
HEARTBEAT_INTERVAL_SECONDS = 60  # Per FR-014
MIN_SCHEDULER_INTERVAL_SECONDS = 30  # Per spec
