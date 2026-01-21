# Tasks: Silver Tier - Schema, Business Logic & Freshness Enforcement

**Input**: Design documents from `/specs/003-silver-tier-enforcement/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included inline with each user story per TDD approach.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (extending existing Bronze structure)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and basic Silver tier structure

- [x] T001 Add Silver tier dependencies (jsonschema, deepdiff, croniter) to pyproject.toml
- [x] T002 [P] Create src/skills/silver/__init__.py with skill exports
- [x] T003 [P] Create tests/silver/__init__.py and tests/silver/conftest.py with Silver fixtures
- [x] T004 [P] Create config/schemas/ directory with sample_schema.json
- [x] T005 [P] Create config/rules/ directory with sample_rules.yaml
- [x] T006 [P] Create config/sla/ directory with sample_sla.yaml
- [x] T007 [P] Create data/reference/ directory with sample_lookup.csv

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T008 Extend FailureCode enum in src/lib/constants.py with Silver codes (SC-001 to SC-008, BL-001 to BL-008, FR-001 to FR-008)
- [x] T009 [P] Create base Silver anomaly models in src/models/silver_anomaly.py (SchemaAnomaly, BusinessLogicAnomaly, FreshnessAnomaly)
- [x] T010 [P] Create SilverTierHealthScore model in src/models/health_score.py (extend existing)
- [x] T011 [P] Create SilverValidationResult model in src/models/validation_result.py (extend existing)
- [x] T012 Create SilverValidator service skeleton in src/services/silver_validator.py
- [x] T013 [P] Create tests/silver/unit/__init__.py and tests/silver/integration/__init__.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Schema Contract Enforcement (Priority: P1)

**Goal**: Detect schema violations (missing columns, type changes, version mismatches) and block invalid data

**Independent Test**: Send data with intentional schema mismatches and verify SC-001 to SC-008 anomalies are raised correctly

### Tests for User Story 1

- [x] T014 [P] [US1] Unit test for schema skill in tests/silver/unit/skills/test_schema.py
- [x] T015 [P] [US1] Unit test for version skill in tests/silver/unit/skills/test_version.py
- [x] T016 [P] [US1] Unit test for contract skill in tests/silver/unit/skills/test_contract.py
- [x] T017 [P] [US1] Integration test for schema validation E2E in tests/silver/integration/test_schema_validation_e2e.py

### Implementation for User Story 1

- [x] T018 [P] [US1] Create SchemaContract model in src/models/schema_contract.py
- [x] T019 [P] [US1] Create ColumnDefinition model in src/models/schema_contract.py
- [x] T020 [US1] Implement SchemaRegistry service in src/services/schema_registry.py (load schemas from config/schemas/)
- [x] T021 [US1] Implement silver.schema skill in src/skills/silver/schema.py (validate data against JSON Schema)
- [x] T022 [US1] Implement silver.version skill in src/skills/silver/version.py (compare schema versions, detect breaking changes)
- [x] T023 [US1] Implement silver.contract skill in src/skills/silver/contract.py (checksum comparison)
- [x] T024 [US1] Add SC-001 to SC-008 detection logic in schema skill with severity based on column criticality
- [x] T025 [US1] Integrate schema validation into SilverValidator.validate_schema() in src/services/silver_validator.py
- [x] T026 [US1] Add blocking logic for CRITICAL schema violations in src/services/silver_validator.py

**Checkpoint**: Schema validation complete - data with schema mismatches is detected and blocked

---

## Phase 4: User Story 2 - Business Logic Validation (Priority: P1)

**Goal**: Detect business rule violations (cross-field, referential, calculations, state transitions, distribution)

**Independent Test**: Send data with business rule violations and verify BL-001 to BL-008 anomalies are raised

### Tests for User Story 2

- [ ] T027 [P] [US2] Unit test for crossfield skill in tests/silver/unit/skills/test_crossfield.py
- [ ] T028 [P] [US2] Unit test for refint skill in tests/silver/unit/skills/test_refint.py
- [ ] T029 [P] [US2] Unit test for bizrule skill in tests/silver/unit/skills/test_bizrule.py
- [ ] T030 [P] [US2] Unit test for distrib skill in tests/silver/unit/skills/test_distrib.py
- [ ] T031 [P] [US2] Integration test for business logic E2E in tests/silver/integration/test_business_logic_e2e.py

### Implementation for User Story 2

- [x] T032 [P] [US2] Create BusinessRule model in src/models/business_rule.py
- [x] T033 [P] [US2] Create ReferenceDataSet model in src/models/reference_data.py
- [x] T034 [US2] Implement RuleEngine service in src/services/rule_engine.py (load rules from config/rules/)
- [x] T035 [US2] Implement ReferenceDataLoader in src/services/rule_engine.py (load CSV/JSON lookup files)
- [x] T036 [US2] Implement silver.crossfield skill in src/skills/silver/crossfield.py (field comparisons: end_date > start_date)
- [x] T037 [US2] Implement silver.refint skill in src/skills/silver/refint.py (referential integrity checks)
- [x] T038 [US2] Implement silver.bizrule skill in src/skills/silver/bizrule.py (calculation validation, state transitions)
- [x] T039 [US2] Implement silver.distrib skill in src/skills/silver/distrib.py (PSI-based distribution shift detection)
- [x] T040 [US2] Add BL-001 to BL-008 detection logic across business logic skills
- [x] T041 [US2] Integrate business logic validation into SilverValidator.validate_business_logic() in src/services/silver_validator.py

**Checkpoint**: Business logic validation complete - data with rule violations is detected

---

## Phase 5: User Story 3 - Freshness & SLA Monitoring (Priority: P2)

**Goal**: Monitor data freshness, detect SLA breaches, track pipeline delays

**Independent Test**: Configure SLA thresholds and verify FR-001 to FR-008 anomalies fire when data is late

### Tests for User Story 3

- [ ] T042 [P] [US3] Unit test for freshness skill in tests/silver/unit/skills/test_freshness.py
- [ ] T043 [P] [US3] Unit test for sla skill in tests/silver/unit/skills/test_sla.py
- [ ] T044 [P] [US3] Unit test for pipeline skill in tests/silver/unit/skills/test_pipeline.py
- [ ] T045 [P] [US3] Integration test for freshness monitoring E2E in tests/silver/integration/test_freshness_monitoring_e2e.py

### Implementation for User Story 3

- [x] T046 [P] [US3] Create SLADefinition model in src/models/sla_definition.py
- [x] T047 [P] [US3] Create FreshnessState model in src/models/sla_definition.py
- [x] T048 [US3] Implement FreshnessWatcher service in src/services/freshness_watcher.py (scheduled checks)
- [x] T049 [US3] Implement silver.freshness skill in src/skills/silver/freshness.py (staleness detection)
- [x] T050 [US3] Implement silver.sla skill in src/skills/silver/sla.py (SLA compliance tracking)
- [x] T051 [US3] Implement silver.pipeline skill in src/skills/silver/pipeline.py (duration monitoring)
- [x] T052 [US3] Implement silver.dependency skill in src/skills/silver/dependency.py (dependency chain tracking)
- [x] T053 [US3] Add FR-001 to FR-008 detection logic across freshness skills
- [x] T054 [US3] Add warning at 60 minutes, critical at 90 minutes escalation logic
- [x] T055 [US3] Integrate FreshnessWatcher with orchestrator scheduler (30-second parallel checks)
- [x] T056 [US3] Create data/state/freshness.json for freshness state persistence

**Checkpoint**: Freshness monitoring complete - stale data and SLA breaches are detected

---

## Phase 6: User Story 4 - Unified Silver Tier Health Reporting (Priority: P2)

**Goal**: Display aggregated health scores for all Silver layers in the dashboard

**Independent Test**: Generate anomalies in each layer and verify dashboard shows correct scores with drill-down

### Tests for User Story 4

- [ ] T057 [P] [US4] Unit test for Silver health calculation in tests/silver/unit/services/test_silver_validator.py
- [ ] T058 [P] [US4] Integration test for dashboard Silver section in tests/dashboard/test_silver_integration.py

### Implementation for User Story 4

- [ ] T059 [US4] Implement Silver tier health score calculation in src/services/silver_validator.py (minimum of layer scores)
- [ ] T060 [US4] Update data/state/health.json schema to include Silver tier section
- [ ] T061 [US4] Extend dashboard/app.py with Silver Tier health section (3 layer scores + overall)
- [ ] T062 [US4] Add Silver anomaly drill-down in dashboard (click layer to see anomalies)
- [ ] T063 [US4] Add Silver anomalies to incident timeline in dashboard
- [ ] T064 [US4] Update dashboard services/data_loader.py to load Silver tier results

**Checkpoint**: Dashboard shows Silver tier health with drill-down capability

---

## Phase 7: User Story 5 - Schema Registry Integration (Priority: P3)

**Goal**: Support loading schemas from a central registry with hot reload and caching

**Independent Test**: Update schema in registry and verify Silver tier uses new version without restart

### Tests for User Story 5

- [ ] T065 [P] [US5] Unit test for registry integration in tests/silver/unit/services/test_schema_registry.py
- [ ] T066 [P] [US5] Integration test for hot reload in tests/silver/integration/test_registry_integration.py

### Implementation for User Story 5

- [ ] T067 [US5] Add registry configuration options to src/services/schema_registry.py
- [ ] T068 [US5] Implement schema caching with TTL in src/services/schema_registry.py
- [ ] T069 [US5] Implement hot reload mechanism (detect registry changes, refresh schemas)
- [ ] T070 [US5] Implement fallback to cached schema when registry unavailable
- [ ] T071 [US5] Add registry health check and warning logging
- [ ] T072 [US5] Update config/default.yaml with registry configuration options

**Checkpoint**: Schema registry integration complete with hot reload and fallback

---

## Phase 8: Supporting Skills & Services

**Purpose**: Implement remaining Silver skills for root cause, incidents, escalation

- [ ] T073 [P] Implement silver.rootcause skill in src/skills/silver/rootcause.py (probable cause attribution)
- [ ] T074 [P] Implement silver.incident skill in src/skills/silver/incident.py (create/manage incidents)
- [ ] T075 [P] Implement silver.escalate skill in src/skills/silver/escalate.py (execute escalation paths)
- [ ] T076 [P] Implement silver.quarantine skill in src/skills/silver/quarantine.py (isolate datasets)
- [ ] T077 Write unit tests for supporting skills in tests/silver/unit/skills/

---

## Phase 9: Integration & Orchestration

**Purpose**: Wire Silver tier into existing Bronze orchestrator

- [ ] T078 Extend orchestrator to trigger Silver validation after Bronze passes in src/services/orchestrator.py
- [ ] T079 Add Silver tier to validation pipeline (Bronze -> Schema -> Business Logic -> [Freshness parallel])
- [ ] T080 Integration test for Bronze-Silver pipeline in tests/silver/integration/test_bronze_silver_pipeline.py
- [ ] T081 Update CLI to display Silver tier status in src/cli/main.py
- [ ] T082 Update audit logging to include Silver tier decisions in src/lib/logger.py

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements and validation

- [ ] T083 [P] Performance testing: validate <5s for 10K records schema validation
- [ ] T084 [P] Performance testing: validate 10K records/second business logic throughput
- [ ] T085 [P] Performance testing: validate <30s freshness detection
- [ ] T086 Edge case handling: NULL values in cross-field validation
- [ ] T087 Edge case handling: missing SLA thresholds (use defaults)
- [ ] T088 Edge case handling: multiple violations on same column
- [ ] T089 Run quickstart.md validation
- [ ] T090 Code review and cleanup

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - Schema Contract Enforcement
- **User Story 2 (Phase 4)**: Depends on Foundational - Business Logic Validation
- **User Story 3 (Phase 5)**: Depends on Foundational - Freshness & SLA Monitoring
- **User Story 4 (Phase 6)**: Depends on US1, US2, US3 - Dashboard Integration
- **User Story 5 (Phase 7)**: Depends on US1 - Schema Registry Integration
- **Supporting Skills (Phase 8)**: Can run in parallel with US1-US5
- **Integration (Phase 9)**: Depends on US1, US2, US3
- **Polish (Phase 10)**: Depends on all phases

### User Story Dependencies

```
        ┌──────────────┐
        │   Setup      │
        │  (Phase 1)   │
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │ Foundational │
        │  (Phase 2)   │
        └──────┬───────┘
               │
    ┌──────────┼──────────┐
    │          │          │
    ▼          ▼          ▼
