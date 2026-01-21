# Data Model: Silver Tier - Schema, Business Logic & Freshness Enforcement

**Feature**: `003-silver-tier-enforcement`
**Date**: 2026-01-18
**Phase**: 1 - Design

---

## Entity Overview

The Silver Tier extends the Bronze data model with 7 new entities from the specification (spec.md Key Entities section):

```
                      ┌─────────────────┐
                      │ Bronze Validated│
                      │     Batch       │
                      └────────┬────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │SchemaContract│    │ BusinessRule │    │ SLADefinition│
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           │                   │                   │
           │ validates         │ evaluates         │ monitors
           ▼                   ▼                   ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │SchemaAnomaly │    │  BizLogic    │    │  Freshness   │
    │ (SC-001-008) │    │   Anomaly    │    │   Anomaly    │
    └──────────────┘    │ (BL-001-008) │    │ (FR-001-008) │
                        └──────────────┘    └──────────────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │SilverTierHealthScore│
                    └─────────────────────┘

    ┌──────────────────┐
    │ ReferenceDataSet │ ◄─── Loaded at startup for refint checks
    └──────────────────┘
```

---

## Entity Definitions

### 1. SchemaContract

**Purpose**: Represents a versioned schema definition for a data source, including column definitions, data types, constraints, and column criticality flags.

**Source**: spec.md Key Entities, Constitution Section 3.2

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique contract identifier |
| `name` | `str` | Yes | Human-readable name |
| `version` | `str` | Yes | Semantic version (e.g., "2.1.0") |
| `source` | `str` | Yes | Data source this contract applies to |
| `schema` | `dict` | Yes | JSON Schema definition |
| `columns` | `list[ColumnDefinition]` | Yes | Column specifications |
| `constraints` | `list[Constraint]` | No | PK, FK, unique constraints |
| `compatibility` | `CompatibilityMode` | Yes | Forward/backward compatibility |
| `checksum` | `str` | Yes | SHA-256 hash of schema |
| `created_at` | `datetime` | Yes | Creation timestamp |
| `updated_at` | `datetime` | No | Last modification |
| `metadata` | `dict` | No | Additional metadata |

**ColumnDefinition**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Column name |
| `type` | `DataType` | Yes | Data type (string, integer, decimal, datetime, boolean) |
| `required` | `bool` | Yes | Whether column is required |
| `criticality` | `ColumnCriticality` | Yes | required or optional (for severity) |
| `precision` | `int` | No | For decimal types |
| `scale` | `int` | No | For decimal types |
| `pattern` | `str` | No | Regex pattern for strings |
| `min_value` | `Any` | No | Minimum allowed value |
| `max_value` | `Any` | No | Maximum allowed value |

**ColumnCriticality Enum** (from clarification Q1):
```
REQUIRED  - Missing/invalid → CRITICAL severity
OPTIONAL  - Missing/invalid → WARNING severity
```

**CompatibilityMode Enum**:
```
BACKWARD  - New schema can read old data
FORWARD   - Old consumers can read new data
FULL      - Both backward and forward compatible
NONE      - Breaking changes allowed
```

**Constraint**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `ConstraintType` | Yes | PRIMARY_KEY, FOREIGN_KEY, UNIQUE |
| `columns` | `list[str]` | Yes | Columns involved |
| `references` | `str` | No | For FK: referenced table.column |

---

### 2. BusinessRule

**Purpose**: Represents a configurable validation rule that checks cross-field relationships, calculations, or domain constraints.

**Source**: spec.md Key Entities, Constitution Section 3.3

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique rule identifier |
| `name` | `str` | Yes | Human-readable rule name |
| `source` | `str` | Yes | Data source this rule applies to |
| `type` | `RuleType` | Yes | Type of validation |
| `expression` | `str` | No | Rule expression (for comparison, calculation) |
| `field` | `str` | No | Primary field (for referential, state) |
| `reference` | `str` | No | Reference source (for referential) |
| `allowed_values` | `list[str]` | No | For state transitions |
| `tolerance` | `float` | No | For calculations (default 0.0) |
| `severity` | `SeverityLevel` | Yes | CRITICAL or WARNING |
| `enabled` | `bool` | Yes | Rule is active |
| `description` | `str` | No | Rule purpose |
| `failure_code` | `str` | Yes | BL-001 through BL-008 |

