# Quickstart: Unified Monitoring Dashboard

**Feature**: 002-unified-dashboard
**Date**: 2026-01-18

## Prerequisites

1. Python 3.11+ installed
2. Bronze Tier MVP running (or sample data available)
3. Dependencies installed (see below)

## Installation

```bash
# From project root
cd D:\ai_dmrg

# Install new dependencies
pip install streamlit>=1.33.0 plotly>=5.18.0

# Or with pyproject.toml (after update)
pip install -e ".[dashboard]"
```

## Running the Dashboard

```bash
# Start Streamlit dashboard
streamlit run dashboard/app.py

# Dashboard opens at http://localhost:8501
```

## Quick Test

1. **Generate sample data** (if no validation results exist):
   ```bash
   python -m src.cli.main validate config/sample_data/valid_batch.csv
   python -m src.cli.main validate config/sample_data/invalid_batch.csv
   ```

2. **Open dashboard**: http://localhost:8501

3. **Verify components**:
   - Executive Summary shows health score (0-100)
   - Layer Health shows Bronze tier score
   - Incident Timeline shows recent validations
   - Click any metric to drill down

## Development Setup

```bash
# Install dev dependencies
pip install -e ".[dev,dashboard]"

# Run tests
pytest tests/dashboard/ -v

# Run with hot reload
streamlit run dashboard/app.py --server.runOnSave true
```

## Configuration

Dashboard reads from existing config + dashboard-specific settings:

```yaml
# config/dashboard.yaml (optional overrides)
dashboard:
  refresh_interval_seconds: 30
  max_timeline_events: 100
  default_time_range_hours: 24
  theme:
    primary_color: "#00A67E"
    warning_color: "#FFB020"
    critical_color: "#DC3545"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No data available" | Run validation on sample data first |
| Port 8501 in use | Use `--server.port 8502` |
| Slow loading | Reduce time range or increase pagination |
| Charts not rendering | Ensure plotly installed |

## File Structure

```
dashboard/
├── app.py                      # Main entry point
├── components/
│   ├── executive_summary.py    # Health score panel
│   ├── layer_health.py         # Per-layer cards
│   ├── business_impact.py      # Impact translations
│   ├── incident_timeline.py    # Timeline chart
│   └── drill_down.py           # Progressive details
├── services/
│   ├── data_loader.py          # Read from Bronze output
│   ├── health_calculator.py    # Compute aggregates
│   ├── impact_translator.py    # Business language
│   └── timeline_builder.py     # Build events
└── config/
    └── translations.yaml       # Impact translation rules
```

## Next Steps

After dashboard is running:

1. **Test with real data**: Run Bronze validator on actual data files
2. **Configure alerts**: Set up business impact translations in `translations.yaml`
3. **Customize views**: Adjust persona defaults in `dashboard.yaml`
