#!/usr/bin/env python
"""DMRG Demo - Generate sample data and run validation.

Run this script to see the dashboard in action with sample data.

Usage:
    python demo.py
    streamlit run dashboard/app.py
"""

import json
import csv
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

def generate_sample_csv(output_path: Path, num_records: int = 1000):
    """Generate a sample CSV file with realistic data quality issues."""
    print(f"Generating {num_records} sample records...")

    headers = ["id", "customer_name", "email", "amount", "date", "status", "region"]

    statuses = ["active", "pending", "completed", "cancelled"]
    regions = ["US-East", "US-West", "EU", "APAC"]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for i in range(num_records):
            # Introduce some data quality issues (about 5%)
            has_issue = random.random() < 0.05

            record = [
                str(uuid4())[:8],
                f"Customer_{i}" if not has_issue else "",  # Missing name
                f"user{i}@example.com" if not has_issue else "invalid-email",  # Invalid email
                round(random.uniform(10, 10000), 2) if not has_issue else -100,  # Negative amount
                (datetime.now() - timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
                random.choice(statuses),
                random.choice(regions),
            ]
            writer.writerow(record)

    print(f"  Created: {output_path}")
    return output_path


def generate_bronze_results(output_dir: Path, num_batches: int = 5):
    """Generate Bronze tier validation results."""
    print("Generating Bronze tier results...")

    for i in range(num_batches):
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d')}_{i:03d}"
        timestamp = (datetime.now(timezone.utc) - timedelta(hours=i)).isoformat()

        # Create some anomalies
        anomalies = []
        if random.random() < 0.4:
            anomalies.append({
                "id": str(uuid4()),
                "failure_code": "DV-002",
                "severity": random.choice(["WARNING", "CRITICAL"]),
                "root_cause": "Null values detected in required field 'customer_name'",
                "detected_at": timestamp,
                "affected_records": random.randint(10, 100),
            })
        if random.random() < 0.3:
            anomalies.append({
                "id": str(uuid4()),
                "failure_code": "DV-004",
                "severity": "WARNING",
                "root_cause": "Amount values outside expected range (0-50000)",
                "detected_at": timestamp,
                "affected_records": random.randint(5, 50),
            })

        result = {
            "id": str(uuid4()),
            "batch_id": batch_id,
            "passed": len(anomalies) == 0,
            "blocked": any(a["severity"] == "CRITICAL" for a in anomalies),
            "anomalies": anomalies,
            "overall_score": max(0, 100 - len(anomalies) * 15 - random.uniform(0, 10)),
            "duration_ms": random.uniform(100, 500),
            "records_processed": random.randint(800, 1200),
            "validated_at": timestamp,
        }

        result_path = output_dir / f"{batch_id}.json"
        with open(result_path, 'w') as f:
            json.dump(result, f, indent=2)

    print(f"  Created {num_batches} batch results in {output_dir}")


def generate_health_state(state_dir: Path, overall_score: float = 85.0):
    """Generate health state file."""
    print("Generating health state...")

    history = []
    score = 95.0
    for h in range(24):
        timestamp = (datetime.now(timezone.utc) - timedelta(hours=23-h)).isoformat()
        score = max(50, min(100, score + random.uniform(-3, 2)))
        history.append([timestamp, round(score, 1)])

    health = {
        "overall_score": overall_score,
        "component_scores": {
            "bronze": {
                "name": "Data Validation",
                "score": overall_score,
                "anomaly_count": random.randint(1, 5),
                "last_check": datetime.now(timezone.utc).isoformat(),
            }
        },
        "trend": "stable" if abs(history[-1][1] - history[-6][1]) < 5 else ("improving" if history[-1][1] > history[-6][1] else "degrading"),
        "active_anomalies": random.randint(1, 5),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "batches_evaluated": random.randint(100, 500),
        "history": history,
    }

    with open(state_dir / "health.json", 'w') as f:
        json.dump(health, f, indent=2)

    print(f"  Created: {state_dir / 'health.json'}")


def generate_silver_data(silver_dir: Path):
    """Generate Silver tier data."""
    print("Generating Silver tier data...")

    # Silver health state
    silver_health = {
        "overall_score": 82.5,
        "schema_layer": {
            "score": 88.0,
            "anomaly_count": 2,
            "critical_count": 0,
        },
        "business_logic_layer": {
            "score": 78.5,
            "anomaly_count": 3,
            "critical_count": 1,
        },
        "freshness_layer": {
            "score": 85.0,
            "anomaly_count": 1,
            "critical_count": 0,
        },
        "total_anomalies": 6,
        "blocking_issues": 1,
        "trend": "stable",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    state_dir = silver_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    with open(state_dir / "health.json", 'w') as f:
        json.dump(silver_health, f, indent=2)

    print(f"  Created: {state_dir / 'health.json'}")


def generate_gold_data(gold_dir: Path):
    """Generate Gold tier data."""
    print("Generating Gold tier data...")

    # Gold health state
    gold_health = {
        "overall_score": 79.0,
        "model_health_layer": {
            "score": 82.0,
            "anomaly_count": 2,
            "critical_count": 0,
        },
        "ethics_layer": {
            "score": 76.0,
            "anomaly_count": 1,
            "critical_count": 1,
        },
        "total_anomalies": 3,
        "blocking_issues": 1,
        "has_regulatory_risk": True,
        "trend": "degrading",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    state_dir = gold_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    with open(state_dir / "health.json", 'w') as f:
        json.dump(gold_health, f, indent=2)

    print(f"  Created: {state_dir / 'health.json'}")


def main():
    """Generate demo data for DMRG dashboard."""
    print("\n" + "="*60)
    print("DMRG Demo Data Generator")
    print("="*60 + "\n")

    # Setup paths
    base_path = Path(__file__).parent
    data_dir = base_path / "data"
    incoming_dir = data_dir / "incoming"
    results_dir = data_dir / "results"
    state_dir = data_dir / "state"
    silver_dir = data_dir / "silver"
    gold_dir = data_dir / "gold"

    # Create directories
    for d in [incoming_dir, results_dir, state_dir, silver_dir, gold_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Generate data
    generate_sample_csv(incoming_dir / "sample_data.csv", num_records=1000)
    generate_bronze_results(results_dir, num_batches=5)
    generate_health_state(state_dir, overall_score=85.0)
    generate_silver_data(silver_dir)
    generate_gold_data(gold_dir)

    print("\n" + "="*60)
    print("Demo data generated successfully!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Start the dashboard:")
    print("     streamlit run dashboard/app.py")
    print("")
    print("  2. Open in browser:")
    print("     http://localhost:8501")
    print("")
    print("To validate your own data:")
    print("  python -m src.cli.main validate data/incoming/your_file.csv")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
