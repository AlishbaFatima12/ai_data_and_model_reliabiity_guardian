"""Layer Health component for per-layer health display.

Implements FR-006 to FR-009 per Constitution 6.3:
- FR-006: Per-layer health scores
- FR-007: Trend arrows
- FR-008: Horizontal progress bars
- FR-009: Overall health as minimum of layers
"""

from typing import Callable

import streamlit as st

from dashboard.services.health_calculator import LayerHealthInfo


def render_layer_card(
    layer: LayerHealthInfo,
    on_click: Callable[[str], None] | None = None,
    expanded: bool = False,
) -> None:
    """Render a single layer health card.

    Args:
        layer: Layer health information.
        on_click: Optional callback when layer is clicked.
        expanded: Whether to show expanded details.
    """
    trend_icons = {
        "improving": ("↑", "#00A67E"),
        "stable": ("→", "#6B7280"),
        "degrading": ("↓", "#DC3545"),
    }

    icon, trend_color = trend_icons.get(layer.trend, ("→", "#6B7280"))

    # Determine tier badge color
    tier_colors = {
        "Bronze": "#CD7F32",
        "Silver": "#C0C0C0",
        "Gold": "#FFD700",
    }
    tier_color = tier_colors.get(layer.tier, "#6B7280")

    st.markdown(
        f"""
        <div style="
            background: white;
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 0.75rem;
            border-left: 4px solid {layer.color};
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        " onmouseover="this.style.transform='translateX(4px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)';"
           onmouseout="this.style.transform='translateX(0)'; this.style.boxShadow='0 1px 3px rgba(0,0,0,0.08)';">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span style="
                        display: inline-block;
                        padding: 0.15rem 0.5rem;
                        border-radius: 4px;
                        background: {tier_color};
                        color: {'white' if layer.tier == 'Bronze' else '#1a1a2e'};
                        font-size: 0.7rem;
                        font-weight: 600;
                    ">{layer.tier}</span>
                    <strong style="font-size: 1rem;">{layer.name}</strong>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    {f'<span style="color: #DC3545; font-size: 0.8rem;">{layer.anomaly_count} issues</span>' if layer.anomaly_count > 0 else ''}
                    <span style="color: {trend_color}; font-size: 1.25rem;">{icon}</span>
                    <span style="
                        font-weight: 700;
                        font-size: 1.5rem;
                        color: {layer.color};
                    ">{layer.score:.0f}</span>
                </div>
            </div>
            <div style="
                height: 6px;
                border-radius: 3px;
                background: #e9ecef;
                overflow: hidden;
                margin-top: 0.75rem;
            ">
                <div style="
                    height: 100%;
                    width: {layer.score}%;
                    background: linear-gradient(90deg, {layer.color}, {layer.color}dd);
                    border-radius: 3px;
                    transition: width 0.5s ease;
                "></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_layer_health(
    layers: list[LayerHealthInfo],
    on_layer_click: Callable[[str], None] | None = None,
    show_overall: bool = True,
) -> None:
    """Render the complete layer health section.

    Args:
        layers: List of layer health information.
        on_layer_click: Optional callback when a layer is clicked.
        show_overall: Whether to show overall health calculation note.
    """
    st.markdown("### 🔍 Layer Health Breakdown")

    if show_overall:
        # Calculate overall as minimum
        if layers:
            min_score = min(layer.score for layer in layers)
            min_layer = next(l for l in layers if l.score == min_score)
            st.caption(
                f"💡 Overall health = minimum of all layers. "
                f"Currently limited by **{min_layer.name}** ({min_score:.0f})"
            )

    # Render each layer
    for layer in layers:
        with st.container():
            render_layer_card(
                layer,
                on_click=on_layer_click,
                expanded=layer.anomaly_count > 0,
            )

            # If there are issues, show expandable details
            if layer.anomaly_count > 0:
                with st.expander(f"View {layer.anomaly_count} issue{'s' if layer.anomaly_count > 1 else ''}", expanded=False):
                    st.markdown(f"**Layer:** {layer.name}")
                    st.markdown(f"**Tier:** {layer.tier}")
                    st.markdown(f"**Trend:** {layer.trend.title()} ({layer.trend_delta:+.1f})")
                    st.markdown("---")
                    st.markdown("*Click on anomalies in the timeline below for details.*")


def render_overall_health_formula(layers: list[LayerHealthInfo]) -> None:
    """Render visual explanation of overall health calculation (FR-009).

    Args:
        layers: List of layer health information.
    """
    if not layers:
        return

    scores_str = " | ".join([f"{l.name}: {l.score:.0f}" for l in layers])
    min_score = min(l.score for l in layers)

    st.markdown(
        f"""
        <div style="
            background: #f0f4f8;
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            font-family: monospace;
            font-size: 0.85rem;
        ">
            <div style="color: #6B7280; margin-bottom: 0.5rem;">Overall Health Formula:</div>
            <div><strong>Overall = min({scores_str}) = {min_score:.0f}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_layer_comparison_chart(layers: list[LayerHealthInfo]) -> None:
    """Render a horizontal bar chart comparing all layers.

    Args:
        layers: List of layer health information.
    """
    import plotly.graph_objects as go

    fig = go.Figure()

    # Sort layers by score
    sorted_layers = sorted(layers, key=lambda l: l.score, reverse=True)

    fig.add_trace(go.Bar(
        y=[l.name for l in sorted_layers],
        x=[l.score for l in sorted_layers],
        orientation='h',
        marker=dict(
            color=[l.color for l in sorted_layers],
            line=dict(width=0),
        ),
        text=[f"{l.score:.0f}" for l in sorted_layers],
        textposition='inside',
        textfont=dict(color='white', size=14, family='Arial Black'),
        hovertemplate="<b>%{y}</b><br>Score: %{x:.0f}<extra></extra>",
    ))

    # Add threshold lines
    fig.add_vline(x=90, line_dash="dash", line_color="#00A67E", opacity=0.5)
    fig.add_vline(x=70, line_dash="dash", line_color="#FFB020", opacity=0.5)
    fig.add_vline(x=50, line_dash="dash", line_color="#FF8C00", opacity=0.5)

    fig.update_layout(
        height=40 * len(layers) + 60,
        margin=dict(l=0, r=20, t=20, b=20),
        xaxis=dict(
            range=[0, 100],
            showgrid=True,
            gridcolor='rgba(0,0,0,0.05)',
            ticksuffix="%",
        ),
        yaxis=dict(
            showgrid=False,
            autorange="reversed",
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
