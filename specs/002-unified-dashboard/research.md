# Research: Unified Monitoring Dashboard

**Date**: 2026-01-18
**Feature**: 002-unified-dashboard

## Research Questions Resolved

### Q1: What existing data structures can the dashboard consume?

**Decision**: Reuse existing Bronze tier models directly

**Rationale**: The Bronze tier implementation already has well-structured Pydantic models that align with dashboard requirements:
- `ValidationResult` - Contains batch validation outcomes, health scores, anomaly lists
- `HealthScore` - Has overall score, component scores, trend, history
- `Anomaly` - Contains failure codes, severity levels, affected records, root cause
- `FailureCode` - Enum with descriptions for business translation
- `SeverityLevel` - Enum with INFO/WARNING/CRITICAL

**Existing storage paths** (from `StorageConfig`):
- `data/results/` - Validation results (JSON)
- `data/state/health.json` - Current health state
- `logs/audit/` - Audit trail

**Alternatives considered**:
- Create new dashboard-specific models: Rejected - would duplicate logic
- Direct database: Rejected - spec explicitly says file-based storage for MVP

---

### Q2: What is the optimal Streamlit architecture for this dashboard?

**Decision**: Single-page app with sidebar navigation and expander-based drill-down

**Rationale**:
- Streamlit's st.sidebar provides persona-based view switching (Executive/Engineer/Compliance)
- st.expander enables progressive disclosure (3-level drill-down per FR-023)
- st.metric with delta provides health scores with trends (FR-007)
- Auto-refresh via st.rerun with timer provides polling-based updates (SC-004)
- Plotly for sparklines and timeline visualization (FR-002, FR-018)

**Structure**:
```
dashboard/
├── app.py              # Main Streamlit entry point
├── components/
│   ├── __init__.py
│   ├── executive_summary.py    # FR-001 to FR-005
│   ├── layer_health.py         # FR-006 to FR-009
│   ├── business_impact.py      # FR-014 to FR-017
│   ├── incident_timeline.py    # FR-018 to FR-022
│   └── drill_down.py           # FR-023 to FR-025
├── services/
│   ├── __init__.py
│   ├── data_loader.py          # Read from Bronze tier output
│   ├── health_calculator.py    # Aggregate health scores
│   └── impact_translator.py    # Technical to business language
└── config/
    └── translations.yaml       # Business impact translation rules
```

**Alternatives considered**:
- Multi-page Streamlit app: Rejected - adds navigation complexity for simple use case
- Dash/Plotly: Rejected - user explicitly requested Streamlit
- Panel/Bokeh: Rejected - less community support than Streamlit

---

### Q3: How to implement the 30-second auto-refresh without full reload?

**Decision**: Use st.fragment with st.rerun trigger

**Rationale**:
- Streamlit 1.33+ supports `@st.fragment` for partial reruns
- Combine with `time.sleep` in background thread + session state
- Dashboard polls data files every 30 seconds
- Visual refresh indicator shows last update time

**Implementation pattern**:
```python
import streamlit as st
from datetime import datetime, timedelta

if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# Check if 30 seconds have passed
if datetime.now() - st.session_state.last_refresh > timedelta(seconds=30):
    st.session_state.last_refresh = datetime.now()
    st.rerun()
```

**Alternatives considered**:
- WebSocket streaming: Rejected - overkill for 30-second polling
- Full page reload: Rejected - poor UX, loses state

---

### Q4: How to implement the incident timeline with scrolling and filtering?

**Decision**: Plotly timeline chart with Streamlit filters

**Rationale**:
- Plotly's `px.timeline` or custom scatter plot for event markers
- Native zoom/pan support for scrollable timeline (FR-018)
- st.multiselect for severity/layer filters (FR-021)
- st.date_input for time range selection
- Hover tooltips for event details (FR-020)

**Alternatives considered**:
- Altair: Limited timeline support
- Matplotlib: No interactivity
- Custom D3: Too complex for MVP

---

### Q5: How to implement business impact translations?

**Decision**: YAML-based translation rules with template interpolation

**Rationale**:
- Constitution 6.5 provides clear translation patterns
- Store translations in `config/translations.yaml`
- Use Python string formatting for dynamic values
- Add default fallback for unmapped failure codes

**Translation format** (from Constitution 6.5):
```yaml
translations:
  data_freshness:
    template: "Customer data may not reflect orders from the last {hours} hours"
    technical_key: "freshness_hours"
  model_accuracy:
    template: "Approximately {incorrect} out of 100 predictions may be incorrect"
    technical_key: "accuracy_percent"
    transform: "100 - value"
  schema_error_rate:
    template: "{rate}% of incoming records cannot be processed"
    technical_key: "error_rate_percent"
```

**Alternatives considered**:
- Hardcoded translations: Rejected - not maintainable
- LLM-generated translations: Rejected - Constitution 9.3 prohibits LLM for core functions

---

### Q6: Color scheme for health status visualization?

**Decision**: Use Constitution 6.4 color bands with accessible palette

**Color mapping** (per Constitution 6.4):
| Score Range | Status | Color (Hex) | Accessible |
|-------------|--------|-------------|------------|
| 90-100 | Excellent | #00A67E (Green) | Yes |
| 70-89 | Good | #FFB020 (Yellow) | Yes |
| 50-69 | Fair | #FF8C00 (Orange) | Yes |
| 0-49 | Poor/Critical | #DC3545 (Red) | Yes |

**Rationale**: Colors meet WCAG 2.1 contrast requirements when used on white background.

---

## Technology Stack Summary

| Component | Technology | Version | Rationale |
|-----------|------------|---------|-----------|
| Framework | Streamlit | 1.33+ | User-specified, rapid prototyping |
| Charting | Plotly | 5.x | Interactive charts, timeline support |
| Data Models | Pydantic | 2.x | Reuse from Bronze tier |
| Config | PyYAML | 6.x | Already in project |
| Testing | pytest | 8.x | Already in project |

**New dependencies to add**:
- streamlit>=1.33.0
- plotly>=5.18.0

---

## Integration Points

### Read from Bronze Tier

| Data | Source Path | Model |
|------|-------------|-------|
| Validation results | data/results/*.json | ValidationResult |
| Health state | data/state/health.json | HealthScore |
| Anomalies | Embedded in ValidationResult | Anomaly |
| Audit events | logs/audit/*.jsonl | Custom TimelineEvent |

### Dashboard State

| State | Storage | Persistence |
|-------|---------|-------------|
| Last refresh time | Streamlit session_state | Session only |
| Selected filters | Streamlit session_state | Session only |
| Acknowledged incidents | data/dashboard/acknowledged.json | Persistent |
| User view preference | Streamlit session_state | Session only |

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Streamlit session timeout | Loss of filter state | Use query params for critical state |
| Large result files slow load | Poor UX | Implement pagination, load recent first |
| No results yet | Empty dashboard | Show "No data" guidance message |
| Concurrent file access | Read errors | Use file locking or copy-on-read |
