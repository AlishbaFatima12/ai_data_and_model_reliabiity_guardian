# Implementation Plan: Bronze Tier MVP with Orchestrator

**Branch**: `001-bronze-orchestrator-mvp` | **Date**: 2026-01-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-bronze-orchestrator-mvp/spec.md`

## Summary

Implement the foundational Bronze tier data validation layer with a basic event-driven orchestrator. The system validates incoming data batches against 7 quality rules (count, null, type, range, format, duplicate, encoding), calculates severity scores, generates alerts for WARNING/CRITICAL issues, and quarantines records with CRITICAL severity. The orchestrator coordinates validation workflows via event triggers and scheduled checks.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `pydantic` (data validation and models)
- `watchdog` (file system monitoring)
- `apscheduler` (scheduled tasks)
- `structlog` (structured logging)
- `pytest` (testing)

**Storage**: File-based (JSON/CSV for data, JSON for checkpoints and logs)
**Testing**: pytest with pytest-cov, pytest-asyncio
**Target Platform**: Windows/Linux (cross-platform Python CLI)
**Project Type**: Single project CLI application
**Performance Goals**:
- 5-second validation for 10K records (SC-001)
- 1-minute CRITICAL alerts, 5-minute WARNING alerts (SC-002)
- 95% detection accuracy (SC-003)

**Constraints**:
- <100ms per record for Bronze validation (Constitution 9.1)
- Maximum 100K records per batch (Assumption 5)
- 60-second recovery time (SC-006)

**Scale/Scope**:
- Single monitored directory
- Batches up to 100K records
- Console/log-based output (no GUI)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Constitution Reference | Status | Notes |
|------|------------------------|--------|-------|
| Always-On Behavior | Section 2.1 | PASS | Orchestrator with heartbeat every 60s (FR-014) |
| Hybrid Orchestration | Section 2.2 | PASS | Event-driven (data arrival) + scheduled (30s minimum) |
| No Manual Prompting | Section 2.3 | PASS | Deterministic validation, no LLM required |
| Safe Failure Handling | Section 2.4 | PASS | No silent failures; all errors logged and alerted |
| Concurrency Handling | Section 2.5 | PASS | Priority queue with FIFO tiebreaker (FR queuing) |
| State Recovery | Section 2.6 | PASS | Checkpoints for validation state (FR-018, FR-019) |
| Bronze Tier Skills | Section 10.2 | PASS | All 7 validation types implemented (FR-001 to FR-007) |
| Severity Scoring | Section 4.2 | PASS | Score formula implemented (FR-008) |
| No Black-Box Decisions | Section 4.4 | PASS | Deterministic rules, no LLM for decisions |
| Audit Requirements | Section 7 | PASS | Full decision logging (FR-020 to FR-022) |

**No constitution violations identified.**

## Project Structure

### Documentation (this feature)

```text
specs/001-bronze-orchestrator-mvp/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── data-batch.contract.md
│   ├── validation-result.contract.md
│   ├── anomaly.contract.md
│   └── orchestrator.contract.md
└── tasks.md             # Phase 2 output (/sp.tasks)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── __init__.py
│   ├── data_batch.py        # DataBatch entity
│   ├── validation_result.py # ValidationResult entity
│   ├── anomaly.py           # Anomaly entity
│   ├── health_score.py      # HealthScore entity
│   ├── checkpoint.py        # Checkpoint entity
│   └── alert.py             # Alert entity
├── services/
│   ├── __init__.py
│   ├── orchestrator.py      # Main orchestration engine
│   ├── validator.py         # Bronze validation coordinator
│   └── alerter.py           # Alert generation and dispatch
├── skills/
│   ├── __init__.py
│   ├── bronze/
│   │   ├── __init__.py
│   │   ├── count.py         # bronze.count skill
│   │   ├── null.py          # bronze.null skill
│   │   ├── type_check.py    # bronze.type skill
│   │   ├── range_check.py   # bronze.range skill
│   │   ├── format.py        # bronze.format skill
│   │   ├── duplicate.py     # bronze.duplicate skill
│   │   ├── encoding.py      # bronze.encoding skill
│   │   ├── quarantine.py    # bronze.quarantine skill
│   │   ├── alert.py         # bronze.alert skill
│   │   └── log.py           # bronze.log skill
│   └── util/
│       ├── __init__.py
│       ├── score.py         # util.score skill
│       ├── health.py        # util.health skill
│       └── checkpoint.py    # util.checkpoint skill
├── cli/
│   ├── __init__.py
│   └── main.py              # CLI entry point
└── lib/
    ├── __init__.py
    ├── config.py            # Configuration loader
    ├── constants.py         # Failure codes, severity levels
    └── logger.py            # Structured logging setup