**RuleType Enum**:
```
CROSSFIELD       - Cross-field comparison (e.g., end_date > start_date)
REFERENTIAL      - Foreign key/lookup validation
CALCULATION      - Derived field verification
STATE_TRANSITION - Valid state sequence
TEMPORAL         - Date/time rules
DOMAIN           - Domain-specific constraints
DISTRIBUTION     - Statistical shift detection
ORPHAN           - Parent/owner validation
```

**Example Rules**:
```yaml
# Cross-field: end_date > start_date
- id: BL-001-date-order
  type: crossfield
  expression: "end_date > start_date"
  failure_code: BL-001

# Referential: account_id exists
- id: BL-002-account-ref
  type: referential
  field: account_id
  reference: accounts
  failure_code: BL-002

# Calculation: sum matches total
- id: BL-003-order-total
  type: calculation
  expression: "sum(line_items.amount) == order_total"
  tolerance: 0.01
  failure_code: BL-003

# State transition: valid order status
- id: BL-004-order-status
  type: state_transition
  field: status
  allowed_values: [PENDING, CONFIRMED, SHIPPED, DELIVERED]
  failure_code: BL-004
```

---

### 3. ReferenceDataSet

**Purpose**: Represents lookup data (CSV/JSON files) loaded at startup for referential integrity checks.

**Source**: spec.md Key Entities (clarification Q2)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | Yes | Reference set name (e.g., "accounts") |
| `source_path` | `Path` | Yes | File path (CSV or JSON) |
| `key_column` | `str` | Yes | Column to use as lookup key |
| `values` | `set[str]` | Yes | Loaded values for lookup |
| `loaded_at` | `datetime` | Yes | Last load timestamp |
| `record_count` | `int` | Yes | Number of entries |
| `refresh_interval` | `timedelta` | No | Auto-refresh interval (default 1 hour) |
| `last_refresh` | `datetime` | No | Last refresh time |

**File Format Support**:
| Format | Key Column |
|--------|------------|
| CSV | Specified column header |
| JSON (array) | Specified field path |
| JSON (object) | Keys of object |

**Usage**:
```python
# Check if account_id exists
reference_sets["accounts"].lookup("ACC-12345")  # Returns True/False
```

---

### 4. SLADefinition

**Purpose**: Represents expected arrival times, latency thresholds, and freshness requirements for a data source.

**Source**: spec.md Key Entities, Constitution Section 3.4

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique SLA identifier |
| `source` | `str` | Yes | Data source name |
| `schedule` | `str` | Yes | Cron expression for expected arrivals |
| `freshness_threshold` | `FreshnessThreshold` | Yes | Staleness thresholds |
| `latency_threshold` | `int` | No | Max end-to-end seconds |
| `enabled` | `bool` | Yes | SLA is active |
| `owner` | `str` | No | Responsible team/person |
| `description` | `str` | No | SLA purpose |

**FreshnessThreshold**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `warning_minutes` | `int` | Yes | Minutes until WARNING (default 60) |
| `critical_minutes` | `int` | Yes | Minutes until CRITICAL (default 90) |

**Example SLA**:
```yaml
- id: sla-orders-hourly
  source: orders
  schedule: "0 * * * *"  # Every hour at :00
  freshness_threshold:
    warning_minutes: 60
    critical_minutes: 90
  latency_threshold: 1800  # 30 minutes
  owner: data-platform-team
```

---

### 5. SchemaAnomaly

**Purpose**: Records schema/contract violations (SC-001 through SC-008) with specific details about the violation.

