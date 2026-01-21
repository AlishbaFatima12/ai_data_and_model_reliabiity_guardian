"""Business Impact component for technical to business translation.

Implements FR-014 to FR-017 per Constitution 6.5:
- FR-014: Technical to business language translation
- FR-015: Affected business processes
- FR-016: Affected customer segments
- FR-017: Recommended business actions
"""

from typing import Any

import streamlit as st

from dashboard.services.impact_translator import BusinessImpact
from src.models.anomaly import Anomaly


def render_impact_card(impact: BusinessImpact) -> None:
    """Render a single business impact card.

    Args:
        impact: Business impact translation.
    """
    # Impact severity colors
    severity_colors = {
        "High": "#DC3545",
        "Medium": "#FFB020",
        "Low": "#6B7280",
    }
    color = severity_colors.get(impact.estimated_impact, "#6B7280")

    st.markdown(
        f"""
        <div style="
            background: white;
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1rem;
            border-left: 4px solid {color};
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        ">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
                <div style="font-size: 0.8rem; color: #6B7280;">
                    Technical: <code>{impact.technical_metric}</code>
                </div>
                <span style="
                    display: inline-block;
                    padding: 0.2rem 0.6rem;
                    border-radius: 12px;
                    background: {color}22;
                    color: {color};
                    font-size: 0.75rem;
                    font-weight: 600;
                ">{impact.estimated_impact} Impact</span>
            </div>
            <div style="font-size: 1.1rem; color: #1a1a2e; margin-bottom: 1rem;">
                {impact.business_description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_affected_processes(processes: list[str]) -> None:
    """Render affected business processes list (FR-015).

    Args:
        processes: List of affected process names.
    """
    if not processes:
        return

    st.markdown("##### 📋 Affected Business Processes")

    cols = st.columns(min(len(processes), 3))
    for i, process in enumerate(processes):
        with cols[i % 3]:
            st.markdown(
                f"""
                <div style="
                    background: #FEF3C7;
                    padding: 0.5rem 0.75rem;
                    border-radius: 8px;
                    margin-bottom: 0.5rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                ">
                    <span>⚡</span>
                    <span style="font-size: 0.9rem;">{process}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_affected_segments(segments: list[str]) -> None:
    """Render affected customer segments (FR-016).

    Args:
        segments: List of affected segment names.
    """
    if not segments:
        return

    st.markdown("##### 👥 Affected Customer Segments")

    for segment in segments:
        st.markdown(
            f"""
            <div style="
                display: inline-block;
                background: #E0E7FF;
                padding: 0.4rem 0.75rem;
                border-radius: 16px;
                margin-right: 0.5rem;
                margin-bottom: 0.5rem;
                font-size: 0.85rem;
                color: #4338CA;
            ">
                👤 {segment}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_recommended_actions(actions: list[str]) -> None:
    """Render recommended business actions (FR-017).

    Args:
        actions: List of recommended action descriptions.
    """
    if not actions:
        return

    st.markdown("##### ✅ Recommended Actions")

    for i, action in enumerate(actions, 1):
        st.markdown(
            f"""
            <div style="
                background: #ECFDF5;
                padding: 0.6rem 1rem;
                border-radius: 8px;
                margin-bottom: 0.5rem;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            ">
                <span style="
                    background: #059669;
                    color: white;
                    width: 24px;
                    height: 24px;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 0.8rem;
                    font-weight: 600;
                ">{i}</span>
                <span style="color: #065F46;">{action}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_business_impact(
    impact: BusinessImpact,
    show_all_sections: bool = True,
) -> None:
    """Render complete business impact section.

    Args:
        impact: Business impact translation.
        show_all_sections: Whether to show all subsections.
    """
    render_impact_card(impact)

    if show_all_sections:
        col1, col2 = st.columns(2)

        with col1:
            render_affected_processes(impact.affected_processes)

        with col2:
            render_affected_segments(impact.affected_segments)

        render_recommended_actions(impact.recommended_actions)


def render_business_impact_summary(
    impacts: list[BusinessImpact],
    max_display: int = 5,
) -> None:
    """Render summary of multiple business impacts.

    Args:
        impacts: List of business impacts.
        max_display: Maximum number to display.
    """
    if not impacts:
        st.info("📊 No business impact analysis available. System is operating normally.")
        return

    st.markdown("### 💼 Business Impact Analysis")

    # Count by severity
    high_count = sum(1 for i in impacts if i.estimated_impact == "High")
    medium_count = sum(1 for i in impacts if i.estimated_impact == "Medium")
    low_count = sum(1 for i in impacts if i.estimated_impact == "Low")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("High Impact", high_count, delta_color="inverse" if high_count > 0 else "off")

    with col2:
        st.metric("Medium Impact", medium_count, delta_color="off")

    with col3:
        st.metric("Low Impact", low_count, delta_color="off")

    st.divider()

    # Show individual impacts
    for impact in impacts[:max_display]:
        with st.expander(f"**{impact.technical_metric}**: {impact.business_description[:50]}...", expanded=impact.estimated_impact == "High"):
            render_business_impact(impact)

    if len(impacts) > max_display:
        st.caption(f"Showing {max_display} of {len(impacts)} impacts. Use filters to narrow results.")


def render_impact_from_anomaly(
    anomaly: Anomaly,
    impact: BusinessImpact,
) -> None:
    """Render business impact for a specific anomaly.

    Args:
        anomaly: The source anomaly.
        impact: The translated business impact.
    """
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1rem;
        ">
            <div style="font-size: 0.85rem; color: #92400E; margin-bottom: 0.5rem;">
                <strong>Technical Issue:</strong> {anomaly.failure_code.value} - {anomaly.failure_code.description}
            </div>
            <div style="font-size: 1.2rem; color: #78350F; font-weight: 600;">
                📢 {impact.business_description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        render_affected_processes(impact.affected_processes)

    with col2:
        render_affected_segments(impact.affected_segments)

    render_recommended_actions(impact.recommended_actions)
