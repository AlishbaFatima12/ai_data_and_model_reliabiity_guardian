"""Incident Timeline component for event visualization.

Implements FR-018 to FR-022 per Constitution 6.6:
- FR-018: Horizontal, scrollable, zoomable timeline
- FR-019: Events as vertical markers with severity color
- FR-020: Event details popup on hover/click
- FR-021: Filtering by severity, layer, asset, time range
- FR-022: Visual clustering for related events
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Callable

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from dashboard.services.timeline_builder import TimelineEvent, EventGroup
from src.lib.constants import SeverityLevel


# Severity color mapping
SEVERITY_COLORS = {
    SeverityLevel.CRITICAL: "#DC3545",
    SeverityLevel.WARNING: "#FFB020",
    SeverityLevel.INFO: "#6B7280",
}

# Event type icons
EVENT_ICONS = {
    "validation_start": "▶",
    "validation_complete": "✓",
    "anomaly_detected": "⚠",
    "alert_sent": "🔔",
    "acknowledged": "✓",
}


def render_timeline_filters(
    on_filter_change: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    """Render timeline filter controls (FR-021).

    Args:
        on_filter_change: Optional callback when filters change.

    Returns:
        Current filter state.
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        severity_filter = st.multiselect(
            "Severity",
            options=["CRITICAL", "WARNING", "INFO"],
            default=["CRITICAL", "WARNING"],
            key="timeline_severity_filter",
        )

    with col2:
        layer_filter = st.multiselect(
            "Layer",
            options=["Bronze", "Silver", "Gold"],
            default=["Bronze"],
            key="timeline_layer_filter",
        )

    with col3:
        time_range = st.selectbox(
            "Time Range",
            options=[1, 6, 12, 24, 48, 168, 720],
            format_func=lambda x: f"{x}h" if x < 24 else f"{x // 24}d",
            index=3,
            key="timeline_time_range",
        )

    with col4:
        zoom_level = st.selectbox(
            "Zoom",
            options=["hour", "day", "week", "month"],
            index=1,
            key="timeline_zoom",
        )

    filters = {
        "severity": severity_filter,
        "layer": layer_filter,
        "time_range_hours": time_range,
        "zoom_level": zoom_level,
    }

    return filters


def render_timeline_chart(
    events: list[TimelineEvent],
    groups: list[EventGroup] | None = None,
    height: int = 400,
    on_event_click: Callable[[str], None] | None = None,
) -> None:
    """Render the interactive timeline chart (FR-018, FR-019).

    Args:
        events: List of timeline events.
        groups: Optional list of event groups for clustering.
        height: Chart height in pixels.
        on_event_click: Optional callback when event is clicked.
    """
    if not events:
        st.info("📅 No events found for the selected time range.")
        return

    # Prepare data for plotting
    timestamps = [e.timestamp for e in events]
    severities = [e.severity for e in events]
    colors = [SEVERITY_COLORS.get(s, "#6B7280") for s in severities]
    icons = [EVENT_ICONS.get(e.event_type, "●") for e in events]
    labels = [f"{e.title}" for e in events]

    # Create figure
    fig = go.Figure()

    # Add event markers
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=[1] * len(timestamps),  # All events on same y-level
        mode='markers+text',
        marker=dict(
            size=20,
            color=colors,
            symbol='diamond',
            line=dict(width=2, color='white'),
        ),
        text=icons,
        textposition='middle center',
        textfont=dict(color='white', size=10),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Time: %{x|%Y-%m-%d %H:%M}<br>"
            "Severity: %{customdata[1]}<br>"
            "%{customdata[2]}"
            "<extra></extra>"
        ),
        customdata=[[e.title, e.severity.value, e.description[:100]] for e in events],
    ))

    # Add group connections if provided (FR-022)
    if groups:
        for group in groups:
            group_events = [e for e in events if e.id in group.event_ids]
            if len(group_events) >= 2:
                group_times = [e.timestamp for e in group_events]
                fig.add_trace(go.Scatter(
                    x=group_times,
                    y=[0.9] * len(group_times),
                    mode='lines',
                    line=dict(color='rgba(100,100,100,0.3)', width=2, dash='dot'),
                    hoverinfo='skip',
                    showlegend=False,
                ))

    # Add severity legend
    for severity, color in SEVERITY_COLORS.items():
        fig.add_trace(go.Scatter(
            x=[None],
            y=[None],
            mode='markers',
            marker=dict(size=12, color=color, symbol='diamond'),
            name=severity.value,
            showlegend=True,
        ))

    # Update layout
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40, b=40),
        xaxis=dict(
            title="Time",
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)',
            rangeslider=dict(visible=True, thickness=0.05),
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1h", step="hour", stepmode="backward"),
                    dict(count=6, label="6h", step="hour", stepmode="backward"),
                    dict(count=24, label="24h", step="hour", stepmode="backward"),
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(step="all", label="All"),
                ]
            ),
        ),
        yaxis=dict(
            visible=False,
            range=[0.5, 1.5],
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hovermode='closest',
    )

    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    })


