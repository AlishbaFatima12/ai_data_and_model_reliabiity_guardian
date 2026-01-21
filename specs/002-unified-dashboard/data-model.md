# Data Model: Unified Monitoring Dashboard

**Date**: 2026-01-18
**Feature**: 002-unified-dashboard

## Overview

The dashboard primarily consumes existing Bronze tier models and adds view-specific models for UI state and business impact translations.

## Reused Models (from Bronze Tier)

### ValidationResult
**Source**: `src/models/validation_result.py`

| Field | Type | Description |
|-------|------|-------------|
| id | str (UUID) | Unique result identifier |
| batch_id | str | ID of validated batch |
| passed | bool | Whether validation passed (no CRITICAL) |
| anomalies | list[Anomaly] | Detected anomalies |
| health_score | float (0-100) | Overall health score |
| duration_ms | float | Validation duration |
| skills_executed | list[str] | Skills that ran |
| validated_at | datetime | When validation completed |
| metadata | dict | Additional context |

**Computed properties**: anomaly_count, critical_anomalies, warning_anomalies, info_anomalies, has_critical, has_warnings

### HealthScore
**Source**: `src/models/health_score.py`

| Field | Type | Description |
|-------|------|-------------|
| overall_score | float (0-100) | Overall health score |
| component_scores | dict[str, ComponentScore] | Per-component breakdown |
| trend | str | "improving", "stable", "degrading" |
| active_anomalies | int | Count of active anomalies |
| last_updated | datetime | Last calculation time |
| batches_evaluated | int | Batches evaluated for this score |
| history | list[tuple] | Recent (timestamp, score) history |

**Computed properties**: is_healthy (>=70), is_critical (<40), status_label

### Anomaly
**Source**: `src/models/anomaly.py`

| Field | Type | Description |
|-------|------|-------------|
| id | str (UUID) | Unique anomaly identifier |
| batch_id | str | Source batch ID |
| failure_code | FailureCode | DV-001 to DV-008 |
| severity | SeverityLevel | INFO, WARNING, CRITICAL |
| severity_score | float (0-100) | Calculated severity |
| affected_records | list[int] | Affected record indices |
| affected_fields | list[str] | Affected field names |
| root_cause | str | Root cause description |
| explanation | str | Detailed explanation |
| detected_at | datetime | Detection timestamp |
| metadata | dict | Additional context |

---

## New Dashboard Models

### TimelineEvent
**Purpose**: Unified event model for incident timeline (FR-018 to FR-022)

| Field | Type | Description |
|-------|------|-------------|
| id | str (UUID) | Event identifier |
| event_type | EventType | validation_start, validation_complete, anomaly_detected, alert_sent, acknowledged |
| timestamp | datetime | When event occurred |
| severity | SeverityLevel | Event severity for color coding |
| title | str | Short title (plain language) |
| description | str | Detailed description |
| related_batch_id | str | Associated batch |
| related_anomaly_id | str? | Associated anomaly (if applicable) |
| layer | str | Intelligence layer (Bronze, Silver, Gold) |
| asset | str | Affected asset name |
| metadata | dict | Additional event data |

**State transitions**: Events are immutable once created.

### BusinessImpact
**Purpose**: Translate technical metrics to business language (FR-014 to FR-017)

| Field | Type | Description |
|-------|------|-------------|
| technical_metric | str | Original metric name |
| technical_value | any | Original value |
| business_description | str | Plain language description |
| affected_processes | list[str] | Business processes affected |
| affected_segments | list[str] | Customer segments affected |
| recommended_actions | list[str] | Suggested business actions |
| estimated_impact | str | Impact severity (High/Medium/Low) |

### DashboardState
**Purpose**: Persist user session state for acknowledged incidents

| Field | Type | Description |
|-------|------|-------------|
| acknowledged_anomalies | set[str] | IDs of acknowledged anomalies |
| selected_view | str | Current persona view |
| filter_severity | list[str] | Active severity filters |
| filter_layer | list[str] | Active layer filters |
| filter_time_range | tuple[datetime, datetime] | Selected time range |
| last_refresh | datetime | Last data refresh time |

---

## Entity Relationships

```
ValidationResult (1) ──contains──▶ (N) Anomaly
       │
       │ produces
       ▼
HealthScore (1) ──tracks──▶ (N) ComponentScore
       │
       │ generates
       ▼
TimelineEvent (N) ◀──references── Anomaly
       │
       │ translates to
       ▼
BusinessImpact (N)
```

---

## Data Flow

### Read Path (Dashboard → Bronze Tier Data)

```
Bronze Tier Output          Dashboard Services           UI Components
─────────────────          ──────────────────           ─────────────
data/results/*.json   ──▶   DataLoader           ──▶   ExecutiveSummary
                             │                           LayerHealth
                             ▼                           IncidentTimeline
data/state/health.json ──▶  HealthCalculator     ──▶   DrillDown
                             │
                             ▼
logs/audit/*.jsonl    ──▶   TimelineBuilder      ──▶   BusinessImpact
                             │
                             ▼
config/translations.yaml ─▶ ImpactTranslator
```

### Write Path (Dashboard State)

```
User Action              Dashboard State              Storage
───────────              ───────────────              ───────
Acknowledge anomaly  ──▶  DashboardState.acknowledged ──▶  data/dashboard/acknowledged.json
Change filters       ──▶  st.session_state (memory)
```

---

## Validation Rules

### TimelineEvent
- `timestamp` required, must be ISO 8601
- `event_type` must be valid enum value
- `severity` must be valid enum value
- `title` max 100 characters
- `layer` must be one of: Bronze, Silver, Gold

### BusinessImpact
- `business_description` max 200 characters
- `affected_processes` max 10 items
- `recommended_actions` max 5 items
- `estimated_impact` must be High, Medium, or Low

### DashboardState
- `filter_time_range` end must be after start
- `filter_time_range` max 30 days
- `selected_view` must be one of: executive, engineer, compliance
