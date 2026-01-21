# Contract: Anomaly

**Entity**: Anomaly
**Version**: 1.0.0
**Feature**: `001-bronze-orchestrator-mvp`

---

## Purpose

Represents a detected data quality issue with full context for root cause analysis, severity classification, and human-readable explanation.

---

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": [
    "id", "failure_code", "severity", "severity_score",
    "affected_records", "root_cause", "confidence",
    "timestamp", "explanation"
  ],
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique anomaly identifier"
    },
    "failure_code": {
      "type": "string",
      "enum": ["DV-001", "DV-002", "DV-003", "DV-004", "DV-005", "DV-006", "DV-007", "DV-008"],
      "description": "Bronze tier failure code"
    },
    "severity": {
      "type": "string",
      "enum": ["INFO", "WARNING", "CRITICAL"],
      "description": "Severity classification"
    },
    "severity_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "description": "Calculated severity score"
    },
    "affected_records": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of affected record IDs"
    },
    "affected_fields": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of affected field names"
    },
    "root_cause": {
      "type": "string",
      "description": "Attribution explanation"
    },
    "confidence": {
      "type": "integer",
      "minimum": 0,
      "maximum": 100,
      "description": "Attribution confidence percentage"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "Detection timestamp"
    },
    "explanation": {
      "type": "string",
      "description": "Human-readable description"
    },
    "details": {
      "type": "object",
      "description": "Additional context specific to failure type"
    }
  }
}
```

---

## Failure Codes

| Code | Name | Description | Typical Severity |
|------|------|-------------|------------------|
| DV-001 | Missing Records | Batch has fewer records than expected | WARNING-CRITICAL |
| DV-002 | Excess Records | Batch has more records than expected | WARNING |
| DV-003 | Null Violation | Required field contains null/empty | WARNING-CRITICAL |
| DV-004 | Type Mismatch | Value doesn't match declared type | CRITICAL |
| DV-005 | Range Violation | Value outside permitted boundaries | WARNING-CRITICAL |
| DV-006 | Format Violation | Value doesn't match required pattern | WARNING |
| DV-007 | Duplicate Record | Exact duplicate detected | CRITICAL |
| DV-008 | Encoding Error | Invalid character encoding | WARNING-CRITICAL |

---

## Severity Score Calculation

```
Score = (Impact × 40) + (Frequency × 30) + (Recency × 30)

Where:
- Impact (0.0-1.0): Potential business harm
- Frequency (0.0-1.0): How often this anomaly occurs
- Recency (0.0-1.0): How new the issue is (1.0 = just detected)
```

### Default Weights by Failure Code

```yaml
DV-001:  # Missing Records
  impact: 0.8
  base_frequency: 0.3

DV-002:  # Excess Records
  impact: 0.4
  base_frequency: 0.2

DV-003:  # Null Violation
  impact: 0.6
  base_frequency: 0.5

DV-004:  # Type Mismatch
  impact: 0.9
  base_frequency: 0.4

DV-005:  # Range Violation
  impact: 0.7
  base_frequency: 0.4

DV-006:  # Format Violation
  impact: 0.5
  base_frequency: 0.5

DV-007:  # Duplicate Record
  impact: 0.85
  base_frequency: 0.3

DV-008:  # Encoding Error
  impact: 0.7
  base_frequency: 0.2
```

---

## Examples

### DV-001: Missing Records (CRITICAL)

```json
{
  "id": "anomaly-dv001-001",
  "failure_code": "DV-001",
  "severity": "CRITICAL",
  "severity_score": 78,
  "affected_records": [],
  "affected_fields": [],
  "root_cause": "Batch record count 500 is below minimum threshold of 1000",
  "confidence": 100,
  "timestamp": "2026-01-18T10:30:00Z",
  "explanation": "The batch contains only 500 records, but we expected at least 1000. This indicates a potential data loss or incomplete extraction.",
  "details": {
    "expected_min": 1000,
    "expected_max": 10000,
    "actual_count": 500,
    "delta": -500,
    "delta_pct": -50.0
  }
}
```

### DV-003: Null Violation (WARNING)

```json
{
  "id": "anomaly-dv003-001",
  "failure_code": "DV-003",
  "severity": "WARNING",
  "severity_score": 52,
  "affected_records": ["rec-101", "rec-205", "rec-308"],
  "affected_fields": ["customer_email"],
  "root_cause": "Required field 'customer_email' contains 3 null values (0.3%)",
  "confidence": 100,
  "timestamp": "2026-01-18T10:30:01Z",
  "explanation": "3 records are missing customer email addresses. While this is within tolerance, it may affect communication workflows.",
  "details": {
    "field": "customer_email",
    "null_count": 3,
    "total_records": 1000,
    "null_pct": 0.3,
    "tolerance_pct": 1.0,
    "within_tolerance": true
  }
}
```

### DV-007: Duplicate Record (CRITICAL)

```json
{
  "id": "anomaly-dv007-001",
  "failure_code": "DV-007",
  "severity": "CRITICAL",
  "severity_score": 85,
  "affected_records": ["rec-150", "rec-151", "rec-500"],
  "affected_fields": ["order_id"],
  "root_cause": "Exact duplicate records detected with order_id 'ORD-12345'",
  "confidence": 100,
  "timestamp": "2026-01-18T10:30:02Z",
  "explanation": "3 records have identical order_id 'ORD-12345'. Duplicate orders could result in double-billing or inventory errors.",
  "details": {
    "duplicate_key": "order_id",
    "duplicate_value": "ORD-12345",
    "occurrence_count": 3,
    "first_occurrence_row": 150,
    "all_rows": [150, 151, 500]
  }
}
```

---

## Confidence Levels

| Range | Interpretation |
|-------|----------------|
| 80-100% | High confidence - root cause likely identified |
| 50-79% | Medium confidence - probable cause with alternatives |
| 0-49% | Low confidence - multiple possible causes |

---

## Invariants

1. `severity` MUST match score range: INFO (0-39), WARNING (40-69), CRITICAL (70-100)
2. `confidence` MUST be between 0 and 100
3. `explanation` MUST be human-readable (no technical jargon)
4. `root_cause` MUST identify specific source or pattern
5. `affected_records` MAY be empty for batch-level anomalies (e.g., DV-001)

---

## Operations

### Create

**Trigger**: Validation skill detects issue
**Input**: failure_code, affected data, validation context
**Output**: Fully populated Anomaly
**Side Effects**: None (pure data)

### Classify Severity

**Input**: impact, frequency, recency weights
**Output**: severity_score and severity level
**Algorithm**:
```python
def classify_severity(impact: float, frequency: float, recency: float) -> tuple[int, str]:
    score = int((impact * 40) + (frequency * 30) + (recency * 30))
    if score >= 70:
        return score, "CRITICAL"
    elif score >= 40:
        return score, "WARNING"
    else:
        return score, "INFO"
```

### Generate Explanation

**Input**: Anomaly data, context
**Output**: Human-readable explanation string
**Requirements**:
- No technical jargon
- Include specific numbers
- State business impact when possible
