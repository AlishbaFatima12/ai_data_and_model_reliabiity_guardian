# Data Model: Bronze Tier MVP with Orchestrator

**Feature**: `001-bronze-orchestrator-mvp`
**Date**: 2026-01-18
**Phase**: 1 - Design

---

## Entity Overview

The Bronze MVP defines 6 core entities from the specification (spec.md Key Entities section):

```
┌─────────────┐      validates      ┌──────────────────┐
│  DataBatch  │─────────────────────│ ValidationResult │
└─────────────┘                     └──────────────────┘
      │                                    │
      │ contains                           │ contains
      ▼                                    ▼
┌─────────────┐                     ┌──────────────┐
│   Record    │                     │   Anomaly    │
└─────────────┘                     └──────────────┘
                                           │
                                           │ triggers
                                           ▼
┌─────────────┐      calculates     ┌──────────────┐
│ HealthScore │◄────────────────────│    Alert     │
└─────────────┘                     └──────────────┘
      ▲
      │ saves/restores
      │
┌─────────────┐
│ Checkpoint  │
└─────────────┘
```

---

## Entity Definitions

### 1. DataBatch

**Purpose**: A collection of records arriving for validation.

**Source**: spec.md Key Entities

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique batch identifier (UUID) |
| `source` | `str` | Yes | Origin location (file path or source name) |
| `arrival_timestamp` | `datetime` | Yes | When the batch was detected |
| `record_count` | `int` | Yes | Number of records in the batch |
| `status` | `BatchStatus` | Yes | Current validation status |
| `records` | `list[Record]` | Yes | The actual data records |
| `metadata` | `dict` | No | Optional source metadata |

**BatchStatus Enum**:
```
PENDING    - Batch received, not yet validated
VALIDATING - Validation in progress
PASSED     - All records passed validation
FAILED     - One or more records failed validation
ERROR      - Validation could not complete (system error)
```

**Constraints**:
- `record_count` must equal `len(records)`
- `id` must be unique within the system
- `source` must be a valid path or identifier

---

### 2. Record

**Purpose**: A single data record within a batch.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique record identifier |
| `batch_id` | `str` | Yes | Parent batch reference |
| `row_number` | `int` | Yes | Position in batch (1-indexed) |
| `data` | `dict[str, Any]` | Yes | The actual field values |
| `validation_status` | `RecordStatus` | Yes | Validation outcome |

**RecordStatus Enum**:
```
PENDING    - Not yet validated
VALID      - Passed all validations
INVALID    - Failed one or more validations
QUARANTINED - Isolated due to CRITICAL severity
```

---

### 3. ValidationResult

**Purpose**: Outcome of validating a batch or record.

**Source**: spec.md Key Entities

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique result identifier |
| `batch_id` | `str` | Yes | Reference to validated batch |
| `timestamp` | `datetime` | Yes | When validation completed |
| `passed` | `bool` | Yes | Overall pass/fail |
| `total_records` | `int` | Yes | Records in batch |
| `valid_records` | `int` | Yes | Records that passed |
| `invalid_records` | `int` | Yes | Records that failed |
| `anomalies` | `list[Anomaly]` | Yes | Detected issues |
| `health_score` | `int` | Yes | Calculated health (0-100) |
| `duration_ms` | `int` | Yes | Validation duration |
| `skills_executed` | `list[str]` | Yes | Skills that ran |

**Computed Fields**:
- `pass_rate`: `valid_records / total_records * 100`
- `anomaly_count`: `len(anomalies)`

---

### 4. Anomaly

**Purpose**: A detected data quality issue.

**Source**: spec.md Key Entities, Constitution Section 4

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique anomaly identifier |
| `failure_code` | `FailureCode` | Yes | DV-001 through DV-008 |
| `severity` | `SeverityLevel` | Yes | INFO, WARNING, CRITICAL |
| `severity_score` | `int` | Yes | Calculated score (0-100) |
| `affected_records` | `list[str]` | Yes | Record IDs affected |
| `affected_fields` | `list[str]` | No | Field names affected |
| `root_cause` | `str` | Yes | Attribution explanation |
| `confidence` | `int` | Yes | Attribution confidence (0-100) |
| `timestamp` | `datetime` | Yes | Detection time |
| `explanation` | `str` | Yes | Human-readable description |
| `details` | `dict` | No | Additional context |