tests/
├── conftest.py              # Pytest fixtures
├── contract/
│   ├── test_data_batch.py
│   ├── test_validation_result.py
│   └── test_anomaly.py
├── integration/
│   ├── test_orchestrator.py
│   ├── test_validator.py
│   └── test_end_to_end.py
└── unit/
    ├── skills/
    │   ├── bronze/
    │   │   ├── test_count.py
    │   │   ├── test_null.py
    │   │   ├── test_type_check.py
    │   │   ├── test_range_check.py
    │   │   ├── test_format.py
    │   │   ├── test_duplicate.py
    │   │   └── test_encoding.py
    │   └── util/
    │       ├── test_score.py
    │       └── test_health.py
    └── services/
        ├── test_validator.py
        └── test_alerter.py

config/
├── default.yaml             # Default configuration
├── validation_rules.yaml    # Validation rule definitions
└── sample_data/             # Test data files
    ├── valid_batch.csv
    ├── invalid_batch.csv
    └── schema.json
```

**Structure Decision**: Single project structure selected. The Bronze MVP is a standalone CLI application that monitors a directory and validates incoming data files. No frontend/backend separation needed for MVP (console output only).

## Complexity Tracking

> **No constitution violations identified - this section is intentionally empty.**

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI Entry                               │
│                         (cli/main.py)                            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                        ORCHESTRATOR                              │
│                   (services/orchestrator.py)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ File Watcher│  │  Scheduler  │  │  Heartbeat  │             │
│  │  (watchdog) │  │(apscheduler)│  │  (60s loop) │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          │                                       │
│                  ┌───────▼───────┐                              │
│                  │  Event Queue  │                              │
│                  │    (FIFO)     │                              │
│                  └───────┬───────┘                              │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                        VALIDATOR                                 │
│                   (services/validator.py)                        │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  count   │ │   null   │ │   type   │ │  range   │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │  format  │ │duplicate │ │ encoding │                        │
│  └──────────┘ └──────────┘ └──────────┘                        │
│                                                                  │
│              Bronze Skills (skills/bronze/)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
┌──────────▼────┐ ┌────────▼────┐ ┌────────▼────────┐
│   ALERTER     │ │ CHECKPOINT  │ │   QUARANTINE    │
│ (alerter.py)  │ │(util skill) │ │(bronze skill)   │
└───────────────┘ └─────────────┘ └─────────────────┘
```

### Data Flow

```
Data File Arrives
       │
       ▼
┌──────────────┐
│ File Watcher │ ──────► Event Queue
└──────────────┘
       │
       ▼
┌──────────────┐
│ Load Batch   │ ──────► DataBatch model
└──────────────┘
       │
       ▼
┌──────────────┐
│ Checkpoint   │ ──────► Save start state
│   (start)    │
└──────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│         BRONZE VALIDATION            │
│  count → null → type → range →      │
│  format → duplicate → encoding      │
└──────────────────────────────────────┘
       │
       ├──── Anomalies detected?
       │         │
       │    ┌────▼────┐
       │    │ Score   │ ──────► Severity (INFO/WARNING/CRITICAL)
       │    └────┬────┘
       │         │
       │    ┌────▼────┐
       │    │ Alert   │ ──────► Console/Log (WARNING/CRITICAL only)
       │    └────┬────┘
       │         │
       │    ┌────▼────┐
       │    │Quarantine│ ──────► Isolate records (CRITICAL only)
       │    └─────────┘
       │
       ▼
┌──────────────┐
│ Health Score │ ──────► Calculate aggregate score
└──────────────┘
       │
       ▼
┌──────────────┐
│ Checkpoint   │ ──────► Save completion state
│  (complete)  │
└──────────────┘
       │
       ▼
┌──────────────┐
│ Log Result   │ ──────► Audit trail
└──────────────┘
```

---

## Key Design Decisions

### D1: Skill-Based Architecture
Each validation type is implemented as an independent skill (per Constitution Section 10.2). This provides:
- Single responsibility per skill
- Easy testing in isolation
- Composable validation workflows
- Future extensibility for Silver/Gold tiers

### D2: File-Based Storage for MVP
For MVP simplicity, all persistence uses file-based JSON storage:
- Checkpoints: `data/checkpoints/*.json`
- Audit logs: `logs/audit/*.jsonl`
- Quarantine: `data/quarantine/*.json`
- Health state: `data/state/health.json`

### D3: Synchronous Validation with Async Events
The orchestrator uses async event handling (file watcher, scheduler) but validation is synchronous within each batch. This simplifies error handling while maintaining responsive event processing.

### D4: Configuration-Driven Rules
All validation rules are externalized to YAML configuration, supporting:
- Field-level null tolerance
- Type declarations per field
- Range boundaries
- Format patterns (regex)
- Expected record counts

---

## Next Steps

1. **Phase 0**: Generate `research.md` - technology research and validation
2. **Phase 1**: Generate `data-model.md` - entity definitions and relationships
3. **Phase 1**: Generate `contracts/` - API contracts for each entity
4. **Phase 1**: Generate `quickstart.md` - developer setup guide
5. **Phase 2**: Run `/sp.tasks` to generate `tasks.md` with implementation tasks
