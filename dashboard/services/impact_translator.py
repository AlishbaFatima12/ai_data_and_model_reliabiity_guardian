"""ImpactTranslator service for converting technical metrics to business language.

Translates anomalies and health metrics to plain language per Constitution 6.5.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.models.anomaly import Anomaly
from src.models.health_score import HealthScore
from src.lib.constants import SeverityLevel


@dataclass
class BusinessImpact:
    """Business impact translation of a technical anomaly."""

    technical_metric: str
    technical_value: Any
    business_description: str
    affected_processes: list[str] = field(default_factory=list)
    affected_segments: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    estimated_impact: str = "Medium"  # High/Medium/Low


class ImpactTranslator:
    """Translates technical metrics to business language.

    Provides:
    - Anomaly to business impact translation
    - Health summary generation in plain language
    - Technical metric to business description conversion
    """

    def __init__(self, translations_path: Path | None = None):
        """Initialize ImpactTranslator.

        Args:
            translations_path: Path to translations.yaml file.
        """
        if translations_path is None:
            translations_path = Path.cwd() / "config" / "translations.yaml"

        self.translations_path = Path(translations_path)
        self._translations: dict[str, Any] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load translations from YAML file."""
        if self.translations_path.exists():
            try:
                with open(self.translations_path, "r", encoding="utf-8") as f:
                    self._translations = yaml.safe_load(f) or {}
            except Exception:
                self._translations = {}

    def translate_health_summary(
        self,
        health: HealthScore,
        anomaly_counts: dict[str, int],
    ) -> str:
        """Generate plain language health summary.

        Args:
            health: Current HealthScore.
            anomaly_counts: Dict with CRITICAL, WARNING, INFO counts.

        Returns:
            1-2 sentence plain language summary.

        Examples:
            - "All systems healthy. No issues detected in the past 24 hours."
            - "2 data sources showing delays. Customer orders may be up to 3 hours stale."
            - "ALERT: Critical data quality issue. 5% of payment records have invalid formats."
        """
        score = health.overall_score
        critical = anomaly_counts.get("CRITICAL", 0)
        warning = anomaly_counts.get("WARNING", 0)
        total_issues = critical + warning

        templates = self._translations.get("health_summary", {})

        # Select appropriate template based on health status
        if score >= 90 and total_issues == 0:
            template_data = templates.get("excellent", {})
            template = template_data.get(
                "template",
                "All systems healthy. No issues detected in the past 24 hours.",
            )
            return template.format(hours=24)

        elif score >= 70:
            template_data = templates.get("good", {})
            template = template_data.get(
                "template",
                "Systems operating normally with {warning_count} minor issues under review.",
            )
            return template.format(warning_count=warning)

        elif score >= 50:
            template_data = templates.get("fair", {})
            template = template_data.get(
                "template",
                "{issue_count} data quality issues detected. Some reports may be affected.",
            )
            return template.format(issue_count=total_issues)

        elif critical == 0:
            template_data = templates.get("poor", {})
            template = template_data.get(
                "template",
                "ATTENTION: {warning_count} warning issues require review.",
            )
            return template.format(
                critical_count=critical,
                warning_count=warning,
                impact="Review recommended.",
            )

        else:
            template_data = templates.get("critical", {})
            template = template_data.get(
                "template",
                "ALERT: {critical_count} critical issues require immediate attention.",
            )
            return template.format(
                critical_count=critical,
                affected_systems="data validation",
            )

    def translate_anomaly(self, anomaly: Anomaly) -> BusinessImpact:
        """Convert anomaly to business impact.

        Args:
            anomaly: Technical anomaly from validation.

        Returns:
            BusinessImpact with business-friendly description.
        """
        failure_codes = self._translations.get("failure_codes", {})
        code_data = failure_codes.get(anomaly.failure_code.value, {})

        # Get business description
        business_desc = code_data.get(
            "business_description",
            f"Data quality issue detected: {anomaly.root_cause}",
        )

        # Build detailed description from template
        impact_template = code_data.get(
            "impact_template",
            "{root_cause}",
        )

        # Prepare template variables
        template_vars = {
            "root_cause": anomaly.root_cause,
            "count": len(anomaly.affected_records),
            "percentage": round(len(anomaly.affected_records) / 100 * 100, 1),
            "field": ", ".join(anomaly.affected_fields) if anomaly.affected_fields else "Field",
            "expected": "expected",
            "actual": "actual",
        }

        # Add metadata variables if available
        template_vars.update(anomaly.metadata)

        try:
            detailed_desc = impact_template.format(**template_vars)
        except KeyError:
            detailed_desc = business_desc

        # Get affected processes
        affected_processes = code_data.get("affected_processes", [])
        if not affected_processes:
            affected_processes = ["Data processing", "Reporting"]

        # Get recommended actions
        recommended_actions = code_data.get("recommended_actions", [])
        if not recommended_actions:
            recommended_actions = [
                "Review affected records",
                "Contact data team if issue persists",
            ]

        # Determine severity impact
        severity_impact = code_data.get("severity_impact", "Medium")
        if anomaly.severity == SeverityLevel.CRITICAL:
            severity_impact = "High"
        elif anomaly.severity == SeverityLevel.INFO:
            severity_impact = "Low"

        return BusinessImpact(
            technical_metric=anomaly.failure_code.value,
            technical_value=anomaly.severity_score,
            business_description=detailed_desc,
            affected_processes=affected_processes,
            affected_segments=self._get_affected_segments(anomaly),
            recommended_actions=recommended_actions,
            estimated_impact=severity_impact,
        )

    def _get_affected_segments(self, anomaly: Anomaly) -> list[str]:
        """Determine which customer segments are affected.

        Args:
            anomaly: The anomaly to analyze.

        Returns:
            List of affected customer segment names.
        """
        # Default segments based on severity
        if anomaly.severity == SeverityLevel.CRITICAL:
            return ["All Customers"]
        elif anomaly.affected_count > 100:
            return ["Enterprise", "Small Business"]
        else:
            return ["Affected Records Only"]

    def translate_freshness(
        self,
        hours_stale: float,
        source: str = "data",
    ) -> str:
        """Translate freshness metric to business language.

        Args:
            hours_stale: Hours since last update.
            source: Name of the data source.

        Returns:
            Business-friendly freshness description.
        """
        freshness = self._translations.get("freshness", {})

        if hours_stale < 1:
            return f"Data is current (updated within the last hour)."

        template_data = freshness.get("stale_data", {})
        template = template_data.get(
            "template",
            "Customer data may not reflect changes from the last {hours} hours.",
        )

        return template.format(hours=int(hours_stale))

    def get_failure_code_name(self, code: str) -> str:
        """Get human-readable name for failure code.

        Args:
            code: Failure code (e.g., "DV-001").

        Returns:
            Human-readable name.
        """
        failure_codes = self._translations.get("failure_codes", {})
        code_data = failure_codes.get(code, {})
        return code_data.get("name", code)

    def get_process_description(self, process_key: str) -> str:
        """Get description for a business process.

        Args:
            process_key: Process identifier key.

        Returns:
            Process description.
        """
        processes = self._translations.get("business_processes", {})
        process_data = processes.get(process_key, {})
        return process_data.get("description", process_key)