**FailureCode Enum** (Constitution Section 3.1):
```
DV_001 = "Missing Records"
DV_002 = "Excess Records"
DV_003 = "Null Violation"
DV_004 = "Type Mismatch"
DV_005 = "Range Violation"
DV_006 = "Format Violation"
DV_007 = "Duplicate Record"
DV_008 = "Encoding Error"
```

**SeverityLevel Enum** (Constitution Section 4.2):
```
INFO     = 0-39   (log only)
WARNING  = 40-69  (alert within 5 min)
CRITICAL = 70-100 (alert within 1 min)
```

**Severity Score Formula** (Constitution Section 4.2):
```
Score = (Impact × 40) + (Frequency × 30) + (Recency × 30)

Where:
- Impact (0.0-1.0): Business harm potential
- Frequency (0.0-1.0): Occurrence rate
- Recency (0.0-1.0): How new the issue is
```

---

### 5. HealthScore

**Purpose**: Aggregate quality metric representing current data health.

**Source**: spec.md Key Entities, Constitution Section 6.3

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | `datetime` | Yes | Calculation time |
| `overall_score` | `int` | Yes | Aggregate score (0-100) |
| `component_scores` | `dict[str, int]` | Yes | Per-skill scores |
| `trend` | `Trend` | Yes | Direction of change |
| `active_anomalies` | `int` | Yes | Current unresolved issues |
| `last_validation` | `datetime` | No | Most recent validation time |

**Trend Enum**:
```
IMPROVING  - Score increasing
STABLE     - Score unchanged (±2 points)
DEGRADING  - Score decreasing
```

**Aggregate Formula** (Constitution Section 6.3):
```
Overall Health = Minimum(All Component Scores)
```

Component scores for Bronze tier:
- `count_score`: Record count validation
- `null_score`: Null detection
- `type_score`: Type conformance
- `range_score`: Range validation
- `format_score`: Format matching
- `duplicate_score`: Duplicate detection
- `encoding_score`: Encoding validation

---

### 6. Checkpoint

**Purpose**: Recovery point capturing validation progress.

**Source**: spec.md Key Entities, Constitution Section 2.6

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Checkpoint identifier |
| `timestamp` | `datetime` | Yes | Creation time |
| `batch_id` | `str` | Yes | Associated batch |
| `position` | `int` | Yes | Record position in batch |
| `partial_results` | `dict` | Yes | Intermediate state |
| `validation_context` | `dict` | Yes | Skill states |
| `health_state` | `HealthScore` | No | Health at checkpoint |

**Checkpoint Types** (Constitution Section 2.6):
| Type | Frequency | Contents |
|------|-----------|----------|
| Validation | Every N records (default 1000) | Position, partial results |
| Health | Every 30 seconds | Layer scores, active alerts |

---

### 7. Alert

**Purpose**: Notification of an issue requiring attention.

**Source**: spec.md Key Entities

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique alert identifier |
| `anomaly_id` | `str` | Yes | Source anomaly reference |
| `severity` | `SeverityLevel` | Yes | Alert severity |
| `message` | `str` | Yes | Alert message |
| `channel` | `str` | Yes | Delivery channel (console/log) |
| `sent_timestamp` | `datetime` | Yes | When alert was sent |
| `acknowledged` | `bool` | No | If acknowledged by user |
| `acknowledged_by` | `str` | No | Who acknowledged |
| `acknowledged_at` | `datetime` | No | When acknowledged |

**Alert Timing Requirements** (spec.md SC-002):
| Severity | Max Delivery Time |
|----------|-------------------|
| CRITICAL | 1 minute |
| WARNING | 5 minutes |
| INFO | No alert (log only) |

---

## Relationships

```
DataBatch (1) ────────── (N) Record
     │
     │ produces
     ▼
ValidationResult (1) ─── (N) Anomaly
     │                        │
     │                        │ triggers
     │                        ▼
     │                    Alert (0..1)
     │
     └──────────────────► HealthScore (updates)

Checkpoint ◄──────────── DataBatch (saves state)
```

**Key Relationships**:
1. A `DataBatch` contains multiple `Records`
2. A `ValidationResult` references one `DataBatch`
3. A `ValidationResult` contains multiple `Anomalies`
4. An `Anomaly` may trigger one `Alert` (WARNING/CRITICAL only)
5. `HealthScore` is updated after each validation
6. `Checkpoint` saves state during validation

