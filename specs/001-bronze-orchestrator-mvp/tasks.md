# Tasks: Bronze Tier MVP with Orchestrator

**Input**: Design documents from `/specs/001-bronze-orchestrator-mvp/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested - test tasks omitted. Add tests in Polish phase if needed.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md)
- Config files in `config/`
- Data directories in `data/` and `logs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project directory structure per plan.md (src/models/, src/services/, src/skills/bronze/, src/skills/util/, src/cli/, src/lib/, tests/, config/)
- [ ] T002 Initialize Python project with pyproject.toml including dependencies: pydantic>=2.5.0, watchdog>=4.0.0, apscheduler>=3.10.0, structlog>=24.0.0, pyyaml>=6.0
- [ ] T003 [P] Create all __init__.py files for Python packages
- [ ] T004 [P] Create config/default.yaml with orchestrator settings (watcher path, scheduler intervals, heartbeat config)
- [ ] T005 [P] Create config/validation_rules.yaml with sample field definitions and severity weights

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Implement failure codes enum (DV-001 through DV-008) in src/lib/constants.py
- [ ] T007 [P] Implement severity level enum (INFO, WARNING, CRITICAL) in src/lib/constants.py
- [ ] T008 [P] Implement batch status enum (PENDING, VALIDATING, PASSED, FAILED, ERROR) in src/lib/constants.py
- [ ] T009 Implement structured JSON logger setup using structlog in src/lib/logger.py
- [ ] T010 Implement YAML configuration loader in src/lib/config.py
- [ ] T011 Create data directories (data/incoming/, data/checkpoints/, data/quarantine/, data/state/, data/batches/, data/results/, logs/audit/, logs/alerts/)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Data Engineer Validates Incoming Batch (Priority: P1) 🎯 MVP

**Goal**: Incoming data batches are automatically validated against 7 quality rules with pass/fail results and specific failure details

**Independent Test**: Submit a data batch file and verify validation results are returned with pass/fail status and failure codes

### Models for User Story 1

- [ ] T012 [P] [US1] Create DataBatch model with id, source, arrival_timestamp, record_count, status, records, metadata in src/models/data_batch.py
- [ ] T013 [P] [US1] Create Anomaly model with failure_code, severity, severity_score, affected_records, root_cause, explanation in src/models/anomaly.py
- [ ] T014 [P] [US1] Create ValidationResult model with batch_id, passed, anomalies, health_score, duration_ms, skills_executed in src/models/validation_result.py
- [ ] T015 [P] [US1] Create HealthScore model with overall_score, component_scores, trend, active_anomalies in src/models/health_score.py

### Bronze Skills for User Story 1

- [ ] T016 [P] [US1] Implement bronze.count skill (validate record counts) in src/skills/bronze/count.py
- [ ] T017 [P] [US1] Implement bronze.null skill (detect null/missing values) in src/skills/bronze/null.py
- [ ] T018 [P] [US1] Implement bronze.type skill (verify data type conformance) in src/skills/bronze/type_check.py
- [ ] T019 [P] [US1] Implement bronze.range skill (validate range boundaries) in src/skills/bronze/range_check.py
- [ ] T020 [P] [US1] Implement bronze.format skill (regex pattern matching) in src/skills/bronze/format.py
- [ ] T021 [P] [US1] Implement bronze.duplicate skill (detect exact duplicates) in src/skills/bronze/duplicate.py
- [ ] T022 [P] [US1] Implement bronze.encoding skill (verify UTF-8 compliance) in src/skills/bronze/encoding.py

### Utility Skills for User Story 1

- [ ] T023 [P] [US1] Implement util.score skill (calculate severity score using formula) in src/skills/util/score.py
- [ ] T024 [P] [US1] Implement util.health skill (calculate aggregate health score) in src/skills/util/health.py

### Services for User Story 1

- [ ] T025 [US1] Implement Validator service that coordinates all Bronze skills in src/services/validator.py
- [ ] T026 [US1] Implement batch file loader (CSV/JSON parsing) in src/services/validator.py
- [ ] T027 [US1] Implement validation result persistence (write to data/results/) in src/services/validator.py

### Logging for User Story 1

- [ ] T028 [US1] Implement bronze.log skill (write audit entries) in src/skills/bronze/log.py
- [ ] T029 [US1] Add structured logging for all validation decisions per FR-020 in src/services/validator.py

