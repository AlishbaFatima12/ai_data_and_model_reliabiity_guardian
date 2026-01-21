# Feature Specification: Silver Tier - Schema, Business Logic & Freshness Enforcement

**Feature Branch**: `003-silver-tier-enforcement`
**Created**: 2026-01-18
**Status**: Draft
**Input**: User description: "Silver Tier - Schema Contract Enforcement, Business Logic Validation, and Freshness SLA Monitoring"

## Overview

The Silver Tier builds upon the Bronze Tier's data validation by adding three additional intelligence layers that ensure data not only passes basic quality checks but also conforms to declared schemas, adheres to business rules, and arrives within acceptable time windows. This tier operates after Bronze validation, processing only data that has already passed fundamental quality checks.

## Clarifications

### Session 2026-01-18

- Q: How is schema violation severity determined? → A: Severity based on column criticality flags in schema contract (required columns = CRITICAL, optional columns = WARNING)
- Q: Where does referential integrity data come from? → A: Reference data loaded from configured lookup files (CSV/JSON) at startup with periodic refresh

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Schema Contract Enforcement Catches Breaking Changes (Priority: P1)

A data engineer receives data from an upstream system that has silently changed its schema. The Silver Tier detects that required columns are missing, new unexpected columns have appeared, or column data types have changed from the registered contract. The system blocks the data from proceeding to downstream consumers and alerts the engineer with specific details about which contract violations occurred.

**Why this priority**: Schema violations can cause immediate pipeline failures and data corruption. Catching these before data enters business logic processing prevents cascading failures across the entire data platform.

**Independent Test**: Can be fully tested by sending data with intentional schema mismatches (missing columns, type changes, extra columns) and verifying the system detects and reports each violation type accurately.

**Acceptance Scenarios**:

1. **Given** a registered schema contract requiring columns [id, name, email, created_at], **When** data arrives missing the 'email' column, **Then** the system raises SC-001 (Missing Column) anomaly with severity based on column criticality and blocks processing.

2. **Given** a registered schema where 'amount' is declared as decimal(10,2), **When** data arrives with 'amount' as string type, **Then** the system raises SC-003 (Column Type Change) anomaly and prevents data from proceeding.

3. **Given** a registered schema version 2.1, **When** data arrives tagged as version 3.0 with breaking changes, **Then** the system raises SC-006 (Version Mismatch) and SC-007 (Breaking Change) anomalies.

4. **Given** data that fully conforms to the registered schema, **When** processed through schema validation, **Then** the data passes to the next layer without blocking.

---

### User Story 2 - Business Logic Validation Detects Domain Rule Violations (Priority: P1)

A data analyst discovers that order records are being processed where the discount amount exceeds the order total, or where end dates precede start dates. The Silver Tier's Business Logic layer catches these cross-field inconsistencies and domain rule violations before they corrupt business reports and analytics.

**Why this priority**: Business logic violations create silent data corruption that leads to incorrect analytics, financial miscalculations, and regulatory compliance issues. These are harder to detect after the fact than schema issues.

**Independent Test**: Can be fully tested by sending data with intentional business rule violations (impossible state transitions, invalid cross-field relationships, calculation mismatches) and verifying detection.

**Acceptance Scenarios**:

1. **Given** a business rule that end_date must be after start_date, **When** a record arrives with end_date='2026-01-01' and start_date='2026-01-15', **Then** the system raises BL-001 (Cross-Field Inconsistency) anomaly.

2. **Given** an order record where line items sum to $100.00, **When** the order_total field shows $95.00, **Then** the system raises BL-003 (Calculation Error) anomaly.

3. **Given** an order status lifecycle of [PENDING -> CONFIRMED -> SHIPPED -> DELIVERED], **When** an order attempts to transition from PENDING to DELIVERED, **Then** the system raises BL-004 (Invalid State Transition) anomaly.

4. **Given** a customer record referencing account_id='ACC-999', **When** no account with that ID exists in the reference data, **Then** the system raises BL-002 (Referential Break) anomaly.

5. **Given** historical data showing average daily orders between 900-1100, **When** today's batch contains only 150 orders, **Then** the system raises BL-007 (Distribution Shift) anomaly as a warning.

---

### User Story 3 - Freshness & SLA Monitoring Prevents Stale Data Usage (Priority: P2)

A business stakeholder relies on hourly sales reports but the source data pipeline has silently failed. The Silver Tier's Freshness Watcher detects that expected data has not arrived within the SLA window, alerts stakeholders before they make decisions on stale data, and tracks the exact delay duration.

