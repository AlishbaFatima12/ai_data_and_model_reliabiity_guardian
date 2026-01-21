"""Executive Summary component for health overview display.

Implements FR-001 to FR-005 per Constitution 6.2:
- FR-001: Health score with color coding
- FR-002: Health trend sparkline
- FR-003: Active issues count badge
- FR-004: Last Updated timestamp
- FR-005: Plain language summary
"""

from datetime import datetime, timezone
from typing import Any

import streamlit as st
import plotly.graph_objects as go

from dashboard.services.health_calculator import HealthCalculator, OverallHealthInfo, LayerHealthInfo
from dashboard.services.impact_translator import ImpactTranslator


def render_health_score_card(health_info: OverallHealthInfo) -> None:
    """Render the main health score card (FR-001).

    Args:
        health_info: Overall health information.
    """
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        ">
            <div style="
                font-size: 4.5rem;
                font-weight: 700;
                line-height: 1;
                margin-bottom: 0.5rem;
                color: {health_info.color};
            ">{health_info.score:.0f}</div>
            <div style="
                font-size: 1.25rem;
                font-weight: 500;
                opacity: 0.9;
                color: white;
                margin-bottom: 1rem;
            ">Overall Health</div>
            <div style="
                color: {health_info.color};
                font-size: 1.5rem;
                font-weight: 600;
            ">{health_info.status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_health_trend_sparkline(
    timestamps: list[datetime],
    scores: list[float],
    color: str,
    height: int = 200,
) -> None:
    """Render the health trend sparkline (FR-002).

    Args:
        timestamps: List of datetime points.
        scores: List of health scores.
        color: Primary color for the line.
        height: Chart height in pixels.
    """
    if not timestamps or not scores:
        st.info("No historical data available for trend display.")
        return

    fig = go.Figure()

    # Convert color to RGB for fill
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)

    # Add area chart
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=scores,
        mode='lines',
        fill='tozeroy',
        line=dict(color=color, width=2),
        fillcolor=f"rgba({r}, {g}, {b}, 0.2)",
        hovertemplate="<b>%{y:.0f}</b><br>%{x|%H:%M}<extra></extra>",
    ))

    # Add threshold lines with annotations
    fig.add_hline(y=90, line_dash="dash", line_color="#00A67E", opacity=0.5,
                  annotation_text="Excellent", annotation_position="right")
    fig.add_hline(y=70, line_dash="dash", line_color="#FFB020", opacity=0.5,
                  annotation_text="Good", annotation_position="right")
    fig.add_hline(y=50, line_dash="dash", line_color="#FF8C00", opacity=0.5,
                  annotation_text="Fair", annotation_position="right")

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=60, t=10, b=30),
        xaxis=dict(
            showgrid=False,
            showticklabels=True,
            tickformat="%H:%M",
        ),
        yaxis=dict(
            range=[0, 100],
            showgrid=True,
            gridcolor='rgba(0,0,0,0.1)',
            ticksuffix="%",
        ),
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def render_issue_badges(severity_counts: dict[str, int]) -> None:
    """Render issue count badges by severity (FR-003).

    Args:
        severity_counts: Dict with CRITICAL, WARNING, INFO counts.
    """
    critical = severity_counts.get("CRITICAL", 0)
    warning = severity_counts.get("WARNING", 0)
    info = severity_counts.get("INFO", 0)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div style="
                display: inline-block;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                background: {'#DC3545' if critical > 0 else '#f8f9fa'};
                color: {'white' if critical > 0 else '#6B7280'};
                font-weight: 600;
                text-align: center;
                width: 100%;
            ">
                🚨 {critical} Critical
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div style="
                display: inline-block;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                background: {'#FFB020' if warning > 0 else '#f8f9fa'};
                color: {'#1a1a2e' if warning > 0 else '#6B7280'};
                font-weight: 600;
                text-align: center;
                width: 100%;
            ">
                ⚠️ {warning} Warning
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div style="
                display: inline-block;
                padding: 0.5rem 1rem;
                border-radius: 20px;
                background: #f8f9fa;
                color: #6B7280;
                font-weight: 600;
                text-align: center;
                width: 100%;
            ">
                ℹ️ {info} Info
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_last_updated(timestamp: datetime, is_stale: bool = False) -> None:
    """Render last updated timestamp with relative time (FR-004).

    Args:
        timestamp: Last update datetime.
        is_stale: Whether the data is considered stale.
    """
    now = datetime.now(timezone.utc)
    diff = now - timestamp
    seconds = int(diff.total_seconds())

    if seconds < 60:
        relative = f"{seconds} seconds ago"
    elif seconds < 3600:
        minutes = seconds // 60
        relative = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        hours = seconds // 3600
        relative = f"{hours} hour{'s' if hours > 1 else ''} ago"

    icon = "🔴" if is_stale else "🟢"

    st.markdown(
        f"""
        <div style="
            text-align: right;
            font-size: 0.85rem;
            color: {'#DC3545' if is_stale else '#6B7280'};
            padding: 0.5rem 0;
        ">
            {icon} Last updated: {relative} ({timestamp.strftime('%H:%M:%S')})
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_plain_summary(
    summary: str,
    health_score: float,
) -> None:
    """Render plain language summary (FR-005).

    Args:
        summary: Plain language summary text.
        health_score: Current health score for styling.
    """
    if health_score >= 90:
        st.success(f"✅ {summary}")
    elif health_score >= 70:
        st.info(f"ℹ️ {summary}")
    elif health_score >= 50:
        st.warning(f"⚠️ {summary}")
    else:
        st.error(f"🚨 {summary}")


def render_layer_health_cards(layers: list[LayerHealthInfo]) -> None:
    """Render per-layer health cards with progress bars.

    Args:
        layers: List of layer health information.
    """
    for layer in layers:
        trend_icon = "↑" if layer.trend == "improving" else "↓" if layer.trend == "degrading" else "→"
        trend_class = "color: #00A67E;" if layer.trend == "improving" else "color: #DC3545;" if layer.trend == "degrading" else "color: #6B7280;"

        st.markdown(
            f"""
            <div style="
                background: #f8f9fa;
                border-radius: 12px;
                padding: 1rem;
                margin-bottom: 0.75rem;
                border-left: 4px solid {layer.color};
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>{layer.name}</strong>
                        <span style="color: #6B7280; font-size: 0.85rem;"> ({layer.tier})</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <span style="{trend_class}">{trend_icon}</span>
                        <span style="font-weight: 700; color: {layer.color};">{layer.score:.0f}</span>
                    </div>
                </div>
                <div style="
                    height: 8px;
                    border-radius: 4px;
                    background: #e9ecef;
                    overflow: hidden;
                    margin-top: 0.5rem;
                ">
                    <div style="
                        height: 100%;
                        width: {layer.score}%;
                        background: {layer.color};
                        border-radius: 4px;
                    "></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_executive_summary(
    health_info: OverallHealthInfo,
    severity_counts: dict[str, int],
    summary: str,
    timestamps: list[datetime],
    scores: list[float],
    layers: list[LayerHealthInfo],
    last_updated: datetime,
    is_stale: bool = False,
) -> None:
    """Render complete executive summary panel.

    Args:
        health_info: Overall health information.
        severity_counts: Issue counts by severity.
        summary: Plain language summary.
        timestamps: Health history timestamps.
        scores: Health history scores.
        layers: Per-layer health information.
        last_updated: Last data update time.
        is_stale: Whether data is stale.
    """
    # Header with last updated
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("## 📊 System Health Overview")
    with col2:
        render_last_updated(last_updated, is_stale)

    st.divider()

    # Main content
    col1, col2 = st.columns([1, 2])

    with col1:
        render_health_score_card(health_info)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Issue Breakdown")
        render_issue_badges(severity_counts)

    with col2:
        st.markdown("#### 💬 Summary")
        render_plain_summary(summary, health_info.score)

        st.markdown("#### 📈 Health Trend (Last 24 Hours)")
        render_health_trend_sparkline(timestamps, scores, health_info.color)

        st.markdown("#### 🔍 Layer Health")
        render_layer_health_cards(layers)