**Checkpoint**: User Story 1 complete - can validate batches and return results with failure codes

---

## Phase 4: User Story 2 - System Alerts on Critical Data Issues (Priority: P1)

**Goal**: Alerts are generated within specified timeframes for WARNING and CRITICAL severity issues

**Independent Test**: Submit data with known critical issues and verify alerts appear within 1 minute (CRITICAL) or 5 minutes (WARNING)

### Models for User Story 2

- [ ] T030 [P] [US2] Create Alert model with anomaly_id, severity, message, channel, sent_timestamp in src/models/alert.py

### Implementation for User Story 2

- [ ] T031 [US2] Implement Alerter service with severity-based timing (1min CRITICAL, 5min WARNING) in src/services/alerter.py
- [ ] T032 [US2] Implement bronze.alert skill (format and dispatch alerts) in src/skills/bronze/alert.py
- [ ] T033 [US2] Implement console alert channel output in src/services/alerter.py
- [ ] T034 [US2] Implement alert logging to logs/alerts/{date}.jsonl in src/services/alerter.py
- [ ] T035 [US2] Integrate Alerter with Validator to trigger alerts post-validation in src/services/validator.py

**Checkpoint**: User Story 2 complete - alerts generated for WARNING/CRITICAL within timeframes

---

## Phase 5: User Story 3 - Orchestrator Coordinates Validation Flow (Priority: P1)

**Goal**: Validation executes automatically based on file arrival, schedules, and manual triggers

**Independent Test**: Start orchestrator, drop file in monitored directory, verify validation triggers within 5 seconds

### Models for User Story 3

- [ ] T036 [P] [US3] Create Checkpoint model with batch_id, position, partial_results, validation_context in src/models/checkpoint.py

### Utility Skills for User Story 3

- [ ] T037 [P] [US3] Implement util.checkpoint skill (save/restore validation state) in src/skills/util/checkpoint.py

### Orchestrator Implementation

- [ ] T038 [US3] Implement file watcher using watchdog for data/incoming/ in src/services/orchestrator.py
- [ ] T039 [US3] Implement FIFO event queue for batch processing in src/services/orchestrator.py
- [ ] T040 [US3] Implement scheduler using apscheduler for periodic tasks in src/services/orchestrator.py
- [ ] T041 [US3] Implement 60-second heartbeat emission (FR-014) in src/services/orchestrator.py
- [ ] T042 [US3] Implement manual validation trigger method in src/services/orchestrator.py
- [ ] T043 [US3] Implement error recovery - continue after validation failures (FR-015) in src/services/orchestrator.py
- [ ] T044 [US3] Implement checkpoint save/restore for recovery (FR-018, FR-019) in src/services/orchestrator.py
- [ ] T045 [US3] Integrate orchestrator with validator and alerter services in src/services/orchestrator.py

### CLI for User Story 3

- [ ] T046 [US3] Implement CLI entry point with start/stop/status commands in src/cli/main.py
- [ ] T047 [US3] Implement CLI manual trigger command (validate <path>) in src/cli/main.py

**Checkpoint**: User Story 3 complete - orchestrator runs continuously, detects files, triggers validation

---

## Phase 6: User Story 4 - View Validation Results and Health Score (Priority: P2)

**Goal**: Users can query current health score and recent validation results via CLI

**Independent Test**: Run validations, then use CLI to query health status and see score 0-100

### Implementation for User Story 4

- [ ] T048 [US4] Implement health state persistence to data/state/health.json in src/skills/util/health.py
- [ ] T049 [US4] Implement CLI health command showing current score (0-100) and trend in src/cli/main.py
- [ ] T050 [US4] Implement CLI results command showing last N validation results in src/cli/main.py
- [ ] T051 [US4] Implement CLI issues command showing recent anomalies with severity/code/timestamp in src/cli/main.py
- [ ] T052 [US4] Add "healthy" status display when no anomalies exist in src/cli/main.py

**Checkpoint**: User Story 4 complete - health and results viewable via CLI

---

## Phase 7: User Story 5 - Invalid Records Are Quarantined (Priority: P2)

**Goal**: Records with CRITICAL severity are isolated to quarantine location while preserving original

**Independent Test**: Submit data with CRITICAL issues, verify affected records appear in data/quarantine/