**Why this priority**: Stale data leads to poor business decisions but doesn't cause immediate system failures. It's critical for operational accuracy but can be addressed after schema and business logic are enforced.

**Independent Test**: Can be fully tested by configuring expected arrival times for data sources and verifying alerts fire when data is late or missing.

**Acceptance Scenarios**:

1. **Given** a data source with SLA of "new data every hour", **When** 65 minutes pass since last data arrival, **Then** the system raises FR-001 (Stale Data) warning at 60 minutes and escalates to critical at 90 minutes.

2. **Given** a nightly batch job expected to complete by 6:00 AM, **When** the job has not completed by 6:15 AM, **Then** the system raises FR-003 (SLA Breach) anomaly with the exact delay duration.

3. **Given** a pipeline with 5 sequential stages, **When** stage 3 completes but stage 4 has not started within 10 minutes, **Then** the system raises FR-006 (Pipeline Stall) warning.

4. **Given** end-to-end latency threshold of 30 minutes from source to destination, **When** data takes 45 minutes to traverse the pipeline, **Then** the system raises FR-004 (Latency Breach) anomaly.

---

### User Story 4 - Unified Silver Tier Health Reporting (Priority: P2)

An operations manager views the unified dashboard and sees aggregated health scores for all three Silver Tier layers. They can quickly identify which layer (Schema, Business Logic, or Freshness) is causing the most issues and drill down into specific anomalies.

**Why this priority**: Unified visibility enables efficient triage and resource allocation but requires all three layers to be operational first.

**Independent Test**: Can be tested by generating anomalies in each layer and verifying the dashboard aggregates and displays them correctly with drill-down capability.

**Acceptance Scenarios**:

1. **Given** 2 schema anomalies, 5 business logic anomalies, and 1 freshness anomaly, **When** viewing the Silver Tier dashboard section, **Then** the user sees individual layer scores and an overall Silver Tier health score.

2. **Given** a Silver Tier health score of 65%, **When** the user clicks on "Business Logic" layer, **Then** they see the 5 specific business logic anomalies with details.

3. **Given** anomalies detected across all layers, **When** the system calculates overall health, **Then** it uses the minimum layer score as the overall Silver Tier score.

---

### User Story 5 - Schema Registry Integration (Priority: P3)

A data platform team maintains a central schema registry where all data contracts are versioned and stored. The Silver Tier reads schema definitions from this registry rather than requiring manual configuration for each data source.

**Why this priority**: Registry integration improves maintainability but the core enforcement logic can function with locally-defined schemas initially.

**Independent Test**: Can be tested by updating a schema in the registry and verifying the Silver Tier picks up the new definition without restart.

**Acceptance Scenarios**:

1. **Given** a schema registered in the central registry, **When** the Silver Tier needs to validate incoming data, **Then** it fetches the current schema version from the registry.

2. **Given** a schema updated in the registry from v2.0 to v2.1, **When** new data arrives, **Then** the Silver Tier uses v2.1 for validation without requiring restart.

3. **Given** the schema registry is temporarily unavailable, **When** data arrives for validation, **Then** the system uses the last cached schema version and logs a warning about registry unavailability.

---

### Edge Cases

- What happens when a column is both missing AND has a type change in the contract? (Report both violations)
- How does the system handle NULL values in cross-field validation rules? (Configurable: skip validation or treat as violation)
- What if SLA thresholds are not configured for a data source? (Use system defaults, log warning)
- How does the system handle retroactive schema changes? (Validate against the schema version active at data arrival time)
- What if business rules reference external data that is itself stale? (Chain staleness detection, escalate appropriately)
- How are partial batch arrivals handled for freshness monitoring? (Track completion percentage, alert on incomplete batches)

## Requirements *(mandatory)*

### Functional Requirements

**Schema & Contract Enforcement (Layer 2)**

- **FR-001**: System MUST validate incoming data against registered schema definitions before allowing processing
- **FR-002**: System MUST detect missing required columns and raise SC-001 anomaly (CRITICAL severity for required columns, WARNING for optional columns)
- **FR-003**: System MUST detect unexpected/extra columns and raise SC-002 anomaly
- **FR-004**: System MUST detect column data type mismatches and raise SC-003 anomaly
- **FR-005**: System MUST detect numeric precision/scale violations and raise SC-004 anomaly
- **FR-006**: System MUST detect primary key, foreign key, and uniqueness constraint violations and raise SC-005 anomaly
- **FR-007**: System MUST compare schema versions and raise SC-006 for incompatible versions
- **FR-008**: System MUST identify breaking vs non-breaking schema changes and raise SC-007 for breaking changes
- **FR-009**: System MUST compute and compare contract checksums/signatures and raise SC-008 on mismatch

