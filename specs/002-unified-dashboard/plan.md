# Implementation Plan: Unified Monitoring Dashboard

**Branch**: `002-unified-dashboard` | **Date**: 2026-01-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-unified-dashboard/spec.md`

## Summary

Build a Streamlit-based unified monitoring dashboard that visualizes Bronze tier validation results per Constitution Section 6 requirements. The dashboard enables executives to understand system health within 30 seconds, engineers to drill down to root causes, and compliance officers to export audit reports.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Streamlit 1.33+, Plotly 5.x, Pydantic 2.x (reuse from Bronze)
**Storage**: File-based (JSON/JSONL) - reuse existing Bronze tier output paths
**Testing**: pytest 8.x with Streamlit testing utilities
**Target Platform**: Web browser (localhost:8501)
**Project Type**: Single project extending existing codebase
**Performance Goals**: Initial load <3 seconds, auto-refresh every 30 seconds
**Constraints**: No external database, file-based storage only, desktop-first
**Scale/Scope**: Single-user MVP, up to 30 days historical data, 100 timeline events max

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Constitution Section 6 Compliance Matrix

| Requirement | Spec FR | Plan Coverage | Status |
|-------------|---------|---------------|--------|
| 6.1 Unified Dashboard | - | Single Streamlit app | PASS |
| 6.2 Executive Summary Panel | FR-001 to FR-005 | ExecutiveSummary component | PASS |
| 6.3 Health Scores Display | FR-006 to FR-009 | LayerHealth component | PASS |
| 6.4 Visual Indicators | FR-010 to FR-013 | Color scheme, trend arrows | PASS |
| 6.5 Business Impact Views | FR-014 to FR-017 | ImpactTranslator service | PASS |
| 6.6 Incident Timeline | FR-018 to FR-022 | IncidentTimeline + Plotly | PASS |
| 6.7 Drill-Down Capability | FR-023 to FR-025 | DrillDown with expanders | PASS |
| 6.8 User Personas | FR-026 to FR-028 | Sidebar view switcher | PASS |

### Additional Constitution Checks

| Section | Check | Status |
|---------|-------|--------|
| 9.3 LLM Usage | No LLM for core functions | PASS (translations are template-based) |
| 9.1 Technical Constraints | <3s load, <100ms per record | PASS (polling model) |
| 10.1 Skill Architecture | Single-purpose components | PASS (component structure) |

**Gate Result**: PASSED - Ready for implementation

## Project Structure

### Documentation (this feature)

```text
specs/002-unified-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output (complete)
├── data-model.md        # Phase 1 output (complete)
├── quickstart.md        # Phase 1 output (complete)
├── contracts/           # Phase 1 output (complete)
│   └── dashboard-api.yaml
└── tasks.md             # Phase 2 output (/sp.tasks command)
```

### Source Code (repository root)

```text
# Existing structure (Bronze Tier)
src/
├── models/              # Reuse: ValidationResult, HealthScore, Anomaly
├── services/            # Reuse: config.py
├── cli/                 # Existing CLI
└── lib/                 # Reuse: constants.py, logger.py, config.py

# New dashboard code
dashboard/
├── app.py               # Main Streamlit entry point
├── __init__.py
├── components/
│   ├── __init__.py
│   ├── executive_summary.py    # FR-001 to FR-005
│   ├── layer_health.py         # FR-006 to FR-009
│   ├── business_impact.py      # FR-014 to FR-017
│   ├── incident_timeline.py    # FR-018 to FR-022
│   └── drill_down.py           # FR-023 to FR-025
├── services/
│   ├── __init__.py
│   ├── data_loader.py          # Read Bronze tier output
│   ├── health_calculator.py    # Aggregate health scores
│   ├── impact_translator.py    # Technical to business language
│   ├── timeline_builder.py     # Build timeline events
│   └── state_manager.py        # Persistent dashboard state
└── config/
    └── translations.yaml       # Business impact translation rules

# New test code
tests/
├── dashboard/
│   ├── __init__.py
│   ├── conftest.py             # Dashboard test fixtures
│   ├── test_data_loader.py
│   ├── test_health_calculator.py
│   ├── test_impact_translator.py
│   ├── test_timeline_builder.py
│   └── test_components.py      # Streamlit component tests

# Configuration
config/
├── dashboard.yaml              # Dashboard-specific settings
└── translations.yaml           # Business impact translations
```

**Structure Decision**: Extension of existing single-project layout. Dashboard is a new top-level module alongside `src/` to keep UI separate from core logic while sharing models via imports.

## Complexity Tracking

> No constitution violations to justify - design passes all gates.

| Aspect | Complexity Level | Justification |
|--------|------------------|---------------|
| Component count | Low (5 components) | Matches spec FR groupings |
| Service count | Low (5 services) | One per data concern |
| New dependencies | Minimal (2: Streamlit, Plotly) | User-specified technology |
| Model reuse | High | 80% from existing Bronze tier |

## Implementation Phases (for /sp.tasks)

### Phase 1: Foundation
- Setup dashboard directory structure
- Add Streamlit/Plotly dependencies to pyproject.toml
- Create DataLoader service to read Bronze tier output
- Create basic app.py with health score display

### Phase 2: Core Components (P1 Stories)
- Implement ExecutiveSummary component (FR-001 to FR-005)
- Implement LayerHealth component (FR-006 to FR-009)
- Implement DrillDown component (FR-023 to FR-025)
- Add auto-refresh mechanism

### Phase 3: Business Features (P2 Stories)
- Implement ImpactTranslator with translations.yaml
- Implement BusinessImpact component (FR-014 to FR-017)
- Implement IncidentTimeline with Plotly (FR-018 to FR-022)
- Add filtering and time range selection

### Phase 4: Persona Views & Export (P3 Stories)
- Implement view switcher in sidebar (FR-026 to FR-028)
- Add report export capability
- Implement StateManager for acknowledgments

### Phase 5: Polish & Testing
- Write unit tests for services
- Write component tests
- Add edge case handling (no data, errors)
- Performance optimization

## Artifacts Generated

| Artifact | Path | Status |
|----------|------|--------|
| Research | specs/002-unified-dashboard/research.md | Complete |
| Data Model | specs/002-unified-dashboard/data-model.md | Complete |
| Contracts | specs/002-unified-dashboard/contracts/dashboard-api.yaml | Complete |
| Quickstart | specs/002-unified-dashboard/quickstart.md | Complete |

## Next Steps

Run `/sp.tasks` to generate detailed implementation tasks from this plan.
