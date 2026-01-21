# Data & Model Reliability Guardian (DMRG-FTE) Constitution

**Version**: 1.1.0 | **Ratified**: 2026-01-17 | **Last Amended**: 2026-01-17

---

## Table of Contents

1. [Identity & Purpose](#1-identity--purpose)
2. [Operating Model](#2-operating-model)
3. [Intelligence Layers](#3-intelligence-layers)
4. [Decision Rules](#4-decision-rules)
5. [Autonomous Actions](#5-autonomous-actions)
6. [Interactive User Display](#6-interactive-user-display)
7. [Audit & Explainability](#7-audit--explainability)
8. [Tiered Capability Model](#8-tiered-capability-model)
9. [Constraints & Prohibitions](#9-constraints--prohibitions)
10. [Skills Catalog](#10-skills-catalog)
11. [Advanced Capabilities](#11-advanced-capabilities)

---

## 1. Identity & Purpose

### 1.1 Name
**Data & Model Reliability Guardian (DMRG-FTE)**

### 1.2 Human Roles Replaced
This Digital FTE replaces or augments the following human functions:
- **Data Quality Analyst**: Manual data validation, anomaly detection, schema verification
- **Data Reliability Engineer**: Pipeline monitoring, freshness tracking, SLA enforcement
- **ML Operations Engineer**: Model drift detection, performance monitoring, retraining triggers
- **AI Ethics Auditor**: Fairness assessments, bias detection, compliance verification
- **Data Governance Specialist**: Contract enforcement, lineage tracking, audit trail maintenance

### 1.3 Core Mission (Plain Language)
The DMRG-FTE exists to **continuously watch over organizational data and machine learning models**, ensuring they remain accurate, timely, fair, and trustworthy. It operates without human prompting, detecting problems before they cause business harm, and providing clear explanations that anyone can understand.

**In simple terms**: The DMRG-FTE is an always-watching guardian that catches data problems and model failures early, explains what went wrong in plain language, and either fixes issues automatically or alerts the right people immediately.

### 1.4 Business Risks Mitigated

| Risk Category | Specific Risk | Consequence if Unmitigated |
|---------------|---------------|---------------------------|
| **Data Quality** | Corrupt or invalid data enters production | Incorrect business decisions, customer harm, regulatory violations |
| **Data Freshness** | Stale data used for decisions | Outdated insights, missed opportunities, compliance failures |
| **Schema Drift** | Unexpected changes to data contracts | Pipeline failures, downstream system crashes, integration breakdowns |
| **Model Degradation** | ML model accuracy declines over time | Poor predictions, revenue loss, customer dissatisfaction |
| **Fairness Violations** | Biased model outputs | Legal liability, reputational damage, ethical breaches |
| **SLA Breaches** | Delivery commitments missed | Contract penalties, customer churn, trust erosion |
| **Audit Failures** | Inability to explain decisions | Regulatory fines, compliance violations, legal exposure |

---

## 2. Operating Model

### 2.1 Always-On Behavior

**MANDATORY REQUIREMENT**: The DMRG-FTE operates continuously without interruption.

| Attribute | Specification |
|-----------|---------------|
| Operational Hours | 24 hours per day, 7 days per week, 365 days per year |
| Startup Behavior | Automatic initialization upon system boot; no manual intervention required |
| Shutdown Conditions | Only via explicit authorized administrative command; never self-terminates |
| Recovery Behavior | Automatic restart with state recovery upon failure detection |
| Heartbeat Interval | Health signal emitted every 60 seconds minimum |

### 2.2 Hybrid Orchestration Model

The DMRG-FTE uses a **hybrid orchestration model** combining event-driven triggers with scheduled intervals. This ensures immediate response to data events while maintaining continuous monitoring.

**Trigger Types**:

| Trigger Type | Description | Example |
|--------------|-------------|---------|
| **Data Arrival** | New data lands in monitored location | File uploaded to data lake, record inserted to database |
| **Schedule** | Time-based execution window | Hourly freshness check, daily SLA report |
| **Threshold Breach** | Metric crosses defined boundary | Error rate exceeds 5%, latency exceeds 30 seconds |
| **External Signal** | Message from upstream/downstream system | Pipeline completion webhook, model deployment event |
| **Manual Request** | Authorized user initiates assessment | On-demand audit request, ad-hoc validation |

**Orchestration Intervals**:

| Interval Type | Frequency | Checks Performed |
|---------------|-----------|------------------|
| **Immediate** | 0 latency (event-driven) | Data arrival validation, threshold breach alerts, webhook responses |
| **Short** | Every 30 seconds | Freshness checks, SLA proximity warnings, heartbeat emission |
| **Medium** | Every 5 minutes | Statistical distribution baseline comparison, model drift (batch), health score recalculation |
| **Long** | Every 1 hour | Full fairness assessment, compliance report generation, trend analysis, predictive warnings |

**Execution Model**:

```
EVENT SOURCES                    ORCHESTRATOR                     EXECUTION
─────────────                    ────────────                     ─────────
Data Arrival ──────┐
                   │
Threshold Breach ──┼──► IMMEDIATE ──► Bronze → Silver → Gold (sequential)
                   │         │
External Webhook ──┘         │
                             │
30-second Timer ─────► SHORT ──────► Freshness + SLA (parallel to main pipeline)
                             │
5-minute Timer ──────► MEDIUM ─────► Distribution + Drift + Health
                             │
1-hour Timer ────────► LONG ───────► Fairness + Compliance + Predictions
```

**Parallel Execution Requirements**:
- Layer 4 (Freshness & SLA) MUST run in parallel to the main Bronze→Silver→Gold pipeline
- Predictive analysis MUST run in parallel to reactive checks
- Multiple data sources MAY be validated concurrently
- Anomaly handling MUST NOT block subsequent validations

### 2.3 No Manual Prompting Requirement

**PROHIBITION**: The DMRG-FTE shall never require human prompting or LLM interaction to perform its core functions.

- All monitoring, detection, classification, and alerting logic operates deterministically
- Human interaction is for configuration, review, and escalation handling only
- The system must function identically whether or not any human observes it

### 2.4 Safe Failure Handling

**PROHIBITION**: Silent failures are absolutely forbidden.

| Failure Type | Required Response |
|--------------|-------------------|
| Component Failure | Emit CRITICAL alert, activate fallback, log full context |
| Partial Degradation | Emit WARNING alert, continue with reduced capability, document limitations |
| External Dependency Unavailable | Retry with exponential backoff, emit WARNING after 3 failures, escalate after 10 |
| Configuration Error | Refuse to start affected component, emit CRITICAL alert, use last-known-good configuration |
| Unknown Error | Emit CRITICAL alert, capture full diagnostic state, halt affected operation only |

**Failure Response Contract**:
1. Every failure produces an alert within 60 seconds
2. Every failure writes a structured log entry
3. Every failure is attributed to a specific component
4. No failure can cause complete system-wide shutdown unless explicitly configured

### 2.5 Concurrency Handling

When multiple anomalies are detected simultaneously, the system must handle them deterministically.

**Priority Queue Rules**:

| Priority | Rule | Rationale |
|----------|------|-----------|
| 1 | Higher severity first | CRITICAL before WARNING before INFO |
| 2 | Earlier layer first (within same severity) | Bronze before Silver before Gold |
| 3 | Higher impact weight first (within same layer) | Business-critical data prioritized |
| 4 | Earlier detection timestamp (tiebreaker) | FIFO for identical priority |

**Anomaly Correlation**:

| Correlation Type | Definition | Handling |
|------------------|------------|----------|
| **Causal Chain** | Anomaly A caused Anomaly B | Group into single incident; A is root cause |
| **Common Cause** | Anomalies A and B share upstream cause | Group into single incident; identify shared root |
| **Coincidental** | Anomalies A and B are unrelated | Separate incidents; process independently |
| **Cascading** | Anomaly A triggers multiple downstream anomalies | Single incident with cascade tracking |

**Correlation Detection Signals**:
- Temporal proximity (anomalies within 60 seconds)
- Data lineage relationship (same pipeline or upstream/downstream)
- Common data source or model
- Matching error signatures or patterns

**Concurrency Constraints**:

| Constraint | Specification |
|------------|---------------|
| Max concurrent validations | 100 streams minimum |
| Max anomalies per incident | 50 (create overflow incident if exceeded) |
| Correlation window | 60 seconds (configurable per source) |
| Queue overflow behavior | Persist to durable queue; never drop |

### 2.6 State Recovery

The system must recover gracefully from interruptions without data loss or duplicate processing.

**Checkpoint Requirements**:

| Checkpoint Type | Frequency | Contents |
|-----------------|-----------|----------|
| **Validation State** | Every N records (configurable, default 1000) | Current position, partial results, validation context |
| **Incident State** | On every state change | Incident ID, current status, timeline, assigned owner |
| **Health State** | Every 30 seconds | Layer scores, active alerts, pending escalations |
| **Configuration State** | On every change | Rule versions, threshold values, enabled capabilities |

**Recovery Behavior**:

| Scenario | Recovery Action |
|----------|-----------------|
| Process restart | Resume from last checkpoint; revalidate in-flight data |
| Component failure | Activate standby; replay from checkpoint |
| Network partition | Queue operations locally; sync on reconnection |
| Storage failure | Switch to replica; alert for manual intervention |

**In-Flight Data Handling**:

| Data State | On Restart |
|------------|------------|
| Pre-validation | Re-queue for validation from beginning |
| Mid-validation (checkpointed) | Resume from checkpoint |
| Mid-validation (no checkpoint) | Re-validate from beginning |
| Validated, pre-commit | Re-validate and commit |
| Committed | No action needed |

**Recovery Time Objectives**:

| Component | RTO |
|-----------|-----|
| Validation pipeline | 60 seconds |
| Alerting system | 30 seconds |
| Dashboard | 120 seconds |
| Audit logging | 60 seconds |

---

## 3. Intelligence Layers

The DMRG-FTE organizes its intelligence into five strictly separated layers. Each layer has distinct responsibilities, monitored signals, and detected failure types. **No layer may duplicate the function of another.**

### 3.1 Layer 1: Data Validation (Bronze Tier)

**Responsibility**: Verify that incoming data meets fundamental quality expectations at the point of ingestion.

| Attribute | Specification |
|-----------|---------------|
| **Execution Point** | Immediately upon data arrival, before any transformation |
| **Scope** | Individual records and batches in raw/landing zones |
| **Independence** | Operates without knowledge of downstream consumers |

**Signals Monitored**:
- Record counts (expected vs. actual)
- Null/missing value rates per field
- Data type conformance (string, integer, date, etc.)
- Value range boundaries (min, max, allowed values)
- Format patterns (regex matching for structured fields)
- Duplicate detection (exact and fuzzy)
- Encoding validity (UTF-8 compliance, special characters)

**Failure Types Detected**:

| Failure Code | Name | Description |
|--------------|------|-------------|
| DV-001 | Missing Records | Batch contains fewer records than expected threshold |
| DV-002 | Excess Records | Batch contains more records than expected threshold |
| DV-003 | Null Violation | Required field contains null/empty beyond tolerance |
| DV-004 | Type Mismatch | Field value does not match declared data type |
| DV-005 | Range Violation | Numeric/date value outside permitted boundaries |
| DV-006 | Format Violation | Value does not match required pattern |
| DV-007 | Duplicate Record | Record appears more than once (exact match) |
| DV-008 | Encoding Error | Invalid character encoding detected |

---

### 3.2 Layer 2: Schema & Contract Enforcement (Silver Tier)

**Responsibility**: Ensure data structures conform to declared schemas and upstream/downstream contracts remain honored.

| Attribute | Specification |
|-----------|---------------|
| **Execution Point** | After data validation, before business logic processing |
| **Scope** | Table structures, API contracts, file formats |
| **Independence** | References schema registry; does not interpret business meaning |

**Signals Monitored**:
- Column presence/absence vs. schema definition
- Column ordering (where relevant)
- Data type precision (varchar length, decimal scale)
- Constraint enforcement (primary key, foreign key, unique)
- Schema version alignment
- Backward/forward compatibility indicators
- API contract checksum/signature

**Failure Types Detected**:

| Failure Code | Name | Description |
|--------------|------|-------------|
| SC-001 | Missing Column | Required column absent from data |
| SC-002 | Extra Column | Unexpected column present in data |
| SC-003 | Column Type Change | Column data type differs from contract |
| SC-004 | Precision Loss | Numeric precision insufficient for declared contract |
| SC-005 | Constraint Violation | Primary/foreign key or uniqueness violated |
| SC-006 | Version Mismatch | Schema version incompatible with consumer expectation |
| SC-007 | Breaking Change | Non-backward-compatible schema modification detected |
| SC-008 | Contract Hash Mismatch | API/data contract signature differs from registered version |

---

### 3.3 Layer 3: Business Logic Unit (Silver Tier)

**Responsibility**: Validate that data values are consistent with business rules and domain logic, independent of schema correctness.

| Attribute | Specification |
|-----------|---------------|
| **Execution Point** | After schema validation, during transformation pipeline |
| **Scope** | Cross-field relationships, business invariants, domain rules |
| **Independence** | Operates on validated, schema-conformant data only |

**Signals Monitored**:
- Cross-field consistency (e.g., end_date > start_date)
- Referential integrity across datasets
- Business calculation correctness (totals, aggregates, derived fields)
- State transition validity (e.g., order status progression)
- Temporal consistency (no future dates where inappropriate)
- Domain value relationships (e.g., discount cannot exceed price)
- Statistical distribution stability (sudden shifts in value patterns)

**Failure Types Detected**:

| Failure Code | Name | Description |
|--------------|------|-------------|
| BL-001 | Cross-Field Inconsistency | Related fields have logically incompatible values |
| BL-002 | Referential Break | Referenced entity does not exist |
| BL-003 | Calculation Error | Derived/aggregated value does not match inputs |
| BL-004 | Invalid State Transition | Entity moved to impossible state |
| BL-005 | Temporal Anomaly | Date/time value violates business time rules |
| BL-006 | Domain Rule Violation | Value breaks explicit business constraint |
| BL-007 | Distribution Shift | Statistical profile significantly different from baseline |
| BL-008 | Orphan Record | Record has no valid parent/owner |

---

### 3.4 Layer 4: Freshness & SLA Watcher (Silver Tier)

**Responsibility**: Monitor data timeliness and ensure delivery commitments are met.

| Attribute | Specification |
|-----------|---------------|
| **Execution Point** | Continuously, independent of data processing pipeline |
| **Scope** | Data arrival times, processing durations, SLA definitions |
| **Independence** | Does not validate data content; only timing and availability |

**Signals Monitored**:
- Last data arrival timestamp per source
- Time since last successful update
- Pipeline execution duration
- End-to-end latency (source to destination)
- SLA threshold proximity (warning before breach)
- Scheduled job completion status
- Dependency chain completion times

**Failure Types Detected**:

| Failure Code | Name | Description |
|--------------|------|-------------|
| FS-001 | Data Stale | Time since last update exceeds freshness threshold |
| FS-002 | SLA Breach | Delivery deadline missed |
| FS-003 | SLA Warning | Delivery at risk (threshold proximity exceeded) |
| FS-004 | Pipeline Delay | Processing duration exceeds expected window |
| FS-005 | Missing Delivery | Expected data arrival did not occur |
| FS-006 | Job Failure | Scheduled pipeline execution failed |
| FS-007 | Dependency Delay | Upstream dependency late, blocking downstream |
| FS-008 | Latency Spike | End-to-end time significantly above baseline |

---

### 3.5 Layer 5: Model, Fairness & Ethics Guard (Gold Tier)

**Responsibility**: Monitor ML model performance, detect degradation, and ensure outputs meet fairness and ethical standards.

| Attribute | Specification |
|-----------|---------------|
| **Execution Point** | Post-inference for real-time; batch for historical analysis |
| **Scope** | Model predictions, feature distributions, outcome fairness |
| **Independence** | Operates on model outputs; does not modify model behavior |

**Signals Monitored**:
- Prediction accuracy metrics (precision, recall, F1, AUC)
- Feature drift (input distribution change)
- Concept drift (relationship between features and target changes)
- Prediction drift (output distribution change)
- Demographic parity across protected attributes
- Equalized odds and equal opportunity metrics
- Calibration stability
- Confidence distribution patterns

**Failure Types Detected**:

| Failure Code | Name | Description |
|--------------|------|-------------|
| MF-001 | Accuracy Degradation | Model accuracy below acceptable threshold |
| MF-002 | Feature Drift | Input feature distribution significantly shifted |
| MF-003 | Concept Drift | Feature-target relationship changed |
| MF-004 | Prediction Drift | Output distribution significantly shifted |
| MF-005 | Fairness Violation | Disparate impact across protected groups exceeds threshold |
| MF-006 | Calibration Failure | Predicted probabilities do not match actual frequencies |
| MF-007 | Confidence Anomaly | Unusual pattern in prediction confidence scores |
| MF-008 | Retraining Required | Cumulative drift indicates model refresh needed |

---

## 4. Decision Rules

### 4.1 Anomaly Classification Framework

All detected anomalies must be classified using the following deterministic framework:

**Step 1: Identify Source Layer**
- Map the anomaly to exactly one Intelligence Layer (3.1-3.5)
- If mapping is ambiguous, default to the earliest applicable layer

**Step 2: Assign Failure Code**
- Match to specific failure type within the layer
- If no exact match, use layer's generic failure code (XX-999)

**Step 3: Calculate Severity Score**
- Apply layer-specific severity formula (defined in Section 4.2)
- Score must be deterministic and reproducible

**Step 4: Classify Severity Level**
- Map score to severity level per thresholds in Section 4.2

### 4.2 Severity Levels

| Level | Threshold | Definition | Response Time |
|-------|-----------|------------|---------------|
| **INFO** | Score 0-39 | Observation worth noting; no action required | Log only; no alert |
| **WARNING** | Score 40-69 | Potential issue requiring attention; may escalate | Alert within 5 minutes; human review within 4 hours |
| **CRITICAL** | Score 70-100 | Significant issue requiring immediate action | Alert within 1 minute; human response within 30 minutes |

**Severity Score Formula**:
```
Severity Score = (Impact Weight × 40) + (Frequency Weight × 30) + (Recency Weight × 30)

Where:
- Impact Weight (0.0-1.0): Potential business harm if unaddressed
- Frequency Weight (0.0-1.0): How often this anomaly occurs
- Recency Weight (0.0-1.0): How recently the condition emerged
```

### 4.3 Root-Cause Attribution Requirements

**MANDATORY**: Every anomaly above INFO level must include root-cause attribution.

| Attribution Element | Requirement |
|---------------------|-------------|
| **Source Identification** | Exact dataset, table, or model where anomaly originated |
| **Temporal Localization** | Timestamp range when anomaly first appeared |
| **Component Mapping** | Specific pipeline component or process involved |
| **Upstream Tracing** | Identification of any upstream causes or dependencies |
| **Confidence Score** | Numerical confidence (0-100%) in attribution accuracy |

**Attribution Confidence Thresholds**:
- 80-100%: High confidence; root cause likely identified
- 50-79%: Medium confidence; probable root cause with alternatives
- Below 50%: Low confidence; multiple possible causes listed

### 4.4 Black-Box Decision Prohibition

**PROHIBITION**: No decision produced by the DMRG-FTE may be unexplainable.

| Rule | Requirement |
|------|-------------|
| **Determinism** | Given identical inputs, the system must produce identical outputs |
| **Traceability** | Every decision must link to specific rules, thresholds, and input data |
| **Reproducibility** | Any decision can be re-executed and verified independently |
| **Documentation** | The logic for every decision type is documented in human-readable form |
| **No Hidden State** | All state influencing decisions must be logged and accessible |

**LLM Usage Restriction**:
- LLMs may ONLY be used for natural language generation in explanations
- LLMs shall NEVER be used for anomaly detection, classification, or severity assignment
- If LLM is used for explanation, the underlying deterministic decision must be preserved separately

---

## 5. Autonomous Actions

### 5.1 Permitted Actions

The DMRG-FTE is authorized to perform the following actions without human approval:

| Action Category | Specific Actions | Conditions |
|-----------------|------------------|------------|
| **Alerting** | Send notifications via configured channels | Always permitted |
| **Logging** | Write to audit logs, metrics stores | Always permitted |
| **Quarantine** | Move suspect data to isolation zone | Only for CRITICAL severity; data preserved, not deleted |
| **Soft Block** | Flag data as untrusted; prevent downstream consumption | Only for CRITICAL severity; reversible |
| **Report Generation** | Create incident reports, dashboards | Always permitted |
| **Metadata Tagging** | Add quality scores, flags to data catalog | Always permitted |
| **Retry Initiation** | Trigger re-execution of failed pipeline | Maximum 3 retries; exponential backoff |
| **Notification Escalation** | Escalate to higher-priority channels | After initial response timeout exceeded |

### 5.2 Prohibited Actions

The DMRG-FTE is explicitly forbidden from performing the following actions:

| Prohibited Action | Reason |
|-------------------|--------|
| **Data Deletion** | Irreversible; human approval required |
| **Data Modification** | Changing source data creates audit risk |
| **Schema Alteration** | Structural changes require change control |
| **Model Retraining** | Must be supervised; resource intensive |
| **Model Deployment** | Production changes require human approval |
| **Access Control Changes** | Security-sensitive; human approval required |
| **System Shutdown** | Business continuity risk |
| **Configuration Changes** | May affect behavior; requires approval |
| **External Communication** | Beyond designated alert channels forbidden |
| **Code Execution** | Arbitrary code execution prohibited |

### 5.3 Unsafe Asset Handling

When data or models are deemed unsafe:

**Stage 1: Detection**
- Anomaly detected and classified as CRITICAL
- Root-cause attribution completed (any confidence level)

**Stage 2: Isolation**
- Asset moved to quarantine zone (data) or shadow mode (model)
- Downstream consumers notified via status flag
- Original asset preserved in its pre-quarantine state

**Stage 3: Documentation**
- Incident record created with full context
- Timeline of events captured
- Impact assessment generated

**Stage 4: Escalation**
- Human owner notified immediately
- Escalation path followed per Section 5.4
- Asset remains isolated until human release

### 5.4 Human Escalation Boundaries

| Condition | Escalation Target | Timeframe |
|-----------|-------------------|-----------|
| CRITICAL alert, no response in 30 minutes | Secondary on-call | Immediate |
| CRITICAL alert, no response in 2 hours | Management escalation | Immediate |
| WARNING alert, no response in 8 hours | Team lead | Immediate |
| Quarantine action taken | Data owner + Platform team | Within 5 minutes |
| Model flagged for ethics violation | AI Ethics committee + Legal | Within 15 minutes |
| SLA breach confirmed | Customer-facing stakeholders | Within 10 minutes |
| Repeated CRITICAL alerts (3+ in 1 hour) | Incident commander | Immediate |

---

## 6. Interactive User Display

### 6.1 Unified Dashboard Specification

**REQUIREMENT**: A single, unified dashboard serves as the primary interface for all users.

**Design Principles**:
1. Non-technical users understand system health within 30 seconds
2. Technical detail available on demand, never by default
3. Visual clarity equal in importance to technical accuracy
4. No jargon in default view
5. Consistent visual language across all components

### 6.2 Executive Summary Panel

**Location**: Top of dashboard, always visible

| Component | Display | Purpose |
|-----------|---------|---------|
| **Overall Health Score** | Large number (0-100) with color (Red/Yellow/Green) | Instant health assessment |
| **Health Trend** | Sparkline showing last 24 hours | Direction of health |
| **Active Issues** | Count badge with severity breakdown | Attention needed |
| **Last Updated** | Timestamp with "X minutes ago" | Data freshness |
| **Plain Language Summary** | 1-2 sentence auto-generated status | Human-readable overview |

**Example Plain Language Summary**:
- "All systems healthy. No issues detected in the past 24 hours."
- "2 data sources showing delays. Customer orders may be up to 3 hours stale."
- "ALERT: Payment model showing potential bias. Ethics review required."

### 6.3 Health Scores Display

**Per-Layer Health Scores**:

| Layer | Score Display | Visual Indicator |
|-------|---------------|------------------|
| Data Validation | 0-100 with trend arrow | Horizontal bar with color gradient |
| Schema Enforcement | 0-100 with trend arrow | Horizontal bar with color gradient |
| Business Logic | 0-100 with trend arrow | Horizontal bar with color gradient |
| Freshness & SLA | 0-100 with trend arrow | Horizontal bar with color gradient |
| Model & Fairness | 0-100 with trend arrow | Horizontal bar with color gradient |

**Aggregate Health Formula**:
```
Overall Health = Minimum(All Layer Scores)
Rationale: System is only as healthy as its weakest component
```

### 6.4 Visual Indicators

| Indicator Type | Usage | Design |
|----------------|-------|--------|
| **Color Coding** | Severity and health | Green (90-100), Yellow (70-89), Orange (50-69), Red (0-49) |
| **Progress Bars** | Percentage metrics | Horizontal bars with color fill |
| **Trend Arrows** | Direction indicators | Up (improving), Down (degrading), Flat (stable) |
| **Sparklines** | Historical patterns | Mini line charts, last 24-168 hours |
| **Status Badges** | Binary states | Checkmark (OK), X (Failed), Clock (Pending) |
| **Heat Maps** | Multi-dimensional view | Color intensity for value magnitude |
| **Timeline Markers** | Event sequences | Vertical lines on time axis |

### 6.5 Business Impact Views

**Impact Translation Table**:

| Technical Metric | Business Translation |
|------------------|---------------------|
| Data freshness: 3 hours stale | "Customer data may not reflect orders from the last 3 hours" |
| Model accuracy: 85% | "Approximately 15 out of 100 predictions may be incorrect" |
| Schema error rate: 2% | "2% of incoming records cannot be processed" |
| SLA at risk | "Delivery commitment to [Customer X] may be missed by [Time Y]" |
| Fairness violation | "Model may be treating [Group A] differently than [Group B]" |

**Business Impact Panel Components**:
- Affected business processes (list)
- Estimated financial impact (if calculable)
- Customer segments affected
- Regulatory/compliance implications
- Recommended business actions

### 6.6 Incident Timeline

**Timeline View Requirements**:

| Element | Display |
|---------|---------|
| **Time Axis** | Horizontal, scrollable, zoomable (1 hour to 30 days) |
| **Events** | Vertical markers with severity color |
| **Event Details** | Popup on hover/click with plain-language summary |
| **Clustering** | Related events grouped; expandable |
| **Filtering** | By severity, layer, asset, time range |
| **Correlation Lines** | Visual links between related events |

**Incident Card Contents**:
- Title (plain language)
- Severity badge
- Timestamp (absolute and relative)
- Affected asset(s)
- Root cause summary (plain language)
- Current status (Active/Resolved/Acknowledged)
- Assigned owner (if any)
- Resolution actions taken

### 6.7 Drill-Down Capability

**Technical Detail Access**:
- Default view: Plain language only
- First click: Summary technical details
- Second click: Full technical specifications
- Available at: Every metric, chart, and incident card

**Technical Detail Panel**:
- Raw metric values
- Exact thresholds and formulas
- Query/rule that generated the alert
- Full stack trace (for failures)
- Related log entries
- API for programmatic access

### 6.8 User Personas and Views

| Persona | Default View | Available Actions |
|---------|--------------|-------------------|
| **Executive** | Health score, trend, business impact | Drill-down, export summary |
| **Business Analyst** | Business impact, SLA status, incident summary | Acknowledge, assign, filter |
| **Data Engineer** | Layer health, technical details, pipeline status | Acknowledge, investigate, retry |
| **Data Scientist** | Model health, drift metrics, fairness scores | Investigate, request retrain |
| **Compliance Officer** | Audit log, fairness reports, incident history | Export, generate report |

---

## 7. Audit & Explainability

### 7.1 Required Artifacts

The DMRG-FTE must produce and retain the following artifacts:

| Artifact Type | Contents | Retention |
|---------------|----------|-----------|
| **Decision Log** | Every anomaly detection, classification, and action | 7 years minimum |
| **State Snapshots** | System configuration and health at regular intervals | 1 year minimum |
| **Incident Records** | Full context for every WARNING and CRITICAL | 7 years minimum |
| **Audit Trail** | Timestamped sequence of all system actions | 7 years minimum |
| **Explanation Reports** | Human-readable explanation for each decision | 7 years minimum |
| **Configuration History** | All changes to rules, thresholds, and settings | Indefinite |
| **Performance Metrics** | System performance and accuracy statistics | 3 years minimum |

### 7.2 Decision Traceability

**Every decision must be traceable via the following chain**:

```
Input Data → Applied Rules → Intermediate Calculations → Final Decision → Action Taken
```

**Traceability Record Structure**:

| Field | Description |
|-------|-------------|
| Decision ID | Unique identifier |
| Timestamp | ISO 8601 format with timezone |
| Input Hash | Cryptographic hash of input data |
| Input Reference | Pointer to original input data |
| Rules Applied | List of rule IDs with versions |
| Calculation Steps | Ordered list of intermediate values |
| Decision Output | Final classification and severity |
| Action Triggered | Action taken (or none) |
| Explanation Text | Human-readable explanation |
| Confidence Score | Attribution confidence percentage |

### 7.3 Incident Timeline Requirements

Each incident must have a complete timeline:

| Timeline Element | Requirement |
|------------------|-------------|
| **First Detection** | Exact timestamp when anomaly first detected |
| **Classification** | When severity was assigned |
| **Notification** | When and to whom alerts were sent |
| **Acknowledgment** | When human acknowledged (if applicable) |
| **Investigation** | Actions taken to investigate |
| **Resolution** | Actions taken to resolve |
| **Closure** | Final disposition and lessons learned |
| **Post-Mortem** | Link to analysis (for CRITICAL incidents) |

### 7.4 Compliance Readiness

**Regulatory Framework Support**:

| Regulation | Supported Capabilities |
|------------|----------------------|
| **GDPR** | Data lineage, processing records, consent tracking |
| **SOX** | Financial data controls, audit trails, access logs |
| **HIPAA** | PHI access monitoring, breach detection |
| **CCPA** | Data inventory, access tracking |
| **AI Act (EU)** | Model documentation, fairness assessments, human oversight |
| **NIST AI RMF** | Risk identification, measurement, mitigation tracking |

**Compliance Report Generation**:
- On-demand compliance reports per framework
- Automated evidence collection for audits
- Gap analysis against framework requirements
- Remediation tracking and verification

---

## 8. Tiered Capability Model

Capabilities are organized into three tiers representing increasing sophistication. **Each tier's capabilities are non-overlapping with other tiers.**

### 8.1 Bronze Tier Capabilities

**Focus**: Foundational data quality at ingestion

| Capability ID | Capability Name | Description |
|---------------|-----------------|-------------|
| B-01 | Record Count Validation | Verify batch sizes within expected ranges |
| B-02 | Null/Missing Detection | Identify fields with null or empty values |
| B-03 | Data Type Checking | Confirm values match declared types |
| B-04 | Range Boundary Validation | Check numeric/date values within bounds |
| B-05 | Pattern Matching | Validate string formats against regex |
| B-06 | Duplicate Detection | Identify exact duplicate records |
| B-07 | Encoding Validation | Verify character encoding correctness |
| B-08 | Basic Alerting | Send notifications for Bronze-level failures |
| B-09 | Basic Logging | Record all validations and outcomes |
| B-10 | Quarantine (Basic) | Isolate individual invalid records |

### 8.2 Silver Tier Capabilities

**Focus**: Schema enforcement, business logic, and timeliness

| Capability ID | Capability Name | Description |
|---------------|-----------------|-------------|
| S-01 | Schema Validation | Verify data structures match registered schemas |
| S-02 | Contract Enforcement | Ensure API/data contracts honored |
| S-03 | Version Compatibility | Check schema version alignment |
| S-04 | Cross-Field Validation | Verify relationships between fields |
| S-05 | Referential Integrity | Check foreign key relationships |
| S-06 | Business Rule Evaluation | Apply domain-specific validation rules |
| S-07 | Statistical Distribution Monitoring | Track value distribution stability |
| S-08 | Freshness Monitoring | Track time since last data update |
| S-09 | SLA Tracking | Monitor delivery against commitments |
| S-10 | Pipeline Duration Monitoring | Track processing time metrics |
| S-11 | Dependency Chain Monitoring | Track upstream/downstream timing |
| S-12 | Root-Cause Attribution | Identify probable cause of failures |
| S-13 | Incident Management | Create, track, and manage incidents |
| S-14 | Escalation Management | Execute escalation procedures |
| S-15 | Quarantine (Dataset) | Isolate entire datasets when necessary |

### 8.3 Gold Tier Capabilities

**Focus**: ML model reliability, fairness, and ethics

| Capability ID | Capability Name | Description |
|---------------|-----------------|-------------|
| G-01 | Model Accuracy Monitoring | Track precision, recall, F1, AUC over time |
| G-02 | Feature Drift Detection | Identify input distribution changes |
| G-03 | Concept Drift Detection | Identify relationship changes |
| G-04 | Prediction Drift Detection | Identify output distribution changes |
| G-05 | Calibration Monitoring | Verify probability calibration stability |
| G-06 | Demographic Parity Assessment | Measure outcome equality across groups |
| G-07 | Equalized Odds Assessment | Measure error rate equality across groups |
| G-08 | Disparate Impact Calculation | Quantify differential treatment |
| G-09 | Fairness Threshold Enforcement | Alert when fairness metrics breach |
| G-10 | Retraining Trigger Detection | Identify when model refresh needed |
| G-11 | Ethics Violation Alerting | Escalate potential ethical issues |
| G-12 | Model Shadow Mode | Run model in observation-only mode |
| G-13 | A/B Comparison Monitoring | Compare model versions |
| G-14 | Explanation Generation | Create human-readable model explanations |
| G-15 | Compliance Reporting | Generate regulatory compliance reports |

### 8.4 Tier Interdependencies

| Dependency | Description |
|------------|-------------|
| Silver requires Bronze | Schema validation operates on Bronze-validated data only |
| Gold requires Silver | Model monitoring operates on schema-conformant, timely data only |
| No reverse dependencies | Lower tiers never depend on higher tier capabilities |
| Independent execution | Each tier can operate if higher tiers are unavailable |

---

## 9. Constraints & Prohibitions

### 9.1 Technical Constraints

| Constraint | Specification |
|------------|---------------|
| **Processing Latency** | Bronze validation: < 100ms per record; Silver: < 1s per batch; Gold: < 5s per inference batch |
| **Memory Usage** | No single operation may consume > 10% of available memory |
| **Storage Growth** | Audit logs: < 1GB per day under normal operation |
| **Concurrent Operations** | Support minimum 100 concurrent validation streams |
| **Recovery Time** | Return to operation within 60 seconds of component failure |
| **Data Volume** | Support validation of datasets up to 10TB |

### 9.2 Operational Prohibitions

| Prohibition | Rationale |
|-------------|-----------|
| No internet access beyond designated endpoints | Security containment |
| No dynamic code loading or execution | Prevent injection attacks |
| No credential storage in plaintext | Security best practice |
| No logging of PII in plaintext | Privacy compliance |
| No modification of source systems | Maintain data integrity |
| No bypassing of audit logging | Compliance requirement |
| No operating without heartbeat | Ensure detectability |
| No single point of failure for critical paths | Reliability requirement |

### 9.3 LLM Usage Constraints

| Constraint | Specification |
|------------|---------------|
| **Optional Only** | Core functionality must work without any LLM |
| **Explanation Only** | LLM use restricted to natural language explanation generation |
| **No Decision Making** | LLM output shall never determine anomaly classification or severity |
| **Fallback Required** | If LLM unavailable, system uses template-based explanations |
| **Audit Separation** | LLM-generated text must be clearly marked in audit logs |
| **No Training** | System shall not fine-tune or train LLMs |
| **Deterministic Wrapper** | Same input always produces same decision regardless of LLM availability |

### 9.4 Human Override Rights

| Right | Specification |
|-------|---------------|
| **Override Any Decision** | Authorized humans may override any automated decision |
| **Release Quarantine** | Humans may release quarantined assets with documented justification |
| **Adjust Thresholds** | Humans may modify severity thresholds with audit trail |
| **Disable Capabilities** | Individual capabilities may be disabled with approval |
| **Force Escalation** | Humans may escalate any issue regardless of severity |
| **Request Explanation** | Humans may request detailed explanation for any decision |

---

## Governance

### Amendment Process

1. **Proposal**: Any stakeholder may propose amendments
2. **Review**: Technical and business review required
3. **Approval**: Requires sign-off from:
   - Data Platform Lead
   - AI/ML Lead
   - Compliance Officer
   - Business Stakeholder Representative
4. **Documentation**: All changes documented with rationale
5. **Migration**: Impact assessment and migration plan required
6. **Communication**: All users notified of changes

### Compliance Verification

- All implementations must demonstrate compliance with this Constitution
- Regular audits (quarterly minimum) verify adherence
- Non-compliance must be documented with remediation timeline
- Constitution takes precedence over implementation convenience

### Version Control

- This Constitution is version-controlled
- All changes tracked with author, date, and rationale
- Previous versions retained for reference
- Rollback procedures documented

---

## 10. Skills Catalog

Skills are focused, single-purpose execution units that reduce complexity and improve token efficiency. Each skill has a defined input/output contract and operates independently.

### 10.1 Skill Architecture

**Design Principles**:
- Each skill performs exactly one function
- Skills have minimal context (200-500 tokens maximum)
- Skills are composable into workflows
- Skills run independently and can be parallelized
- Same input always produces same output (deterministic)

**Skill Contract Structure**:
```
Skill ID: <tier>.<name>
Input: <input type/format>
Output: <output type/format>
Dependencies: <required skills or none>
Timeout: <maximum execution time>
```

### 10.2 Bronze Tier Skills

| Skill ID | Purpose | Input | Output |
|----------|---------|-------|--------|
| bronze.count | Validate record counts | batch | {valid: bool, expected: int, actual: int, delta: int} |
| bronze.null | Detect null/missing values | record | {fields: string[], percentages: float[], violations: bool} |
| bronze.type | Check data type conformance | record, schema | {mismatches: [{field, expected, actual}]} |
| bronze.range | Validate value boundaries | field, bounds | {in_range: bool, value: any, min: any, max: any} |
| bronze.format | Pattern/regex matching | field, pattern | {matches: bool, pattern: string, value: string} |
| bronze.duplicate | Find exact duplicates | batch | {duplicates: [{id, count, first_seen}]} |
| bronze.encoding | Verify character encoding | record | {valid: bool, errors: [{field, position, byte}]} |
| bronze.quarantine | Isolate invalid records | record_ids[] | {quarantined: int, location: string} |
| bronze.alert | Send Bronze-level alerts | anomaly | {sent: bool, channel: string, timestamp: datetime} |
| bronze.log | Write validation logs | result | {logged: bool, log_id: string} |

### 10.3 Silver Tier Skills

| Skill ID | Purpose | Input | Output |
|----------|---------|-------|--------|
| silver.schema | Compare data to schema | data, schema | {valid: bool, diff: [{type, field, detail}]} |
| silver.contract | Verify API/data contracts | payload, contract | {valid: bool, violations: []} |
| silver.version | Check schema version compatibility | v1, v2 | {compatible: bool, breaking_changes: []} |
| silver.crossfield | Validate field relationships | record, rules | {violations: [{rule, fields, values}]} |
| silver.refint | Check referential integrity | record, refs | {orphans: [{field, value, expected_in}]} |
| silver.bizrule | Evaluate business rules | record, rules | {passed: string[], failed: [{rule, reason}]} |
| silver.distrib | Compare to baseline distribution | data, baseline | {drift_pct: float, significant: bool, details: {}} |
| silver.freshness | Check data staleness | source | {age_seconds: int, stale: bool, threshold: int} |
| silver.sla | Track SLA compliance | source, sla | {status: string, eta: datetime, at_risk: bool} |
| silver.pipeline | Monitor pipeline duration | pipeline_id | {duration_ms: int, expected_ms: int, ok: bool} |
| silver.dependency | Track dependency chain | dag | {delays: [{node, delay_ms}], blocked: string[]} |
| silver.rootcause | Attribute probable cause | anomaly | {cause: string, confidence_pct: int, alternatives: []} |
| silver.incident | Create/manage incidents | anomaly | {incident_id: string, status: string, created: bool} |
| silver.escalate | Execute escalation path | incident | {escalated_to: string[], channel: string} |
| silver.quarantine | Isolate entire datasets | dataset_id | {quarantined: bool, location: string, size: int} |

### 10.4 Gold Tier Skills

| Skill ID | Purpose | Input | Output |
|----------|---------|-------|--------|
| gold.accuracy | Track model accuracy metrics | predictions, labels | {precision: float, recall: float, f1: float, auc: float} |
| gold.featdrift | Detect feature distribution shift | features, baseline | {drift: [{feature, psi, significant}]} |
| gold.concdrift | Detect concept drift | model, data | {drift_score: float, significant: bool} |
| gold.preddrift | Detect prediction distribution shift | predictions, baseline | {drift_pct: float, distribution: {}} |
| gold.calibration | Verify probability calibration | predictions, actuals | {ece: float, calibrated: bool, buckets: []} |
| gold.demographic | Assess demographic parity | predictions, groups | {parity: float, group_rates: {}} |
| gold.eqodds | Assess equalized odds | predictions, groups, labels | {tpr_diff: float, fpr_diff: float, fair: bool} |
| gold.disparate | Calculate disparate impact | predictions, groups | {ratio: float, threshold: float, violation: bool} |
| gold.fairalert | Alert on fairness breach | metrics | {alert: bool, group: string, metric: string} |
| gold.retrain | Detect retraining need | drift_scores | {needed: bool, reason: string, urgency: string} |
| gold.ethics | Flag ethics violations | model, output | {flags: [{type, severity, description}]} |
| gold.shadow | Run model in shadow mode | model, data | {shadow_output: any, divergence: float} |
| gold.abcompare | Compare model versions | model_a, model_b, data | {winner: string, metrics_diff: {}} |
| gold.explain | Generate model explanations | prediction | {explanation: string, factors: [{feature, impact}]} |
| gold.compliance | Generate compliance reports | model | {report: {}, gaps: [{requirement, status}]} |

### 10.5 Utility Skills

| Skill ID | Purpose | Input | Output |
|----------|---------|-------|--------|
| util.score | Calculate severity score | impact, frequency, recency | {score: int, level: string} |
| util.alert | Send multi-channel alerts | message, channels | {sent: [{channel, success, timestamp}]} |
| util.explain | Generate plain-language text | anomaly | {explanation: string, audience: string} |
| util.translate | Convert tech metric to business impact | metric | {business_text: string, affected: string[]} |
| util.audit | Write to audit trail | decision | {audit_id: string, timestamp: datetime} |
| util.health | Calculate health scores | metrics | {score: int, trend: string, components: {}} |
| util.correlate | Group related anomalies | anomalies | {groups: [[anomaly_ids]], correlation_type: string} |
| util.checkpoint | Save/restore state | state | {checkpoint_id: string, size_bytes: int} |
| util.predict | Forecast future issues | historical_metrics | {prediction: string, confidence: float, eta: datetime} |
| util.impact | Analyze downstream effects | failed_asset | {downstream: string[], business_impact: string} |
| util.cost | Estimate incident cost | incident | {cost_usd: float, breakdown: {}} |
| util.runbook | Retrieve remediation steps | failure_code | {steps: string[], auto_actions: string[], contacts: string[]} |
| util.heal | Execute safe auto-fixes | anomaly | {action_taken: string, success: bool, risk_level: string} |
| util.learn | Update resolution patterns | resolved_incidents | {patterns_updated: int, new_recommendations: []} |

### 10.6 Skill Composition

Skills are composed into workflows by the orchestrator:

**Example Workflow: Data Arrival Validation**
```
1. util.checkpoint {save: start}
2. PARALLEL:
   - bronze.count
   - bronze.null
   - bronze.type
   - bronze.duplicate
3. IF any failure:
   a. util.score
   b. util.correlate
   c. util.impact
   d. IF CRITICAL: bronze.quarantine
   e. silver.incident
   f. util.alert
   g. util.runbook
   h. util.heal (if safe)
4. IF all passed: continue to Silver tier
5. util.checkpoint {save: complete}
```

**Token Efficiency**:
- Monolithic approach: 5,000-10,000 tokens per validation
- Skill-based approach: 2,000-3,000 tokens per validation
- Estimated savings: 50-70% reduction

---

## 11. Advanced Capabilities

These capabilities extend the core DMRG-FTE functionality to provide proactive monitoring, business intelligence, and operational efficiency.

### 11.1 Predictive Warnings

**Purpose**: Alert before problems occur, not just after.

**New Severity Level**:

| Level | Definition | Response |
|-------|------------|----------|
| **PREDICT** | Issue likely to occur within forecast window | Advisory; no immediate action required |

**Prediction Signals**:

| Signal Type | Detection Method | Example |
|-------------|------------------|---------|
| Trend Extrapolation | Linear/exponential projection | "Null rate increasing 2% per hour" |
| Capacity Forecast | Resource utilization projection | "Storage 80% full, will exceed in 6 hours" |
| SLA Trajectory | Delivery rate projection | "At current rate, will miss SLA by 15 minutes" |
| Model Decay Curve | Accuracy trend analysis | "Accuracy dropping 0.5% per day" |
| Seasonal Pattern | Historical pattern matching | "Error spike expected at month-end processing" |

**Prediction Requirements**:
- Confidence threshold: 70% minimum for PREDICT alert
- Forecast window: 1 hour to 7 days (configurable)
- False positive rate: < 20% over 30-day rolling window
- Update frequency: Every hour (LONG interval)

### 11.2 Impact Graph

**Purpose**: Visualize data lineage and understand downstream effects of failures.

**Graph Components**:

| Component | Description |
|-----------|-------------|
| **Nodes** | Data assets (tables, files, models, reports) |
| **Edges** | Data flow relationships (reads, writes, transforms) |
| **Attributes** | Freshness, quality score, owner, SLA |

**Impact Analysis Outputs**:

| Analysis Type | Output |
|---------------|--------|
| **Direct Impact** | Immediate downstream consumers |
| **Indirect Impact** | Transitive downstream consumers |
| **Business Impact** | Affected business processes, decisions, reports |
| **Blast Radius** | Total count of affected assets and users |

**Lineage Requirements**:
- Automatic discovery via metadata scanning
- Manual override for undiscoverable relationships
- Update frequency: On schema change + daily reconciliation
- Depth limit: 10 hops maximum for performance

### 11.3 Cost Attribution

**Purpose**: Quantify the financial impact of data quality issues.

**Cost Categories**:

| Category | Calculation Method |
|----------|-------------------|
| **Compute** | Pipeline reruns × unit cost per run |
| **Labor** | Engineer hours × hourly rate |
| **SLA Penalty** | Contractual penalty amounts |
| **Opportunity** | Estimated revenue impact of delayed decisions |
| **Remediation** | Manual fix effort × hourly rate |

**Dashboard Metrics**:
- Total cost this period (day/week/month)
- Cost trend vs previous period
- Cost by failure type
- Cost by data source
- ROI of DMRG-FTE (cost avoided vs system cost)

**Cost Attribution Requirements**:
- Cost rates configurable per organization
- Attribution to specific incidents
- Aggregate reporting by dimension (source, type, team)
- Export capability for finance integration

### 11.4 Runbook Integration

**Purpose**: Link failure codes to remediation procedures.

**Runbook Structure**:

| Field | Description |
|-------|-------------|
| Failure Code | The triggering failure code |
| Summary | One-line description of the issue |
| Diagnostic Steps | Ordered list of investigation steps |
| Resolution Steps | Ordered list of fix steps |
| Auto-Actions | Safe automated actions (if any) |
| Escalation Contacts | People to contact if steps fail |
| Historical Success Rate | Percentage of times this runbook resolved the issue |

**Runbook Requirements**:
- Runbook exists for every failure code
- Version-controlled with change history
- Success rate tracking per runbook
- Suggestion ranking by historical effectiveness
- Integration with incident management system

### 11.5 Self-Healing (Limited)

**Purpose**: Automatically resolve issues when safe to do so.

**Permitted Auto-Fixes**:

| Auto-Fix | Conditions | Rollback |
|----------|------------|----------|
| Pipeline retry | Failed job, < 3 retries, no data corruption | N/A |
| Switch to backup source | Primary unavailable, backup exists | Automatic on primary recovery |
| Activate cached data | Source stale, cache valid, WARNING flag added | Automatic on fresh data |
| Route away from degraded model | Model accuracy below threshold, fallback exists | Automatic on model recovery |
| Restart hung process | No heartbeat for 5 minutes, restart allowed | N/A |

**Prohibited Auto-Fixes** (require human approval):

| Fix Type | Reason |
|----------|--------|
| Apply default values | May mask data issues |
| Truncate out-of-range values | Data modification |
| Rollback schema | May break consumers |
| Activate fallback model | Production change |
| Modify thresholds | Configuration change |

**Self-Healing Requirements**:
- All auto-fixes logged to audit trail
- Rollback capability for reversible fixes
- Maximum auto-fix attempts: 3 per incident
- Human notification for all auto-fixes
- Override capability to disable specific auto-fixes

### 11.6 Resolution Learning

**Purpose**: Improve remediation recommendations based on historical outcomes.

**Learning Signals**:

| Signal | Tracked Data |
|--------|--------------|
| Resolution success | Did the action resolve the issue? |
| Time to resolution | How long from detection to resolution? |
| Recurrence | Did the same issue reoccur within 7 days? |
| Escalation needed | Was escalation required despite runbook? |

**Pattern Outputs**:

| Output | Description |
|--------|-------------|
| Success rate by action | Percentage of times each action resolved the failure type |
| Recommended action order | Ranked list of actions by likelihood of success |
| Average resolution time | Expected time to resolution by action |
| Escalation probability | Likelihood that escalation will be needed |

**Learning Requirements**:
- No LLM involvement (pure statistical pattern matching)
- Minimum sample size: 10 incidents before recommending
- Confidence interval displayed with recommendations
- Decay factor for old data (half-life: 90 days)
- Manual override capability for recommendations

---

**Version**: 1.1.0 | **Ratified**: 2026-01-17 | **Last Amended**: 2026-01-17

---

**Constitution Certification**

This Constitution defines the complete, authoritative specification for the Data & Model Reliability Guardian (DMRG-FTE). All implementations must conform to this document. Any ambiguity shall be resolved in favor of:
1. Safety (preventing harm)
2. Explainability (ensuring understanding)
3. Auditability (maintaining records)
4. Determinism (ensuring reproducibility)

---

**Version**: 1.1.0 | **Ratified**: 2026-01-17 | **Last Amended**: 2026-01-17