┌───────┐  ┌───────┐  ┌───────┐
│  US1  │  │  US2  │  │  US3  │
│Schema │  │BizLog │  │Fresh  │
│ (P1)  │  │ (P1)  │  │ (P2)  │
└───┬───┘  └───┬───┘  └───┬───┘
    │          │          │
    │          ▼          │
    │      ┌───────┐      │
    └─────►│  US4  │◄─────┘
           │DashInt│
           │ (P2)  │
           └───────┘
    │
    │
    ▼
┌───────┐
│  US5  │
│Registy│
│ (P3)  │
└───────┘
```

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 4 (P2)**: Requires US1, US2, US3 to have data to display
- **User Story 5 (P3)**: Requires US1 (schema validation must exist first)

### Parallel Opportunities

**Within User Stories** (same story tasks that can run in parallel):
- All test tasks marked [P] within a story
- All model creation tasks marked [P] within a story
- Skills that operate on different files

**Across User Stories** (once Foundational is complete):
- US1, US2, US3 can all start in parallel
- Supporting skills (Phase 8) can run in parallel with any user story

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together:
Task: "Unit test for schema skill in tests/silver/unit/skills/test_schema.py"
Task: "Unit test for version skill in tests/silver/unit/skills/test_version.py"
Task: "Unit test for contract skill in tests/silver/unit/skills/test_contract.py"

# Launch all models for US1 together:
Task: "Create SchemaContract model in src/models/schema_contract.py"
Task: "Create ColumnDefinition model in src/models/schema_contract.py"
```

