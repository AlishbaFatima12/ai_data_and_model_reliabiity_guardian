# Contract: DataBatch

**Entity**: DataBatch
**Version**: 1.0.0
**Feature**: `001-bronze-orchestrator-mvp`

---

## Purpose

Represents a collection of records arriving for validation. This is the primary input to the Bronze validation system.

---

## Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["id", "source", "arrival_timestamp", "record_count", "status", "records"],
  "properties": {
    "id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique batch identifier"
    },
    "source": {
      "type": "string",
      "minLength": 1,
      "description": "Origin location (file path or source name)"
    },
    "arrival_timestamp": {
      "type": "string",
      "format": "date-time",
      "description": "When the batch was detected (ISO 8601)"
    },
    "record_count": {
      "type": "integer",
      "minimum": 0,
      "description": "Number of records in the batch"
    },
    "status": {
      "type": "string",
      "enum": ["pending", "validating", "passed", "failed", "error"],
      "description": "Current validation status"
    },
    "records": {
      "type": "array",
      "items": {
        "type": "object"
      },
      "description": "The actual data records"
    },
    "metadata": {
      "type": "object",
      "description": "Optional source metadata"
    }
  }
}
```

---

## Examples

### Valid Batch (Pending)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "/data/incoming/orders_2026-01-18.csv",
  "arrival_timestamp": "2026-01-18T10:30:00Z",
  "record_count": 1000,
  "status": "pending",
  "records": [
    {"id": "ORD001", "amount": 150.00, "customer": "CUST001"},
    {"id": "ORD002", "amount": 250.00, "customer": "CUST002"}
  ],
  "metadata": {
    "file_size_bytes": 45000,
    "encoding": "utf-8"
  }
}
```

### Validated Batch (Passed)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "source": "/data/incoming/inventory_2026-01-18.json",
  "arrival_timestamp": "2026-01-18T11:00:00Z",
  "record_count": 500,
  "status": "passed",
  "records": [...],
  "metadata": {}
}
```

---

## Invariants

1. `record_count` MUST equal `len(records)`
2. `id` MUST be unique across all batches
3. `status` transitions follow: `pending → validating → (passed | failed | error)`
4. `arrival_timestamp` MUST be in the past (not future)

---

## Operations

### Create

**Input**: File path or data stream
**Output**: DataBatch with status=pending
**Errors**:
- `INVALID_SOURCE`: Source path does not exist
- `PARSE_ERROR`: Unable to parse file format
- `EMPTY_BATCH`: No records in file

### Update Status

**Input**: batch_id, new_status
**Output**: Updated DataBatch
**Errors**:
- `INVALID_TRANSITION`: Status change not allowed
- `BATCH_NOT_FOUND`: Batch ID does not exist

### Query

**Input**: filters (status, date range, source)
**Output**: List of matching DataBatch objects