**Business Logic Validation (Layer 3)**

- **FR-010**: System MUST validate cross-field consistency rules (e.g., end_date > start_date)
- **FR-011**: System MUST validate referential integrity against reference data loaded from configured lookup files (CSV/JSON) at startup with periodic refresh
- **FR-012**: System MUST verify calculation correctness for derived/aggregated fields
- **FR-013**: System MUST enforce valid state transitions for entities with lifecycle states
- **FR-014**: System MUST detect temporal anomalies (future dates where inappropriate, invalid date sequences)
- **FR-015**: System MUST enforce explicit domain value constraints (e.g., discount <= price)
- **FR-016**: System MUST detect statistical distribution shifts compared to historical baselines
- **FR-017**: System MUST detect orphan records with no valid parent/owner

**Freshness & SLA Monitoring (Layer 4)**

- **FR-018**: System MUST track last data arrival timestamp for each monitored source
- **FR-019**: System MUST calculate and monitor time since last successful update
- **FR-020**: System MUST track pipeline execution duration for each stage
- **FR-021**: System MUST calculate end-to-end latency from source to destination
- **FR-022**: System MUST issue warnings before SLA thresholds are breached (configurable warning window)
- **FR-023**: System MUST monitor scheduled job completion status
- **FR-024**: System MUST track dependency chain completion times

**Integration & Reporting**

- **FR-025**: System MUST integrate with the existing Bronze Tier, processing only Bronze-validated data
- **FR-026**: System MUST report Silver Tier anomalies to the unified dashboard
- **FR-027**: System MUST calculate per-layer health scores (Schema, Business Logic, Freshness)
- **FR-028**: System MUST support configurable business rules via declarative rule definitions
- **FR-029**: System MUST support configurable SLA thresholds per data source
- **FR-030**: System MUST log all validation decisions with full audit trail

### Key Entities

- **SchemaContract**: Represents a versioned schema definition for a data source, including column definitions, data types, constraints, compatibility markers, and column criticality flags (required/optional) that determine violation severity
- **BusinessRule**: Represents a configurable validation rule that checks cross-field relationships, calculations, or domain constraints
- **ReferenceDataSet**: Represents lookup data (CSV/JSON files) loaded at startup for referential integrity checks, with configurable refresh interval
- **SLADefinition**: Represents expected arrival times, latency thresholds, and freshness requirements for a data source
- **SchemaAnomaly**: Records schema/contract violations (SC-001 through SC-008) with specific details about the violation
- **BusinessLogicAnomaly**: Records business rule violations (BL-001 through BL-008) with affected records and rule details
- **FreshnessAnomaly**: Records timeliness violations (FR-001 through FR-008) with timing details and breach duration
- **SilverTierHealthScore**: Aggregates health metrics across all three Silver Tier layers

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Schema violations are detected and reported within 5 seconds of data arrival
- **SC-002**: Business logic rules process at least 10,000 records per second without backlog
- **SC-003**: Freshness monitoring detects stale data within 30 seconds of SLA threshold breach
- **SC-004**: 100% of configured business rules are evaluated for every qualifying record
- **SC-005**: False positive rate for distribution shift detection is below 5%
- **SC-006**: System correctly identifies and classifies at least 95% of schema changes as breaking vs non-breaking
- **SC-007**: All Silver Tier anomalies appear in the unified dashboard within 10 seconds of detection
- **SC-008**: Silver Tier can validate 50,000 records per minute sustained throughput
- **SC-009**: Schema registry synchronization occurs within 60 seconds of registry updates
- **SC-010**: End-to-end latency from Bronze validation completion to Silver validation completion is under 2 seconds per batch

## Assumptions

- Bronze Tier validation is operational and all data entering Silver Tier has already passed Bronze validation
- Schema definitions will be provided either via local configuration files or a schema registry
- Business rules can be expressed declaratively (no arbitrary code execution required)
- Historical baseline data is available for distribution shift detection (at least 7 days of history)
- SLA definitions are provided by data source owners or default system values are acceptable
- The unified dashboard (Feature 002) is available for Silver Tier anomaly display
- Data sources have consistent identifiers that persist across schema versions

## Out of Scope

- Gold Tier (Model & Fairness monitoring) - separate feature
- Automatic schema migration or data transformation
- Business rule authoring UI (rules configured via YAML/JSON files)
- Real-time streaming validation (batch-oriented processing only for MVP)
- Multi-tenant isolation (single-tenant deployment assumed)
- External alerting integrations (Slack, PagerDuty) - uses existing dashboard/console
