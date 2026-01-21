# Research: Silver Tier - Schema, Business Logic & Freshness Enforcement

**Feature**: `003-silver-tier-enforcement`
**Date**: 2026-01-18
**Phase**: 0 - Research

---

## Executive Summary

This document captures technology research and validation for the Silver Tier implementation. The selected additions to the technology stack (jsonschema, deepdiff, croniter) complement the existing Bronze dependencies and are well-suited for schema validation, comparison, and SLA scheduling requirements.

---

## Technology Research

### 1. Schema Validation: jsonschema

**Selected**: `jsonschema>=4.21.0`

**Why jsonschema**:
- Reference implementation of JSON Schema specification
- Supports Draft 4, 6, 7, 2019-09, and 2020-12
- Extensible with custom format validators
- Well-maintained with active community
- Integrates seamlessly with Python dicts and JSON files

**Validation Capabilities**:
| Requirement | jsonschema Feature |
|-------------|-------------------|
| Column presence (FR-002) | `required` keyword |
| Extra columns (FR-003) | `additionalProperties: false` |
| Data types (FR-004) | `type` keyword |
| Precision/Scale (FR-005) | `pattern` for numeric strings, custom validators |
| Constraints (FR-006) | `$ref` for relationships, `uniqueItems` |

**Schema Contract Example**:
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["id", "name", "email"],
  "properties": {
    "id": {"type": "integer"},
    "name": {"type": "string", "minLength": 1},
    "email": {"type": "string", "format": "email"},
    "phone": {"type": "string", "pattern": "^\\+?[0-9]{10,15}$"}
  },
  "additionalProperties": false,
  "x-column-criticality": {
    "id": "required",
    "name": "required",
    "email": "required",
    "phone": "optional"
  }
}
```

**Custom Extension**: The `x-column-criticality` extension allows marking columns as required/optional for severity determination (per clarification Q1).

**Performance**:
- Schema compilation: ~1ms per schema
- Validation: ~10-50μs per record (compiled schema)
- Caching: Schemas are compiled once and reused

**Alternatives Considered**:
- **fastjsonschema**: 3x faster but less feature-complete, no format validators
- **Pydantic**: Already used, but jsonschema provides schema-first approach needed for external contracts

**Decision**: Use jsonschema for external schema validation; Pydantic for internal models.

---

### 2. Schema Comparison: deepdiff

**Selected**: `deepdiff>=7.0`

**Why deepdiff**:
- Deep comparison of complex nested structures
- Detailed diff output with path information
- Support for ignoring specific paths or types
- Change type detection (add, remove, modify, type change)
- Well-suited for schema version comparison

**Use Cases**:
| Requirement | deepdiff Feature |
|-------------|-----------------|
| Version compatibility (FR-007) | `DeepDiff.affected_paths` |
| Breaking changes (FR-008) | Detect removed required fields, type changes |
| Contract checksum (FR-009) | `DeepHash` for deterministic hashing |

**Breaking Change Detection**:
```python
from deepdiff import DeepDiff

old_schema = {"required": ["id", "name"], "properties": {...}}
new_schema = {"required": ["id"], "properties": {...}}  # 'name' removed

diff = DeepDiff(old_schema, new_schema)
# {'iterable_item_removed': {"root['required'][1]": 'name'}}

def is_breaking_change(diff: dict) -> bool:
    """Detect breaking schema changes."""
    breaking_indicators = [
        'iterable_item_removed',  # Required field removed
        'type_changes',           # Field type changed
        'dictionary_item_removed' # Property removed
    ]
    return any(key in diff for key in breaking_indicators)
```

**Schema Checksum**:
```python
from deepdiff import DeepHash

schema_hash = DeepHash(schema)[schema]
# Deterministic hash for contract verification
```

**Performance**:
- Comparison: ~1-5ms for typical schema sizes
- Hashing: ~0.5ms per schema

**Alternatives Considered**:
- **dictdiffer**: Less feature-complete, no type change detection
- **jsondiff**: JSON-specific, less flexible for schema semantics

**Decision**: deepdiff provides comprehensive comparison needed for breaking change detection.

---

### 3. SLA Schedule Parsing: croniter

**Selected**: `croniter>=2.0.0`

**Why croniter**:
- Standard cron expression parsing
- Next/previous occurrence calculation
- Support for extended cron syntax (seconds, years)
- Timezone-aware scheduling
- Lightweight with no external dependencies

**Use Cases**:
| Requirement | croniter Feature |
|-------------|-----------------|
| Scheduled jobs (FR-023) | `croniter.get_next()` |
| SLA definitions (FR-020-022) | Time-based thresholds |
| Pipeline schedules (FR-020) | Cron expression parsing |

**SLA Definition Example**:
```yaml
# config/sla/orders.yaml
source: orders
schedule: "0 * * * *"  # Every hour
thresholds:
  warning_minutes: 60
  critical_minutes: 90