**Source**: spec.md Key Entities, Constitution Section 3.2

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique anomaly identifier |
| `failure_code` | `SchemaFailureCode` | Yes | SC-001 through SC-008 |
| `severity` | `SeverityLevel` | Yes | Based on column criticality |
| `contract_id` | `str` | Yes | Schema contract reference |
| `contract_version` | `str` | Yes | Contract version |
| `affected_columns` | `list[str]` | Yes | Columns with violations |
| `violation_details` | `list[ViolationDetail]` | Yes | Specific issues |
| `batch_id` | `str` | Yes | Data batch reference |
| `timestamp` | `datetime` | Yes | Detection time |
| `explanation` | `str` | Yes | Human-readable description |
| `blocking` | `bool` | Yes | Prevents downstream processing |

**SchemaFailureCode Enum** (Constitution Section 3.2):
```
SC_001 = "Missing Column"        - Required column absent
SC_002 = "Extra Column"          - Unexpected column present
SC_003 = "Column Type Change"    - Type differs from contract
SC_004 = "Precision Loss"        - Numeric precision insufficient
SC_005 = "Constraint Violation"  - PK/FK/unique violated
SC_006 = "Version Mismatch"      - Schema version incompatible
SC_007 = "Breaking Change"       - Non-backward-compatible change
SC_008 = "Contract Hash Mismatch"- Contract signature differs
```

**ViolationDetail**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `column` | `str` | Yes | Column name |
| `issue` | `str` | Yes | What's wrong |
| `expected` | `str` | No | Expected value/type |
| `actual` | `str` | No | Actual value/type |

---

### 6. BusinessLogicAnomaly

**Purpose**: Records business rule violations (BL-001 through BL-008) with affected records and rule details.

**Source**: spec.md Key Entities, Constitution Section 3.3

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique anomaly identifier |
| `failure_code` | `BusinessFailureCode` | Yes | BL-001 through BL-008 |
| `severity` | `SeverityLevel` | Yes | From rule definition |
| `severity_score` | `int` | Yes | Calculated 0-100 |
| `rule_id` | `str` | Yes | Business rule reference |
| `rule_name` | `str` | Yes | Human-readable rule name |
| `affected_records` | `list[str]` | Yes | Record IDs |
| `affected_fields` | `list[str]` | Yes | Fields involved |
| `batch_id` | `str` | Yes | Data batch reference |
| `timestamp` | `datetime` | Yes | Detection time |
| `explanation` | `str` | Yes | Human-readable description |
| `expected_value` | `str` | No | What was expected |
| `actual_value` | `str` | No | What was found |
| `details` | `dict` | No | Additional context |

**BusinessFailureCode Enum** (Constitution Section 3.3):
```
BL_001 = "Cross-Field Inconsistency"  - Related fields incompatible
BL_002 = "Referential Break"          - Referenced entity missing
BL_003 = "Calculation Error"          - Derived value mismatch
BL_004 = "Invalid State Transition"   - Impossible state change
BL_005 = "Temporal Anomaly"           - Date/time rule violation
BL_006 = "Domain Rule Violation"      - Business constraint broken
BL_007 = "Distribution Shift"         - Statistical profile changed
BL_008 = "Orphan Record"              - No valid parent/owner
```

---

### 7. FreshnessAnomaly

**Purpose**: Records timeliness violations (FR-001 through FR-008) with timing details and breach duration.

**Source**: spec.md Key Entities, Constitution Section 3.4

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique anomaly identifier |
| `failure_code` | `FreshnessFailureCode` | Yes | FR-001 through FR-008 |
| `severity` | `SeverityLevel` | Yes | Based on threshold |
| `source` | `str` | Yes | Data source name |
| `sla_id` | `str` | Yes | SLA definition reference |
| `expected_at` | `datetime` | Yes | When data was expected |
| `last_arrival` | `datetime` | No | When data last arrived |
| `delay_seconds` | `int` | Yes | Delay duration |
| `timestamp` | `datetime` | Yes | Detection time |
| `explanation` | `str` | Yes | Human-readable description |
| `pipeline_stage` | `str` | No | For pipeline stalls |
| `details` | `dict` | No | Additional context |