## Parallel Example: User Story 2

```bash
# Launch all tests for US2 together:
Task: "Unit test for crossfield skill in tests/silver/unit/skills/test_crossfield.py"
Task: "Unit test for refint skill in tests/silver/unit/skills/test_refint.py"
Task: "Unit test for bizrule skill in tests/silver/unit/skills/test_bizrule.py"
Task: "Unit test for distrib skill in tests/silver/unit/skills/test_distrib.py"

# Launch all models for US2 together:
Task: "Create BusinessRule model in src/models/business_rule.py"
Task: "Create ReferenceDataSet model in src/models/reference_data.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Schema Validation)
4. Complete Phase 4: User Story 2 (Business Logic)
5. **STOP and VALIDATE**: Test both P1 stories independently
6. Deploy/demo Silver tier core validation

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Schema validation working (MVP!)
3. Add User Story 2 → Business logic working (MVP complete!)
4. Add User Story 3 → Freshness monitoring working
5. Add User Story 4 → Dashboard integrated
6. Add User Story 5 → Registry integration (P3 - optional for MVP)

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Schema)
   - Developer B: User Story 2 (Business Logic)
   - Developer C: User Story 3 (Freshness)
3. Stories complete and integrate independently
4. Developer D: User Story 4 (Dashboard) - after A, B, C complete
5. Developer A: User Story 5 (Registry) - after US1 complete

---

## Summary

| Phase | Tasks | Parallel Tasks |
|-------|-------|----------------|
| 1. Setup | 7 | 6 |
| 2. Foundational | 6 | 4 |
| 3. US1 Schema (P1) | 13 | 7 |
| 4. US2 Business Logic (P1) | 15 | 9 |
| 5. US3 Freshness (P2) | 15 | 8 |
| 6. US4 Dashboard (P2) | 8 | 2 |
| 7. US5 Registry (P3) | 8 | 2 |
| 8. Supporting Skills | 5 | 4 |
| 9. Integration | 5 | 0 |
| 10. Polish | 8 | 3 |
| **Total** | **90** | **45** |

**MVP Scope**: Phases 1-4 (User Stories 1 + 2) = 41 tasks
**Full Scope**: All phases = 90 tasks

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US1 and US2 are both P1 priority - complete both for true MVP