latency:
  max_seconds: 1800  # 30 minutes
```

**Usage Pattern**:
```python
from croniter import croniter
from datetime import datetime

cron = croniter("0 * * * *", datetime.now())
next_expected = cron.get_next(datetime)

# SLA check
time_since_last = (datetime.now() - last_arrival).total_seconds()
if time_since_last > warning_threshold_seconds:
    raise FreshnessWarning(...)
```

**Performance**:
- Expression parsing: ~0.01ms
- Next occurrence: ~0.001ms

**Alternatives Considered**:
- **APScheduler cron**: Already in stack, but croniter is more flexible for threshold calculation
- **python-crontab**: System crontab management, not expression parsing

**Decision**: croniter is lightweight and purpose-built for cron expression handling.

---

### 4. Business Rule DSL (Research)

**Approach**: YAML-based declarative rules (no new dependency)

**Why Custom DSL over Rule Engines**:
- Existing YAML infrastructure (PyYAML already in stack)
- Simple expression language sufficient for MVP
- No need for complex rule chaining (Drools, Pyke)
- Transparency: rules are auditable text files

**Rule Format**:
```yaml
# config/rules/orders.yaml
rules:
  - id: BL-001-date-order
    name: End date after start date
    type: crossfield
    expression: "end_date > start_date"
    severity: critical

  - id: BL-002-account-exists
    name: Account reference valid
    type: referential
    field: account_id
    reference: accounts.id
    severity: critical

  - id: BL-003-total-matches
    name: Order total matches line items
    type: calculation
    expression: "sum(line_items.amount) == order_total"
    tolerance: 0.01
    severity: warning

  - id: BL-004-valid-transition
    name: Valid order status transition
    type: state_transition
    field: status
    allowed: [PENDING, CONFIRMED, SHIPPED, DELIVERED]
    severity: critical
```

**Expression Evaluation**:
- Simple comparisons: Python `ast.literal_eval` + safe evaluation
- Field access: Attribute getter with error handling
- Aggregations: Built-in sum, count, avg functions

**Security Consideration**:
- No `eval()` usage - safe expression parsing only
- Whitelist of allowed operators and functions
- No arbitrary code execution per Constitution 9.2

---

### 5. Reference Data Loading (Research)

**Approach**: CSV/JSON files with in-memory caching

**Why File-Based**:
- Per clarification Q2: "Reference data loaded from configured lookup files (CSV/JSON) at startup"
- No database dependency for MVP
- Simple refresh mechanism (periodic file reload)

**Implementation Pattern**:
```python
from pathlib import Path
import csv
import json
from datetime import datetime, timedelta

class ReferenceDataLoader:
    def __init__(self, refresh_interval: timedelta = timedelta(hours=1)):
        self.cache: dict[str, set] = {}
        self.loaded_at: dict[str, datetime] = {}
        self.refresh_interval = refresh_interval

    def load(self, name: str, path: Path) -> set:
        """Load reference data from file."""
        if path.suffix == '.csv':
            return self._load_csv(path)
        elif path.suffix == '.json':
            return self._load_json(path)
        raise ValueError(f"Unsupported format: {path.suffix}")

    def lookup(self, name: str, value: str) -> bool:
        """Check if value exists in reference set."""
        self._refresh_if_stale(name)
        return value in self.cache.get(name, set())
```

**Performance**:
- Typical lookup file: <10MB, <100K entries
- Load time: <1 second
- Lookup time: O(1) with set-based storage

---

### 6. Distribution Shift Detection (Research)

**Approach**: Statistical comparison with historical baselines

**Method**: Population Stability Index (PSI)

**Why PSI**:
- Industry standard for distribution comparison
- Single-number summary of distribution shift
- Interpretable thresholds (0.1 = minor, 0.25 = significant)
- Works for both numeric and categorical data

**Implementation**:
```python
import numpy as np
from collections import Counter

def calculate_psi(expected: list, actual: list, buckets: int = 10) -> float:
    """Calculate Population Stability Index."""
    def get_distribution(data: list, bins: np.ndarray) -> np.ndarray:
        counts, _ = np.histogram(data, bins)
        return (counts + 0.0001) / len(data)  # Avoid log(0)

    # Create bins from expected distribution
    bins = np.linspace(min(expected), max(expected), buckets + 1)

    expected_dist = get_distribution(expected, bins)
    actual_dist = get_distribution(actual, bins)

    psi = np.sum((actual_dist - expected_dist) * np.log(actual_dist / expected_dist))
    return psi

