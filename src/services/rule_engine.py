"""RuleEngine service for Silver Tier business logic validation.

This module provides:
- RuleEngine: Loads and evaluates business rules from config/rules/
- ReferenceDataLoader: Loads CSV/JSON lookup files for referential integrity
"""

import csv
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
import yaml

from src.lib.constants import FailureCode, SeverityLevel
from src.models.business_rule import (
    BusinessRule,
    RuleType,
    RuleViolation,
    RuleEvaluationResult,
    StateTransitionRule,
    CalculationRule,
)
from src.models.reference_data import (
    ReferenceDataSet,
    ReferenceDataConfig,
    ReferenceDataFormat,
    LookupResult,
)

logger = structlog.get_logger(__name__)


class ReferenceDataLoader:
    """Loads and caches reference data from CSV/JSON files.

    Reference data is used for:
    - BL-002: Referential integrity checks (FK validation)
    - BL-008: Orphan record detection
    """

    def __init__(self, reference_dir: Path | None = None) -> None:
        """Initialize the reference data loader.

        Args:
            reference_dir: Directory containing reference data files.
        """
        self.reference_dir = reference_dir or Path("data/reference")
        self._cache: dict[str, ReferenceDataSet] = {}
        logger.info("reference_data_loader_initialized", dir=str(self.reference_dir))

    def load(self, config: ReferenceDataConfig) -> ReferenceDataSet:
        """Load reference data from file.

        Args:
            config: Configuration for the reference data.

        Returns:
            Loaded ReferenceDataSet.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file format is unsupported.
        """
        # Check cache first
        cached = self._cache.get(config.id)
        if cached is not None and not cached.needs_refresh():
            return cached

        file_path = Path(config.file_path)
        if not file_path.is_absolute():
            file_path = self.reference_dir / file_path

        if not file_path.exists():
            logger.warning("reference_file_not_found", path=str(file_path))
            return ReferenceDataSet.create_empty(config)

        # Calculate file hash
        file_hash = self._calculate_file_hash(file_path)

        # Check if file changed
        if cached is not None and cached.file_hash == file_hash:
            # File unchanged, just update load time
            cached.loaded_at = datetime.utcnow()
            return cached

        # Load data based on format
        start_time = time.perf_counter()

        if config.format == ReferenceDataFormat.CSV:
            data, keys = self._load_csv(file_path, config.key_column)
        elif config.format == ReferenceDataFormat.JSON:
            data, keys = self._load_json(file_path, config.key_column)
        elif config.format == ReferenceDataFormat.JSONL:
            data, keys = self._load_jsonl(file_path, config.key_column)
        else:
            raise ValueError(f"Unsupported format: {config.format}")

        duration_ms = (time.perf_counter() - start_time) * 1000

        dataset = ReferenceDataSet(
            config=config,
            data=data,
            keys=keys,
            record_count=len(data),
            loaded_at=datetime.utcnow(),
            file_hash=file_hash,
        )

        # Cache it
        self._cache[config.id] = dataset

        logger.info(
            "reference_data_loaded",
            id=config.id,
            records=len(data),
            duration_ms=duration_ms,
        )

        return dataset

    def _load_csv(
        self, file_path: Path, key_column: str
    ) -> tuple[dict[str, dict[str, Any]], set[str]]:
        """Load CSV file into lookup dict."""
        data: dict[str, dict[str, Any]] = {}
        keys: set[str] = set()

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row.get(key_column)
                if key is not None:
                    data[str(key)] = dict(row)
                    keys.add(str(key))

        return data, keys

    def _load_json(
        self, file_path: Path, key_column: str
    ) -> tuple[dict[str, dict[str, Any]], set[str]]:
        """Load JSON file (array of objects) into lookup dict."""
        data: dict[str, dict[str, Any]] = {}
        keys: set[str] = set()

        with open(file_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    key = record.get(key_column)
                    if key is not None:
                        data[str(key)] = record
                        keys.add(str(key))

        return data, keys

    def _load_jsonl(
        self, file_path: Path, key_column: str
    ) -> tuple[dict[str, dict[str, Any]], set[str]]:
        """Load JSONL file (one JSON object per line) into lookup dict."""
        data: dict[str, dict[str, Any]] = {}
        keys: set[str] = set()

        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        key = record.get(key_column)
                        if key is not None:
                            data[str(key)] = record
                            keys.add(str(key))

        return data, keys

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of file for change detection."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def lookup(self, reference_id: str, key: str) -> LookupResult:
        """Look up a key in cached reference data.

        Args:
            reference_id: ID of the reference data set.
            key: The key to look up.

        Returns:
            LookupResult with found status and record.
        """
        start_time = time.perf_counter()

        dataset = self._cache.get(reference_id)
        if dataset is None:
            return LookupResult(
                found=False,
                key=key,
                reference_id=reference_id,
                lookup_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        found = dataset.contains(key)
        record = dataset.get(key) if found else None
        is_active = dataset.is_active(key) if found else False

        return LookupResult(
            found=found,
            key=key,
            reference_id=reference_id,
            record=record,
            is_active=is_active,
            lookup_time_ms=(time.perf_counter() - start_time) * 1000,
        )

    def get_all_keys(self, reference_id: str) -> set[str]:
        """Get all keys from a reference data set.

        Args:
            reference_id: ID of the reference data set.

        Returns:
            Set of all keys, or empty set if not loaded.
        """
        dataset = self._cache.get(reference_id)
        if dataset is None:
            return set()
        return dataset.keys

    def clear_cache(self) -> None:
        """Clear all cached reference data."""
        self._cache.clear()
        logger.info("reference_data_cache_cleared")


class RuleEngine:
    """Loads and evaluates business rules from config/rules/.

    Supports rule types:
    - crossfield: Field comparisons (BL-001)
    - referential: FK checks (BL-002)
    - calculation: Math validation (BL-003)
    - state_transition: Lifecycle validation (BL-004)
    - temporal: Date/time rules (BL-005)
    - domain: Value constraints (BL-006)
    - distribution: Statistical checks (BL-007)
    - orphan: Parent record checks (BL-008)
    """

    def __init__(
        self,
        rules_dir: Path | None = None,
        reference_loader: ReferenceDataLoader | None = None,
    ) -> None:
        """Initialize the rule engine.

        Args:
            rules_dir: Directory containing rule YAML files.
            reference_loader: Reference data loader for FK checks.
        """
        self.rules_dir = rules_dir or Path("config/rules")
        self.reference_loader = reference_loader or ReferenceDataLoader()

        self._rules: dict[str, BusinessRule] = {}
        self._state_transition_rules: dict[str, StateTransitionRule] = {}
        self._calculation_rules: dict[str, CalculationRule] = {}

        logger.info("rule_engine_initialized", dir=str(self.rules_dir))

    def load_rules(self) -> int:
        """Load all rules from rules directory.

        Returns:
            Number of rules loaded.
        """
        self._rules.clear()
        self._state_transition_rules.clear()
        self._calculation_rules.clear()

        if not self.rules_dir.exists():
            logger.warning("rules_dir_not_found", dir=str(self.rules_dir))
            return 0

        count = 0
        for file_path in self.rules_dir.glob("*.yaml"):
            count += self._load_rule_file(file_path)

        for file_path in self.rules_dir.glob("*.yml"):
            count += self._load_rule_file(file_path)

        logger.info("rules_loaded", count=count)
        return count

    def _load_rule_file(self, file_path: Path) -> int:
        """Load rules from a single YAML file."""
        count = 0

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                return 0

            rules = data.get("rules", [])
            if not isinstance(rules, list):
                rules = [data]  # Single rule file

            for rule_data in rules:
                if not isinstance(rule_data, dict):
                    continue

                rule_type = rule_data.get("type", "domain")

                # Map failure_code string to enum
                failure_code_str = rule_data.get("failure_code", "BL-006")
                failure_code = self._map_failure_code(failure_code_str)

                # Map severity string to enum
                severity_str = rule_data.get("severity", "warning").upper()
                severity = SeverityLevel(severity_str) if severity_str in [s.value for s in SeverityLevel] else SeverityLevel.WARNING

                if rule_type == "state_transition":
                    rule = StateTransitionRule(
                        id=rule_data.get("id", f"rule-{count}"),
                        name=rule_data.get("name", "Unnamed rule"),
                        field=rule_data.get("field", "status"),
                        allowed_states=rule_data.get("allowed_values", []),
                        allowed_transitions=rule_data.get("transitions", {}),
                        severity=severity,
                    )
                    self._state_transition_rules[rule.id] = rule
                elif rule_type == "calculation":
                    rule = CalculationRule(
                        id=rule_data.get("id", f"rule-{count}"),
                        name=rule_data.get("name", "Unnamed rule"),
                        result_field=rule_data.get("result_field", "total"),
                        expression=rule_data.get("expression", ""),
                        tolerance=rule_data.get("tolerance", 0.001),
                        severity=severity,
                    )
                    self._calculation_rules[rule.id] = rule
                else:
                    rule = BusinessRule(
                        id=rule_data.get("id", f"rule-{count}"),
                        name=rule_data.get("name", "Unnamed rule"),
                        description=rule_data.get("description", ""),
                        type=RuleType(rule_type) if rule_type in [t.value for t in RuleType] else RuleType.DOMAIN,
                        failure_code=failure_code,
                        severity=severity,
                        enabled=rule_data.get("enabled", True),
                        priority=rule_data.get("priority", 0),
                        expression=rule_data.get("expression", ""),
                        fields=rule_data.get("fields", []),
                        condition=rule_data.get("condition"),
                        parameters=rule_data.get("parameters", {}),
                    )
                    self._rules[rule.id] = rule

                count += 1

        except Exception as e:
            logger.error("rule_file_load_error", file=str(file_path), error=str(e))

        return count

    def _map_failure_code(self, code_str: str) -> FailureCode:
        """Map failure code string to FailureCode enum."""
        mapping = {
            "BL-001": FailureCode.CROSS_FIELD_INCONSISTENCY,
            "BL-002": FailureCode.REFERENTIAL_BREAK,
            "BL-003": FailureCode.CALCULATION_ERROR,
            "BL-004": FailureCode.INVALID_STATE_TRANSITION,
            "BL-005": FailureCode.TEMPORAL_ANOMALY,
            "BL-006": FailureCode.DOMAIN_RULE_VIOLATION,
            "BL-007": FailureCode.DISTRIBUTION_SHIFT,
            "BL-008": FailureCode.ORPHAN_RECORD,
        }
        return mapping.get(code_str, FailureCode.DOMAIN_RULE_VIOLATION)

    def get_rules_by_type(self, rule_type: RuleType) -> list[BusinessRule]:
        """Get all rules of a specific type.

        Args:
            rule_type: The type of rules to retrieve.

        Returns:
            List of matching rules, sorted by priority.
        """
        rules = [r for r in self._rules.values() if r.type == rule_type and r.enabled]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def get_state_transition_rules(self) -> list[StateTransitionRule]:
        """Get all state transition rules."""
        return list(self._state_transition_rules.values())

    def get_calculation_rules(self) -> list[CalculationRule]:
        """Get all calculation rules."""
        return list(self._calculation_rules.values())

    def evaluate_expression(
        self, expression: str, record: dict[str, Any]
    ) -> tuple[bool, str]:
        """Evaluate a rule expression against a record.

        Supports expressions like:
        - "field1 > field2"
        - "field1 <= 100"
        - "field1 in ['a', 'b', 'c']"
        - "field1 * field2 == field3"

        Args:
            expression: The expression to evaluate.
            record: The record data.

        Returns:
            Tuple of (passed, error_message).
        """
        try:
            # Replace field names with actual values
            eval_expr = expression
            for field, value in record.items():
                if isinstance(value, str):
                    eval_expr = re.sub(
                        rf"\b{re.escape(field)}\b",
                        f"'{value}'",
                        eval_expr
                    )
                elif value is None:
                    eval_expr = re.sub(
                        rf"\b{re.escape(field)}\b",
                        "None",
                        eval_expr
                    )
                else:
                    eval_expr = re.sub(
                        rf"\b{re.escape(field)}\b",
                        str(value),
                        eval_expr
                    )

            # Safe evaluation with limited builtins
            allowed_names = {
                "True": True,
                "False": False,
                "None": None,
                "abs": abs,
                "min": min,
                "max": max,
                "sum": sum,
                "len": len,
            }

            result = eval(eval_expr, {"__builtins__": {}}, allowed_names)
            return bool(result), ""

        except Exception as e:
            return False, str(e)

    def evaluate_rule(
        self, rule: BusinessRule, record: dict[str, Any]
    ) -> RuleViolation | None:
        """Evaluate a single rule against a record.

        Args:
            rule: The rule to evaluate.
            record: The record to check.

        Returns:
            RuleViolation if rule failed, None if passed.
        """
        if not rule.enabled:
            return None

        # Check precondition if present
        if rule.condition:
            condition_met, _ = self.evaluate_expression(rule.condition, record)
            if not condition_met:
                return None  # Condition not met, skip rule

        # Evaluate main expression
        passed, error = self.evaluate_expression(rule.expression, record)

        if passed:
            return None

        # Get record ID if available
        record_id = record.get("id") or record.get("order_id") or record.get("_id")

        return RuleViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            failure_code=rule.failure_code,
            severity=rule.severity,
            record_id=str(record_id) if record_id else None,
            affected_fields=rule.fields,
            expected_value=rule.expression,
            actual_value=error or "Expression evaluated to False",
            message=f"{rule.name}: {rule.expression} failed",
        )

    def evaluate_state_transition(
        self,
        rule: StateTransitionRule,
        from_state: str,
        to_state: str,
        record_id: str | None = None,
    ) -> RuleViolation | None:
        """Evaluate a state transition.

        Args:
            rule: The state transition rule.
            from_state: Current state.
            to_state: Target state.
            record_id: Optional record identifier.

        Returns:
            RuleViolation if transition is invalid.
        """
        if rule.is_valid_transition(from_state, to_state):
            return None

        return RuleViolation(
            rule_id=rule.id,
            rule_name=rule.name,
            failure_code=rule.failure_code,
            severity=rule.severity,
            record_id=record_id,
            affected_fields=[rule.field],
            expected_value=f"Valid transitions from {from_state}: {rule.allowed_transitions.get(from_state, [])}",
            actual_value=f"{from_state} -> {to_state}",
            message=f"Invalid state transition: {from_state} -> {to_state}",
        )

    def evaluate_all(
        self, records: list[dict[str, Any]]
    ) -> RuleEvaluationResult:
        """Evaluate all rules against a batch of records.

        Args:
            records: List of records to validate.

        Returns:
            RuleEvaluationResult with all violations.
        """
        start_time = time.perf_counter()
        violations: list[RuleViolation] = []
        rules_evaluated = 0
        rules_passed = 0
        rules_failed = 0
        rules_skipped = 0

        # Get all enabled rules sorted by priority
        all_rules = sorted(
            self._rules.values(),
            key=lambda r: r.priority,
            reverse=True
        )

        for rule in all_rules:
            if not rule.enabled:
                rules_skipped += 1
                continue

            rules_evaluated += 1
            rule_failed = False

            for record in records:
                violation = self.evaluate_rule(rule, record)
                if violation:
                    violations.append(violation)
                    rule_failed = True

            if rule_failed:
                rules_failed += 1
            else:
                rules_passed += 1

        duration_ms = (time.perf_counter() - start_time) * 1000

        return RuleEvaluationResult(
            rules_evaluated=rules_evaluated,
            rules_passed=rules_passed,
            rules_failed=rules_failed,
            rules_skipped=rules_skipped,
            violations=violations,
            duration_ms=duration_ms,
        )
