# Data & Model Reliability Guardian (DMRG)
## Project Presentation

---

# Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [System Architecture](#4-system-architecture)
5. [Three-Tier Validation Model](#5-three-tier-validation-model)
6. [Dashboard & User Interface](#6-dashboard--user-interface)
7. [Technical Implementation](#7-technical-implementation)
8. [Live Demo Example](#8-live-demo-example)
9. [Business Value](#9-business-value)
10. [Future Roadmap](#10-future-roadmap)

---

# 1. Executive Summary

## What is DMRG?

**Data & Model Reliability Guardian (DMRG)** is a data quality monitoring and validation system that continuously validates data across three tiers:

- **Accurate** - Data meets quality standards
- **Compliant** - Data follows business rules
- **Ethical** - No PII exposure or bias issues

## The Three-Tier Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     DMRG VALIDATION FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   CSV FILE  ──▶  🥉 BRONZE  ──▶  🥈 SILVER  ──▶  🏆 GOLD       │
│                  (Quality)      (Logic)        (Ethics)         │
│                                                                 │
│   Checks:        Nulls          Schema         PII Detection    │
│                  Types          Business       Protected Attrs  │
│                  Ranges         Rules          Minor Data       │
│                  Outliers       Freshness      Bias Detection   │
│                  Duplicates                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

# 2. Problem Statement

## The Data Quality Crisis

Organizations face critical challenges:

| Risk | Consequence |
|------|-------------|
| **Corrupt Data** | Incorrect business decisions |
| **Missing Values** | Incomplete analysis |
| **Logic Violations** | Invalid calculations |
| **PII Exposure** | Regulatory fines (GDPR: up to €20M) |
| **Biased Data** | Unfair ML model outputs |

## Manual Analysis Problems

| Manual Approach | DMRG Solution |
|-----------------|---------------|
| Hours to detect issues | Seconds |
| Spot-check sampling | 100% coverage |
| Human error prone | Deterministic |
| No audit trail | Full logging |

---

# 3. Solution Overview

## What DMRG Does

```
┌─────────────────────────────────────────────────────────────────┐
│                    DMRG CAPABILITIES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  DETECTION                        MONITORING                    │
│  ─────────                        ──────────                    │
│  ✓ Null/Missing values            ✓ Health scores (0-100)       │
│  ✓ Type mismatches                ✓ Severity levels             │
│  ✓ Range violations               ✓ Trend tracking              │
│  ✓ Z-score outliers               ✓ Real-time dashboard         │
│  ✓ Duplicate records                                            │
│  ✓ Business logic violations      REMEDIATION                   │
│  ✓ PII exposure                   ───────────                   │
│  ✓ Protected attribute issues     ✓ Quarantine bad records      │
│                                   ✓ Detailed anomaly reports    │
│                                   ✓ Affected row identification │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

# 4. System Architecture

## High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      SYSTEM ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────┘

    INPUT                      DMRG ENGINE                 OUTPUT
    ─────                      ───────────                 ──────

  ┌─────────┐              ┌────────────────┐          ┌──────────┐
  │  CSV    │              │                │          │Dashboard │
  │  File   │─────────────▶│  VALIDATOR     │─────────▶│   UI     │
  │ Upload  │              │                │          │          │
  └─────────┘              │  Bronze ──┐    │          └──────────┘
                           │           │    │
                           │  Silver ──┼───▶│──────────▶┌──────────┐
                           │           │    │          │  Alerts  │
                           │  Gold ────┘    │          └──────────┘
                           │                │
                           └────────────────┘          ┌──────────┐
                                  │                    │Quarantine│
                                  └───────────────────▶│  Zone    │
                                                       └──────────┘
```

## Data Flow

```
1. USER UPLOADS CSV
        │
        ▼
2. BRONZE VALIDATION
   • Check for nulls in each column
   • Validate data types
   • Check value ranges
   • Detect outliers (Z-score > 3)
   • Find duplicates
        │
        ▼
3. SILVER VALIDATION
   • Validate against schema
   • Check business logic rules
   • Auto-detect impossible combinations
   • Monitor data freshness
        │
        ▼
4. GOLD VALIDATION
   • Scan for PII (emails, phones, SSN)
   • Check protected attributes
   • Flag minor data (age < 18)
   • Detect distribution imbalance
        │
        ▼
5. RESULTS DISPLAYED
   • Health scores per tier
   • Anomaly cards with details
   • Affected columns and row counts
   • Drill-down to view records
```

---

# 5. Three-Tier Validation Model

## Tier Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  🥉 BRONZE TIER - Layer 1: Data Validation                      │
│  ─────────────────────────────────────────                      │
│  Entry point. Catches fundamental quality issues.               │
│                                                                 │
│  Skills: null, type_check, range_check, outlier, duplicate      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  🥈 SILVER TIER - Layers 2, 3, 4                                │
│  ─────────────────────────────────────────                      │
│  Layer 2: Schema validation                                     │
│  Layer 3: Business logic (auto_logic rules)                     │
│  Layer 4: Freshness monitoring                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  🏆 GOLD TIER - Layers 5, 6                                     │
│  ─────────────────────────────────────────                      │
│  Layer 5: Model health (basic)                                  │
│  Layer 6: Ethics - PII, bias, protected attributes              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5.1 Bronze Tier - Data Validation

### What It Checks

| Check | Description | Example |
|-------|-------------|---------|
| **Null Detection** | Finds missing values | "age" column has 2,446 nulls |
| **Type Validation** | Ensures correct types | "income" should be numeric |
| **Range Check** | Values within bounds | Age should be 0-120 |
| **Outlier Detection** | Z-score analysis | Income values > 3 std dev |
| **Duplicate Detection** | Exact matches | Same record appears twice |

### Failure Codes

| Code | Name | Severity |
|------|------|----------|
| DV-003 | Null Violation | CRITICAL |
| DV-004 | Type Mismatch | CRITICAL |
| DV-005 | Range Violation | WARNING |
| DV-007 | Duplicate Record | WARNING |

---

## 5.2 Silver Tier - Business Logic

### Auto-Logic Validation (Automatic Rules)

These rules run automatically without configuration:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTO-LOGIC RULES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  RULE: age_income_logic                                         │
│  CHECK: Age < 16 AND Income > $50,000                           │
│  RESULT: Flags logically impossible combinations                │
│                                                                 │
│  RULE: negative_income                                          │
│  CHECK: Income < 0                                              │
│  RESULT: Catches data entry errors                              │
│                                                                 │
│  RULE: zero_tenure_purchases                                    │
│  CHECK: Days on platform = 0 AND Has purchases                  │
│  RESULT: Identifies impossible scenarios                        │
│                                                                 │
│  RULE: invalid_age_range                                        │
│  CHECK: Age < 0 OR Age > 120                                    │
│  RESULT: Validates realistic boundaries                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Failure Codes

| Code | Name | Description |
|------|------|-------------|
| BL-001 | Cross-Field Inconsistency | Related fields incompatible |
| BL-006 | Domain Rule Violation | Business constraint broken |

---

## 5.3 Gold Tier - Ethics & PII

### Auto-Ethics Validation

Runs automatically to detect:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTO-ETHICS CHECKS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  PII DETECTION (Pattern Matching):                              │
│  • Email addresses (user@domain.com)                            │
│  • Phone numbers (+1-555-123-4567)                              │
│  • Social Security Numbers (123-45-6789)                        │
│  • Credit card numbers (4111-1111-1111-1111)                    │
│  • IP addresses (192.168.1.1)                                   │
│                                                                 │
│  PROTECTED ATTRIBUTES:                                          │
│  • Gender distribution imbalance (>95% one group)               │
│  • Age group representation                                     │
│  • Race/ethnicity columns flagged                               │
│                                                                 │
│  CONSENT REQUIREMENTS:                                          │
│  • Minor data (age < 18) flagged                                │
│  • COPPA/GDPR compliance alerts                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Failure Codes

| Code | Name | Regulatory Reference |
|------|------|---------------------|
| ET-005 | Consent Violation | COPPA, GDPR Article 8 |
| ET-006 | PII Exposure Risk | GDPR, CCPA |
| ET-001 | Demographic Disparity | EEOC Guidelines |

---

# 6. Dashboard & User Interface

## Main Dashboard View

```
┌─────────────────────────────────────────────────────────────────┐
│                    DMRG DASHBOARD                                │
│                http://localhost:8650                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            EXECUTIVE SUMMARY                              │ │
│  │                                                           │ │
│  │   Overall Health: 78%  [████████░░]  YELLOW              │ │
│  │                                                           │ │
│  │   Active Issues: 🔴 2 Critical  🟡 5 Warning  🔵 12 Info  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │🥉 BRONZE    │  │🥈 SILVER    │  │🏆 GOLD      │            │
│  │   78%       │  │   25%       │  │   70%       │            │
│  │ 3 anomalies │  │ 3 anomalies │  │ 2 anomalies │            │
│  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │            ANOMALY FEED                                   │ │
│  │                                                           │ │
│  │  🔴 DV-003 | Null values in 'age' | 2,446 rows           │ │
│  │  🟡 BL-006 | Logic violation | 308 rows                   │ │
│  │  🟡 ET-006 | PII in 'email' | GDPR risk                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Dashboard Features

| Feature | Description |
|---------|-------------|
| **Health Scores** | 0-100 score per tier with color coding |
| **Anomaly Cards** | Shows failure code, description, affected rows |
| **Column Breakdown** | Chart showing which columns have issues |
| **Drill-Down** | Click to see affected records |
| **Compliance Export** | Download JSON, CSV, TXT reports |

---

# 7. Technical Implementation

## Technology Stack

| Component | Technology |
|-----------|------------|
| Core Engine | Python 3.11+ |
| Data Models | Pydantic 2.x |
| Dashboard | Streamlit 1.33+ |
| Charts | Plotly 5.x |
| Data Processing | Pandas, NumPy |
| Logging | Structlog (JSON) |

## Project Structure

```
DMRG/
├── src/
│   ├── services/
│   │   ├── validator.py         # Bronze validation
│   │   ├── silver_validator.py  # Silver validation
│   │   └── gold_validator.py    # Gold validation
│   │
│   ├── skills/
│   │   ├── bronze/
│   │   │   ├── null.py          # Null detection
│   │   │   ├── type_check.py    # Type validation
│   │   │   ├── range_check.py   # Range checking
│   │   │   ├── outlier.py       # Z-score outliers
│   │   │   └── quarantine.py    # Isolate bad records
│   │   │
│   │   ├── silver/
│   │   │   ├── schema.py        # Schema validation
│   │   │   └── auto_logic.py    # Auto business rules
│   │   │
│   │   └── gold/
│   │       └── auto_ethics.py   # PII & ethics checks
│   │
│   └── models/                  # Pydantic models
│
├── dashboard/
│   └── app.py                   # Streamlit dashboard
│
├── data/
│   ├── results/                 # Validation results
│   └── quarantine/              # Isolated bad records
│
└── start_dashboard.bat          # Easy launcher
```

## How to Run

**Option 1: Batch File**
```
Double-click: start_dashboard.bat
```

**Option 2: Command Line**
```bash
python -m streamlit run dashboard/app.py --server.port 8650
```

**Option 3: Python Code**
```python
from src.services import Validator

validator = Validator()
result = validator.validate_file("data.csv")

print(f"Health Score: {result.health_score}%")
print(f"Anomalies Found: {len(result.anomalies)}")
```

---

# 8. Live Demo Example

## Sample Data: CLV Dataset

When you upload a customer lifetime value (CLV) dataset, DMRG detects:

### Bronze Tier Findings
```
┌─────────────────────────────────────────────────────────────────┐
│  🔴 CRITICAL | DV-003                                           │
│  Null values detected in required field                         │
│  Column: age | Affected: 2,446 rows (48.9%)                     │
├─────────────────────────────────────────────────────────────────┤
│  🟡 WARNING | DV-005                                            │
│  Outliers detected (Z-score > 3)                                │
│  Column: income | Affected: 41 rows                             │
├─────────────────────────────────────────────────────────────────┤
│  🟡 WARNING | DV-005                                            │
│  Outliers detected (Z-score > 3)                                │
│  Column: total_purchases | Affected: 59 rows                    │
└─────────────────────────────────────────────────────────────────┘
```

### Silver Tier Findings
```
┌─────────────────────────────────────────────────────────────────┐
│  🟡 WARNING | BL-006                                            │
│  Business logic violation: age_income_logic                     │
│  "Person under 16 with income over $50,000"                     │
│  Affected: 308 rows                                             │
└─────────────────────────────────────────────────────────────────┘
```

### Gold Tier Findings
```
┌─────────────────────────────────────────────────────────────────┐
│  🔴 CRITICAL | ET-006                                           │
│  PII Exposure Risk detected                                     │
│  Fields: email | Regulatory: GDPR, CCPA                         │
│  Remediation: Apply data masking before processing              │
├─────────────────────────────────────────────────────────────────┤
│  🟡 WARNING | ET-005                                            │
│  Minor data detected (age < 18)                                 │
│  Affected: 847 records                                          │
│  Regulatory: COPPA, GDPR Article 8                              │
└─────────────────────────────────────────────────────────────────┘
```

---

# 9. Business Value

## Why Use DMRG?

| Benefit | Description |
|---------|-------------|
| **Speed** | Detect issues in seconds, not hours |
| **Coverage** | 100% of data validated, not samples |
| **Consistency** | Same rules applied every time |
| **Compliance** | GDPR, CCPA, COPPA support |
| **Audit Trail** | Full logging of all decisions |

## Problems Prevented

| Problem | DMRG Prevention |
|---------|-----------------|
| Bad data in reports | Bronze tier catches nulls/types |
| Impossible values | Silver auto-logic flags violations |
| PII data breaches | Gold tier detects emails/phones |
| Biased datasets | Protected attribute monitoring |
| Compliance failures | Automatic regulatory flagging |

---

# 10. Future Roadmap

## Current Status (MVP Complete)

- ✅ Bronze tier validation
- ✅ Silver tier with auto-logic
- ✅ Gold tier with auto-ethics
- ✅ Streamlit dashboard
- ✅ Quarantine functionality
- ✅ Compliance export

## Planned Enhancements

| Phase | Features |
|-------|----------|
| **Phase 2** | Predictive warnings, cost attribution |
| **Phase 3** | Slack/email alerts, multi-user support |
| **Phase 4** | ML-based anomaly detection |

---

# Summary

## DMRG at a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│           DATA & MODEL RELIABILITY GUARDIAN                     │
│                                                                 │
│   🥉 BRONZE ──▶ 🥈 SILVER ──▶ 🏆 GOLD                          │
│    Quality       Logic         Ethics                           │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  WORKING FEATURES:                                      │  │
│   │  ✓ Null/Type/Range detection                            │  │
│   │  ✓ Z-score outlier detection                            │  │
│   │  ✓ Auto business logic rules                            │  │
│   │  ✓ PII detection (email, phone, SSN)                    │  │
│   │  ✓ Protected attribute monitoring                       │  │
│   │  ✓ Minor data flagging                                  │  │
│   │  ✓ Quarantine for bad records                           │  │
│   │  ✓ Real-time dashboard                                  │  │
│   │  ✓ Compliance export                                    │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   START: Double-click start_dashboard.bat                       │
│   URL: http://localhost:8650                                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

**Version**: 1.0.0
**Last Updated**: 2026-01-21
**Status**: MVP Complete