**FreshnessFailureCode Enum** (Constitution Section 3.4):
```
FR_001 = "Data Stale"       - Time since update exceeds threshold
FR_002 = "SLA Breach"       - Delivery deadline missed
FR_003 = "SLA Warning"      - Delivery at risk
FR_004 = "Pipeline Delay"   - Processing exceeds expected window
FR_005 = "Missing Delivery" - Expected data did not arrive
FR_006 = "Job Failure"      - Scheduled pipeline failed
FR_007 = "Dependency Delay" - Upstream blocking downstream
FR_008 = "Latency Spike"    - End-to-end time above baseline
```

---

### 8. SilverTierHealthScore

**Purpose**: Aggregates health metrics across all three Silver Tier layers.

**Source**: spec.md Key Entities, Constitution Section 6.3

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | `datetime` | Yes | Calculation time |
| `overall_score` | `int` | Yes | Minimum of layer scores (0-100) |
| `schema_score` | `int` | Yes | Layer 2 health (0-100) |
| `business_logic_score` | `int` | Yes | Layer 3 health (0-100) |
| `freshness_score` | `int` | Yes | Layer 4 health (0-100) |
| `trend` | `Trend` | Yes | Direction of change |
| `active_anomalies` | `AnomalyCount` | Yes | Counts by layer |
| `last_validation` | `datetime` | No | Most recent validation |

**AnomalyCount**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema` | `int` | Yes | Active schema anomalies |
| `business_logic` | `int` | Yes | Active BL anomalies |
| `freshness` | `int` | Yes | Active freshness anomalies |
| `total` | `int` | Yes | Sum of all |

**Aggregate Formula** (Constitution Section 6.3):
```
Overall Silver Health = Minimum(schema_score, business_logic_score, freshness_score)
```

---

## Extended Failure Codes (constants.py)

Add to existing FailureCode enum:

```python
class FailureCode(str, Enum):
    # Bronze Tier (existing)
    DV_001 = "DV-001"  # Missing Records
    DV_002 = "DV-002"  # Excess Records
    DV_003 = "DV-003"  # Null Violation
    DV_004 = "DV-004"  # Type Mismatch
    DV_005 = "DV-005"  # Range Violation
    DV_006 = "DV-006"  # Format Violation
    DV_007 = "DV-007"  # Duplicate Record
    DV_008 = "DV-008"  # Encoding Error

    # Silver Tier - Schema (NEW)
    SC_001 = "SC-001"  # Missing Column
    SC_002 = "SC-002"  # Extra Column
    SC_003 = "SC-003"  # Column Type Change
    SC_004 = "SC-004"  # Precision Loss
    SC_005 = "SC-005"  # Constraint Violation
    SC_006 = "SC-006"  # Version Mismatch
    SC_007 = "SC-007"  # Breaking Change
    SC_008 = "SC-008"  # Contract Hash Mismatch

    # Silver Tier - Business Logic (NEW)
    BL_001 = "BL-001"  # Cross-Field Inconsistency
    BL_002 = "BL-002"  # Referential Break
    BL_003 = "BL-003"  # Calculation Error
    BL_004 = "BL-004"  # Invalid State Transition
    BL_005 = "BL-005"  # Temporal Anomaly
    BL_006 = "BL-006"  # Domain Rule Violation
    BL_007 = "BL-007"  # Distribution Shift
    BL_008 = "BL-008"  # Orphan Record

    # Silver Tier - Freshness (NEW)
    FR_001 = "FR-001"  # Data Stale
    FR_002 = "FR-002"  # SLA Breach
    FR_003 = "FR-003"  # SLA Warning
    FR_004 = "FR-004"  # Pipeline Delay
    FR_005 = "FR-005"  # Missing Delivery
    FR_006 = "FR-006"  # Job Failure
    FR_007 = "FR-007"  # Dependency Delay
    FR_008 = "FR-008"  # Latency Spike
```

---

## Relationships

```
SchemaContract (1) ────── validates ────── (N) DataBatch
       │
       │ produces
       ▼
SchemaAnomaly (N) ────────────────────────┐
                                          │
