"""CLI entry point for DMRG-FTE."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.lib.config import load_config, validate_config_on_startup
from src.lib.logger import configure_logging, get_logger
from src.services.orchestrator import Orchestrator, OrchestratorConfig
from src.services.validator import Validator
from src.services.alerter import Alerter
from src.skills.util.health import HealthSkill
from src.skills.bronze.quarantine import QuarantineSkill


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    parser = argparse.ArgumentParser(
        prog="dmrg",
        description="DMRG-FTE: Data & Model Reliability Guardian",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the orchestrator")
    start_parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="Path to configuration file",
    )
    start_parser.add_argument(
        "--watch", "-w",
        type=str,
        default=None,
        help="Directory to watch for incoming files",
    )

    # Stop command
    subparsers.add_parser("stop", help="Stop the orchestrator (sends signal)")

    # Status command
    subparsers.add_parser("status", help="Show orchestrator status")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Manually validate a file")
    validate_parser.add_argument(
        "path",
        type=str,
        help="Path to file to validate",
    )
    validate_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results as JSON",
    )

    # Health command
    health_parser = subparsers.add_parser("health", help="Show current health score")
    health_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    # Results command
    results_parser = subparsers.add_parser("results", help="List recent validation results")
    results_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of results to show",
    )
    results_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    # Issues command
    issues_parser = subparsers.add_parser("issues", help="List recent anomalies")
    issues_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of issues to show",
    )
    issues_parser.add_argument(
        "--severity", "-s",
        type=str,
        choices=["INFO", "WARNING", "CRITICAL"],
        default=None,
        help="Filter by severity",
    )
    issues_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    # Quarantine command
    quarantine_parser = subparsers.add_parser("quarantine", help="List quarantined records")
    quarantine_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of records to show",
    )
    quarantine_parser.add_argument(
        "--batch", "-b",
        type=str,
        default=None,
        help="Filter by batch ID",
    )
    quarantine_parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON",
    )

    # Version command
    subparsers.add_parser("version", help="Show version information")

    args = parser.parse_args()

    # Handle commands
    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "start":
            return cmd_start(args)
        elif args.command == "stop":
            return cmd_stop(args)
        elif args.command == "status":
            return cmd_status(args)
        elif args.command == "validate":
            return cmd_validate(args)
        elif args.command == "health":
            return cmd_health(args)
        elif args.command == "results":
            return cmd_results(args)
        elif args.command == "issues":
            return cmd_issues(args)
        elif args.command == "quarantine":
            return cmd_quarantine(args)
        elif args.command == "version":
            return cmd_version(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_start(args: argparse.Namespace) -> int:
    """Start the orchestrator.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    # Load and validate configuration
    config = load_config(args.config)
    is_valid, errors = validate_config_on_startup(args.config)

    if not is_valid:
        print("Configuration validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    # Configure logging
    configure_logging(
        level=config.logging.level,
        json_format=config.logging.json_format,
    )

    # Create orchestrator config
    orch_config = OrchestratorConfig(
        watch_path=args.watch or config.orchestrator.watch_path,
        file_patterns=config.orchestrator.file_patterns,
        scheduler_interval=config.orchestrator.scheduler_interval,
        heartbeat_interval=config.orchestrator.heartbeat_interval,
    )

    print(f"Starting DMRG-FTE orchestrator...")
    print(f"  Watch path: {orch_config.watch_path}")
    print(f"  Patterns: {', '.join(orch_config.file_patterns)}")
    print(f"  Press Ctrl+C to stop")
    print()

    orchestrator = Orchestrator(orch_config)

    # Attempt recovery
    recovered = orchestrator.recover_from_checkpoint()
    if recovered:
        print(f"  Recovered from {recovered} checkpoint(s)")

    # Run (blocking)
    orchestrator.run()

    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop the orchestrator (placeholder - actual stop via signal).

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    print("To stop the orchestrator, press Ctrl+C in the running terminal")
    print("or send SIGTERM to the process.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show orchestrator status.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    # For MVP, show health and recent activity
    health_skill = HealthSkill()
    health = health_skill.get_current_score()

    validator = Validator()
    results = validator.list_results(limit=5)

    print("DMRG-FTE Status")
    print("=" * 40)
    print()
    print(f"Health Score: {health.overall_score:.1f}/100 ({health.status_label})")
    print(f"Trend: {health.trend}")
    print(f"Active Anomalies: {health.active_anomalies}")
    print()

    if results:
        print("Recent Validations:")
        for r in results:
            status = "✓" if r["passed"] else "✗"
            print(f"  {status} {r['batch_id'][:8]}... | {r['anomaly_count']} anomalies | {r['health_score']:.1f} health")
    else:
        print("No recent validations.")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Manually validate a file.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    path = Path(args.path)
    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1

    configure_logging(level="WARNING", json_format=False)

    print(f"Validating: {path}")
    print()

    validator = Validator()
    result = validator.validate_file(path)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(result.format_summary())
        print()

        if result.anomalies:
            print("Anomalies:")
            for anomaly in result.anomalies:
                print(f"  {anomaly.format_summary()}")
        else:
            print("No anomalies detected. Data quality is good!")

    return 0 if result.passed else 1


def cmd_health(args: argparse.Namespace) -> int:
    """Show current health score.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    health_skill = HealthSkill()
    health = health_skill.get_current_score()

    if args.json:
        print(json.dumps(health.to_dict(), indent=2, default=str))
    else:
        print("Health Score")
        print("=" * 40)
        print()
        print(f"Overall: {health.overall_score:.1f}/100")
        print(f"Status: {health.status_label}")
        print(f"Trend: {health.trend}")
        print(f"Active Anomalies: {health.active_anomalies}")
        print(f"Batches Evaluated: {health.batches_evaluated}")
        print()

        if health.component_scores:
            print("Component Scores:")
            for name, comp in health.component_scores.items():
                print(f"  {name}: {comp.score:.1f}/100 (weight: {comp.weight:.2f})")

        if health.active_anomalies == 0:
            print()
            print("✓ System is healthy - no active anomalies")

    return 0


def cmd_results(args: argparse.Namespace) -> int:
    """List recent validation results.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    validator = Validator()
    results = validator.list_results(limit=args.limit)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print(f"Recent Validation Results (last {args.limit})")
        print("=" * 60)
        print()

        if not results:
            print("No validation results found.")
            return 0

        for r in results:
            status = "PASSED" if r["passed"] else "FAILED"
            time_str = r.get("validated_at", "unknown")[:19]
            print(f"{status:6} | {r['batch_id'][:8]}... | "
                  f"{r['anomaly_count']:2} anomalies | "
                  f"{r['health_score']:5.1f} health | "
                  f"{r['duration_ms']:6.1f}ms | {time_str}")

    return 0


def cmd_issues(args: argparse.Namespace) -> int:
    """List recent anomalies/issues.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    alerter = Alerter()
    alerts = alerter.read_alerts(
        severity=args.severity,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(alerts, indent=2, default=str))
    else:
        print(f"Recent Issues (last {args.limit})")
        print("=" * 70)
        print()

        if not alerts:
            print("No issues found. System is healthy!")
            return 0

        for alert in alerts:
            severity = alert.get("severity", "UNKNOWN")
            icon = "🚨" if severity == "CRITICAL" else "⚠️" if severity == "WARNING" else "ℹ️"
            time_str = alert.get("timestamp", "unknown")[:19]
            code = alert.get("failure_code", "N/A")
            batch = alert.get("batch_id", "unknown")[:8]

            print(f"{icon} {severity:8} | {code:7} | batch {batch}... | {time_str}")
            print(f"   {alert.get('message', 'No message')[:60]}")
            print()

    return 0


def cmd_quarantine(args: argparse.Namespace) -> int:
    """List quarantined records.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    quarantine_skill = QuarantineSkill()
    records = quarantine_skill.list_quarantined(
        batch_id=args.batch,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(records, indent=2, default=str))
    else:
        print(f"Quarantined Records (last {args.limit})")
        print("=" * 70)
        print()

        if not records:
            print("No quarantined records. All data is clean!")
            return 0

        for record in records:
            time_str = record.get("quarantined_at", "unknown")[:19]
            batch = record.get("batch_id", "unknown")[:8]
            codes = ", ".join(record.get("failure_codes", []))
            idx = record.get("record_index", "?")

            print(f"Record #{idx} from batch {batch}...")
            print(f"  Codes: {codes}")
            print(f"  Reason: {record.get('quarantine_reason', 'Unknown')[:60]}")
            print(f"  Time: {time_str}")
            print()

        # Show stats
        stats = quarantine_skill.get_quarantine_stats()
        print(f"Total quarantined: {stats['total']}")

    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version information.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code.
    """
    from src import __version__

    print(f"DMRG-FTE v{__version__}")
    print("Data & Model Reliability Guardian")
    print()
    print("Bronze Tier MVP with Orchestrator")
    print("https://github.com/your-org/dmrg-fte")

    return 0


if __name__ == "__main__":
    sys.exit(main())
