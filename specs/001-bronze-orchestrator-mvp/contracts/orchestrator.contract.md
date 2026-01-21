# Contract: Orchestrator

**Component**: Orchestrator Service
**Version**: 1.0.0
**Feature**: `001-bronze-orchestrator-mvp`

---

## Purpose

The Orchestrator is the central coordination engine that:
1. Detects data arrival events (file watcher)
2. Executes scheduled validations (scheduler)
3. Emits heartbeat signals (health monitoring)
4. Manages the event queue (FIFO processing)
5. Coordinates validation workflow execution

---

## Event Types

### Input Events

| Event Type | Source | Trigger | Response |
|------------|--------|---------|----------|
| `DATA_ARRIVAL` | File Watcher | New file in monitored directory | Queue validation job |
| `SCHEDULED_CHECK` | Scheduler | Timer interval elapsed | Execute scheduled task |
| `MANUAL_TRIGGER` | CLI/API | User command | Queue validation job |
| `HEARTBEAT_TICK` | Internal | 60-second timer | Emit health signal |

### Output Events

| Event Type | Target | Trigger | Payload |
|------------|--------|---------|---------|
| `VALIDATION_STARTED` | Logger | Job begins | batch_id, timestamp |
| `VALIDATION_COMPLETE` | Logger/Alerter | Job ends | ValidationResult |
| `ALERT_GENERATED` | Alert Channel | Anomaly detected | Alert |
| `HEARTBEAT` | Health Monitor | Timer tick | health_status, timestamp |
| `ERROR` | Logger/Alerter | Failure | error_details |

---

## Configuration Schema

```yaml
# config/orchestrator.yaml
orchestrator:
  # File watching configuration
  watcher:
    enabled: true
    path: "./data/incoming"
    patterns:
      - "*.csv"
      - "*.json"
    recursive: false
    debounce_ms: 500  # Wait for file write to complete

  # Scheduler configuration
  scheduler:
    enabled: true
    jobs:
      - name: "freshness_check"
        interval_seconds: 30
        task: "check_freshness"
      - name: "health_recalculation"
        interval_seconds: 300  # 5 minutes
        task: "recalculate_health"

  # Heartbeat configuration
  heartbeat:
    enabled: true
    interval_seconds: 60
    channel: "console"  # console, file, or both

  # Queue configuration
  queue:
    max_size: 1000
    overflow_behavior: "persist"  # persist or reject

  # Error handling
  error_handling:
    max_retries: 3
    retry_delay_seconds: 5
    exponential_backoff: true
```

---

## State Machine

```
                     ┌─────────────────┐
                     │    STARTING     │
                     └────────┬────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │                 RUNNING                  │
        │  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
        │  │ Watcher │  │Scheduler│  │Heartbeat│  │
        │  │ Active  │  │ Active  │  │ Active  │  │
        │  └─────────┘  └─────────┘  └─────────┘  │
        └───────────────────┬─────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│    DEGRADED     │ │   ERROR     │ │   STOPPING      │
│ (partial work)  │ │ (recoverable)│ │  (graceful)     │
└────────┬────────┘ └──────┬──────┘ └────────┬────────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           ▼
                  ┌─────────────────┐
                  │    STOPPED      │
                  └─────────────────┘
```

### State Transitions

| From | To | Trigger |
|------|----|---------|
| STARTING | RUNNING | All components initialized |
| STARTING | ERROR | Initialization failure |
| RUNNING | DEGRADED | Component failure (non-critical) |
| RUNNING | ERROR | Critical failure |
| RUNNING | STOPPING | Shutdown signal |
| DEGRADED | RUNNING | Component recovered |
| DEGRADED | ERROR | Additional failure |
| ERROR | RUNNING | Successful recovery |
| ERROR | STOPPING | Unrecoverable or shutdown |
| STOPPING | STOPPED | Graceful shutdown complete |

---

## API Contract

### Start Orchestrator

```python
def start() -> OrchestratorStatus:
    """
    Start the orchestrator and all components.

    Returns:
        OrchestratorStatus with state=RUNNING on success

    Raises:
        OrchestratorError: If initialization fails
    """
```

### Stop Orchestrator