BusinessRule (N) ─── evaluates against ── DataBatch
       │                                  │
       │ produces                         │
       ▼                                  │
BusinessLogicAnomaly (N) ─────────────────┤
                                          │
SLADefinition (1) ─── monitors ─── DataSource
       │                                  │
       │ produces                         │
       ▼                                  │
FreshnessAnomaly (N) ─────────────────────┤
                                          │
                                          ▼
                             SilverTierHealthScore
                                          │
                                          │ updates
                                          ▼
                                  Unified Dashboard

ReferenceDataSet (N) ◄─── used by ─── BusinessRule (referential type)
```

**Key Relationships**:
1. A `SchemaContract` validates multiple `DataBatch` instances
2. A `SchemaAnomaly` references one `SchemaContract` and one `DataBatch`
3. Multiple `BusinessRule` instances evaluate against each `DataBatch`
4. A `BusinessLogicAnomaly` references one `BusinessRule` and affects multiple records
5. An `SLADefinition` monitors one data source
6. A `FreshnessAnomaly` references one `SLADefinition`
7. `ReferenceDataSet` is used by referential-type `BusinessRule` instances
8. `SilverTierHealthScore` aggregates all three anomaly types

---

## File Storage Locations

For MVP file-based storage:

| Entity | Location | Format |
|--------|----------|--------|
| SchemaContract | `config/schemas/{source}.json` | JSON Schema |
| BusinessRule | `config/rules/{source}.yaml` | YAML |
| ReferenceDataSet | `data/reference/{name}.csv` or `.json` | CSV/JSON |
| SLADefinition | `config/sla/{source}.yaml` | YAML |
| SchemaAnomaly | `data/results/{result_id}.json` (embedded) | JSON |
| BusinessLogicAnomaly | `data/results/{result_id}.json` (embedded) | JSON |
| FreshnessAnomaly | `data/results/{result_id}.json` (embedded) | JSON |
| SilverTierHealthScore | `data/state/health.json` (silver section) | JSON |
| Freshness State | `data/state/freshness.json` | JSON |
| Baselines | `data/state/baselines.json` | JSON |

---

## Pydantic Model Examples

### SchemaContract Model

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Any
from pathlib import Path

class ColumnCriticality(str, Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"

class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATETIME = "datetime"
    BOOLEAN = "boolean"

class ColumnDefinition(BaseModel):
    name: str
    type: DataType
    required: bool
    criticality: ColumnCriticality
    precision: int | None = None
    scale: int | None = None
    pattern: str | None = None
    min_value: Any | None = None
    max_value: Any | None = None

class SchemaContract(BaseModel):
    id: str
    name: str
    version: str
    source: str
    schema: dict[str, Any]  # JSON Schema
    columns: list[ColumnDefinition]
    constraints: list[dict] = Field(default_factory=list)
    compatibility: str = "BACKWARD"
    checksum: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### BusinessRule Model

```python
class RuleType(str, Enum):
    CROSSFIELD = "crossfield"
    REFERENTIAL = "referential"
    CALCULATION = "calculation"
    STATE_TRANSITION = "state_transition"
    TEMPORAL = "temporal"
    DOMAIN = "domain"
    DISTRIBUTION = "distribution"
    ORPHAN = "orphan"

class BusinessRule(BaseModel):
    id: str
    name: str
    source: str
    type: RuleType
    expression: str | None = None
    field: str | None = None
    reference: str | None = None
    allowed_values: list[str] | None = None
    tolerance: float = 0.0
    severity: SeverityLevel
    enabled: bool = True
    description: str | None = None
    failure_code: str
```

### SLADefinition Model

```python
from datetime import timedelta

class FreshnessThreshold(BaseModel):
    warning_minutes: int = 60
    critical_minutes: int = 90

class SLADefinition(BaseModel):
    id: str
    source: str
    schedule: str  # Cron expression
    freshness_threshold: FreshnessThreshold
    latency_threshold: int | None = None  # Seconds
    enabled: bool = True
    owner: str | None = None
    description: str | None = None