### Implementation for User Story 5

- [ ] T053 [US5] Implement bronze.quarantine skill (isolate records to data/quarantine/) in src/skills/bronze/quarantine.py
- [ ] T054 [US5] Implement quarantine logging with record reference in src/skills/bronze/quarantine.py
- [ ] T055 [US5] Integrate quarantine trigger for CRITICAL severity only in src/services/validator.py
- [ ] T056 [US5] Ensure WARNING/INFO records are flagged but NOT quarantined in src/services/validator.py
- [ ] T057 [US5] Add CLI quarantine command to list quarantined records in src/cli/main.py

**Checkpoint**: User Story 5 complete - CRITICAL records quarantined, preserved for investigation

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T058 [P] Create sample test data files in config/sample_data/ (valid_batch.csv, invalid_batch.csv)
- [ ] T059 [P] Validate quickstart.md instructions by running through setup
- [ ] T060 Add graceful shutdown handling to orchestrator in src/services/orchestrator.py
- [ ] T061 Add configuration validation on startup in src/lib/config.py
- [ ] T062 Add last-known-good config fallback per edge case requirements in src/lib/config.py
- [ ] T063 Implement chunked processing for batches >10K records in src/services/validator.py
- [ ] T064 Run full end-to-end test: start orchestrator → drop file → verify validation → check alerts → verify health score

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1, US2, US3 are all P1 priority - complete in order for MVP
  - US4, US5 are P2 priority - can follow after P1 stories
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - Core validation, no dependencies
- **User Story 2 (P1)**: Depends on US1 (needs anomalies to generate alerts)
- **User Story 3 (P1)**: Depends on US1 & US2 (orchestrator coordinates validator + alerter)
- **User Story 4 (P2)**: Depends on US1 (needs health score from validation)
- **User Story 5 (P2)**: Depends on US1 & US2 (needs severity classification)

### Within Each User Story

- Models before services
- Skills can be implemented in parallel
- Services integrate skills
- CLI commands integrate services

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T007, T008 (enums) can run in parallel
- T009, T010 (logger, config) can run in parallel after enums

**Phase 3 (User Story 1)**:
- T012-T015 (all models) can run in parallel
- T016-T022 (all Bronze skills) can run in parallel
- T023-T024 (util skills) can run in parallel

**Phase 4-7 (User Stories 2-5)**:
- Model tasks marked [P] within each story

---

## Parallel Example: User Story 1 Skills

```bash
# Launch all Bronze skills in parallel (different files, no dependencies):
Task T016: "Implement bronze.count skill in src/skills/bronze/count.py"
Task T017: "Implement bronze.null skill in src/skills/bronze/null.py"
Task T018: "Implement bronze.type skill in src/skills/bronze/type_check.py"
Task T019: "Implement bronze.range skill in src/skills/bronze/range_check.py"
Task T020: "Implement bronze.format skill in src/skills/bronze/format.py"
Task T021: "Implement bronze.duplicate skill in src/skills/bronze/duplicate.py"
Task T022: "Implement bronze.encoding skill in src/skills/bronze/encoding.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1-3)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (validation works)
4. Complete Phase 4: User Story 2 (alerts work)
5. Complete Phase 5: User Story 3 (orchestrator works)
6. **STOP and VALIDATE**: Full autonomous validation system working
7. Deploy/demo MVP

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Can manually validate files (MVP core)
3. Add US2 → Alerts generated (operational value)
4. Add US3 → Fully autonomous (MVP complete!)
5. Add US4 → Health visibility (nice-to-have)
6. Add US5 → Quarantine (data governance)

---

## Summary

| Phase | Story | Tasks | Parallel Tasks |
|-------|-------|-------|----------------|
| 1 - Setup | - | 5 | 3 |
| 2 - Foundational | - | 6 | 3 |
| 3 - US1 | P1 | 18 | 15 |
| 4 - US2 | P1 | 6 | 1 |
| 5 - US3 | P1 | 12 | 2 |
| 6 - US4 | P2 | 5 | 0 |
| 7 - US5 | P2 | 5 | 0 |
| 8 - Polish | - | 7 | 2 |
| **Total** | | **64** | **26** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable at its checkpoint
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP = completing User Stories 1, 2, and 3 (Phase 3-5)