---

## File Storage Locations

For MVP file-based storage:

| Entity | Location | Format |
|--------|----------|--------|
| DataBatch | `data/batches/{batch_id}.json` | JSON |
| ValidationResult | `data/results/{result_id}.json` | JSON |
| Anomaly | Embedded in ValidationResult | JSON |
| HealthScore | `data/state/health.json` | JSON |
| Checkpoint | `data/checkpoints/{checkpoint_id}.json` | JSON |
| Alert | `logs/alerts/{date}.jsonl` | JSON Lines |
| Audit Log | `logs/audit/{date}.jsonl` | JSON Lines |
| Quarantine | `data/quarantine/{record_id}.json` | JSON |

---

## Pydantic Model Examples

### DataBatch Model

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Any

class BatchStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"

class DataBatch(BaseModel):
    id: str = Field(..., description="Unique batch identifier")
    source: str = Field(..., description="Origin location")
    arrival_timestamp: datetime = Field(default_factory=datetime.utcnow)
    record_count: int = Field(..., ge=0)
    status: BatchStatus = Field(default=BatchStatus.PENDING)
    records: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
```

### Anomaly Model

```python
class FailureCode(str, Enum):
    DV_001 = "DV-001"  # Missing Records
    DV_002 = "DV-002"  # Excess Records
    DV_003 = "DV-003"  # Null Violation
    DV_004 = "DV-004"  # Type Mismatch
    DV_005 = "DV-005"  # Range Violation
    DV_006 = "DV-006"  # Format Violation
    DV_007 = "DV-007"  # Duplicate Record
    DV_008 = "DV-008"  # Encoding Error

class SeverityLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class Anomaly(BaseModel):
    id: str
    failure_code: FailureCode
    severity: SeverityLevel
    severity_score: int = Field(..., ge=0, le=100)
    affected_records: list[str]
    affected_fields: list[str] = Field(default_factory=list)
    root_cause: str
    confidence: int = Field(..., ge=0, le=100)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    explanation: str
    details: dict[str, Any] = Field(default_factory=dict)
```

---

## Validation Rules Configuration

Rules are externalized to YAML:

```yaml
# config/validation_rules.yaml
schema:
  fields:
    - name: id
      type: string
      required: true
      pattern: "^[A-Z0-9]{8}$"
    - name: amount
      type: float
      required: true
      min: 0.0
      max: 1000000.0
    - name: email
      type: string
      required: false
      pattern: "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"
    - name: created_at
      type: datetime
      required: true

thresholds:
  expected_record_count:
    min: 100
    max: 10000
  null_tolerance:
    default: 0.01  # 1% allowed
    fields:
      email: 0.10  # 10% allowed for optional fields

severity_weights:
  DV-001:  # Missing Records
    impact: 0.8
    frequency: 0.5
    recency: 0.9
  DV-003:  # Null Violation
    impact: 0.6
    frequency: 0.7
    recency: 0.8
```

---

## Index/Lookup Strategies

For MVP file-based storage, maintain index files:

```json
// data/indexes/batches.json
{
  "by_status": {
    "pending": ["batch-001", "batch-002"],
    "passed": ["batch-003", "batch-004"],
    "failed": ["batch-005"]
  },
  "by_date": {
    "2026-01-18": ["batch-001", "batch-002", "batch-003"]
  }
}
```

**Lookup Patterns**:
| Query | Method |
|-------|--------|
| Get batch by ID | Direct file access |
| Get batches by status | Index lookup |
| Get recent anomalies | Scan last N result files |
| Get health history | Read health.json history array |

---

## Data Lifecycle

```
1. Data Arrival
   └── DataBatch created (status=PENDING)

2. Validation Start
   └── DataBatch.status = VALIDATING
   └── Checkpoint created (position=0)

3. Validation Progress
   └── Checkpoint updated every 1000 records
   └── Anomalies accumulated

4. Validation Complete
   └── ValidationResult created
   └── DataBatch.status = PASSED | FAILED
   └── Alerts generated for WARNING/CRITICAL
   └── HealthScore updated

5. Quarantine (if CRITICAL)
   └── Affected records moved to quarantine/
   └── Original record preserved

6. Cleanup (future)
   └── Old checkpoints pruned (after success)
   └── Audit logs rotated (per retention policy)
```