```python
def stop(graceful: bool = True) -> OrchestratorStatus:
    """
    Stop the orchestrator.

    Args:
        graceful: If True, wait for in-flight jobs to complete

    Returns:
        OrchestratorStatus with state=STOPPED
    """
```

### Get Status

```python
def get_status() -> OrchestratorStatus:
    """
    Get current orchestrator status.

    Returns:
        OrchestratorStatus with:
        - state: Current state (STARTING, RUNNING, etc.)
        - uptime_seconds: Time since start
        - jobs_processed: Total jobs completed
        - jobs_queued: Current queue depth
        - last_heartbeat: Timestamp of last heartbeat
        - component_status: Dict of component states
    """
```

### Manual Validation Trigger

```python
def trigger_validation(source: str) -> str:
    """
    Manually trigger validation for a source.

    Args:
        source: Path to file or data source identifier

    Returns:
        job_id: Unique identifier for the queued job

    Raises:
        SourceNotFoundError: If source doesn't exist
        QueueFullError: If queue is at capacity
    """
```

---

## Response Schemas

### OrchestratorStatus

```json
{
  "state": "RUNNING",
  "uptime_seconds": 3600,
  "jobs_processed": 150,
  "jobs_queued": 3,
  "jobs_failed": 2,
  "last_heartbeat": "2026-01-18T10:30:00Z",
  "component_status": {
    "watcher": "active",
    "scheduler": "active",
    "heartbeat": "active",
    "queue": "healthy"
  },
  "health_score": 95
}
```

### HeartbeatSignal

```json
{
  "timestamp": "2026-01-18T10:30:00Z",
  "state": "RUNNING",
  "health_score": 95,
  "jobs_in_flight": 1,
  "last_validation": "2026-01-18T10:29:45Z",
  "uptime_seconds": 3600
}
```

---

## Error Handling

### Error Categories

| Category | Response | Example |
|----------|----------|---------|
| Transient | Retry with backoff | File locked, network timeout |
| Recoverable | Log + continue | Single validation failure |
| Critical | Alert + degrade | Watcher initialization failed |
| Fatal | Alert + shutdown | Storage failure |

### Error Response Contract

```json
{
  "error_id": "err-001",
  "category": "recoverable",
  "component": "validator",
  "message": "Validation failed for batch-001",
  "timestamp": "2026-01-18T10:30:00Z",
  "context": {
    "batch_id": "batch-001",
    "source": "/data/incoming/orders.csv"
  },
  "retry_count": 0,
  "next_retry": "2026-01-18T10:30:05Z"
}
```

---

## Invariants

1. Heartbeat MUST emit every 60 seconds (±5 seconds tolerance)
2. Queue MUST process events in FIFO order
3. Orchestrator MUST NOT shutdown on recoverable errors
4. All errors MUST be logged within 60 seconds
5. State transitions MUST be logged to audit trail
6. In-flight jobs MUST complete or checkpoint before shutdown

---

## Performance Requirements

| Metric | Requirement | Source |
|--------|-------------|--------|
| Event detection latency | <5 seconds | FR-012, SC-001 |
| Queue throughput | 100 events/second | Constitution 9.1 |
| Heartbeat reliability | 99.9% on-time | Constitution 2.1 |
| Recovery time | <60 seconds | SC-006 |

---

## Monitoring Integration

### Metrics Emitted

| Metric | Type | Description |
|--------|------|-------------|
| `orchestrator_state` | Gauge | Current state (0=stopped, 1=running, 2=degraded) |
| `orchestrator_uptime_seconds` | Counter | Seconds since start |
| `orchestrator_jobs_total` | Counter | Total jobs processed |
| `orchestrator_jobs_queued` | Gauge | Current queue depth |
| `orchestrator_errors_total` | Counter | Total errors by category |
| `orchestrator_heartbeat_timestamp` | Gauge | Last heartbeat Unix timestamp |

### Health Check Endpoint

For future API integration (MVP: CLI status command):

```
GET /health

Response:
{
  "status": "healthy",  // healthy, degraded, unhealthy
  "checks": {
    "watcher": "pass",
    "scheduler": "pass",
    "heartbeat": "pass",
    "storage": "pass"
  },
  "timestamp": "2026-01-18T10:30:00Z"
}
```