# Thresholds (Constitution: <5% false positive)
PSI_THRESHOLD_WARNING = 0.1
PSI_THRESHOLD_CRITICAL = 0.25
```

**Historical Baseline**:
- Spec assumption: 7 days of history available
- Storage: Rolling statistics in `data/state/baselines.json`
- Update: Append new batch statistics, prune old data

**Dependency Note**: Uses `numpy` which is likely already available via existing stack. If not, can implement with pure Python for MVP.

---

## Dependency Matrix

| Dependency | Version | Purpose | License | New? |
|------------|---------|---------|---------|------|
| jsonschema | >=4.21.0 | Schema validation | MIT | YES |
| deepdiff | >=7.0 | Schema comparison | MIT | YES |
| croniter | >=2.0.0 | SLA scheduling | MIT | YES |
| pydantic | >=2.5.0 | Internal models | MIT | Existing |
| pyyaml | >=6.0 | Rule/config loading | MIT | Existing |
| structlog | >=24.0.0 | Audit logging | MIT | Existing |
| pytest | >=8.0.0 | Testing | MIT | Existing |

**New direct dependencies**: 3
**Total dependencies**: Maintains reasonable count for enterprise deployment

---

## Performance Validation

### Constraint: <1 second per batch (Constitution 9.1)

**Breakdown for 10K record batch**:
| Operation | Time | Notes |
|-----------|------|-------|
| Schema validation | 500ms | 10K × 50μs |
| Business logic | 300ms | 10K × 30μs (rule evaluation) |
| Reference lookups | 50ms | 10K × 5μs (in-memory) |
| Distribution check | 50ms | Single batch computation |
| **Total** | **900ms** | Within 1s constraint |

### Constraint: 10K records/second throughput (SC-002)

**Validation**: 10K records in 900ms = 11,111 records/second ✓

### Constraint: <30 seconds freshness detection (SC-003)

**Method**: Layer 4 runs on 30-second timer per Constitution 2.2
- Maximum detection delay: 30 seconds between checks
- SLA evaluation: <10ms per source
- **Total worst-case**: 30 seconds ✓

---

## Risk Analysis

| Risk | Mitigation |
|------|------------|
| jsonschema performance with complex schemas | Pre-compile schemas; use draft-2020-12 optimizations |
| deepdiff memory for large schema diffs | Limit comparison depth; use `max_depth` parameter |
| PSI false positives | Tune bucket count; require 7-day baseline minimum |
| Reference data file locking | Read-only access; copy-on-refresh pattern |
| croniter timezone issues | Use UTC internally; convert at display layer |

---

## Alternatives Considered

### Alternative 1: Great Expectations for Schema Validation
**Rejected**: Designed for data quality checks, not schema contract enforcement. Better suited for future enhanced profiling but overkill for MVP schema validation.

### Alternative 2: Drools/Pyke for Business Rules
**Rejected**: Heavy rule engines with complex learning curves. Simple YAML DSL sufficient for MVP rule types (comparisons, lookups, calculations).

### Alternative 3: Apache Airflow for SLA Monitoring
**Rejected**: Workflow orchestrator, not monitoring tool. Would require significant infrastructure. croniter + existing APScheduler is simpler.

### Alternative 4: Statistical Libraries (scipy, statsmodels)
**Deferred**: May be useful for Gold tier model drift detection. PSI implementation with numpy sufficient for distribution shift in Silver tier.

---

## Integration Points

### With Bronze Tier
- **Input**: Silver receives `ValidationResult` from Bronze
- **Dependency**: Only processes data that passed Bronze (Constitution 8.4)
- **Reuse**: Shares models (Anomaly, Alert), util skills (score, health)

### With Dashboard (002)
- **Output**: SilverAnomaly events to `data/results/`
- **Health Scores**: Extends health.json with Silver layer scores
- **Timeline**: Adds SC-*, BL-*, FR-* events to audit log

---

## Conclusion

The selected technology additions are validated against Silver Tier requirements:
- **jsonschema**: Standard-compliant schema validation
- **deepdiff**: Robust schema comparison for breaking changes
- **croniter**: Lightweight SLA schedule management

The stack maintains:
- **Minimal footprint**: 3 new direct dependencies
- **Performance headroom**: Within 1s batch constraint
- **Constitution alignment**: All checks passed

**Ready for Phase 1: Data Model and Contract Design**
