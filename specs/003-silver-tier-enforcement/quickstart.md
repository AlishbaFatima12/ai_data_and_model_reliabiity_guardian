# Quickstart: Silver Tier - Schema, Business Logic & Freshness Enforcement

**Feature**: `003-silver-tier-enforcement`
**Date**: 2026-01-18
**Phase**: 1 - Design

---

## Prerequisites

Before working on Silver Tier, ensure:

1. **Bronze Tier is complete and working**
   - All Bronze validation skills implemented
   - Orchestrator running and processing data
   - Health scores being calculated

2. **Dashboard is operational**
   - Streamlit dashboard displaying Bronze tier data
   - Health score visualization working

3. **Development environment ready**
   - Python 3.11+
   - Existing dependencies installed

---

## Quick Setup

### 1. Install New Dependencies

```bash
# From repository root
pip install jsonschema>=4.21.0 deepdiff>=7.0 croniter>=2.0.0
```

Or update pyproject.toml:

```toml
[project]
dependencies = [
    # Existing
    "pydantic>=2.5.0",
    "watchdog>=4.0.0",
    "apscheduler>=3.10.0",
    "structlog>=24.0.0",
    "pyyaml>=6.0",
    # NEW for Silver Tier
    "jsonschema>=4.21.0",
    "deepdiff>=7.0",
    "croniter>=2.0.0",
]
```

### 2. Create Directory Structure

```bash
# Create Silver tier directories
mkdir -p src/skills/silver
mkdir -p config/schemas
mkdir -p config/rules
mkdir -p config/sla
mkdir -p data/reference
mkdir -p tests/silver/unit/skills
mkdir -p tests/silver/unit/services
mkdir -p tests/silver/integration

# Create __init__.py files
touch src/skills/silver/__init__.py
touch tests/silver/__init__.py
touch tests/silver/unit/__init__.py
touch tests/silver/unit/skills/__init__.py
touch tests/silver/unit/services/__init__.py
touch tests/silver/integration/__init__.py
```

### 3. Create Sample Configuration Files

**Schema Contract** (`config/schemas/orders.json`):
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "id": "orders-v1.0",
  "name": "Orders Schema",
  "version": "1.0.0",
  "source": "orders",
  "type": "object",
  "required": ["order_id", "customer_id", "order_total", "created_at"],
  "properties": {
    "order_id": {"type": "string", "pattern": "^ORD-[0-9]{8}$"},
    "customer_id": {"type": "string"},
    "order_total": {"type": "number", "minimum": 0},
    "discount": {"type": "number", "minimum": 0, "default": 0},
    "status": {"type": "string", "enum": ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"]},
    "created_at": {"type": "string", "format": "date-time"}
  },
  "additionalProperties": false,
  "x-column-criticality": {
    "order_id": "required",
    "customer_id": "required",
    "order_total": "required",
    "discount": "optional",
    "status": "required",
    "created_at": "required"
  }
}
```

**Business Rules** (`config/rules/orders.yaml`):
```yaml
rules:
  - id: BL-001-discount-limit
    name: Discount cannot exceed order total
    type: domain
    expression: "discount <= order_total"
    severity: critical
    enabled: true
    failure_code: BL-006

  - id: BL-002-customer-exists
    name: Customer must exist in reference data
    type: referential
    field: customer_id
    reference: customers
    severity: critical
    enabled: true
    failure_code: BL-002

  - id: BL-003-valid-status
    name: Valid order status values
    type: state_transition
    field: status
    allowed_values: [PENDING, CONFIRMED, SHIPPED, DELIVERED]
    severity: critical
    enabled: true
    failure_code: BL-004
```

**SLA Definition** (`config/sla/orders.yaml`):
```yaml
- id: sla-orders-hourly
  source: orders
  schedule: "0 * * * *"
  freshness_threshold:
    warning_minutes: 60
    critical_minutes: 90
  latency_threshold: 1800
  enabled: true
  owner: data-platform-team
  description: Orders data expected hourly
```

**Reference Data** (`data/reference/customers.csv`):
```csv
id,name,status
CUST-001,Acme Corp,active
CUST-002,Widget Inc,active
CUST-003,Old Corp,inactive
```

---

## Development Workflow

### Phase 1: Extend Constants

Add Silver failure codes to `src/lib/constants.py`:

```python
# Add to existing FailureCode enum
class FailureCode(str, Enum):
    # ... existing Bronze codes ...

    # Silver - Schema (Layer 2)
    SC_001 = "SC-001"  # Missing Column
    SC_002 = "SC-002"  # Extra Column
    SC_003 = "SC-003"  # Column Type Change
    SC_004 = "SC-004"  # Precision Loss
    SC_005 = "SC-005"  # Constraint Violation
    SC_006 = "SC-006"  # Version Mismatch
    SC_007 = "SC-007"  # Breaking Change
    SC_008 = "SC-008"  # Contract Hash Mismatch

    # Silver - Business Logic (Layer 3)
    BL_001 = "BL-001"  # Cross-Field Inconsistency
    BL_002 = "BL-002"  # Referential Break
    BL_003 = "BL-003"  # Calculation Error
    BL_004 = "BL-004"  # Invalid State Transition
    BL_005 = "BL-005"  # Temporal Anomaly
    BL_006 = "BL-006"  # Domain Rule Violation
    BL_007 = "BL-007"  # Distribution Shift
    BL_008 = "BL-008"  # Orphan Record

    # Silver - Freshness (Layer 4)
    FR_001 = "FR-001"  # Data Stale
    FR_002 = "FR-002"  # SLA Breach
    FR_003 = "FR-003"  # SLA Warning
    FR_004 = "FR-004"  # Pipeline Delay
    FR_005 = "FR-005"  # Missing Delivery
    FR_006 = "FR-006"  # Job Failure
    FR_007 = "FR-007"  # Dependency Delay
    FR_008 = "FR-008"  # Latency Spike
