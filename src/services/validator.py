"""Validator service - Coordinates Bronze validation skills."""

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.models.data_batch import DataBatch
from src.models.anomaly import Anomaly
from src.models.validation_result import ValidationResult
from src.lib.constants import BatchStatus, FailureCode, SeverityLevel
from src.lib.config import get_config
from src.lib.logger import get_logger, bind_correlation_id

from src.skills.bronze.count import CountSkill, CountConfig
from src.skills.bronze.null import NullSkill, NullConfig
from src.skills.bronze.type_check import TypeCheckSkill, TypeConfig, FieldTypeSpec
from src.skills.bronze.range_check import RangeCheckSkill, RangeConfig, FieldRangeSpec
from src.skills.bronze.format import FormatSkill, FormatConfig, FieldFormatSpec
from src.skills.bronze.duplicate import DuplicateSkill, DuplicateConfig
from src.skills.bronze.encoding import EncodingSkill, EncodingConfig
from src.skills.bronze.outlier import OutlierDetectionSkill, OutlierConfig
from src.skills.bronze.log import LogSkill
from src.skills.bronze.alert import AlertSkill
from src.skills.bronze.quarantine import QuarantineSkill

from src.skills.util.score import ScoreSkill
from src.skills.util.health import HealthSkill


class ValidationConfig(BaseModel):
    """Configuration for the validator service."""

    results_dir: str = Field(default="data/results")
    enable_quarantine: bool = Field(default=True)
    enable_alerts: bool = Field(default=True)


