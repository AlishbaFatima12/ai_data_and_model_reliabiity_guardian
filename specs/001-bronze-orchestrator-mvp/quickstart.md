# Quickstart: Bronze Tier MVP with Orchestrator

**Feature**: `001-bronze-orchestrator-mvp`
**Date**: 2026-01-18

---

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git (for version control)

### Verify Python Version

```bash
python --version
# Expected: Python 3.11.x or higher
```

---

## Project Setup

### 1. Clone and Navigate

```bash
cd D:/ai_dmrg
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/macOS)
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install production dependencies
pip install pydantic>=2.5.0 watchdog>=4.0.0 apscheduler>=3.10.0 structlog>=24.0.0 pyyaml>=6.0

# Install development dependencies
pip install pytest>=8.0.0 pytest-cov>=4.0 pytest-asyncio>=0.23

# Or use requirements file (once created)
pip install -r requirements.txt
```

### 4. Create Directory Structure

```bash
# Create source directories
mkdir -p src/models src/services src/skills/bronze src/skills/util src/cli src/lib

# Create test directories
mkdir -p tests/unit/skills/bronze tests/unit/skills/util tests/unit/services
mkdir -p tests/integration tests/contract

# Create config and data directories
mkdir -p config/sample_data data/incoming data/checkpoints data/quarantine data/state
mkdir -p logs/audit logs/alerts
```

### 5. Create __init__.py Files

```bash
# Initialize Python packages
touch src/__init__.py
touch src/models/__init__.py
touch src/services/__init__.py
touch src/skills/__init__.py
touch src/skills/bronze/__init__.py
touch src/skills/util/__init__.py
touch src/cli/__init__.py
touch src/lib/__init__.py
touch tests/__init__.py
```

---

## Configuration

### Create Default Configuration

Create `config/default.yaml`:

```yaml
# DMRG-FTE Bronze MVP Configuration

orchestrator:
  watcher:
    enabled: true
    path: "./data/incoming"
    patterns:
      - "*.csv"
      - "*.json"
    recursive: false
    debounce_ms: 500

  scheduler:
    enabled: true
    jobs:
      - name: "heartbeat"
        interval_seconds: 60
        task: "emit_heartbeat"

  heartbeat:
    enabled: true
    interval_seconds: 60
    channel: "console"

  queue:
    max_size: 1000
    overflow_behavior: "persist"

validation:
  checkpoint_interval: 1000  # Records between checkpoints

logging:
  level: "INFO"
  format: "json"
  output: "console"  # console, file, or both
  audit_path: "./logs/audit"

storage:
  checkpoints: "./data/checkpoints"
  quarantine: "./data/quarantine"
  state: "./data/state"
```

### Create Sample Validation Rules

Create `config/validation_rules.yaml`:

```yaml
# Validation Rules for Bronze Tier

schema:
  fields:
    - name: id
      type: string
      required: true
      pattern: "^[A-Z0-9-]+$"
    - name: amount
      type: float
      required: true
      min: 0.0
      max: 1000000.0
    - name: customer_id
      type: string
      required: true
    - name: email
      type: string
      required: false
      pattern: "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$"
    - name: created_at
      type: datetime
      required: true

thresholds:
  expected_record_count:
    min: 10
    max: 100000
  null_tolerance:
    default: 0.01
    fields:
      email: 0.10

severity_weights:
  DV-001:
    impact: 0.8
    frequency: 0.5
  DV-002:
    impact: 0.4
    frequency: 0.2
  DV-003:
    impact: 0.6
    frequency: 0.5
  DV-004:
    impact: 0.9
    frequency: 0.4
  DV-005:
    impact: 0.7
    frequency: 0.4
  DV-006:
    impact: 0.5
    frequency: 0.5
  DV-007:
    impact: 0.85
    frequency: 0.3
  DV-008:
    impact: 0.7
    frequency: 0.2
```

---

## Sample Test Data

### Create Valid Test File

Create `config/sample_data/valid_batch.csv`:

```csv
id,amount,customer_id,email,created_at
ORD-001,150.00,CUST-001,john@example.com,2026-01-18T10:00:00Z
ORD-002,250.50,CUST-002,jane@example.com,2026-01-18T10:05:00Z
ORD-003,99.99,CUST-003,bob@example.com,2026-01-18T10:10:00Z
```

### Create Invalid Test File

Create `config/sample_data/invalid_batch.csv`:

```csv
id,amount,customer_id,email,created_at
ORD-001,150.00,CUST-001,john@example.com,2026-01-18T10:00:00Z
ORD-001,-50.00,CUST-002,invalid-email,2026-01-18T10:05:00Z
,250.50,CUST-003,,not-a-date
ORD-002,150.00,CUST-001,john@example.com,2026-01-18T10:00:00Z
```

Issues in invalid_batch.csv:
- Row 2: Duplicate ID (ORD-001), negative amount, invalid email format
- Row 3: Missing ID, missing email (within tolerance), invalid date
- Row 4: Duplicate of Row 1

---

## Running the Application

### Start Orchestrator (MVP CLI)

Once implemented, the CLI will support:

```bash
# Start the orchestrator (watch mode)
python -m src.cli.main start

# Check status
python -m src.cli.main status

# Manually trigger validation
python -m src.cli.main validate ./data/incoming/orders.csv

# View health score
python -m src.cli.main health

# Stop gracefully
python -m src.cli.main stop
```

### Expected Output

```
[2026-01-18 10:30:00] INFO  Orchestrator starting...
[2026-01-18 10:30:00] INFO  File watcher initialized: ./data/incoming
[2026-01-18 10:30:00] INFO  Scheduler initialized: 1 jobs scheduled
[2026-01-18 10:30:00] INFO  Orchestrator running (state=RUNNING)
[2026-01-18 10:31:00] INFO  ♥ Heartbeat | health=100 | queued=0 | uptime=60s
[2026-01-18 10:31:05] INFO  File detected: orders.csv
[2026-01-18 10:31:05] INFO  Validation started: batch-001
[2026-01-18 10:31:06] INFO  Validation complete: batch-001 | passed=true | score=100 | duration=450ms
```

---

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run with Coverage

```bash
pytest tests/ --cov=src --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Contract tests only
pytest tests/contract/ -v
```

---

## Development Workflow

### 1. Red-Green-Refactor Cycle

For each skill implementation:

1. **Red**: Write failing test
   ```bash
   pytest tests/unit/skills/bronze/test_count.py -v
   # Expected: FAILED
   ```

2. **Green**: Implement minimum code to pass
   ```bash
   pytest tests/unit/skills/bronze/test_count.py -v
   # Expected: PASSED
   ```

3. **Refactor**: Improve code quality
   ```bash
   pytest tests/unit/skills/bronze/test_count.py -v
   # Expected: PASSED (still)
   ```

### 2. Verify Against Contracts

```bash
# Run contract tests to verify data models
pytest tests/contract/ -v
```

### 3. Integration Testing

```bash
# Test full validation flow
pytest tests/integration/test_end_to_end.py -v
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Package not in PYTHONPATH | Add `src` to PYTHONPATH or use `-m` flag |
| `File not found: config/default.yaml` | Config missing | Create config files as shown above |
| `Permission denied: ./data/incoming` | Directory permissions | Check write permissions |
| `Watchdog not detecting files` | Windows file system events | Use polling observer fallback |

### Debug Mode

```bash
# Run with debug logging
DMRG_LOG_LEVEL=DEBUG python -m src.cli.main start
```

### Check Health Manually

```bash
# View current health state
cat data/state/health.json
```

---

## Next Steps

After completing setup:

1. Run `/sp.tasks` to generate implementation tasks
2. Begin with `bronze.count` skill implementation
3. Follow Red-Green-Refactor cycle
4. Complete all Bronze skills
5. Implement orchestrator
6. Integration testing
7. Documentation

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest --cov=src` | Run with coverage |
| `python -m src.cli.main start` | Start orchestrator |
| `python -m src.cli.main status` | Check status |
| `python -m src.cli.main health` | View health score |
