"""SilverValidator service for Silver tier validation.

This service orchestrates validation across all three Silver layers:
- Layer 2: Schema & Contract Enforcement (SC-001 to SC-008)
- Layer 3: Business Logic Validation (BL-001 to BL-008)
- Layer 4: Freshness & SLA Monitoring (FR-001 to FR-008)
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

from src.lib.constants import SeverityLevel
from src.models.data_batch import DataBatch
from src.models.schema_contract import SchemaContract
from src.models.silver_anomaly import (
    SchemaAnomaly,
    BusinessLogicAnomaly,
    FreshnessAnomaly,
)
from src.models.validation_result import SilverValidationResult
from src.models.health_score import SilverTierHealthScore, SilverLayerScore
from src.services.schema_registry import SchemaRegistry
from src.skills.silver.schema import validate_schema, SchemaValidationResult
from src.skills.silver.version import check_version_compatibility
from src.skills.silver.contract import verify_contract, ContractRegistry
from src.skills.silver.crossfield import validate_crossfield
from src.skills.silver.refint import check_referential_integrity, detect_orphan_records
from src.skills.silver.bizrule import evaluate_business_rules
from src.skills.silver.distrib import detect_distribution_shift, DistributionProfile
from src.skills.silver.auto_logic import validate_auto_logic
from src.services.rule_engine import RuleEngine, ReferenceDataLoader
from src.services.freshness_watcher import FreshnessWatcher

logger = structlog.get_logger(__name__)


class SilverValidator:
    """Orchestrates Silver tier validation across all layers.

    Per spec: Validates data against schema contracts (Layer 2),
    business rules (Layer 3), and freshness SLAs (Layer 4).
    """

    def __init__(
        self,
        schema_dir: Path | None = None,
        rules_dir: Path | None = None,
        sla_dir: Path | None = None,
        reference_dir: Path | None = None,
    ) -> None:
        """Initialize the Silver validator.

        Args:
            schema_dir: Directory containing JSON schema files.
            rules_dir: Directory containing business rule files.
            sla_dir: Directory containing SLA definition files.
            reference_dir: Directory containing reference data files.
        """
        self.schema_dir = schema_dir or Path("config/schemas")
        self.rules_dir = rules_dir or Path("config/rules")
        self.sla_dir = sla_dir or Path("config/sla")
        self.reference_dir = reference_dir or Path("data/reference")

        # Initialize schema registry
        self._schema_registry = SchemaRegistry(self.schema_dir)
        self._schema_registry.load_schemas()

        # Contract registry for hash verification
        self._contract_registry = ContractRegistry()

        # Business logic validation (Phase 4)
        self._reference_loader = ReferenceDataLoader(self.reference_dir)
        self._rule_engine = RuleEngine(self.rules_dir, self._reference_loader)
        self._rule_engine.load_rules()

        # Distribution baselines (loaded on demand)
        self._distribution_baselines: dict[str, dict[str, DistributionProfile]] = {}

        # Freshness monitoring (Phase 5)
        self._freshness_watcher = FreshnessWatcher(
            sla_dir=self.sla_dir,
            state_file=Path("data/state/freshness.json"),
        )

        # Health score tracking
        self._current_health: SilverTierHealthScore | None = None

        logger.info(
            "silver_validator_initialized",
            schema_dir=str(self.schema_dir),
            rules_dir=str(self.rules_dir),
            sla_dir=str(self.sla_dir),
        )

    def validate(self, batch: DataBatch) -> SilverValidationResult:
        """Run full Silver tier validation on a batch.

        Executes all three layers in order:
        1. Schema validation (blocking on critical)
        2. Business logic validation
        3. Freshness check

        Args:
            batch: The data batch to validate.

        Returns:
            SilverValidationResult with all anomalies and scores.
        """
        start_time = time.perf_counter()
        skills_executed: list[str] = []

        logger.info("silver_validation_started", batch_id=batch.id)

        # Layer 2: Schema validation
        schema_anomalies, schema_score = self.validate_schema(batch)
        skills_executed.extend(["schema", "version", "contract"])

        # Check for blocking schema issues
        blocking = any(a.blocking for a in schema_anomalies)
        if blocking:
            logger.warning(
                "silver_validation_blocked",
                batch_id=batch.id,
                blocking_count=len([a for a in schema_anomalies if a.blocking]),
            )
            # Skip further validation if blocked
            duration_ms = (time.perf_counter() - start_time) * 1000
            return SilverValidationResult.create(
                batch_id=batch.id,
                schema_anomalies=schema_anomalies,
                business_logic_anomalies=[],
                freshness_anomalies=[],
                schema_score=schema_score,
                business_logic_score=100.0,  # Not evaluated due to blocking
                freshness_score=100.0,  # Not evaluated due to blocking
                duration_ms=duration_ms,
                skills_executed=skills_executed,
                metadata={"blocked_at": "schema"},
            )

        # Layer 3: Business logic validation
        bl_anomalies, bl_score = self.validate_business_logic(batch)
        skills_executed.extend(["crossfield", "refint", "bizrule", "distrib"])

        # Layer 4: Freshness check (source-level, not batch-level)
        freshness_anomalies, freshness_score = self.check_freshness(batch.source)
        skills_executed.extend(["freshness", "sla", "pipeline"])

        duration_ms = (time.perf_counter() - start_time) * 1000

        result = SilverValidationResult.create(
            batch_id=batch.id,
            schema_anomalies=schema_anomalies,
            business_logic_anomalies=bl_anomalies,
            freshness_anomalies=freshness_anomalies,
            schema_score=schema_score,
            business_logic_score=bl_score,
            freshness_score=freshness_score,
            duration_ms=duration_ms,
            skills_executed=skills_executed,
        )

        # Update health score
        self._update_health_score(result)

        logger.info(
            "silver_validation_completed",
            batch_id=batch.id,
            passed=result.passed,
            blocked=result.blocked,
            total_anomalies=result.total_anomalies,
            duration_ms=duration_ms,
        )

        return result

    def validate_schema(
        self, batch: DataBatch
    ) -> tuple[list[SchemaAnomaly], float]:
        """Validate batch against schema contracts (Layer 2).

        Detects:
        - SC-001: Missing required columns
        - SC-002: Extra unexpected columns
        - SC-003: Column type changes
        - SC-004: Precision loss
        - SC-005: Constraint violations
        - SC-006: Version mismatches
        - SC-007: Breaking changes
        - SC-008: Contract hash mismatches

        Args:
            batch: The data batch to validate.

        Returns:
            Tuple of (anomalies, health_score).
        """
        all_anomalies: list[SchemaAnomaly] = []

        # Get schema contract for this source
        contract = self._schema_registry.get_contract_for_source(batch.source)
        if contract is None:
            logger.warning(
                "no_schema_contract_found",
                batch_id=batch.id,
                source=batch.source,
            )
            # No contract = no schema validation possible
            return [], 100.0

        # Step 1: Validate data against schema (SC-001 to SC-005)
        schema_result = validate_schema(
            records=batch.records,
            contract=contract,
            batch_id=batch.id,
        )
        all_anomalies.extend(schema_result.anomalies)

        # Step 2: Check contract hash (SC-008)
        # Only if contract is registered
        registered = self._contract_registry.get(contract.id, contract.version)
        if registered is not None:
            contract_result = verify_contract(
                current_contract=contract,
                registered_contract=registered,
                batch_id=batch.id,
            )
            all_anomalies.extend(contract_result.anomalies)

        # Calculate combined score
        score = 100.0
        for anomaly in all_anomalies:
            if anomaly.severity == SeverityLevel.CRITICAL:
                score -= 30.0
            elif anomaly.severity == SeverityLevel.WARNING:
                score -= 10.0
            else:
                score -= 2.0
        score = max(0.0, min(100.0, score))

        # Set blocking flag for CRITICAL anomalies
        has_blocking = any(
            a.blocking or a.severity == SeverityLevel.CRITICAL
            for a in all_anomalies
        )

        logger.info(
            "schema_validation_complete",
            batch_id=batch.id,
            source=batch.source,
            anomaly_count=len(all_anomalies),
            score=score,
            has_blocking=has_blocking,
        )

        return all_anomalies, score

    def register_contract(self, contract: SchemaContract) -> str:
        """Register a schema contract for hash verification.

        Args:
            contract: The schema contract to register.

        Returns:
            The contract hash.
        """
        return self._contract_registry.register(contract)

    def validate_business_logic(
        self, batch: DataBatch
    ) -> tuple[list[BusinessLogicAnomaly], float]:
        """Validate batch against business rules (Layer 3).

        Detects:
        - BL-001: Cross-field inconsistencies
        - BL-002: Referential integrity breaks
        - BL-003: Calculation errors
        - BL-004: Invalid state transitions
        - BL-005: Temporal anomalies
        - BL-006: Domain rule violations
        - BL-007: Distribution shifts
        - BL-008: Orphan records

        Args:
            batch: The data batch to validate.

        Returns:
            Tuple of (anomalies, health_score).
        """
        all_anomalies: list[BusinessLogicAnomaly] = []

        logger.info("business_logic_validation_started", batch_id=batch.id)

        # Get cross-field rules from rule engine
        from src.models.business_rule import RuleType
        crossfield_rules = self._rule_engine.get_rules_by_type(RuleType.CROSSFIELD)
        domain_rules = self._rule_engine.get_rules_by_type(RuleType.DOMAIN)
        temporal_rules = self._rule_engine.get_rules_by_type(RuleType.TEMPORAL)

        # Step 1: Cross-field validation (BL-001)
        if crossfield_rules:
            crossfield_result = validate_crossfield(
                records=batch.records,
                rules=crossfield_rules,
                batch_id=batch.id,
            )
            all_anomalies.extend(crossfield_result.anomalies)

        # Step 2: Business rule validation (BL-003, BL-004, BL-005, BL-006)
        all_rules = domain_rules + temporal_rules
        all_rules.extend(self._rule_engine.get_calculation_rules())
        all_rules.extend(self._rule_engine.get_state_transition_rules())

        if all_rules:
            bizrule_result = evaluate_business_rules(
                records=batch.records,
                rules=all_rules,
                batch_id=batch.id,
            )
            all_anomalies.extend(bizrule_result.anomalies)

        # Step 3: Referential integrity (BL-002)
        # Check if we have reference data loaded
        reference_data = self._build_reference_lookup()
        if reference_data:
            refint_result = check_referential_integrity(
                records=batch.records,
                reference_data=reference_data,
                batch_id=batch.id,
            )
            all_anomalies.extend(refint_result.anomalies)

        # Step 4: Distribution shift detection (BL-007)
        baseline = self._distribution_baselines.get(batch.source)
        if baseline:
            distrib_result = detect_distribution_shift(
                records=batch.records,
                baseline=baseline,
                batch_id=batch.id,
            )
            all_anomalies.extend(distrib_result.anomalies)

        # Step 5: Automatic logic validation (BL-006 domain violations)
        # This detects common logical issues like:
        # - Age < 16 with income > $50k
        # - Negative income values
        # - Zero days on platform with purchases
        auto_logic_result = validate_auto_logic(
            records=batch.records,
            batch_id=batch.id,
        )
        if auto_logic_result.anomalies:
            all_anomalies.extend(auto_logic_result.anomalies)
            logger.info(
                "auto_logic_violations_found",
                batch_id=batch.id,
                violations=len(auto_logic_result.anomalies),
                violations_by_type=auto_logic_result.violations_by_type,
            )

        # Calculate health score
        score = 100.0
        for anomaly in all_anomalies:
            if anomaly.severity == SeverityLevel.CRITICAL:
                score -= 25.0
            elif anomaly.severity == SeverityLevel.WARNING:
                score -= 10.0
            else:
                score -= 2.0
        score = max(0.0, min(100.0, score))

        logger.info(
            "business_logic_validation_complete",
            batch_id=batch.id,
            anomaly_count=len(all_anomalies),
            score=score,
        )

        return all_anomalies, score

    def _build_reference_lookup(self) -> dict[str, set[str]]:
        """Build reference data lookup from loaded reference data.

        Returns:
            Dictionary mapping reference_id to set of valid keys.
        """
        lookup: dict[str, set[str]] = {}

        # Check for reference data files in reference_dir
        if self.reference_dir.exists():
            for file_path in self.reference_dir.glob("*.csv"):
                ref_id = file_path.stem
                try:
                    from src.models.reference_data import ReferenceDataConfig, ReferenceDataFormat
                    config = ReferenceDataConfig(
                        id=ref_id,
                        name=ref_id,
                        file_path=str(file_path),
                        format=ReferenceDataFormat.CSV,
                        key_column="id",  # Default assumption
                    )
                    dataset = self._reference_loader.load(config)
                    lookup[ref_id] = dataset.keys
                except Exception as e:
                    logger.debug("reference_load_error", file=str(file_path), error=str(e))

            for file_path in self.reference_dir.glob("*.json"):
                ref_id = file_path.stem
                try:
                    from src.models.reference_data import ReferenceDataConfig, ReferenceDataFormat
                    config = ReferenceDataConfig(
                        id=ref_id,
                        name=ref_id,
                        file_path=str(file_path),
                        format=ReferenceDataFormat.JSON,
                        key_column="id",  # Default assumption
                    )
                    dataset = self._reference_loader.load(config)
                    lookup[ref_id] = dataset.keys
                except Exception as e:
                    logger.debug("reference_load_error", file=str(file_path), error=str(e))

        return lookup

    def set_distribution_baseline(
        self, source: str, baseline: dict[str, DistributionProfile]
    ) -> None:
        """Set distribution baseline for a data source.

        Args:
            source: Data source name.
            baseline: Distribution profiles by column.
        """
        self._distribution_baselines[source] = baseline
        logger.info(
            "distribution_baseline_set",
            source=source,
            columns=list(baseline.keys()),
        )

    def check_freshness(
        self, source: str
    ) -> tuple[list[FreshnessAnomaly], float]:
        """Check freshness/SLA status for a source (Layer 4).

        Detects:
        - FR-001: Stale data
        - FR-002: SLA breach
        - FR-003: SLA warning
        - FR-004: Pipeline delay
        - FR-005: Missing delivery
        - FR-006: Job failure
        - FR-007: Dependency delay
        - FR-008: Latency spike

        Args:
            source: The data source name.

        Returns:
            Tuple of (anomalies, health_score).
        """
        logger.info("freshness_check_started", source=source)

        # Use FreshnessWatcher to check source
        anomalies, score = self._freshness_watcher.check_source(source)

        logger.info(
            "freshness_check_complete",
            source=source,
            anomaly_count=len(anomalies),
            score=score,
        )

        return anomalies, score

    def record_data_arrival(
        self, source: str, record_count: int = 0
    ) -> None:
        """Record data arrival for freshness tracking.

        Args:
            source: Data source name.
            record_count: Number of records in batch.
        """
        from datetime import datetime
        self._freshness_watcher.record_arrival(source, datetime.utcnow(), record_count)

    def start_freshness_monitoring(self) -> None:
        """Start background freshness monitoring."""
        self._freshness_watcher.start()

    def stop_freshness_monitoring(self) -> None:
        """Stop background freshness monitoring."""
        self._freshness_watcher.stop()

    def get_health_score(self) -> SilverTierHealthScore:
        """Get current Silver tier health score.

        Returns:
            Current aggregated health score across all layers.
        """
        if self._current_health is None:
            self._current_health = SilverTierHealthScore.create_initial()
        return self._current_health

    def _update_health_score(self, result: SilverValidationResult) -> None:
        """Update health score based on validation result.

        Args:
            result: The validation result to incorporate.
        """
        now = datetime.now(timezone.utc)
        previous_score = self._current_health.overall_score if self._current_health else None

        # Create layer scores from result
        schema_layer = SilverLayerScore(
            layer_name="schema",
            layer_number=2,
            score=result.schema_score,
            anomaly_count=len(result.schema_anomalies),
            critical_count=len(result.critical_schema_anomalies),
            warning_count=len([
                a for a in result.schema_anomalies
                if a.severity == SeverityLevel.WARNING
            ]),
            last_check=now,
        )

        bl_layer = SilverLayerScore(
            layer_name="business_logic",
            layer_number=3,
            score=result.business_logic_score,
            anomaly_count=len(result.business_logic_anomalies),
            critical_count=len(result.critical_business_logic_anomalies),
            warning_count=len([
                a for a in result.business_logic_anomalies
                if a.severity == SeverityLevel.WARNING
            ]),
            last_check=now,
        )

        freshness_layer = SilverLayerScore(
            layer_name="freshness",
            layer_number=4,
            score=result.freshness_score,
            anomaly_count=len(result.freshness_anomalies),
            critical_count=len(result.critical_freshness_anomalies),
            warning_count=len([
                a for a in result.freshness_anomalies
                if a.severity == SeverityLevel.WARNING
            ]),
            last_check=now,
        )

        self._current_health = SilverTierHealthScore.calculate(
            schema_layer=schema_layer,
            business_logic_layer=bl_layer,
            freshness_layer=freshness_layer,
            previous_score=previous_score,
        )

        logger.debug(
            "health_score_updated",
            overall=self._current_health.overall_score,
            trend=self._current_health.trend,
        )

    def reset_health(self) -> None:
        """Reset health score to initial state."""
        self._current_health = SilverTierHealthScore.create_initial()
        logger.info("health_score_reset")