class Validator:
    """Validator service that coordinates all Bronze validation skills.

    Executes validation in sequence:
    count → null → type → range → format → duplicate → encoding
    """

    def __init__(self, config: ValidationConfig | None = None):
        """Initialize the validator service.

        Args:
            config: Configuration for the validator.
        """
        self.config = config or ValidationConfig()
        self._logger = get_logger("validator")

        # Initialize skills
        self._count_skill = CountSkill()
        self._null_skill = NullSkill()
        self._type_skill = TypeCheckSkill()
        self._range_skill = RangeCheckSkill()
        self._format_skill = FormatSkill()
        self._duplicate_skill = DuplicateSkill()
        self._encoding_skill = EncodingSkill()
        self._outlier_skill = OutlierDetectionSkill()

        self._log_skill = LogSkill()
        self._alert_skill = AlertSkill()
        self._quarantine_skill = QuarantineSkill()

        self._score_skill = ScoreSkill()
        self._health_skill = HealthSkill()

    def validate(
        self,
        batch: DataBatch,
        rules: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate a data batch against all Bronze rules.

        Args:
            batch: DataBatch to validate.
            rules: Optional validation rules override.

        Returns:
            ValidationResult with anomalies and health score.
        """
        correlation_id = str(uuid4())
        bind_correlation_id(correlation_id)

        start_time = time.perf_counter()
        batch.mark_validating()

        # Log validation start
        self._log_skill.log_validation_start(
            batch_id=batch.id,
            source=batch.source,
            record_count=batch.record_count,
        )

        self._logger.info(
            "validation_started",
            batch_id=batch.id,
            source=batch.source,
            record_count=batch.record_count,
        )

        anomalies: list[Anomaly] = []
        skills_executed: list[str] = []

        try:
            # Get validation rules
            validation_rules = rules or self._get_default_rules()

            # Execute skills in sequence
            anomalies.extend(self._run_count_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_null_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_type_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_range_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_format_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_duplicate_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_encoding_skill(batch, validation_rules, skills_executed))
            anomalies.extend(self._run_outlier_skill(batch, validation_rules, skills_executed))

            # Log each anomaly
            for anomaly in anomalies:
                self._log_skill.log_anomaly(anomaly)

            # Calculate health score
            health = self._health_skill.update_from_validation(
                anomalies=anomalies,
                total_records=batch.record_count,
            )

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Create result
            result = ValidationResult.create(
                batch_id=batch.id,
                anomalies=anomalies,
                health_score=health.overall_score,
                duration_ms=duration_ms,
                skills_executed=skills_executed,
                metadata={
                    "correlation_id": correlation_id,
                    "source": batch.source,
                },
            )

            # Update batch status
            if result.passed:
                batch.mark_passed()
            else:
                batch.mark_failed()

            # Handle alerts
            if self.config.enable_alerts and result.requires_alerts:
                self._alert_skill.dispatch_for_anomalies(anomalies)

            # Handle quarantine
            if self.config.enable_quarantine and result.requires_quarantine:
                self._quarantine_skill.quarantine_records(
                    records=batch.records,
                    anomalies=anomalies,
                    batch_id=batch.id,
                )

            # Log completion
            self._log_skill.log_validation_complete(result)

            # Save result
            self._save_result(result)

            self._logger.info(
                "validation_completed",
                batch_id=batch.id,
                passed=result.passed,
                anomaly_count=result.anomaly_count,
                health_score=result.health_score,
                duration_ms=result.duration_ms,
            )

            return result

        except Exception as e:
            batch.mark_error()
            self._logger.error("validation_error", batch_id=batch.id, error=str(e))
            raise

    def validate_file(
        self,
        file_path: str | Path,
        rules: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate a data file.

        Args:
            file_path: Path to the data file (CSV or JSON).
            rules: Optional validation rules override.

        Returns:
            ValidationResult with anomalies and health score.
        """
        path = Path(file_path)
        records = self._load_file(path)

        batch = DataBatch.from_records(
            records=records,
            source=str(path),
            metadata={"filename": path.name},
        )

        return self.validate(batch, rules)

    def _load_file(self, path: Path) -> list[dict[str, Any]]:
        """Load records from a file.

        Args:
            path: Path to the file.

        Returns:
            List of record dictionaries.
        """
        suffix = path.suffix.lower()

        if suffix == ".csv":
            return self._load_csv(path)
        elif suffix == ".json":
            return self._load_json(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _load_csv(self, path: Path) -> list[dict[str, Any]]:
        """Load records from a CSV file.

        Args:
            path: Path to CSV file.

        Returns:
            List of record dictionaries.
        """
        records = []
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert empty strings to None
                cleaned = {k: (v if v != "" else None) for k, v in row.items()}
                records.append(cleaned)
        return records

    def _load_json(self, path: Path) -> list[dict[str, Any]]:
        """Load records from a JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            List of record dictionaries.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Check for common structures
            if "records" in data:
                return data["records"]
            elif "data" in data:
                return data["data"]
            else:
                return [data]
        else:
            raise ValueError("Invalid JSON structure")

    def _get_default_rules(self) -> dict[str, Any]:
        """Get default validation rules.

        Returns:
            Default rules dictionary.
        """
        return {
            "count": {
                "expected_min": 1,
                "expected_max": 100000,
            },
            "null": {
                "required_fields": [],
                "tolerance_percent": 5.0,
            },
            "type": {
                "field_specs": [],
            },
            "range": {
                "field_specs": [],
            },
            "format": {
                "field_specs": [],
            },
            "duplicate": {
                "tolerance_percent": 0.5,
            },
            "encoding": {
                "expected_encoding": "utf-8",
                "strict": True,
            },
        }

    def _run_count_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run count validation skill.

        Args:
            batch: Data batch.
            rules: Validation rules.
            skills_executed: List to track executed skills.

        Returns:
            List of detected anomalies.
        """
        skill_start = time.perf_counter()
        skills_executed.append(self._count_skill.name)

        count_rules = rules.get("count", {})
        config = CountConfig(
            expected_min=count_rules.get("expected_min"),
            expected_max=count_rules.get("expected_max"),
            expected_exact=count_rules.get("expected_exact"),
        )

        result = self._count_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._count_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=1 if result.anomaly else 0,
        )

        return [result.anomaly] if result.anomaly else []

    def _run_null_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run null validation skill."""
        skill_start = time.perf_counter()
        skills_executed.append(self._null_skill.name)

        null_rules = rules.get("null", {})
        config = NullConfig(
            required_fields=null_rules.get("required_fields", []),
            tolerance_percent=null_rules.get("tolerance_percent", 5.0),
        )

        result = self._null_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._null_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=len(result.anomalies),
        )

        return result.anomalies

    def _run_type_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run type validation skill."""
        skill_start = time.perf_counter()
        skills_executed.append(self._type_skill.name)

        type_rules = rules.get("type", {})
        field_specs = [
            FieldTypeSpec(**spec) for spec in type_rules.get("field_specs", [])
        ]
        config = TypeConfig(
            field_specs=field_specs,
            tolerance_percent=type_rules.get("tolerance_percent", 1.0),
        )

        result = self._type_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._type_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=len(result.anomalies),
        )

        return result.anomalies

    def _run_range_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run range validation skill."""
        skill_start = time.perf_counter()
        skills_executed.append(self._range_skill.name)

        range_rules = rules.get("range", {})
        field_specs = [
            FieldRangeSpec(**spec) for spec in range_rules.get("field_specs", [])
        ]
        config = RangeConfig(field_specs=field_specs)

        result = self._range_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._range_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=len(result.anomalies),
        )

        return result.anomalies

    def _run_format_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run format validation skill."""
        skill_start = time.perf_counter()
        skills_executed.append(self._format_skill.name)

        format_rules = rules.get("format", {})
        field_specs = [
            FieldFormatSpec(**spec) for spec in format_rules.get("field_specs", [])
        ]
        config = FormatConfig(field_specs=field_specs)

        result = self._format_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._format_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=len(result.anomalies),
        )

        return result.anomalies

    def _run_duplicate_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run duplicate detection skill."""
        skill_start = time.perf_counter()
        skills_executed.append(self._duplicate_skill.name)

        dup_rules = rules.get("duplicate", {})
        config = DuplicateConfig(
            key_fields=dup_rules.get("key_fields"),
            tolerance_percent=dup_rules.get("tolerance_percent", 0.5),
            case_sensitive=dup_rules.get("case_sensitive", True),
        )

        result = self._duplicate_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._duplicate_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=1 if result.anomaly else 0,
        )

        return [result.anomaly] if result.anomaly else []

    def _run_encoding_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run encoding validation skill."""
        skill_start = time.perf_counter()
        skills_executed.append(self._encoding_skill.name)

        encoding_rules = rules.get("encoding", {})
        config = EncodingConfig(
            expected_encoding=encoding_rules.get("expected_encoding", "utf-8"),
            strict=encoding_rules.get("strict", True),
        )

        result = self._encoding_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._encoding_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=1 if result.anomaly else 0,
        )

        return [result.anomaly] if result.anomaly else []

    def _run_outlier_skill(
        self,
        batch: DataBatch,
        rules: dict[str, Any],
        skills_executed: list[str],
    ) -> list[Anomaly]:
        """Run outlier detection skill (Z-score based)."""
        skill_start = time.perf_counter()
        skills_executed.append(self._outlier_skill.name)

        outlier_rules = rules.get("outlier", {})
        config = OutlierConfig(
            z_threshold=outlier_rules.get("z_threshold", 3.0),
            numeric_fields=outlier_rules.get("numeric_fields", []),
            min_records=outlier_rules.get("min_records", 30),
        )

        result = self._outlier_skill.validate(
            records=batch.records,
            batch_id=batch.id,
            config=config,
        )

        duration_ms = (time.perf_counter() - skill_start) * 1000
        self._log_skill.log_skill_execution(
            skill_name=self._outlier_skill.name,
            batch_id=batch.id,
            duration_ms=duration_ms,
            passed=result.passed,
            anomaly_count=len(result.anomalies),
        )

        return result.anomalies

    def _save_result(self, result: ValidationResult) -> str:
        """Save validation result to disk.

        Args:
            result: ValidationResult to save.

        Returns:
            Path to saved result file.
        """
        results_dir = Path(self.config.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{result.id}.json"
        filepath = results_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)

        return str(filepath)

    def get_result(self, result_id: str) -> ValidationResult | None:
        """Retrieve a saved validation result.

        Args:
            result_id: ID of the result to retrieve.

        Returns:
            ValidationResult or None if not found.
        """
        results_dir = Path(self.config.results_dir)
        filepath = results_dir / f"{result_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct anomalies
            anomalies = []
            for a_data in data.get("anomalies", []):
                a_data["failure_code"] = FailureCode(a_data["failure_code"])
                a_data["severity"] = SeverityLevel(a_data["severity"])
                if "detected_at" in a_data and isinstance(a_data["detected_at"], str):
                    a_data["detected_at"] = datetime.fromisoformat(a_data["detected_at"])
                anomalies.append(Anomaly(**a_data))

            # Convert datetime
            if "validated_at" in data and isinstance(data["validated_at"], str):
                data["validated_at"] = datetime.fromisoformat(data["validated_at"])

            return ValidationResult(
                id=data["id"],
                batch_id=data["batch_id"],
                passed=data["passed"],
                anomalies=anomalies,
                health_score=data["health_score"],
                duration_ms=data["duration_ms"],
                skills_executed=data.get("skills_executed", []),
                validated_at=data.get("validated_at"),
                metadata=data.get("metadata", {}),
            )
        except Exception:
            return None

    def list_results(self, limit: int = 100) -> list[dict[str, Any]]:
        """List recent validation results.

        Args:
            limit: Maximum results to return.

        Returns:
            List of result summaries.
        """
        results_dir = Path(self.config.results_dir)
        if not results_dir.exists():
            return []

        results = []
        for filepath in results_dir.glob("*.json"):
            if len(results) >= limit:
                break

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                results.append({
                    "id": data.get("id"),
                    "batch_id": data.get("batch_id"),
                    "passed": data.get("passed"),
                    "anomaly_count": len(data.get("anomalies", [])),
                    "health_score": data.get("health_score"),
                    "duration_ms": data.get("duration_ms"),
                    "validated_at": data.get("validated_at"),
                })
            except Exception:
                continue

        # Sort by validation time (newest first)
        results.sort(key=lambda x: x.get("validated_at", ""), reverse=True)
        return results[:limit]
