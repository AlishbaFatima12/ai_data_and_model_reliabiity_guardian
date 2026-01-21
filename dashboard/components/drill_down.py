"""Drill-Down component for progressive detail reveal.

Implements FR-023 to FR-025 per Constitution 6.7:
- FR-023: 3-level drill-down (plain -> summary -> full technical)
- FR-024: Raw metric values, thresholds, queries in full view
- FR-025: Drill-down available on every metric, chart, incident
"""

from typing import Any, Callable

import streamlit as st

from src.models.anomaly import Anomaly
from src.models.validation_result import ValidationResult
from dashboard.services.impact_translator import BusinessImpact


# Drill-down level constants
LEVEL_PLAIN = 1      # Plain language only
LEVEL_SUMMARY = 2    # Summary technical details
LEVEL_FULL = 3       # Full technical specifications


def render_drill_down_indicator(current_level: int) -> None:
    """Render visual indicator of current drill-down level.

    Args:
        current_level: Current detail level (1-3).
    """
    levels = [
        ("Plain", "🏠"),
        ("Summary", "📋"),
        ("Technical", "⚙️"),
    ]

    cols = st.columns(3)

    for i, (label, icon) in enumerate(levels):
        level = i + 1
        is_active = level == current_level
        is_complete = level <= current_level

        with cols[i]:
            bg_color = "#00A67E" if is_active else "#e9ecef" if is_complete else "#f8f9fa"
            text_color = "white" if is_active else "#1a1a2e" if is_complete else "#6B7280"

            st.markdown(
                f"""
                <div style="
                    background: {bg_color};
                    color: {text_color};
                    padding: 0.5rem;
                    border-radius: 8px;
                    text-align: center;
                    font-weight: {'600' if is_active else '400'};
                ">
                    {icon} {label}
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_plain_view(
    title: str,
    summary: str,
    severity: str = "INFO",
) -> None:
    """Render plain language view (Level 1).

    Args:
        title: Issue title.
        summary: Plain language summary.
        severity: Severity level for styling.
    """
    severity_colors = {
        "CRITICAL": ("#DC3545", "🚨"),
        "WARNING": ("#FFB020", "⚠️"),
        "INFO": ("#6B7280", "ℹ️"),
    }

    color, icon = severity_colors.get(severity, ("#6B7280", "ℹ️"))

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 12px;
            padding: 1.5rem;
            border-left: 4px solid {color};
        ">
            <div style="font-size: 1.25rem; font-weight: 600; color: #1a1a2e; margin-bottom: 0.75rem;">
                {icon} {title}
            </div>
            <div style="color: #4B5563; font-size: 1rem; line-height: 1.6;">
                {summary}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_view(
    anomaly: Anomaly,
    business_impact: BusinessImpact | None = None,
) -> None:
    """Render summary technical view (Level 2).

    Args:
        anomaly: The anomaly details.
        business_impact: Optional business impact translation.
    """
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 🔍 Issue Details")
        st.markdown(f"**Failure Code:** `{anomaly.failure_code.value}`")
        st.markdown(f"**Description:** {anomaly.failure_code.description}")
        st.markdown(f"**Severity:** {anomaly.severity.value} (Score: {anomaly.severity_score:.1f})")
        st.markdown(f"**Affected Records:** {anomaly.affected_count}")

        if anomaly.affected_fields:
            st.markdown(f"**Affected Fields:** {', '.join(anomaly.affected_fields)}")

    with col2:
        st.markdown("##### 📊 Statistics")

        metrics_col1, metrics_col2 = st.columns(2)

        with metrics_col1:
            st.metric("Records", anomaly.affected_count)

        with metrics_col2:
            st.metric("Severity Score", f"{anomaly.severity_score:.1f}")

        st.markdown(f"**Root Cause:**")
        st.code(anomaly.root_cause, language=None)

    if business_impact:
        st.divider()
        st.markdown("##### 💼 Business Impact")
        st.info(business_impact.business_description)

        if business_impact.affected_processes:
            st.markdown(f"**Affected Processes:** {', '.join(business_impact.affected_processes)}")


def render_full_technical_view(
    anomaly: Anomaly,
    validation_result: ValidationResult | None = None,
    raw_metrics: dict[str, Any] | None = None,
) -> None:
    """Render full technical specifications (Level 3, FR-024).

    Args:
        anomaly: The anomaly details.
        validation_result: Optional associated validation result.
        raw_metrics: Optional raw metric values.
    """
    st.markdown("##### ⚙️ Full Technical Specifications")

    # Anomaly details
    with st.expander("📋 Anomaly Details", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Identifiers**")
            st.code(f"Anomaly ID: {anomaly.id}\nBatch ID: {anomaly.batch_id}", language=None)

            st.markdown("**Classification**")
            st.markdown(f"- Failure Code: `{anomaly.failure_code.value}`")
            st.markdown(f"- Severity: `{anomaly.severity.value}`")
            st.markdown(f"- Severity Score: `{anomaly.severity_score:.4f}`")

        with col2:
            st.markdown("**Timing**")
            st.markdown(f"- Detected: `{anomaly.detected_at.isoformat()}`")

            st.markdown("**Scope**")
            st.markdown(f"- Affected Records: `{anomaly.affected_count}`")
            if anomaly.affected_fields:
                st.markdown(f"- Affected Fields: `{anomaly.affected_fields}`")

    # Raw metrics
    if raw_metrics or anomaly.metadata:
        with st.expander("📈 Raw Metrics & Thresholds", expanded=False):
            metrics = raw_metrics or anomaly.metadata

            st.markdown("**Raw Values:**")
            st.json(metrics)

    # Validation result context
    if validation_result:
        with st.expander("📦 Validation Context", expanded=False):
            st.markdown(f"**Batch ID:** `{validation_result.batch_id}`")
            st.markdown(f"**Passed:** `{validation_result.passed}`")
            st.markdown(f"**Health Score:** `{validation_result.health_score:.2f}`")
            st.markdown(f"**Duration:** `{validation_result.duration_ms:.2f}ms`")
            st.markdown(f"**Skills Executed:** `{validation_result.skills_executed}`")
            st.markdown(f"**Total Anomalies:** `{validation_result.anomaly_count}`")

            if validation_result.metadata:
                st.markdown("**Metadata:**")
                st.json(validation_result.metadata)

    # Root cause and explanation
    with st.expander("🔎 Root Cause Analysis", expanded=False):
        st.markdown("**Root Cause:**")
        st.code(anomaly.root_cause, language=None)

        if anomaly.explanation:
            st.markdown("**Detailed Explanation:**")
            st.markdown(anomaly.explanation)

        st.markdown("**Affected Record Indices:**")
        if anomaly.affected_records:
            if len(anomaly.affected_records) > 20:
                st.code(str(anomaly.affected_records[:20]) + f"... and {len(anomaly.affected_records) - 20} more", language=None)
            else:
                st.code(str(anomaly.affected_records), language=None)
        else:
            st.code("No specific records identified", language=None)


def render_drill_down_controls(
    current_level: int,
    on_level_change: Callable[[int], None],
) -> None:
    """Render drill-down navigation controls.

    Args:
        current_level: Current detail level (1-3).
        on_level_change: Callback when level changes.
    """
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if current_level > 1:
            if st.button("◀ Less Detail", width="stretch"):
                on_level_change(current_level - 1)

    with col2:
        if current_level < 3:
            if st.button("More Detail ▶", width="stretch", type="primary"):
                on_level_change(current_level + 1)

    with col3:
        if st.button("🏠 Reset", width="stretch"):
            on_level_change(1)

    with col4:
        st.markdown(f"**Level {current_level}/3**")


def render_drill_down(
    anomaly: Anomaly,
    business_impact: BusinessImpact | None = None,
    validation_result: ValidationResult | None = None,
    initial_level: int = 1,
    key: str = "drill_down",
) -> None:
    """Render complete drill-down component.

    Args:
        anomaly: The anomaly to display.
        business_impact: Optional business impact translation.
        validation_result: Optional associated validation result.
        initial_level: Starting detail level.
        key: Streamlit widget key prefix.
    """
    # Initialize session state for level
    level_key = f"{key}_level"
    if level_key not in st.session_state:
        st.session_state[level_key] = initial_level

    current_level = st.session_state[level_key]

    # Render level indicator
    render_drill_down_indicator(current_level)

    st.divider()

    # Render content based on level
    if current_level == LEVEL_PLAIN:
        render_plain_view(
            title=f"{anomaly.failure_code.value}: {anomaly.failure_code.description}",
            summary=anomaly.root_cause,
            severity=anomaly.severity.value,
        )

    elif current_level == LEVEL_SUMMARY:
        render_summary_view(anomaly, business_impact)

    else:  # LEVEL_FULL
        render_full_technical_view(anomaly, validation_result)

    st.divider()

    # Render navigation controls
    def change_level(new_level: int) -> None:
        st.session_state[level_key] = new_level

    render_drill_down_controls(current_level, change_level)


def render_metric_drill_down(
    metric_name: str,
    metric_value: Any,
    plain_description: str,
    technical_details: dict[str, Any],
    key: str = "metric_drill",
) -> None:
    """Render drill-down for a generic metric (FR-025).

    Args:
        metric_name: Name of the metric.
        metric_value: Current metric value.
        plain_description: Plain language description.
        technical_details: Technical detail dictionary.
        key: Streamlit widget key prefix.
    """
    level_key = f"{key}_level"
    if level_key not in st.session_state:
        st.session_state[level_key] = 1

    current_level = st.session_state[level_key]

    with st.expander(f"**{metric_name}**: {metric_value}", expanded=False):
        if current_level == 1:
            st.markdown(plain_description)

        elif current_level == 2:
            st.markdown(plain_description)
            st.markdown("---")
            st.markdown("**Summary:**")
            for k, v in list(technical_details.items())[:5]:
                st.markdown(f"- {k}: `{v}`")

        else:
            st.markdown("**Full Technical Details:**")
            st.json(technical_details)

        # Level controls
        col1, col2 = st.columns(2)
        with col1:
            if current_level < 3:
                if st.button("More ▶", key=f"{key}_more"):
                    st.session_state[level_key] = current_level + 1
                    st.rerun()
        with col2:
            if current_level > 1:
                if st.button("◀ Less", key=f"{key}_less"):
                    st.session_state[level_key] = current_level - 1
                    st.rerun()
