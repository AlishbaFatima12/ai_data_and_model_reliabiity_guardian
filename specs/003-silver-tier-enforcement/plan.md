# Implementation Plan: Silver Tier - Schema, Business Logic & Freshness Enforcement

**Branch**: `003-silver-tier-enforcement` | **Date**: 2026-01-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-silver-tier-enforcement/spec.md`

## Summary

Implement the Silver Tier data quality layer consisting of three intelligence sub-layers: (1) Schema & Contract Enforcement (Layer 2) validates data against registered schemas, detects structural changes, and enforces versioning; (2) Business Logic Unit (Layer 3) validates cross-field relationships, referential integrity, calculations, and state transitions; (3) Freshness & SLA Watcher (Layer 4) monitors data arrival times, tracks staleness, and enforces delivery commitments. The Silver Tier processes only Bronze-validated data and reports anomalies to the unified dashboard.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `pydantic` 2.x (data validation and models - reuse from Bronze)
- `structlog` (structured logging - reuse from Bronze)
- `pytest` 8.x (testing - reuse from Bronze)
- `jsonschema` (schema validation)
- `deepdiff` (schema comparison)
- `croniter` (SLA schedule parsing)

**Storage**: File-based (JSON/JSONL) - reuse existing Bronze tier output paths
- Schema contracts: `config/schemas/*.json`
- Business rules: `config/rules/*.yaml`
- SLA definitions: `config/sla/*.yaml`
- Reference data: `data/reference/*.csv` or `*.json`
- Freshness state: `data/state/freshness.json`

**Testing**: pytest with pytest-cov (reuse Bronze fixtures where applicable)
**Target Platform**: Windows/Linux (cross-platform Python CLI)
**Project Type**: Single project extending existing codebase
**Performance Goals**:
- Schema validation: <5 seconds for 10K records (SC-001)
- Business logic: 10,000 records/second throughput (SC-002)
- Freshness detection: <30 seconds of SLA breach (SC-003)
- End-to-end latency: <2 seconds per batch Bronze→Silver (SC-010)

**Constraints**:
- <1 second per batch for Silver validation (Constitution 9.1)
- Maximum 100 concurrent validation streams (Constitution 9.1)
- 60-second recovery time (SC-009)

**Scale/Scope**:
- Single monitored data source initially
- Up to 50 schema contracts registered
- Up to 100 business rules per data source
- Reference data files up to 10MB each

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Constitution Section 3.2-3.4 Compliance (Silver Tier Layers)

| Layer | Constitution Section | Spec Coverage | Status |
|-------|---------------------|---------------|--------|
| Layer 2: Schema & Contract | Section 3.2 | FR-001 to FR-009 | PASS |
| Layer 3: Business Logic | Section 3.3 | FR-010 to FR-017 | PASS |
| Layer 4: Freshness & SLA | Section 3.4 | FR-018 to FR-024 | PASS |

### Constitution Failure Codes Coverage

| Constitution Codes | Spec Failure Codes | Status |
|-------------------|-------------------|--------|
| SC-001 to SC-008 (Schema) | SC-001 to SC-008 | PASS (all 8 codes) |
| BL-001 to BL-008 (Business) | BL-001 to BL-008 | PASS (all 8 codes) |
| FS-001 to FS-008 (Freshness) | FR-001 to FR-008 (spec naming) | PASS (all 8 codes) |

### Silver Tier Skills Required (Constitution 10.3)

| Skill ID | Capability | Spec FR | Status |
|----------|------------|---------|--------|
| silver.schema | Compare data to schema | FR-001 to FR-005 | Required |
| silver.contract | Verify API/data contracts | FR-008, FR-009 | Required |
| silver.version | Check schema version | FR-007 | Required |
| silver.crossfield | Validate field relationships | FR-010 | Required |
| silver.refint | Check referential integrity | FR-011 | Required |
| silver.bizrule | Evaluate business rules | FR-012 to FR-015 | Required |
| silver.distrib | Compare distribution | FR-016 | Required |
| silver.freshness | Check data staleness | FR-018, FR-019 | Required |
| silver.sla | Track SLA compliance | FR-020 to FR-023 | Required |
| silver.pipeline | Monitor pipeline duration | FR-020 | Required |
| silver.dependency | Track dependency chain | FR-024 | Required |
| silver.rootcause | Attribute probable cause | Inherited | Required |
| silver.incident | Create/manage incidents | FR-026 | Required |
| silver.escalate | Execute escalation path | Inherited | Required |
| silver.quarantine | Isolate entire datasets | Inherited | Required |

### Additional Constitution Checks

| Gate | Constitution Reference | Status | Notes |
|------|------------------------|--------|-------|
| Silver requires Bronze | Section 8.4 | PASS | FR-025 ensures Bronze-validated data only |
| No Black-Box Decisions | Section 4.4 | PASS | Deterministic rules, no LLM |
| Severity Scoring | Section 4.2 | PASS | Reuse util.score from Bronze |
| Audit Requirements | Section 7 | PASS | FR-030 audit trail |
| Concurrency Handling | Section 2.5 | PASS | Inherits Bronze queue |
| Safe Failure Handling | Section 2.4 | PASS | No silent failures |

**Gate Result**: PASSED - Ready for implementation

## Project Structure

### Documentation (this feature)

```text
specs/003-silver-tier-enforcement/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── schema-contract.yaml
│   ├── business-rule.yaml
│   ├── sla-definition.yaml
│   └── silver-anomaly.yaml
└── tasks.md             # Phase 2 output (/sp.tasks command)
```

### Source Code (repository root)

```text
# Existing structure (Bronze Tier - reuse)
src/
├── models/              # Extend with Silver entities
│   ├── __init__.py
│   ├── schema_contract.py     # NEW: SchemaContract entity
│   ├── business_rule.py       # NEW: BusinessRule entity
│   ├── reference_data.py      # NEW: ReferenceDataSet entity
│   ├── sla_definition.py      # NEW: SLADefinition entity
│   ├── silver_anomaly.py      # NEW: SchemaAnomaly, BizLogicAnomaly, FreshnessAnomaly
│   └── [existing models]
├── services/
│   ├── __init__.py
│   ├── silver_validator.py    # NEW: Silver validation coordinator
│   ├── freshness_watcher.py   # NEW: Freshness monitoring service
│   ├── schema_registry.py     # NEW: Schema contract management
│   ├── rule_engine.py         # NEW: Business rule evaluation engine
│   └── [existing services]
├── skills/
│   ├── __init__.py
│   ├── bronze/          # Existing Bronze skills
│   ├── silver/          # NEW: Silver tier skills
│   │   ├── __init__.py
│   │   ├── schema.py          # silver.schema skill
│   │   ├── contract.py        # silver.contract skill
│   │   ├── version.py         # silver.version skill
│   │   ├── crossfield.py      # silver.crossfield skill
│   │   ├── refint.py          # silver.refint skill
│   │   ├── bizrule.py         # silver.bizrule skill
│   │   ├── distrib.py         # silver.distrib skill
│   │   ├── freshness.py       # silver.freshness skill
│   │   ├── sla.py             # silver.sla skill
│   │   ├── pipeline.py        # silver.pipeline skill
│   │   ├── dependency.py      # silver.dependency skill
│   │   ├── rootcause.py       # silver.rootcause skill
│   │   ├── incident.py        # silver.incident skill
│   │   ├── escalate.py        # silver.escalate skill
│   │   └── quarantine.py      # silver.quarantine skill
│   └── util/            # Existing utility skills (reuse)
├── cli/
│   ├── __init__.py
│   └── main.py          # Extend CLI for Silver commands
└── lib/
    ├── __init__.py
    ├── constants.py     # Extend with Silver failure codes
    ├── config.py        # Extend for Silver configuration
    └── logger.py        # Reuse

# New test code
tests/
├── [existing tests]
├── silver/              # NEW: Silver tier tests
│   ├── __init__.py
│   ├── conftest.py            # Silver test fixtures
│   ├── unit/
│   │   ├── skills/
│   │   │   ├── test_schema.py
│   │   │   ├── test_contract.py
│   │   │   ├── test_version.py
│   │   │   ├── test_crossfield.py
│   │   │   ├── test_refint.py
│   │   │   ├── test_bizrule.py
│   │   │   ├── test_distrib.py
│   │   │   ├── test_freshness.py
│   │   │   ├── test_sla.py
│   │   │   └── test_pipeline.py
│   │   └── services/
│   │       ├── test_silver_validator.py
│   │       ├── test_freshness_watcher.py
│   │       ├── test_schema_registry.py
│   │       └── test_rule_engine.py
│   └── integration/
│       ├── test_bronze_silver_pipeline.py
│       ├── test_schema_validation_e2e.py
│       ├── test_business_logic_e2e.py
│       └── test_freshness_monitoring_e2e.py

# Configuration
config/
├── schemas/             # NEW: Schema contracts
│   └── sample_schema.json
├── rules/               # NEW: Business rules
│   └── sample_rules.yaml
├── sla/                 # NEW: SLA definitions
│   └── sample_sla.yaml
└── [existing config files]

# Reference data
data/
├── reference/           # NEW: Reference data for referential integrity
│   └── sample_lookup.csv
├── state/
│   └── freshness.json   # NEW: Freshness tracking state
└── [existing data paths]
```

**Structure Decision**: Extension of existing single-project layout. Silver tier skills are added alongside Bronze skills in `src/skills/silver/`. Services are extended with new Silver-specific components. This maintains consistency with the established architecture.

## Complexity Tracking

> No constitution violations to justify - design passes all gates.

| Aspect | Complexity Level | Justification |
|--------|------------------|---------------|
| Skill count | Medium (15 skills) | Matches Constitution 10.3 requirements |
| Service count | Low (4 new services) | One per major concern |
| New dependencies | Minimal (3: jsonschema, deepdiff, croniter) | Standard Python packages |
| Model reuse | High | 60% from existing Bronze tier |

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ORCHESTRATOR                                │
│                   (services/orchestrator.py)                         │
│                                                                      │
│  Bronze Validation Complete                                          │
│         │                                                            │
│         ▼                                                            │
│  ┌──────────────┐                                                   │
│  │ Event: Bronze│ ──────► Silver Pipeline Trigger                    │
│  │   Passed     │                                                    │
│  └──────────────┘                                                   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│                      SILVER VALIDATOR                                │
│                 (services/silver_validator.py)                       │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              LAYER 2: SCHEMA & CONTRACT                      │    │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐    │    │
│  │  │ schema │ │contract│ │version │ │ struct │ │checksum│    │    │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                          │ PASS                                      │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              LAYER 3: BUSINESS LOGIC                         │    │
│  │  ┌──────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │    │
│  │  │crossfield│ │ refint │ │bizrule │ │ state  │ │distrib │  │    │
│  │  └──────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                          │ PASS                                      │
│                          ▼                                           │
│               Continue to Gold Tier (future)                         │
└─────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────────┐
         │          LAYER 4: FRESHNESS & SLA WATCHER           │
         │          (services/freshness_watcher.py)            │
         │    ┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ │
         │    │freshness │ │  sla   │ │pipeline│ │dependency│ │
         │    └──────────┘ └────────┘ └────────┘ └──────────┘ │
         │                                                      │
         │  [Runs PARALLEL to main pipeline per Constitution]  │
         └─────────────────────────────────────────────────────┘
                                 │
                                 ▼
                  ┌─────────────────────────────┐
                  │     UNIFIED DASHBOARD       │
                  │    (Silver Tier Section)    │
                  └─────────────────────────────┘
```

### Data Flow

```
Bronze Validated Batch
       │
       ▼
┌──────────────┐
│ Load Schema  │ ──────► SchemaContract from registry
│  Contract    │
└──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│         LAYER 2: SCHEMA              │
│  schema → contract → version →       │
│  constraint → checksum              │
└──────────────────────────────────────┘
       │
       ├──── Schema Anomalies? (SC-001 to SC-008)
       │         │
       │    ┌────▼────┐
       │    │ Severity│ ──────► Based on column criticality
       │    │ (flag)  │         (required=CRITICAL, optional=WARNING)
       │    └────┬────┘
       │         │
       │    ┌────▼────┐
       │    │ Report  │ ──────► Dashboard + Block if CRITICAL
       │    └─────────┘
       │
       ▼
┌──────────────┐
│ Load Rules   │ ──────► BusinessRule definitions
│ + Reference  │ ──────► ReferenceDataSet (CSV/JSON)
└──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│       LAYER 3: BUSINESS LOGIC        │
│  crossfield → refint → calculation → │
│  state → temporal → domain → distrib │
└──────────────────────────────────────┘
       │
       ├──── Business Logic Anomalies? (BL-001 to BL-008)
       │         │
       │    ┌────▼────┐
       │    │ Score   │ ──────► Severity via util.score
       │    └────┬────┘
       │         │
       │    ┌────▼────┐
       │    │ Report  │ ──────► Dashboard
       │    └─────────┘
       │
       ▼
┌──────────────┐
│ Calculate    │ ──────► Silver Tier Health Score
│ Layer Health │         (minimum of all layer scores)
└──────────────┘
       │
       ▼
┌──────────────┐
│ Audit Log    │ ──────► Decision trail
└──────────────┘

=== PARALLEL FLOW ===

┌──────────────┐
│ SLA Check    │ ◄───── Timer (30s per Constitution 2.2)
│  (scheduled) │
└──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│       LAYER 4: FRESHNESS             │
│  last_arrival → age_check →          │
│  sla_status → latency → pipeline     │
└──────────────────────────────────────┘
       │
       ├──── Freshness Anomalies? (FR-001 to FR-008)
       │         │
       │    ┌────▼────┐
       │    │ Warning │ ──────► Pre-breach warning
       │    │ at 60m  │
       │    └────┬────┘
       │         │
       │    ┌────▼────┐
       │    │Critical │ ──────► Breach at 90m (escalate)
       │    │ at 90m  │
       │    └─────────┘
```

## Key Design Decisions

### D1: Layer 4 Parallel Execution
Per Constitution Section 2.2, the Freshness & SLA Watcher runs in parallel to the main Bronze→Silver pipeline. It operates on a 30-second timer independent of data arrival events.

### D2: Column Criticality for Severity
Schema violation severity is determined by column criticality flags in the schema contract:
- Required columns → CRITICAL severity
- Optional columns → WARNING severity
This aligns with the clarification session answer.

### D3: Reference Data Loading Strategy
Reference data for referential integrity is loaded from CSV/JSON files at startup with periodic refresh (configurable interval, default 1 hour). This avoids database dependencies while maintaining lookup performance.

### D4: Schema Registry (File-Based MVP)
For MVP, schema contracts are stored as JSON files in `config/schemas/`. A future iteration can integrate with external schema registries (User Story 5, P3).

### D5: Business Rules as Declarative YAML
Business rules are defined in YAML format with a simple DSL supporting:
- Field comparisons (e.g., `end_date > start_date`)
- Calculations (e.g., `sum(line_items.amount) == order_total`)
- State transitions (e.g., `[PENDING, CONFIRMED, SHIPPED, DELIVERED]`)
- Domain constraints (e.g., `discount <= price`)

### D6: Health Score Aggregation
Per Constitution Section 6.3, the overall Silver Tier health score is the minimum of all three layer scores. This ensures the weakest component determines overall health.

## Implementation Phases (for /sp.tasks)

### Phase 1: Foundation
- Add new dependencies to pyproject.toml
- Extend constants.py with Silver failure codes (SC-*, BL-*, FR-*)
- Create Silver tier models (SchemaContract, BusinessRule, etc.)
- Create skills/silver/ directory structure
- Setup Silver test infrastructure

### Phase 2: Schema & Contract Enforcement (Layer 2)
- Implement SchemaRegistry service
- Implement silver.schema skill
- Implement silver.contract skill
- Implement silver.version skill
- Implement constraint validation (PK, FK, unique)
- Implement checksum comparison

### Phase 3: Business Logic Validation (Layer 3)
- Implement RuleEngine service
- Implement silver.crossfield skill
- Implement silver.refint skill with reference data loading
- Implement silver.bizrule skill
- Implement silver.distrib skill with historical baselines
- Implement state transition validation

### Phase 4: Freshness & SLA Monitoring (Layer 4)
- Implement FreshnessWatcher service
- Implement silver.freshness skill
- Implement silver.sla skill
- Implement silver.pipeline skill
- Implement silver.dependency skill
- Integrate with orchestrator scheduler

### Phase 5: Integration & Dashboard
- Extend SilverValidator to coordinate all three layers
- Integrate with existing orchestrator
- Extend dashboard with Silver tier health section
- Add Silver anomalies to incident timeline
- Calculate and display per-layer health scores

### Phase 6: Testing & Polish
- Write unit tests for all Silver skills
- Write integration tests for Bronze→Silver pipeline
- Write E2E tests for each user story
- Performance testing against SC targets
- Edge case handling

## Artifacts Generated

| Artifact | Path | Status |
|----------|------|--------|
| Research | specs/003-silver-tier-enforcement/research.md | Complete |
| Data Model | specs/003-silver-tier-enforcement/data-model.md | Complete |
| Contracts | specs/003-silver-tier-enforcement/contracts/*.yaml | Complete |
| Quickstart | specs/003-silver-tier-enforcement/quickstart.md | Complete |

## Next Steps

1. ~~Generate `research.md` - technology research~~ COMPLETE
2. ~~Generate `data-model.md` - entity definitions~~ COMPLETE
3. ~~Generate `contracts/` - API contracts~~ COMPLETE
4. ~~Generate `quickstart.md` - developer setup guide~~ COMPLETE
5. **Run `/sp.tasks` to generate `tasks.md` with implementation tasks**
