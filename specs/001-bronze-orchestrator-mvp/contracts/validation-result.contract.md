# Contract: ValidationResult

**Entity**: ValidationResult
**Version**: 1.0.0
**Feature**: `001-bronze-orchestrator-mvp`

---

## Purpose

Captures the outcome of validating a batch, including pass/fail status, detected anomalies, and health score calculation.

---

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "id", "batch_id", "timestamp", "passed", "total_records",
    "valid_records", "invalid_records", "anomalies", "health_score",
    "duration_ms", "skills_executed"
  ],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique result identifier"
    },
    "batch_id": {
      "type": "string",
      "format": "uuid",
      "description": "Reference to validated batch"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "When validation completed"
    },
    "passed": {
      "type": "boolean",
      "description": "Overall pass/fail"
    },
    "total_records": {
      "type": "integer",
      "minimum": 0,
      "description": "Records in batch"
    },
    "valid_records": {
      "type": "integer",
      "minimum": 0,
      "description": "Records that passed"
    },
    "invalid_records": {
      "type": "integer",
      "minimum": 0,
      "description": "Records that failed"
    },
    "anomalies": {
      "type": "array",
      "items": {
        "$ref": "#/$defs/Anomaly"
      },
      "description": "Detected issues"
    },
    "health_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "description": "Calculated health (0-100)"
    },
    "duration_ms": {
      "type": "integer",
      "minimum": 0,
      "description": "Validation duration in milliseconds"
    },
    "skills_executed": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "List of skill IDs that executed"
    }
  },
  "$defs": {
    "Anomaly": {
      "type": "object",
      "required": [
        "id", "failure_code", "severity", "severity_score",
        "affected_records", "root_cause", "confidence",
        "timestamp", "explanation"
      ],
      "properties": {
        "id": { "type": "string" },
        "failure_code": {
          "type": "string",
          "enum": ["DV-001", "DV-002", "DV-003", "DV-004", "DV-005", "DV-006", "DV-007", "DV-008"]
        },
        "severity": {
          "type": "string",
          "enum": ["INFO", "WARNING", "CRITICAL"]
        },
        "severity_score": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        },
        "affected_records": {
          "type": "array",
          "items": { "type": "string" }
        },
        "affected_fields": {
          "type": "array",
          "items": { "type": "string" }
        },
        "root_cause": { "type": "string" },
        "confidence": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100
        },
        "timestamp": {
          "type": "string",
          "format": "date-time"
        },
        "explanation": { "type": "string" },
        "details": { "type": "object" }
      }
    }
  }
}
```

---

## Examples

### Successful Validation (No Anomalies)

```json
{
  "id": "result-001",
  "batch_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-18T10:30:05Z",
  "passed": true,
  "total_records": 1000,
  "valid_records": 1000,
  "invalid_records": 0,
  "anomalies": [],
  "health_score": 100,
  "duration_ms": 450,
  "skills_executed": [
    "bronze.count",
    "bronze.null",
    "bronze.type",
    "bronze.range",
    "bronze.format",
    "bronze.duplicate",
    "bronze.encoding"
  ]
}
```

### Failed Validation (With Anomalies)

```json
{
  "id": "result-002",
  "batch_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2026-01-18T11:00:03Z",
  "passed": false,
  "total_records": 500,
  "valid_records": 485,
  "invalid_records": 15,
  "anomalies": [
    {
      "id": "anomaly-001",
      "failure_code": "DV-003",
      "severity": "WARNING",
      "severity_score": 55,
      "affected_records": ["rec-101", "rec-102", "rec-103"],
      "affected_fields": ["email"],
      "root_cause": "Required field 'email' contains null values",
      "confidence": 95,
      "timestamp": "2026-01-18T11:00:02Z",
      "explanation": "3 records have missing email addresses. This exceeds the 1% null tolerance threshold.",
      "details": {
        "null_count": 3,
        "tolerance_pct": 1.0,
        "actual_pct": 0.6
      }
    },
    {
      "id": "anomaly-002",
      "failure_code": "DV-007",
      "severity": "CRITICAL",
      "severity_score": 75,
      "affected_records": ["rec-201", "rec-202"],
      "affected_fields": ["id"],
      "root_cause": "Duplicate record IDs detected",
      "confidence": 100,
      "timestamp": "2026-01-18T11:00:03Z",
      "explanation": "2 records have identical IDs. Duplicate records violate uniqueness constraint.",
      "details": {
        "duplicate_id": "ORD-12345",
        "occurrences": 2
      }
    }
  ],
  "health_score": 72,
  "duration_ms": 380,
  "skills_executed": [
    "bronze.count",
    "bronze.null",
    "bronze.type",
    "bronze.range",
    "bronze.format",
    "bronze.duplicate",
    "bronze.encoding"
  ]
}
```

---

## Invariants

1. `valid_records + invalid_records = total_records`
2. `passed = (invalid_records == 0)`
3. `health_score = min(component_scores)` where scores are calculated per skill
4. `duration_ms > 0` always (validation takes time)
5. All anomalies must have unique `id` values

---

## Severity Classification Rules

| Score Range | Severity | Action |
|-------------|----------|--------|
| 0-39 | INFO | Log only |
| 40-69 | WARNING | Alert within 5 minutes |
| 70-100 | CRITICAL | Alert within 1 minute, quarantine |

---

## Operations

### Create

**Trigger**: Validation completion
**Input**: batch_id, validation results from all skills
**Output**: ValidationResult with all fields populated
**Side Effects**:
- Alerts generated for WARNING/CRITICAL anomalies
- Health score updated
- Audit log entry written

### Query

**Input**: filters (batch_id, date range, severity)
**Output**: List of matching ValidationResult objects

### Get Latest

**Input**: None
**Output**: Most recent ValidationResult
