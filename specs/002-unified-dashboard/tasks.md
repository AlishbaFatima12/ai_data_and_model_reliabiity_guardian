# Tasks: Unified Monitoring Dashboard

**Input**: Design documents from `/specs/002-unified-dashboard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests will be included in Phase 8 (Polish) as the spec does not mandate TDD approach.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Dashboard module**: `dashboard/` at repository root (alongside existing `src/`)
- **Existing Bronze tier**: `src/models/`, `src/lib/` (reused, not modified)
- **Configuration**: `config/` at repository root
- **Tests**: `tests/dashboard/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create dashboard directory structure per plan.md: dashboard/, dashboard/components/, dashboard/services/, dashboard/config/
- [x] T002 Add Streamlit and Plotly dependencies to pyproject.toml (streamlit>=1.33.0, plotly>=5.18.0)
- [x] T003 [P] Create dashboard/__init__.py with package metadata
- [x] T004 [P] Create dashboard/components/__init__.py
- [x] T005 [P] Create dashboard/services/__init__.py
- [x] T006 [P] Create config/dashboard.yaml with refresh interval, max events, theme colors
- [x] T007 [P] Create config/translations.yaml with business impact translation templates

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core services that MUST be complete before ANY user story component can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T008 Implement DataLoader.get_latest_results() in dashboard/services/data_loader.py - reads from data/results/*.json
- [x] T009 Implement DataLoader.get_health_state() in dashboard/services/data_loader.py - reads from data/state/health.json
- [x] T010 Implement DataLoader.get_anomalies() in dashboard/services/data_loader.py - extracts anomalies with filtering
- [x] T011 [P] Implement HealthCalculator.get_overall_health() in dashboard/services/health_calculator.py - score, status, trend, color
- [x] T012 [P] Implement HealthCalculator.get_layer_health() in dashboard/services/health_calculator.py - per-layer breakdown
- [x] T013 [P] Implement HealthCalculator.get_health_history() in dashboard/services/health_calculator.py - sparkline data
- [x] T014 Create dashboard color constants in dashboard/services/health_calculator.py - Green #00A67E, Yellow #FFB020, Orange #FF8C00, Red #DC3545
- [x] T015 Create basic app.py skeleton in dashboard/app.py with Streamlit page config, sidebar, and main container

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Executive Views System Health (Priority: P1) MVP

**Goal**: Non-technical executive views instant health summary within 30 seconds

**Independent Test**: Load dashboard, verify health score (0-100) with color, trend sparkline, issue count badge, and plain language summary display

### Implementation for User Story 1

- [x] T016 [US1] Implement ImpactTranslator.translate_health_summary() in dashboard/services/impact_translator.py - generates plain language summary
- [x] T017 [P] [US1] Create ExecutiveSummary component in dashboard/components/executive_summary.py - FR-001 health score display with color
- [x] T018 [P] [US1] Add health trend sparkline to ExecutiveSummary using Plotly - FR-002
- [x] T019 [US1] Add active issues count badge with severity breakdown to ExecutiveSummary - FR-003
- [x] T020 [US1] Add "Last Updated" timestamp with relative time to ExecutiveSummary - FR-004
- [x] T021 [US1] Add plain language summary display to ExecutiveSummary using ImpactTranslator - FR-005
- [x] T022 [US1] Implement auto-refresh mechanism using st.rerun with 30-second timer in dashboard/app.py - SC-004
- [x] T023 [US1] Integrate ExecutiveSummary into app.py main view
- [x] T024 [US1] Add "No data available" edge case handling with guidance message

**Checkpoint**: User Story 1 complete - Executive can view health summary in 30 seconds

---

## Phase 4: User Story 2 - Data Engineer Investigates Alert (Priority: P1)

**Goal**: Data engineer drills down from health score to technical details in 3 clicks

**Independent Test**: Click health indicator, verify progressive detail reveal (plain -> summary -> full technical)

### Implementation for User Story 2

- [x] T025 [P] [US2] Create LayerHealth component in dashboard/components/layer_health.py - FR-006 layer scores display
- [x] T026 [P] [US2] Add trend arrows (Up/Down/Flat) to LayerHealth - FR-007, FR-011
- [x] T027 [US2] Add horizontal progress bars with color gradient to LayerHealth - FR-008, FR-010
- [x] T028 [US2] Implement overall health calculation as minimum of layers - FR-009
- [x] T029 [US2] Create DrillDown component skeleton in dashboard/components/drill_down.py - FR-023
- [x] T030 [US2] Implement 3-level drill-down logic: plain (default) -> summary (click 1) -> full technical (click 2)
- [x] T031 [US2] Add raw metric values, thresholds, and queries to full technical view - FR-024
- [x] T032 [US2] Implement StateManager.acknowledge_anomaly() in dashboard/services/state_manager.py
- [x] T033 [US2] Add acknowledge button and retry trigger to DrillDown component
- [x] T034 [US2] Integrate LayerHealth and DrillDown into app.py
- [x] T035 [US2] Wire click handlers from LayerHealth to DrillDown expansion - FR-025

**Checkpoint**: User Story 2 complete - Engineer can drill down to root cause in 3 clicks

---

## Phase 5: User Story 3 - Business Analyst Reviews Trends (Priority: P2)

**Goal**: Business analyst sees business impact translation of technical metrics

**Independent Test**: View data quality issue, verify business language description with affected processes and recommendations

### Implementation for User Story 3

- [x] T036 [US3] Implement ImpactTranslator.translate_anomaly() in dashboard/services/impact_translator.py - loads from translations.yaml
- [x] T037 [P] [US3] Create BusinessImpact component in dashboard/components/business_impact.py - FR-014 technical to business translation
- [x] T038 [US3] Add affected business processes list to BusinessImpact - FR-015
- [x] T039 [US3] Add affected customer segments to BusinessImpact - FR-016
- [x] T040 [US3] Add recommended business actions to BusinessImpact - FR-017
- [x] T041 [US3] Populate translations.yaml with Bronze tier failure code translations (DV-001 to DV-008)
- [x] T042 [US3] Integrate BusinessImpact into app.py below ExecutiveSummary

**Checkpoint**: User Story 3 complete - Analyst can see business impact of any issue

---

## Phase 6: User Story 4 - View Incident Timeline (Priority: P2)

**Goal**: Any user views timeline of incidents with filtering and grouping

**Independent Test**: View timeline, filter by severity/layer/date, hover for details, verify event grouping

### Implementation for User Story 4

- [x] T043 [P] [US4] Create TimelineEvent model in dashboard/models/timeline_event.py per data-model.md
- [x] T044 [US4] Implement TimelineBuilder.get_timeline_events() in dashboard/services/timeline_builder.py - reads from logs/audit/*.jsonl
- [x] T045 [US4] Implement event grouping logic for related events in TimelineBuilder - FR-022
- [x] T046 [US4] Implement TimelineBuilder.get_event_details() for drill-down
- [x] T047 [P] [US4] Create IncidentTimeline component in dashboard/components/incident_timeline.py - FR-018 horizontal scrollable timeline
- [x] T048 [US4] Implement Plotly timeline visualization with severity color markers - FR-019
- [x] T049 [US4] Add hover/click popup with plain-language summary - FR-020
- [x] T050 [US4] Add filter controls: severity, layer, asset, time range - FR-021
- [x] T051 [US4] Add zoom controls (hour/day/week/month) to IncidentTimeline
- [x] T052 [US4] Add visual clustering for grouped events with correlation lines
- [x] T053 [US4] Integrate IncidentTimeline into app.py
- [x] T054 [US4] Handle large incident volumes (>50) with pagination

**Checkpoint**: User Story 4 complete - Timeline shows 30 days of history with filtering

---

## Phase 7: User Story 5 - Compliance Officer Generates Report (Priority: P3)

**Goal**: Compliance officer exports audit history and health reports

**Independent Test**: Generate report for time range, download file, verify contents include incidents, health scores, audit trail

### Implementation for User Story 5

- [x] T055 [US5] Implement view switcher in sidebar with Executive/Engineer/Compliance options - FR-026, FR-027, FR-028
- [x] T056 [US5] Configure Executive view: health score, trend, business impact visible
- [x] T057 [US5] Configure Engineer view: layer health, technical details, pipeline status visible
- [x] T058 [US5] Configure Compliance view: audit log, incident history, export button visible
- [x] T059 [US5] Implement StateManager.get_acknowledged_ids() in dashboard/services/state_manager.py
- [x] T060 [US5] Create audit log view component showing timestamped system actions
- [x] T061 [US5] Implement report generation: collect health scores, incidents, audit trail for time range
- [x] T062 [US5] Add st.download_button for compliance report export (JSON format)
- [x] T063 [US5] Store acknowledged anomalies in data/dashboard/acknowledged.json via StateManager

**Checkpoint**: User Story 5 complete - Compliance officer can export full audit report

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Testing, edge cases, and improvements that affect multiple user stories

- [x] T064 [P] Create tests/dashboard/__init__.py and tests/dashboard/conftest.py with fixtures
- [x] T065 [P] Write unit tests for DataLoader in tests/dashboard/test_data_loader.py
- [x] T066 [P] Write unit tests for HealthCalculator in tests/dashboard/test_health_calculator.py
- [x] T067 [P] Write unit tests for ImpactTranslator in tests/dashboard/test_impact_translator.py
- [x] T068 [P] Write unit tests for TimelineBuilder in tests/dashboard/test_timeline_builder.py
- [x] T069 Write integration tests for dashboard startup and basic rendering in tests/dashboard/test_integration.py
- [x] T070 Add error handling for backend service unavailable - display cached data with staleness warning
- [x] T071 Add progressive loading with skeleton placeholders for slow connections
- [x] T072 Validate performance: initial load <3 seconds, refresh without full page reload
- [x] T073 Run quickstart.md validation steps to verify end-to-end functionality

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority - implement US1 first (executive view is MVP)
  - US3 and US4 are both P2 priority - can proceed after US1/US2
  - US5 is P3 priority - last functional story
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - Uses LayerHealth independently, DrillDown can be triggered from US1 components
- **User Story 3 (P2)**: Can start after Foundational - Uses ImpactTranslator independently
- **User Story 4 (P2)**: Can start after Foundational - Timeline is standalone component
- **User Story 5 (P3)**: Can start after Foundational - View switcher integrates all previous components

### Within Each User Story

- Services before components that use them
- Models before services that use them
- Core component before integration with app.py
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks T003-T007 marked [P] can run in parallel
- Foundational tasks T011-T013 marked [P] can run in parallel (after T008-T010)
- Within each user story, tasks marked [P] can run in parallel
- Different user stories can theoretically run in parallel (after Phase 2), but P1 stories should complete first

---

## Parallel Example: User Story 1

```bash
# After T016 (ImpactTranslator) completes, launch these in parallel:
Task: T017 "Create ExecutiveSummary component in dashboard/components/executive_summary.py"
Task: T018 "Add health trend sparkline to ExecutiveSummary using Plotly"

# Then sequential:
Task: T019 "Add active issues count badge..."
Task: T020 "Add Last Updated timestamp..."
Task: T021 "Add plain language summary..."
```

## Parallel Example: User Story 4

```bash
# These can run in parallel:
Task: T043 "Create TimelineEvent model in dashboard/models/timeline_event.py"
Task: T047 "Create IncidentTimeline component in dashboard/components/incident_timeline.py"

# Then T044-T046 depend on T043, T048-T052 depend on T047
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T015)
3. Complete Phase 3: User Story 1 (T016-T024)
4. **STOP and VALIDATE**: Launch `streamlit run dashboard/app.py`, verify executive summary works
5. Deploy/demo if ready - executives can see health status

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test independently -> Deploy (MVP!)
3. Add User Story 2 -> Test drill-down -> Deploy (Engineer functionality)
4. Add User Story 3 -> Test business impact -> Deploy
5. Add User Story 4 -> Test timeline -> Deploy
6. Add User Story 5 -> Test export -> Deploy (Full feature)
7. Add Polish -> Run tests -> Final release

### Task Count Summary

| Phase | Tasks | Parallel Opportunities |
|-------|-------|------------------------|
| 1: Setup | 7 | 5 tasks can run in parallel |
| 2: Foundational | 8 | 3 tasks can run in parallel |
| 3: US1 (P1) | 9 | 2 tasks can run in parallel |
| 4: US2 (P1) | 11 | 2 tasks can run in parallel |
| 5: US3 (P2) | 7 | 1 task can run in parallel |
| 6: US4 (P2) | 12 | 2 tasks can run in parallel |
| 7: US5 (P3) | 9 | 0 (sequential) |
| 8: Polish | 10 | 5 tasks can run in parallel |
| **Total** | **73** | **20 parallel opportunities** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [USx] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Streamlit hot reload (`--server.runOnSave true`) speeds development
- All existing Bronze tier models (ValidationResult, HealthScore, Anomaly) are imported, not modified