```

### Silver Anomaly Models

```python
class SchemaAnomaly(BaseModel):
    id: str
    failure_code: str  # SC-001 to SC-008
    severity: SeverityLevel
    contract_id: str
    contract_version: str
    affected_columns: list[str]
    violation_details: list[dict]
    batch_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    explanation: str
    blocking: bool

class BusinessLogicAnomaly(BaseModel):
    id: str
    failure_code: str  # BL-001 to BL-008
    severity: SeverityLevel
    severity_score: int = Field(..., ge=0, le=100)
    rule_id: str
    rule_name: str
    affected_records: list[str]
    affected_fields: list[str]
    batch_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    explanation: str
    expected_value: str | None = None
    actual_value: str | None = None
    details: dict = Field(default_factory=dict)

class FreshnessAnomaly(BaseModel):
    id: str
    failure_code: str  # FR-001 to FR-008
    severity: SeverityLevel
    source: str
    sla_id: str
    expected_at: datetime
    last_arrival: datetime | None = None
    delay_seconds: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    explanation: str
    pipeline_stage: str | None = None
    details: dict = Field(default_factory=dict)
```

---

## Data Lifecycle

```
1. Bronze Validation Complete
   └── DataBatch passed Bronze → ready for Silver

2. Schema Validation (Layer 2)
   └── Load SchemaContract for source
   └── Validate against JSON Schema
   └── Check version compatibility
   └── Generate SchemaAnomaly for violations
   └── Block if CRITICAL (required column issues)

3. Business Logic Validation (Layer 3)
   └── Load BusinessRule set for source
   └── Load ReferenceDataSet for lookups
   └── Evaluate each rule against records
   └── Generate BusinessLogicAnomaly for failures
   └── Calculate severity scores

4. Freshness Monitoring (Layer 4) [PARALLEL]
   └── Check SLADefinition for each source
   └── Compare last_arrival vs expected
   └── Generate FreshnessAnomaly if threshold exceeded
   └── Escalate at warning/critical thresholds

5. Health Score Update
   └── Calculate per-layer scores
   └── Overall = minimum(schema, bizlogic, freshness)
   └── Update SilverTierHealthScore

6. Dashboard Update
   └── Write anomalies to results/
   └── Update health.json
   └── Append to audit log
```

---

## Configuration Examples

### Schema Contract (config/schemas/orders.json)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "id": "orders-v2.1",
  "name": "Orders Schema",
  "version": "2.1.0",
  "source": "orders",
  "type": "object",
  "required": ["order_id", "customer_id", "order_total", "created_at"],
  "properties": {
    "order_id": {"type": "string", "pattern": "^ORD-[0-9]{8}$"},
    "customer_id": {"type": "string"},
    "order_total": {"type": "number", "minimum": 0},
    "discount": {"type": "number", "minimum": 0},
    "status": {"type": "string", "enum": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"]},
    "created_at": {"type": "string", "format": "date-time"}
  },
  "x-column-criticality": {
    "order_id": "required",
    "customer_id": "required",
    "order_total": "required",
    "discount": "optional",
    "status": "required",
    "created_at": "required"
  }
}
```

### Business Rules (config/rules/orders.yaml)

```yaml
rules:
  - id: BL-001-discount-limit
    name: Discount cannot exceed order total
    type: domain
    expression: "discount <= order_total"
    severity: critical
    failure_code: BL-006

  - id: BL-002-customer-exists
    name: Customer must exist
    type: referential
    field: customer_id
    reference: customers
    severity: critical
    failure_code: BL-002

  - id: BL-003-valid-status
    name: Valid order status transition
    type: state_transition
    field: status
    allowed_values: [PENDING, CONFIRMED, SHIPPED, DELIVERED]
    severity: critical
    failure_code: BL-004
```

### SLA Definition (config/sla/orders.yaml)

```yaml
- id: sla-orders-hourly
  source: orders
  schedule: "0 * * * *"
  freshness_threshold:
    warning_minutes: 60
    critical_minutes: 90
  latency_threshold: 1800
  owner: data-platform-team
  description: Orders data expected hourly
```
