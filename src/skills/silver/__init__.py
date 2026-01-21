"""Silver Tier Skills.

This module provides validation skills for Silver Tier:
- Layer 2: Schema & Contract Enforcement (schema, version, contract)
- Layer 3: Business Logic Validation (crossfield, refint, bizrule, distrib)
- Layer 4: Freshness & SLA Monitoring (freshness, sla, pipeline, dependency)
- Supporting: rootcause, incident, escalate, quarantine
"""

# Schema & Contract Enforcement (Layer 2)
from src.skills.silver.schema import validate_schema, SchemaValidationResult
from src.skills.silver.version import check_version_compatibility, VersionComparisonResult
from src.skills.silver.contract import verify_contract, verify_contract_hash, ContractRegistry

# Business Logic Validation (Layer 3)
from src.skills.silver.crossfield import validate_crossfield, CrossfieldValidationResult
from src.skills.silver.refint import check_referential_integrity, detect_orphan_records, RefintValidationResult
from src.skills.silver.bizrule import evaluate_business_rules, validate_calculation, validate_state_transition, validate_temporal, BizruleValidationResult
from src.skills.silver.distrib import detect_distribution_shift, create_baseline_profile, calculate_psi, DistribValidationResult, DistributionProfile

# Freshness & SLA Monitoring (Layer 4)
from src.skills.silver.freshness import check_freshness, check_freshness_batch, calculate_freshness_score, FreshnessCheckResult
from src.skills.silver.sla import track_sla_compliance, check_sla_batch, calculate_sla_score, SLACheckResult
from src.skills.silver.pipeline import monitor_pipeline_duration, check_pipeline_batch, create_pipeline_execution, calculate_pipeline_score, PipelineCheckResult
from src.skills.silver.dependency import track_dependency_chain, check_dependency_batch, create_dependency_chain, calculate_dependency_score, DependencyCheckResult

# Supporting Skills
# from src.skills.silver.rootcause import attribute_root_cause
# from src.skills.silver.incident import manage_incident
# from src.skills.silver.escalate import execute_escalation
# from src.skills.silver.quarantine import quarantine_dataset

__all__ = [
    # Schema & Contract Enforcement (Layer 2)
    "validate_schema",
    "SchemaValidationResult",
    "check_version_compatibility",
    "VersionComparisonResult",
    "verify_contract",
    "verify_contract_hash",
    "ContractRegistry",
    # Business Logic Validation (Layer 3)
    "validate_crossfield",
    "CrossfieldValidationResult",
    "check_referential_integrity",
    "detect_orphan_records",
    "RefintValidationResult",
    "evaluate_business_rules",
    "validate_calculation",
    "validate_state_transition",
    "validate_temporal",
    "BizruleValidationResult",
    "detect_distribution_shift",
    "create_baseline_profile",
    "calculate_psi",
    "DistribValidationResult",
    "DistributionProfile",
    # Freshness & SLA Monitoring (Layer 4)
    "check_freshness",
    "check_freshness_batch",
    "calculate_freshness_score",
    "FreshnessCheckResult",
    "track_sla_compliance",
    "check_sla_batch",
    "calculate_sla_score",
    "SLACheckResult",
    "monitor_pipeline_duration",
    "check_pipeline_batch",
    "create_pipeline_execution",
    "calculate_pipeline_score",
    "PipelineCheckResult",
    "track_dependency_chain",
    "check_dependency_batch",
    "create_dependency_chain",
    "calculate_dependency_score",
    "DependencyCheckResult",
]
