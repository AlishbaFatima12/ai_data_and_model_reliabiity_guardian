"""Gold Tier validation skills.

Layer 5: Model Health Monitoring (ML-001 to ML-008)
Layer 6: Ethics & Bias Monitoring (ET-001 to ET-008)
"""

from src.skills.gold.drift import detect_prediction_drift, detect_feature_drift
from src.skills.gold.model_health import (
    check_model_staleness,
    check_confidence_degradation,
    check_model_latency,
    check_error_rate,
    check_data_model_compatibility,
    check_retraining_needed,
)
from src.skills.gold.fairness import check_fairness_metrics, detect_bias
from src.skills.gold.ethics import (
    check_explainability,
    check_consent_compliance,
    check_pii_exposure,
    check_audit_trail,
    check_regulatory_compliance,
)

__all__ = [
    # Layer 5 - Model Health
    "detect_prediction_drift",
    "detect_feature_drift",
    "check_model_staleness",
    "check_confidence_degradation",
    "check_model_latency",
    "check_error_rate",
    "check_data_model_compatibility",
    "check_retraining_needed",
    # Layer 6 - Ethics & Bias
    "check_fairness_metrics",
    "detect_bias",
    "check_explainability",
    "check_consent_compliance",
    "check_pii_exposure",
    "check_audit_trail",
    "check_regulatory_compliance",
]