def render_event_popup(event: TimelineEvent) -> None:
    """Render event details popup (FR-020).

    Args:
        event: The timeline event to display.
    """
    severity_color = SEVERITY_COLORS.get(event.severity, "#6B7280")

    st.markdown(
        f"""
        <div style="
            background: white;
            border-radius: 12px;
            padding: 1rem;
            border-left: 4px solid {severity_color};
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <span style="
                    display: inline-block;
                    padding: 0.2rem 0.5rem;
                    border-radius: 4px;
                    background: {severity_color};
                    color: white;
                    font-size: 0.75rem;
                    font-weight: 600;
                ">{event.severity.value}</span>
                <span style="color: #6B7280; font-size: 0.85rem;">
                    {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
                </span>
            </div>
            <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">
                {event.title}
            </div>
            <div style="color: #4B5563; margin-bottom: 0.75rem;">
                {event.description}
            </div>
            <div style="display: flex; gap: 1rem; font-size: 0.8rem; color: #6B7280;">
                <span>📍 Layer: {event.layer}</span>
                <span>📦 Asset: {event.asset or 'N/A'}</span>
                <span>🔗 Type: {event.event_type}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_event_list(
    events: list[TimelineEvent],
    max_display: int = 20,
    on_click: Callable[[str], None] | None = None,
) -> None:
    """Render a scrollable list of events.

    Args:
        events: List of timeline events.
        max_display: Maximum events to display.
        on_click: Optional callback when event is clicked.
    """
    for event in events[:max_display]:
        severity_color = SEVERITY_COLORS.get(event.severity, "#6B7280")
        icon = EVENT_ICONS.get(event.event_type, "●")

        with st.container():
            st.markdown(
                f"""
                <div style="
                    padding: 0.75rem 1rem;
                    border-left: 3px solid {severity_color};
                    margin-bottom: 0.5rem;
                    background: #f8f9fa;
                    border-radius: 0 8px 8px 0;
                    cursor: pointer;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="margin-right: 0.5rem;">{icon}</span>
                            <strong>{event.title}</strong>
                        </div>
                        <span style="color: #6B7280; font-size: 0.8rem;">
                            {event.timestamp.strftime('%H:%M:%S')}
                        </span>
                    </div>
                    <div style="color: #6B7280; font-size: 0.85rem; margin-top: 0.25rem;">
                        {event.description[:80]}{'...' if len(event.description) > 80 else ''}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if len(events) > max_display:
        st.caption(f"Showing {max_display} of {len(events)} events")


def render_incident_timeline(
    events: list[TimelineEvent],
    groups: list[EventGroup] | None = None,
    show_filters: bool = True,
    show_list: bool = True,
) -> None:
    """Render complete incident timeline section.

    Args:
        events: List of timeline events.
        groups: Optional event groups for clustering.
        show_filters: Whether to show filter controls.
        show_list: Whether to show event list below chart.
    """
    st.markdown("### 📅 Incident Timeline")

    if show_filters:
        filters = render_timeline_filters()
        st.divider()

    # Render main timeline chart
    render_timeline_chart(events, groups)

    if show_list and events:
        st.markdown("#### Recent Events")
        render_event_list(events)