```

### Phase 2: Create Models

Create new model files in `src/models/`:

- `schema_contract.py` - SchemaContract, ColumnDefinition
- `business_rule.py` - BusinessRule, RuleType
- `reference_data.py` - ReferenceDataSet
- `sla_definition.py` - SLADefinition, FreshnessThreshold
- `silver_anomaly.py` - SchemaAnomaly, BusinessLogicAnomaly, FreshnessAnomaly

### Phase 3: Implement Skills

Order of implementation (by layer):

**Layer 2 - Schema:**
1. `silver/schema.py` - Core schema validation
2. `silver/version.py` - Version compatibility
3. `silver/contract.py` - Contract checksum

**Layer 3 - Business Logic:**
1. `silver/crossfield.py` - Field comparisons
2. `silver/refint.py` - Referential integrity
3. `silver/bizrule.py` - Rule evaluation
4. `silver/distrib.py` - Distribution shift

**Layer 4 - Freshness:**
1. `silver/freshness.py` - Staleness check
2. `silver/sla.py` - SLA compliance
3. `silver/pipeline.py` - Duration monitoring
4. `silver/dependency.py` - Chain tracking

**Support Skills:**
1. `silver/rootcause.py` - Attribution
2. `silver/incident.py` - Incident creation
3. `silver/escalate.py` - Escalation
4. `silver/quarantine.py` - Dataset isolation

### Phase 4: Create Services

Create new services in `src/services/`:

1. `schema_registry.py` - Load and cache schema contracts
2. `rule_engine.py` - Evaluate business rules
3. `freshness_watcher.py` - Monitor data freshness (runs on scheduler)
4. `silver_validator.py` - Coordinate all three layers

---

## Testing

### Run Existing Tests First

```bash
# Ensure Bronze tests still pass
pytest tests/ -v

# Check coverage
pytest tests/ --cov=src --cov-report=html
```

### Write Silver Tests

Example test structure:

```python
# tests/silver/unit/skills/test_schema.py
import pytest
from src.skills.silver.schema import validate_schema

def test_schema_valid_data():
    """Valid data passes schema validation."""
    schema = {"required": ["id"], "properties": {"id": {"type": "string"}}}
    data = [{"id": "test-001"}]
    result = validate_schema(data, schema)
    assert result.valid == True
    assert len(result.anomalies) == 0

def test_schema_missing_required_column():
    """Missing required column raises SC-001."""
    schema = {"required": ["id", "name"], "properties": {...}}
    data = [{"id": "test-001"}]  # Missing 'name'
    result = validate_schema(data, schema)
    assert result.valid == False
    assert result.anomalies[0].failure_code == "SC-001"
```

---

## Integration with Existing Code

### Modify Orchestrator

In `src/services/orchestrator.py`, add Silver tier processing after Bronze:

```python
async def process_batch(self, batch: DataBatch) -> ValidationResult:
    # Run Bronze validation
    bronze_result = await self.validator.validate(batch)

    if not bronze_result.passed:
        return bronze_result  # Don't proceed to Silver if Bronze fails

    # NEW: Run Silver validation
    silver_result = await self.silver_validator.validate(batch)

    # Combine results
    return self._merge_results(bronze_result, silver_result)
```

### Extend Dashboard

In `dashboard/app.py`, add Silver tier health section:

```python
# Add to health display
st.subheader("Silver Tier Health")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Schema", f"{silver_health.schema_score}%")
with col2:
    st.metric("Business Logic", f"{silver_health.business_logic_score}%")
with col3:
    st.metric("Freshness", f"{silver_health.freshness_score}%")
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `specs/003-silver-tier-enforcement/spec.md` | Requirements |
| `specs/003-silver-tier-enforcement/plan.md` | Architecture |
| `specs/003-silver-tier-enforcement/data-model.md` | Entity definitions |
| `specs/003-silver-tier-enforcement/contracts/*.yaml` | API contracts |
| `.specify/memory/constitution.md` | Layer definitions |

---

## Common Tasks

### Add a New Schema Contract

1. Create JSON Schema file in `config/schemas/{source}.json`
2. Include `x-column-criticality` extension for severity
3. Schema is auto-loaded by SchemaRegistry

### Add a New Business Rule

1. Add rule to `config/rules/{source}.yaml`
2. Set appropriate `type`, `expression`, and `failure_code`
3. Rule is auto-loaded by RuleEngine

### Add a New SLA

1. Add definition to `config/sla/{source}.yaml`
2. Set `schedule` (cron), `freshness_threshold`, `latency_threshold`
3. FreshnessWatcher picks up on next check

---

## Next Steps

After completing Silver Tier:

1. Run `/sp.tasks` to generate detailed implementation tasks
2. Follow TDD: write failing tests first
3. Implement skills in order (Schema → Business Logic → Freshness)
4. Update dashboard with Silver tier visualization
5. End-to-end testing with sample data
