"""DataLoader service for reading Bronze tier validation results.

Loads validation results, health state, and anomalies from file-based storage.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, computed_field

from src.models.validation_result import ValidationResult, SilverValidationResult, GoldValidationResult
from src.models.health_score import HealthScore, SilverTierHealthScore, GoldTierHealthScore
from src.models.anomaly import Anomaly
from src.models.silver_anomaly import SchemaAnomaly, BusinessLogicAnomaly, FreshnessAnomaly
from src.models.gold_anomaly import ModelHealthAnomaly, EthicsAnomaly
from src.lib.constants import SeverityLevel
from src.lib.config import get_config


class DataLoaderResult(BaseModel):
    """Result container for data loading operations."""

    results: list[ValidationResult] = []
    total_count: int = 0
    has_more: bool = False


class AnomalyResult(BaseModel):
    """Result container for anomaly queries."""

    anomalies: list[Anomaly] = []
    by_severity: dict[str, int] = {}


class SilverDataLoaderResult(BaseModel):
    """Result container for Silver tier data loading."""

    results: list[SilverValidationResult] = []
    total_count: int = 0
    has_more: bool = False


class SilverAnomalyResult(BaseModel):
    """Result container for Silver tier anomaly queries."""

    schema_anomalies: list[SchemaAnomaly] = []
    business_logic_anomalies: list[BusinessLogicAnomaly] = []
    freshness_anomalies: list[FreshnessAnomaly] = []
    by_layer: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    @computed_field
    @property
    def total(self) -> int:
        """Get total anomaly count."""
        return len(self.schema_anomalies) + len(self.business_logic_anomalies) + len(self.freshness_anomalies)


class GoldDataLoaderResult(BaseModel):
    """Result container for Gold tier data loading."""

    results: list[GoldValidationResult] = []
    total_count: int = 0
    has_more: bool = False


class GoldAnomalyResult(BaseModel):
    """Result container for Gold tier anomaly queries."""

    model_health_anomalies: list[ModelHealthAnomaly] = []
    ethics_anomalies: list[EthicsAnomaly] = []
    by_layer: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    @computed_field
    @property
    def total(self) -> int:
        """Get total anomaly count."""
        return len(self.model_health_anomalies) + len(self.ethics_anomalies)


class DataLoader:
    """Loads validation results and health data from Bronze tier output.

    Reads from:
    - data/results/*.json - Validation results
    - data/state/health.json - Current health state
    """

    def __init__(self, base_path: Path | None = None):
        """Initialize DataLoader.

        Args:
            base_path: Base path for data files. Defaults to project root.
        """
        if base_path is None:
            base_path = Path.cwd()
        self.base_path = Path(base_path)
        self._config = get_config()

    @property
    def results_path(self) -> Path:
        """Get path to validation results directory."""
        return self.base_path / self._config.storage.results_path

    @property
    def health_state_path(self) -> Path:
        """Get path to health state file."""
        return self.base_path / self._config.storage.health_state_path

    @property
    def audit_log_path(self) -> Path:
        """Get path to audit logs directory."""
        return self.base_path / self._config.storage.audit_log_path

    @property
    def silver_results_path(self) -> Path:
        """Get path to Silver tier validation results directory."""
        return self.base_path / "data" / "silver_results"

    @property
    def silver_health_state_path(self) -> Path:
        """Get path to Silver tier health state file."""
        return self.base_path / "data" / "state" / "silver_health.json"

    def get_latest_results(
        self,
        limit: int = 100,
        since: datetime | None = None,
    ) -> DataLoaderResult:
        """Get most recent validation results.

        Args:
            limit: Maximum number of results to return.
            since: Optional filter for results after this timestamp.

        Returns:
            DataLoaderResult with list of ValidationResult objects.
        """
        results: list[ValidationResult] = []

        if not self.results_path.exists():
            return DataLoaderResult(results=[], total_count=0, has_more=False)

        # Find all result files
        result_files = sorted(
            self.results_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        total_count = len(result_files)

        for file_path in result_files[:limit + 1]:  # Get one extra to check has_more
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Handle both single result and list of results
                if isinstance(data, list):
                    for item in data:
                        result = ValidationResult(**item)
                        if since is None or result.validated_at >= since:
                            results.append(result)
                else:
                    result = ValidationResult(**data)
                    if since is None or result.validated_at >= since:
                        results.append(result)

            except (json.JSONDecodeError, Exception) as e:
                # Log error but continue with other files
                continue

        has_more = len(results) > limit
        results = results[:limit]

        # Sort by validation time descending
        results.sort(key=lambda r: r.validated_at, reverse=True)

        return DataLoaderResult(
            results=results,
            total_count=total_count,
            has_more=has_more,
        )

    def get_health_state(self) -> tuple[HealthScore | None, bool]:
        """Get current health state from state file.

        Returns:
            Tuple of (HealthScore or None, is_stale).
            is_stale is True if state is >60 seconds old.
        """
        if not self.health_state_path.exists():
            # Return default healthy state if no file exists
            default_health = HealthScore.create_initial()
            return default_health, True

        try:
            with open(self.health_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert history from list of dicts to list of tuples
            if "history" in data and data["history"]:
                converted_history = []
                for entry in data["history"]:
                    if isinstance(entry, dict):
                        ts = datetime.fromisoformat(entry["timestamp"])
                        converted_history.append((ts, entry["score"]))
                    elif isinstance(entry, (list, tuple)):
                        converted_history.append(tuple(entry))
                data["history"] = converted_history

            health = HealthScore(**data)

            # Check staleness (>60 seconds old)
            now = datetime.now(timezone.utc)
            age = (now - health.last_updated).total_seconds()
            is_stale = age > 60

            return health, is_stale

        except (json.JSONDecodeError, Exception) as e:
            # Return default on error
            default_health = HealthScore.create_initial()
            return default_health, True

    def get_anomalies(
        self,
        severity_filter: list[SeverityLevel] | None = None,
        layer_filter: list[str] | None = None,
        time_range: tuple[datetime, datetime] | None = None,
        limit: int = 50,
        latest_only: bool = True,
    ) -> AnomalyResult:
        """Get anomalies from validation results.

        Args:
            severity_filter: Optional list of severities to include.
            layer_filter: Optional list of layers to include.
            time_range: Optional (start, end) datetime tuple.
            limit: Maximum number of anomalies to return.
            latest_only: If True, only return anomalies from the most recent validation.

        Returns:
            AnomalyResult with filtered anomalies and severity counts.
        """
        # Get results - only the latest by default to avoid duplicates
        results_limit = 1 if latest_only else 1000
        results_data = self.get_latest_results(limit=results_limit)

        all_anomalies: list[Anomaly] = []
        seen_ids: set[str] = set()  # Deduplicate by ID

        for result in results_data.results:
            for anomaly in result.anomalies:
                # Skip duplicates
                if anomaly.id in seen_ids:
                    continue
                seen_ids.add(anomaly.id)

                # Apply time filter
                if time_range:
                    start, end = time_range
                    if not (start <= anomaly.detected_at <= end):
                        continue

                # Apply severity filter
                if severity_filter and anomaly.severity not in severity_filter:
                    continue

                # Apply layer filter (Bronze tier only for now)
                if layer_filter and "Bronze" not in layer_filter:
                    continue

                all_anomalies.append(anomaly)

        # Sort by detection time descending
        all_anomalies.sort(key=lambda a: a.detected_at, reverse=True)

        # Count by severity
        by_severity = {
            SeverityLevel.CRITICAL.value: 0,
            SeverityLevel.WARNING.value: 0,
            SeverityLevel.INFO.value: 0,
        }

        for anomaly in all_anomalies:
            by_severity[anomaly.severity.value] += 1

        return AnomalyResult(
            anomalies=all_anomalies[:limit],
            by_severity=by_severity,
        )

    def get_audit_events(
        self,
        time_range: tuple[datetime, datetime] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit log events for timeline.

        Args:
            time_range: Optional (start, end) datetime tuple.
            limit: Maximum number of events to return.

        Returns:
            List of audit event dictionaries.
        """
        events: list[dict[str, Any]] = []

        if not self.audit_log_path.exists():
            return events

        # Read JSONL audit logs
        for log_file in self.audit_log_path.glob("*.jsonl"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            event = json.loads(line)

                            # Apply time filter if provided
                            if time_range and "timestamp" in event:
                                event_time = datetime.fromisoformat(event["timestamp"])
                                start, end = time_range
                                if not (start <= event_time <= end):
                                    continue

                            events.append(event)

                        except json.JSONDecodeError:
                            continue

            except Exception:
                continue

        # Sort by timestamp descending
        events.sort(
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )

        return events[:limit]

    def has_data(self) -> bool:
        """Check if any validation data exists.

        Returns:
            True if results exist, False otherwise.
        """
        if not self.results_path.exists():
            return False

        result_files = list(self.results_path.glob("*.json"))
        return len(result_files) > 0

    # -------------------------------------------------------------------------
    # Silver Tier Methods (T064)
    # -------------------------------------------------------------------------

    def get_silver_health_state(self) -> tuple[SilverTierHealthScore | None, bool]:
        """Get current Silver tier health state from state file.

        Returns:
            Tuple of (SilverTierHealthScore or None, is_stale).
            is_stale is True if state is >120 seconds old.
        """
        if not self.silver_health_state_path.exists():
            # Return default healthy state if no file exists
            default_health = SilverTierHealthScore.create_initial()
            return default_health, True

        try:
            with open(self.silver_health_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            health = SilverTierHealthScore(**data)

            # Check staleness (>120 seconds old for Silver tier)
            now = datetime.now(timezone.utc)
            age = (now - health.last_updated).total_seconds()
            is_stale = age > 120

            return health, is_stale

        except (json.JSONDecodeError, Exception) as e:
            # Return default on error
            default_health = SilverTierHealthScore.create_initial()
            return default_health, True

    def get_silver_results(
        self,
        limit: int = 100,
        since: datetime | None = None,
    ) -> SilverDataLoaderResult:
        """Get most recent Silver tier validation results.

        Args:
            limit: Maximum number of results to return.
            since: Optional filter for results after this timestamp.

        Returns:
            SilverDataLoaderResult with list of SilverValidationResult objects.
        """
        results: list[SilverValidationResult] = []

        if not self.silver_results_path.exists():
            return SilverDataLoaderResult(results=[], total_count=0, has_more=False)

        # Find all result files
        result_files = sorted(
            self.silver_results_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        total_count = len(result_files)

        for file_path in result_files[:limit + 1]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    for item in data:
                        result = SilverValidationResult(**item)
                        if since is None or result.validated_at >= since:
                            results.append(result)
                else:
                    result = SilverValidationResult(**data)
                    if since is None or result.validated_at >= since:
                        results.append(result)

            except (json.JSONDecodeError, Exception):
                continue

        has_more = len(results) > limit
        results = results[:limit]

        results.sort(key=lambda r: r.validated_at, reverse=True)

        return SilverDataLoaderResult(
            results=results,
            total_count=total_count,
            has_more=has_more,
        )

    def get_silver_anomalies(
        self,
        severity_filter: list[SeverityLevel] | None = None,
        layer_filter: list[str] | None = None,
        limit: int = 50,
    ) -> SilverAnomalyResult:
        """Get Silver tier anomalies from recent validation results.

        Args:
            severity_filter: Optional list of severities to include.
            layer_filter: Optional list of layers to include (schema, business_logic, freshness).
            limit: Maximum number of anomalies to return per layer.

        Returns:
            SilverAnomalyResult with filtered anomalies and counts.
        """
        results_data = self.get_silver_results(limit=1000)

        schema_anomalies: list[SchemaAnomaly] = []
        bl_anomalies: list[BusinessLogicAnomaly] = []
        freshness_anomalies: list[FreshnessAnomaly] = []

        for result in results_data.results:
            # Schema anomalies
            if layer_filter is None or "schema" in layer_filter:
                for anomaly in result.schema_anomalies:
                    if severity_filter and anomaly.severity not in severity_filter:
                        continue
                    schema_anomalies.append(anomaly)

            # Business logic anomalies
            if layer_filter is None or "business_logic" in layer_filter:
                for anomaly in result.business_logic_anomalies:
                    if severity_filter and anomaly.severity not in severity_filter:
                        continue
                    bl_anomalies.append(anomaly)

            # Freshness anomalies
            if layer_filter is None or "freshness" in layer_filter:
                for anomaly in result.freshness_anomalies:
                    if severity_filter and anomaly.severity not in severity_filter:
                        continue
                    freshness_anomalies.append(anomaly)

        # Sort by detection time descending
        schema_anomalies.sort(key=lambda a: a.timestamp, reverse=True)
        bl_anomalies.sort(key=lambda a: a.timestamp, reverse=True)
        freshness_anomalies.sort(key=lambda a: a.timestamp, reverse=True)

        # Count by layer
        by_layer = {
            "schema": len(schema_anomalies),
            "business_logic": len(bl_anomalies),
            "freshness": len(freshness_anomalies),
        }

        # Count by severity
        by_severity = {
            SeverityLevel.CRITICAL.value: 0,
            SeverityLevel.WARNING.value: 0,
            SeverityLevel.INFO.value: 0,
        }

        all_anomalies = schema_anomalies + bl_anomalies + freshness_anomalies
        for anomaly in all_anomalies:
            by_severity[anomaly.severity.value] += 1

        return SilverAnomalyResult(
            schema_anomalies=schema_anomalies[:limit],
            business_logic_anomalies=bl_anomalies[:limit],
            freshness_anomalies=freshness_anomalies[:limit],
            by_layer=by_layer,
            by_severity=by_severity,
        )

    def has_silver_data(self) -> bool:
        """Check if Silver tier validation data exists.

        Returns:
            True if Silver results exist, False otherwise.
        """
        if not self.silver_results_path.exists():
            return False

        result_files = list(self.silver_results_path.glob("*.json"))
        return len(result_files) > 0

    # -------------------------------------------------------------------------
    # Gold Tier Methods
    # -------------------------------------------------------------------------

    @property
    def gold_results_path(self) -> Path:
        """Get path to Gold tier validation results directory."""
        return self.base_path / "data" / "gold_results"

    @property
    def gold_health_state_path(self) -> Path:
        """Get path to Gold tier health state file."""
        return self.base_path / "data" / "state" / "gold_health.json"

    def get_gold_health_state(self) -> tuple[GoldTierHealthScore | None, bool]:
        """Get current Gold tier health state from state file.

        Returns:
            Tuple of (GoldTierHealthScore or None, is_stale).
            is_stale is True if state is >120 seconds old.
        """
        if not self.gold_health_state_path.exists():
            # Return default healthy state if no file exists
            default_health = GoldTierHealthScore.create_initial()
            return default_health, True

        try:
            with open(self.gold_health_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            health = GoldTierHealthScore(**data)

            # Check staleness (>120 seconds old for Gold tier)
            now = datetime.now(timezone.utc)
            age = (now - health.last_updated).total_seconds()
            is_stale = age > 120

            return health, is_stale

        except (json.JSONDecodeError, Exception):
            # Return default on error
            default_health = GoldTierHealthScore.create_initial()
            return default_health, True

    def get_gold_results(
        self,
        limit: int = 100,
        since: datetime | None = None,
    ) -> GoldDataLoaderResult:
        """Get most recent Gold tier validation results.

        Args:
            limit: Maximum number of results to return.
            since: Optional filter for results after this timestamp.

        Returns:
            GoldDataLoaderResult with list of GoldValidationResult objects.
        """
        results: list[GoldValidationResult] = []

        if not self.gold_results_path.exists():
            return GoldDataLoaderResult(results=[], total_count=0, has_more=False)

        # Find all result files
        result_files = sorted(
            self.gold_results_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        total_count = len(result_files)

        for file_path in result_files[:limit + 1]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    for item in data:
                        result = GoldValidationResult(**item)
                        if since is None or result.validated_at >= since:
                            results.append(result)
                else:
                    result = GoldValidationResult(**data)
                    if since is None or result.validated_at >= since:
                        results.append(result)

            except (json.JSONDecodeError, Exception):
                continue

        has_more = len(results) > limit
        results = results[:limit]

        results.sort(key=lambda r: r.validated_at, reverse=True)

        return GoldDataLoaderResult(
            results=results,
            total_count=total_count,
            has_more=has_more,
        )

    def get_gold_anomalies(
        self,
        severity_filter: list[SeverityLevel] | None = None,
        layer_filter: list[str] | None = None,
        limit: int = 50,
    ) -> GoldAnomalyResult:
        """Get Gold tier anomalies from recent validation results.

        Args:
            severity_filter: Optional list of severities to include.
            layer_filter: Optional list of layers to include (model_health, ethics).
            limit: Maximum number of anomalies to return per layer.

        Returns:
            GoldAnomalyResult with filtered anomalies and counts.
        """
        results_data = self.get_gold_results(limit=1000)

        model_health_anomalies: list[ModelHealthAnomaly] = []
        ethics_anomalies: list[EthicsAnomaly] = []

        for result in results_data.results:
            # Model health anomalies
            if layer_filter is None or "model_health" in layer_filter:
                for anomaly in result.model_health_anomalies:
                    if severity_filter and anomaly.severity not in severity_filter:
                        continue
                    model_health_anomalies.append(anomaly)

            # Ethics anomalies
            if layer_filter is None or "ethics" in layer_filter:
                for anomaly in result.ethics_anomalies:
                    if severity_filter and anomaly.severity not in severity_filter:
                        continue
                    ethics_anomalies.append(anomaly)

        # Sort by detection time descending
        model_health_anomalies.sort(key=lambda a: a.timestamp, reverse=True)
        ethics_anomalies.sort(key=lambda a: a.timestamp, reverse=True)

        # Count by layer
        by_layer = {
            "model_health": len(model_health_anomalies),
            "ethics": len(ethics_anomalies),
        }

        # Count by severity
        by_severity = {
            SeverityLevel.CRITICAL.value: 0,
            SeverityLevel.WARNING.value: 0,
            SeverityLevel.INFO.value: 0,
        }

        all_anomalies = model_health_anomalies + ethics_anomalies
        for anomaly in all_anomalies:
            by_severity[anomaly.severity.value] += 1

        return GoldAnomalyResult(
            model_health_anomalies=model_health_anomalies[:limit],
            ethics_anomalies=ethics_anomalies[:limit],
            by_layer=by_layer,
            by_severity=by_severity,
        )

    def has_gold_data(self) -> bool:
        """Check if Gold tier validation data exists.

        Returns:
            True if Gold results exist, False otherwise.
        """
        if not self.gold_results_path.exists():
            return False

        result_files = list(self.gold_results_path.glob("*.json"))
        return len(result_files) > 0
