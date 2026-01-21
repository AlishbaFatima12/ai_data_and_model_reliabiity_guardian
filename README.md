# Data & Model Reliability Guardian (DMRG)

**Always Watching, Always Alert**

An enterprise-grade data quality monitoring and validation system that continuously watches over organizational data and ML models, ensuring they remain accurate, timely, fair, and trustworthy.

---

## Overview

DMRG is a comprehensive data validation platform that implements a **Three-Tier Validation Model**:

| Tier | Focus | Layers |
|------|-------|--------|
| **Bronze** | Data Quality | Layer 1: Data Validation (nulls, types, ranges, duplicates) |
| **Silver** | Business Logic | Layer 2-4: Schema, Business Rules, Freshness/SLA |
| **Gold** | Ethics & Bias | Layer 5-6: Model Health, Ethics Monitoring |

```
┌─────────────────────────────────────────────────────────────────┐
│                     THREE-TIER VALIDATION                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   DATA  ───▶  BRONZE  ───▶  SILVER  ───▶  GOLD  ───▶  CLEAN    │
│              (Quality)    (Logic)       (Ethics)     DATA      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

### Detection & Validation
- Null/Missing value detection with column-level breakdown
- Data type validation and range checking
- Z-score outlier detection
- Duplicate record identification
- Cross-field logic validation
- PII/sensitive data detection
- Ethics & bias monitoring

### Monitoring & Alerting
- Real-time health scoring (0-100)
- Severity classification (INFO, WARNING, CRITICAL)
- Automated alert generation
- SLA and freshness tracking
- Trend analysis

### Dashboard
- Executive summary with plain language explanations
- Drill-down to affected rows and columns
- Compliance export (JSON, CSV, TXT reports)
- 3D modern UI design

---

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/AlishbaFatima12/ai_data_and_model_reliabiity_guardian.git
cd ai_data_and_model_reliabiity_guardian

# Install dependencies
pip install -r requirements.txt
# Or using pyproject.toml
pip install -e .
```

### Run Dashboard

**Option 1: Batch File (Windows)**
```bash
# Double-click start_dashboard.bat
```

**Option 2: Command Line**
```bash
python -m streamlit run dashboard/app.py --server.port 8650
```

**Option 3: Python**
```python
from src.services import Validator

validator = Validator()
result = validator.validate_file("your_data.csv")
print(f"Health Score: {result.health_score}%")
print(f"Anomalies: {len(result.anomalies)}")
```

Open browser at: **http://localhost:8650**

---

## Architecture

```
DMRG/
├── src/
│   ├── models/           # Pydantic data models
│   ├── services/         # Core validation services
│   │   ├── validator.py         # Bronze tier
│   │   ├── silver_validator.py  # Silver tier
│   │   └── gold_validator.py    # Gold tier
│   ├── skills/           # Validation skills
│   │   ├── bronze/       # Null, type, range, outlier detection
│   │   ├── silver/       # Schema, business logic, freshness
│   │   └── gold/         # Model drift, ethics, fairness
│   └── lib/              # Constants, config, utilities
│
├── dashboard/
│   ├── app.py            # Streamlit dashboard
│   └── services/         # Data loading, health calculation
│
├── config/               # Validation rules, schemas
├── data/                 # Results, quarantine zone
└── tests/                # Test suite
```

---

## Validation Layers

### Layer 1: Bronze - Data Validation
| Code | Issue | Description |
|------|-------|-------------|
| DV-001 | Missing Records | Batch below expected count |
| DV-002 | Excess Records | Batch above expected count |
| DV-003 | Null Violation | Required field is null |
| DV-004 | Type Mismatch | Value doesn't match declared type |
| DV-005 | Range Violation | Value outside boundaries |
| DV-006 | Format Violation | Value doesn't match pattern |
| DV-007 | Duplicate Record | Exact duplicate found |
| DV-008 | Encoding Error | Invalid character encoding |

### Layers 2-4: Silver - Schema, Logic, Freshness
- Schema contract enforcement (SC-001 to SC-008)
- Business logic validation (BL-001 to BL-008)
- Freshness and SLA monitoring (FS-001 to FS-008)

### Layers 5-6: Gold - Model & Ethics
- Model health monitoring (ML-001 to ML-008)
- Ethics and bias detection (ET-001 to ET-008)
- PII exposure detection
- Protected attribute analysis

---

## Example Output

When you upload a CSV file, DMRG detects:

```
BRONZE TIER FINDINGS:
  DV-003: 2,446 null values in 'age' column (48.9%)
  DV-005: 41 outliers in 'income' column (Z-score > 3)

SILVER TIER FINDINGS:
  BL-006: 308 logic violations - minors with income > $50k

GOLD TIER FINDINGS:
  ET-006: PII exposure in 'email' column
  ET-005: 847 minor records requiring consent verification
```

---

## Compliance Support

DMRG helps with regulatory compliance:
- **GDPR** - Data lineage, processing records
- **CCPA** - Data inventory, access tracking
- **COPPA** - Minor data handling
- **SOX** - Financial data controls
- **HIPAA** - PHI access monitoring

---

## Documentation

- [Full Presentation](DMRG_Presentation.md) - Comprehensive project overview
- [Constitution](/.specify/memory/constitution.md) - System design principles
- [Bronze Spec](specs/001-bronze-orchestrator-mvp/spec.md) - Bronze tier specification
- [Silver Spec](specs/003-silver-tier-enforcement/spec.md) - Silver tier specification
- [Dashboard Spec](specs/002-unified-dashboard/spec.md) - Dashboard specification

---

## Technology Stack

- **Python 3.11+** - Core engine
- **Streamlit 1.33+** - Dashboard UI
- **Plotly 5.x** - Charts and visualizations
- **Pydantic 2.x** - Data models
- **Pandas** - Data processing
- **NumPy** - Statistical calculations

---

## License

This project is proprietary software.

---

## Author

**DMRG Development Team**

---

*"Catch data problems before they cause harm"*
